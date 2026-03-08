import json
from datetime import datetime, timezone
from decimal import Decimal

from app import db
from app.models import Admin, FeatureSettings, PayrollSettings, RentSettings
from app.utils.economy_balance import EconomyBalanceChecker


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


def _create_admin_with_block(block='A'):
    admin = Admin(username=f"policyadmin_{block.lower()}", totp_secret="TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        block=block,
        pay_rate=Decimal('0.25'),
        expected_weekly_hours=5.0,
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True,
    )
    rent_settings = RentSettings(
        teacher_id=admin.id,
        block=block,
        is_enabled=True,
        rent_amount=Decimal('500.00'),
        frequency_type='monthly',
    )
    db.session.add(payroll_settings)
    db.session.add(rent_settings)
    db.session.commit()
    return admin, payroll_settings, rent_settings


def test_checker_uses_feature_policy_mode_for_recommendations(client):
    admin, payroll_settings, _ = _create_admin_with_block()

    default_checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='default')
    default_recommendations = default_checker.analyze_economy(payroll_settings).recommendations

    db.session.add(FeatureSettings(teacher_id=admin.id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    tight_checker = EconomyBalanceChecker(admin.id, 'A')
    tight_recommendations = tight_checker.analyze_economy(payroll_settings).recommendations

    assert tight_checker.policy_mode == 'tight'
    assert tight_recommendations['rent']['recommended'] > default_recommendations['rent']['recommended']
    assert tight_recommendations['utilities']['recommended'] > default_recommendations['utilities']['recommended']
    assert tight_recommendations['fine']['min'] > default_recommendations['fine']['min']
    assert tight_recommendations['store_tiers']['standard']['max'] < default_recommendations['store_tiers']['standard']['max']
    assert tight_recommendations['store_tiers']['premium']['max'] < default_recommendations['store_tiers']['premium']['max']
    assert tight_recommendations['store_tiers']['luxury']['max'] < default_recommendations['store_tiers']['luxury']['max']
    assert tight_recommendations['min_weekly_savings'] < default_recommendations['min_weekly_savings']


def test_comfortable_policy_uses_requested_ratio_profile(client):
    admin, payroll_settings, _ = _create_admin_with_block()

    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='comfortable')
    recommendations = checker.analyze_economy(payroll_settings).recommendations

    cwi = 75.0
    assert recommendations['utilities']['min'] == round(cwi * 0.04, 2)
    assert recommendations['utilities']['max'] == round(cwi * 0.08, 2)
    assert recommendations['fine']['max'] == round(cwi * 0.12, 2)
    assert recommendations['store_tiers']['basic']['min'] == round(cwi * 0.02, 2)
    assert recommendations['store_tiers']['basic']['max'] == round(cwi * 0.04, 2)
    assert recommendations['store_tiers']['standard']['min'] == round(cwi * 0.03, 2)
    assert recommendations['store_tiers']['standard']['max'] == round(cwi * 0.06, 2)
    assert recommendations['store_tiers']['premium']['min'] == round(cwi * 0.06, 2)
    assert recommendations['store_tiers']['premium']['max'] == round(cwi * 0.18, 2)
    assert recommendations['store_tiers']['luxury']['min'] == round(cwi * 0.18, 2)
    assert recommendations['store_tiers']['luxury']['max'] == round(cwi * 0.35, 2)
    assert recommendations['min_weekly_savings'] == round(cwi * 0.15, 2)
    assert recommendations['insurance_premium_weekly']['min'] == round(cwi * 0.04, 2)
    assert recommendations['insurance_premium_weekly']['max'] == round(cwi * 0.10, 2)
    assert recommendations['insurance_coverage']['multiplier_min'] == 4.0
    assert recommendations['insurance_coverage']['multiplier_max'] == 6.0
    assert recommendations['insurance_period_cap']['multiplier_min'] == 8.0
    assert recommendations['insurance_period_cap']['multiplier_max'] == 12.0
    assert recommendations['insurance_waiting_period_days']['min'] == 3
    assert recommendations['insurance_waiting_period_days']['max'] == 7


def test_update_economy_policy_creates_block_scoped_settings(client):
    admin, _, _ = _create_admin_with_block()
    _login_admin(client, admin.id)

    response = client.post('/admin/economy-policy', data={
        'policy_mode': 'comfortable',
        'block': 'A',
    })

    assert response.status_code == 302
    assert 'review_rebalance=1' in response.location

    settings_row = FeatureSettings.query.filter_by(teacher_id=admin.id, block='A').first()
    assert settings_row is not None
    assert settings_row.economy_policy_mode == 'comfortable'


def test_immediate_rebalance_updates_rent_setting(client):
    admin, _, rent_settings = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    payload = json.dumps([
        {
            'key': 'rent',
            'change': {
                'type': 'rent',
                'block': 'A',
                'current_value': '500.00',
                'new_value': '575.00',
            },
        }
    ])

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'immediate',
        'confirm_immediate': 'yes',
        'selected_changes': ['rent'],
        'preview_payload': payload,
    })

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('575.00')


def test_run_payroll_applies_scheduled_rebalance(client):
    admin, _, rent_settings = _create_admin_with_block()
    _login_admin(client, admin.id)

    settings_row = FeatureSettings(
        teacher_id=admin.id,
        block='A',
        economy_policy_mode='tight',
        economy_pending_rebalance_json=json.dumps({
            'activation_mode': 'next_payroll',
            'changes': [
                {
                    'type': 'rent',
                    'block': 'A',
                    'current_value': '500.00',
                    'new_value': '610.00',
                }
            ],
        }),
    )
    db.session.add(settings_row)
    db.session.commit()

    response = client.post('/admin/run-payroll')

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    db.session.refresh(settings_row)
    assert rent_settings.rent_amount == Decimal('610.00')
    assert settings_row.economy_pending_rebalance_json is None

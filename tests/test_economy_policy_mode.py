import json
from datetime import datetime, timezone
from decimal import Decimal

from app import db
from app.models import (
    Admin,
    ClassEconomy,
    FeatureSettings,
    IdentityProfile,
    InsurancePolicy,
    PayrollSettings,
    RentSettings,
    TeacherBlock,
)
from app.utils.economy_balance import EconomyBalanceChecker, WarningLevel
from app.utils.economy_policy import get_feature_settings_row, get_insurance_premium_recommendation


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


def _create_teacher_block(admin_id, block='A', join_code='JOINPOLA'):
    identity = IdentityProfile(profile_type='student', first_name='Policy', last_initial='S')
    db.session.add(identity)
    db.session.flush()

    teacher_block = TeacherBlock(
        teacher_id=admin_id,
        block=block,
        first_name='Policy',
        last_initial='S',
        identity_id=identity.id,
        last_name_hash_by_part=['hash'],
        dob_sum_hash=None,
        salt=b'1234567890123456',
        first_half_hash='hashvalue',
        join_code=join_code,
    )
    db.session.add(teacher_block)
    db.session.flush()
    return teacher_block


def _create_admin_with_block(block='A', join_code='JOINPOLA'):
    admin = Admin(username=f"policyadmin_{block.lower()}_{join_code.lower()}", totp_secret="TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=admin.id,
        created_by_admin_id=admin.id,
        display_name=f'Period {block}',
    )
    db.session.add(economy)
    db.session.flush()

    _create_teacher_block(admin.id, block=block, join_code=join_code)

    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        join_code=join_code,
        block=block,
        pay_rate=Decimal('0.25'),
        expected_weekly_hours=5.0,
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True,
    )
    rent_settings = RentSettings(
        teacher_id=admin.id,
        join_code=join_code,
        block=block,
        is_enabled=True,
        rent_amount=Decimal('500.00'),
        frequency_type='monthly',
    )
    db.session.add_all([payroll_settings, rent_settings])
    db.session.commit()
    return admin, payroll_settings, rent_settings, economy


def _create_insurance_policy(admin_id, title, premium, block='A'):
    join_code = f"JOIN{block}{admin_id}"
    if not ClassEconomy.query.filter_by(join_code=join_code).first():
        db.session.add(ClassEconomy(
            join_code=join_code,
            teacher_id=admin_id,
            created_by_admin_id=admin_id,
            display_name=f'Period {block}',
        ))
        db.session.flush()
    policy = InsurancePolicy(
        teacher_id=admin_id,
        join_code=join_code,
        policy_code=f"{title[:3].upper()}{admin_id}",
        title=title,
        premium=Decimal(str(premium)),
        charge_frequency='monthly',
        waiting_period_days=7,
        max_claim_amount=Decimal('100.00'),
        max_payout_per_period=Decimal('200.00'),
        claim_type='legacy_monetary',
        is_monetary=True,
        settings_mode='advanced',
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()
    policy.set_blocks([block])
    db.session.commit()
    return policy


def test_checker_uses_feature_policy_mode_for_recommendations(client):
    admin, payroll_settings, _, economy = _create_admin_with_block()

    default_checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='default')
    default_recommendations = default_checker.analyze_economy(payroll_settings).recommendations

    db.session.add(FeatureSettings(teacher_id=admin.id, join_code='JOINPOLA', class_id=economy.class_id, block='A', economy_policy_mode='tight'))
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
    admin, payroll_settings, _, _ = _create_admin_with_block()

    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='comfortable')
    recommendations = checker.analyze_economy(payroll_settings).recommendations

    cwi = float(payroll_settings.pay_rate) * payroll_settings.expected_weekly_hours * 60
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


def test_insurance_premium_recommendation_matches_checker_output(client):
    admin, payroll_settings, _, _ = _create_admin_with_block()

    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='default')
    analysis = checker.analyze_economy(payroll_settings)
    recommendation = get_insurance_premium_recommendation(
        'default',
        Decimal(str(analysis.cwi.cwi)),
        frequency='monthly',
    )

    assert recommendation is not None
    assert recommendation['min_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['min'])).quantize(Decimal('0.01'))
    assert recommendation['max_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['max'])).quantize(Decimal('0.01'))
    assert recommendation['recommended_weekly'] == Decimal(str(analysis.recommendations['insurance_premium_weekly']['recommended'])).quantize(Decimal('0.01'))
    assert recommendation['min'] == Decimal('16.31')
    assert recommendation['max'] == Decimal('39.13')
    assert recommendation['recommended'] == Decimal('26.09')


def test_edit_insurance_policy_renders_shared_recommendation_text(client):
    admin, _, _, _ = _create_admin_with_block()
    policy = _create_insurance_policy(admin.id, 'Coverage', Decimal('40.00'), block='A')
    _login_admin(client, admin.id)

    response = client.get(f'/admin/insurance/edit/{policy.id}')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Keep monthly premium costs in the $16.31-$39.13 range.' in html
    assert 'Ideal target: $26.09' in html


def test_update_economy_policy_creates_block_scoped_settings(client):
    admin, _, _, _ = _create_admin_with_block()
    _login_admin(client, admin.id)

    response = client.post('/admin/economy-policy', data={
        'policy_mode': 'comfortable',
        'block': 'A',
    })

    assert response.status_code == 302
    assert 'review_rebalance=1' in response.location

    settings_row = FeatureSettings.query.filter_by(teacher_id=admin.id, block='A').first()
    assert settings_row is not None
    assert settings_row.join_code == 'JOINPOLA'
    assert settings_row.economy_policy_mode == 'comfortable'


def test_get_feature_settings_row_requires_scoped_class_resolution(client):
    admin, _, _, _ = _create_admin_with_block()
    read_row = get_feature_settings_row(admin.id, block='A', create=False)
    created_row = get_feature_settings_row(admin.id, block='A', create=True)
    db.session.commit()

    assert read_row is None
    assert created_row is not None
    assert created_row.block == 'A'
    assert created_row.join_code == 'JOINPOLA'


def test_rent_warnings_report_single_monthly_conversion(client):
    admin, payroll_settings, _, _ = _create_admin_with_block()
    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='default')
    cwi = checker.calculate_cwi(payroll_settings).cwi
    high_rent = RentSettings(
        teacher_id=admin.id,
        join_code='JOINPOLA',
        block='A',
        is_enabled=True,
        rent_amount=Decimal('600.00'),
        frequency_type='monthly',
    )

    warnings = checker.check_rent_balance(high_rent, cwi)

    rent_warning = next(w for w in warnings if w.feature == 'Rent' and w.level in (WarningLevel.WARNING, WarningLevel.CRITICAL))
    assert round(float(rent_warning.recommended_max), 2) == round(cwi * 0.75 * checker.AVERAGE_WEEKS_PER_MONTH, 2)


def test_immediate_rebalance_updates_rent_setting(client):
    admin, payroll_settings, rent_settings, economy = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, join_code='JOINPOLA', class_id=economy.class_id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='tight')
    expected_rent = Decimal(str(checker.analyze_economy(payroll_settings).recommendations['rent']['recommended']))

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'immediate',
        'confirm_immediate': 'yes',
        'selected_changes': ['rent'],
    })

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == expected_rent


def test_invalid_activation_mode_is_rejected(client):
    admin, _, rent_settings, economy = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, join_code='JOINPOLA', class_id=economy.class_id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'later',
        'selected_changes': ['rent'],
    })

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('500.00')


def test_rebalance_ignores_cross_teacher_selected_ids(client):
    admin_a, _, _, economy_a = _create_admin_with_block('A', 'JOINPOLA')
    admin_b, _, _, _ = _create_admin_with_block('B', 'JOINPOLB')
    policy_a = _create_insurance_policy(admin_a.id, 'Teacher A Policy', '20.00', block='A')
    policy_b = _create_insurance_policy(admin_b.id, 'Teacher B Policy', '99.00', block='B')
    _login_admin(client, admin_a.id)
    db.session.add(FeatureSettings(teacher_id=admin_a.id, join_code='JOINPOLA', class_id=economy_a.class_id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'immediate',
        'confirm_immediate': 'yes',
        'selected_changes': [f'insurance_{policy_b.id}'],
    })

    assert response.status_code == 302
    db.session.refresh(policy_a)
    db.session.refresh(policy_b)
    assert policy_a.premium == Decimal('20.00')
    assert policy_b.premium == Decimal('99.00')


def test_run_payroll_applies_scheduled_rebalance(client):
    admin, _, rent_settings, economy = _create_admin_with_block()
    _login_admin(client, admin.id)

    settings_row = FeatureSettings(
        teacher_id=admin.id,
        join_code='JOINPOLA',
        class_id=economy.class_id,
        block='A',
        economy_policy_mode='tight',
        economy_pending_rebalance_json=json.dumps({
            'activation_mode': 'next_payroll',
            'changes': [
                {
                    'type': 'rent',
                    'block': 'A',
                    'join_code': 'JOINPOLA',
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

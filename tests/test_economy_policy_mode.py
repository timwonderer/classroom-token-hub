import json
from datetime import datetime, timezone
from decimal import Decimal

from app import db
from app.routes.admin import _build_rebalance_preview, _get_transaction_tier_base_premium, _inverse_weekly_amount
from app.models import Admin, FeatureSettings, InsurancePolicy, PayrollSettings, RentSettings
from app.utils.economy_balance import EconomyBalanceChecker, WarningLevel
from app.utils.economy_policy import (
    get_feature_settings_row,
    get_transaction_coverage_default,
    get_transaction_tier_defaults,
)


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


def _create_insurance_policy(admin_id, title, premium, block='A'):
    sanitized_title = ''.join(ch for ch in title.upper() if ch.isalnum()) or 'POLICY'
    code_seed = f"{sanitized_title[:5]}{sanitized_title[-3:]}"
    policy = InsurancePolicy(
        teacher_id=admin_id,
        policy_code=f"{code_seed}{admin_id}",
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
    assert recommendations['transaction_insurance_defaults']['recommended_base_premium'] == round(cwi * 0.07, 2)
    assert recommendations['transaction_insurance_defaults']['tiers']['basic']['period_cap_multiplier'] == 6.0
    assert recommendations['transaction_insurance_defaults']['tiers']['mid']['period_cap_multiplier'] == 8.0
    assert recommendations['transaction_insurance_defaults']['tiers']['premium']['period_cap_multiplier'] == 10.0


def test_transaction_insurance_defaults_vary_by_policy_mode():
    assert get_transaction_coverage_default('tight') == Decimal('0.5')
    assert get_transaction_coverage_default('default') == Decimal('0.5')
    assert get_transaction_coverage_default('comfortable') == Decimal('0.5')

    default_mid = get_transaction_tier_defaults('default', 2, Decimal('120.00'))
    assert default_mid['coverage_percent'] == Decimal('0.7')
    assert default_mid['base_premium'] == Decimal('9.60')
    assert default_mid['tier_multiplier'] == Decimal('1.0')
    assert default_mid['premium'] == Decimal('9.60')
    assert default_mid['max_payout_per_period'] == Decimal('76.80')

    tight_basic = get_transaction_tier_defaults('tight', 1, Decimal('250.00'))
    assert tight_basic['coverage_percent'] == Decimal('0.5')
    assert tight_basic['base_premium'] == Decimal('22.50')
    assert tight_basic['tier_multiplier'] == Decimal('0.75')
    assert tight_basic['premium'] == Decimal('16.88')
    assert tight_basic['max_payout_per_period'] == Decimal('101.28')

    comfortable_premium = get_transaction_tier_defaults('comfortable', 3, Decimal('250.00'))
    assert comfortable_premium['coverage_percent'] == Decimal('0.9')
    assert comfortable_premium['base_premium'] == Decimal('17.50')
    assert comfortable_premium['tier_multiplier'] == Decimal('1.3')
    assert comfortable_premium['premium'] == Decimal('22.75')
    assert comfortable_premium['max_payout_per_period'] == Decimal('227.50')


def test_transaction_tier_waiting_periods_are_tier_controlled():
    assert get_transaction_tier_defaults('tight', 1)['waiting_period_days'] == 7
    assert get_transaction_tier_defaults('default', 2)['waiting_period_days'] == 5
    assert get_transaction_tier_defaults('comfortable', 3)['waiting_period_days'] == 3


def test_transaction_tier_defaults_accept_teacher_base_premium():
    manual_mid = get_transaction_tier_defaults('default', 2, base_premium=Decimal('60.00'))

    assert manual_mid['base_premium'] == Decimal('60.00')
    assert manual_mid['premium'] == Decimal('60.00')
    assert manual_mid['max_payout_per_period'] == Decimal('480.00')


def test_edit_policy_rejects_contract_shape_changes(client):
    admin, _, _ = _create_admin_with_block()
    policy = _create_insurance_policy(admin.id, "Contract Policy", 25.00)
    _login_admin(client, admin.id)

    response = client.post(f'/admin/insurance/edit/{policy.id}', data={
        'title': policy.title,
        'description': policy.description or '',
        'premium': '25.00',
        'charge_frequency': policy.charge_frequency,
        'claim_type': 'transaction_monetary',
        'waiting_period_days': str(policy.waiting_period_days),
        'is_active': 'y',
    })

    assert response.status_code == 302
    db.session.refresh(policy)
    assert policy.claim_type == 'legacy_monetary'


def test_get_transaction_tier_base_premium_normalizes_nonweekly_storage(client):
    admin, _, _ = _create_admin_with_block()
    weekly_premium = get_transaction_tier_defaults('default', 2, Decimal('120.00'))['premium']
    policy = _create_insurance_policy(admin.id, "Tiered Monthly Policy", _inverse_weekly_amount(weekly_premium, 'monthly'))
    policy.claim_type = 'transaction_monetary'
    policy.charge_frequency = 'monthly'
    policy.tier_rank = 2
    policy.tier_level = 'mid'
    db.session.commit()

    base_premium = _get_transaction_tier_base_premium(policy)

    assert base_premium == Decimal('9.60')


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


def test_get_feature_settings_row_create_preserves_global_fallback_for_reads(client):
    admin, _, _ = _create_admin_with_block()
    global_row = FeatureSettings(teacher_id=admin.id, block=None, economy_policy_mode='default')
    db.session.add(global_row)
    db.session.commit()

    read_row = get_feature_settings_row(admin.id, block='A', create=False)
    created_row = get_feature_settings_row(admin.id, block='A', create=True)
    db.session.commit()

    assert read_row.id == global_row.id
    assert created_row.id != global_row.id
    assert created_row.block == 'A'


def test_rent_warnings_report_single_monthly_conversion(client):
    admin, payroll_settings, _ = _create_admin_with_block()
    checker = EconomyBalanceChecker(admin.id, 'A', policy_mode='default')
    cwi = checker.calculate_cwi(payroll_settings).cwi
    high_rent = RentSettings(
        teacher_id=admin.id,
        block='A',
        is_enabled=True,
        rent_amount=Decimal('600.00'),
        frequency_type='monthly',
    )

    warnings = checker.check_rent_balance(high_rent, cwi)

    rent_warning = next(w for w in warnings if w.feature == 'Rent' and w.level in (WarningLevel.WARNING, WarningLevel.CRITICAL))
    assert round(float(rent_warning.recommended_max), 2) == round(cwi * checker.RENT_MAX_RATIO, 2)


def test_immediate_rebalance_updates_rent_setting(client):
    admin, payroll_settings, rent_settings = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, block='A', economy_policy_mode='tight'))
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
    admin, _, rent_settings = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, block='A', economy_policy_mode='tight'))
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
    admin_a, _, _ = _create_admin_with_block('A')
    admin_b, _, _ = _create_admin_with_block('B')
    policy_a = _create_insurance_policy(admin_a.id, 'Teacher A Policy', '20.00', block='A')
    policy_b = _create_insurance_policy(admin_b.id, 'Teacher B Policy', '99.00', block='B')
    _login_admin(client, admin_a.id)
    db.session.add(FeatureSettings(teacher_id=admin_a.id, block='A', economy_policy_mode='tight'))
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


def test_rebalance_preview_uses_saved_tier_selection_for_transaction_insurance(client):
    admin, payroll_settings, rent_settings = _create_admin_with_block()
    db.session.add(FeatureSettings(teacher_id=admin.id, block='A', economy_policy_mode='default'))
    db.session.commit()

    basic_policy = _create_insurance_policy(admin.id, 'Paycheck Protection Basic', '60.00', block='A')
    basic_policy.claim_type = 'transaction_monetary'
    basic_policy.product_group_id = 1001
    basic_policy.tier_rank = 1
    basic_policy.tier_level = 'basic'

    max_policy = _create_insurance_policy(admin.id, 'Paycheck Protection Max', '140.00', block='A')
    max_policy.claim_type = 'transaction_monetary'
    max_policy.product_group_id = 1001
    max_policy.tier_rank = 3
    max_policy.tier_level = 'premium'
    db.session.commit()

    checker = EconomyBalanceChecker(admin.id, 'A')
    analysis = checker.analyze_economy(payroll_settings, rent_settings=rent_settings, insurance_policies=[basic_policy, max_policy])
    preview_items = _build_rebalance_preview(
        admin.id,
        'A',
        checker,
        analysis.cwi.cwi,
        rent_settings,
        [basic_policy, max_policy],
    )

    by_title = {item['change']['title']: item for item in preview_items if item['change']['type'] == 'insurance'}
    expected_basic = str(
        _inverse_weekly_amount(
            get_transaction_tier_defaults('default', 1, Decimal(str(analysis.cwi.cwi)))['premium'],
            basic_policy.charge_frequency,
        )
    )
    expected_max = str(
        _inverse_weekly_amount(
            get_transaction_tier_defaults('default', 3, Decimal(str(analysis.cwi.cwi)))['premium'],
            max_policy.charge_frequency,
        )
    )

    assert by_title['Paycheck Protection Basic']['change']['new_value'] == expected_basic
    assert by_title['Paycheck Protection Max']['change']['new_value'] == expected_max
    assert by_title['Paycheck Protection Basic']['change']['new_value'] != by_title['Paycheck Protection Max']['change']['new_value']


def test_rebalance_preview_uses_saved_tier_selection_for_custom_monetary_insurance(client):
    admin, payroll_settings, rent_settings = _create_admin_with_block()

    basic_policy = _create_insurance_policy(admin.id, 'Allowance Shield Basic', '40.00', block='A')
    basic_policy.claim_type = 'legacy_monetary'
    basic_policy.product_group_id = 2002
    basic_policy.tier_rank = 1
    basic_policy.tier_level = 'basic'

    max_policy = _create_insurance_policy(admin.id, 'Allowance Shield Max', '90.00', block='A')
    max_policy.claim_type = 'legacy_monetary'
    max_policy.product_group_id = 2002
    max_policy.tier_rank = 3
    max_policy.tier_level = 'premium'
    db.session.commit()

    checker = EconomyBalanceChecker(admin.id, 'A')
    analysis = checker.analyze_economy(payroll_settings, rent_settings=rent_settings, insurance_policies=[basic_policy, max_policy])
    preview_items = _build_rebalance_preview(
        admin.id,
        'A',
        checker,
        analysis.cwi.cwi,
        rent_settings,
        [basic_policy, max_policy],
    )

    by_title = {item['change']['title']: item for item in preview_items if item['change']['type'] == 'insurance'}
    monthly_factor = Decimal(str(EconomyBalanceChecker.AVERAGE_WEEKS_PER_MONTH))
    expected_basic = str((Decimal(str(analysis.recommendations['insurance_premium_weekly']['min'])) * monthly_factor).quantize(Decimal('0.01')))
    expected_max = str((Decimal(str(analysis.recommendations['insurance_premium_weekly']['max'])) * monthly_factor).quantize(Decimal('0.01')))

    assert by_title['Allowance Shield Basic']['change']['new_value'] == expected_basic
    assert by_title['Allowance Shield Max']['change']['new_value'] == expected_max
    assert by_title['Allowance Shield Basic']['change']['new_value'] != by_title['Allowance Shield Max']['change']['new_value']


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

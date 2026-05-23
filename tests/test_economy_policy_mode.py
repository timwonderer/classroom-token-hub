from tests.helpers.v2_fixtures import make_admin, make_sysadmin
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
    RentPayment,
    RentSettings,
    Seat,
    Student,
    TeacherBlock,
    Transaction,
)
from app.hash_utils import get_random_salt, hash_username
from app.routes.student import (
    _get_effective_rent_amount_for_coverage_period,
    _is_coverage_period_paid,
)
from app.utils.economy_balance import EconomyBalanceChecker, WarningLevel
from app.utils.economy_policy import (
    convert_weekly_amount_to_frequency,
    get_feature_settings_row,
    get_insurance_premium_recommendation,
    get_price_recommendation_context,
)
from app.utils.economy_rebalance import (
    REBALANCE_ACTIVATION_NEXT_RENEWAL,
    activate_due_rebalances,
    prepare_scheduled_rebalance_changes,
)


def _login_admin(client, admin_id, *, join_code=None, class_id=None):
    resolved_join_code = join_code
    resolved_class_id = class_id
    if not resolved_join_code:
        block_row = (
            TeacherBlock.query.with_entities(TeacherBlock.join_code)
            .filter(TeacherBlock.teacher_id == admin_id, TeacherBlock.join_code.isnot(None))
            .order_by(TeacherBlock.id.asc())
            .first()
        )
        resolved_join_code = block_row[0] if block_row and block_row[0] else None
    if not resolved_class_id and resolved_join_code:
        class_row = ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(
            join_code=resolved_join_code,
            teacher_id=admin_id,
        ).first()
        resolved_class_id = class_row[0] if class_row and class_row[0] else None

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['is_system_admin'] = False
        if resolved_join_code:
            sess['current_join_code'] = resolved_join_code
        if resolved_class_id:
            sess['current_class_id'] = resolved_class_id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


def _create_teacher_block(admin_id, block='A', join_code='JOINPOLA', class_id=None):
    identity = IdentityProfile(profile_type='student', first_name='Policy', last_initial='S')
    db.session.add(identity)
    db.session.flush()

    teacher_block = TeacherBlock(
        teacher_id=admin_id,
        class_id=class_id,
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
    admin = make_admin(f"policyadmin_{block.lower()}_{join_code.lower()}", "TESTSECRET123456")
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

    _create_teacher_block(admin.id, block=block, join_code=join_code, class_id=economy.class_id)

    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        join_code=join_code,
        class_id=economy.class_id,
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
        class_id=economy.class_id,
        block=block,
        is_enabled=True,
        rent_amount=Decimal('500.00'),
        frequency_type='monthly',
    )
    db.session.add_all([payroll_settings, rent_settings])
    db.session.commit()
    return admin, payroll_settings, rent_settings, economy


def _create_insurance_policy(admin_id, title, premium, block='A', join_code=None):
    join_code = join_code or f"JOIN{block}{admin_id}"
    class_row = ClassEconomy.query.filter_by(join_code=join_code, teacher_id=admin_id).first()
    if not class_row:
        db.session.add(ClassEconomy(
            join_code=join_code,
            teacher_id=admin_id,
            created_by_admin_id=admin_id,
            display_name=f'Period {block}',
        ))
        db.session.flush()
        class_row = ClassEconomy.query.filter_by(join_code=join_code, teacher_id=admin_id).first()
    policy = InsurancePolicy(
        teacher_id=admin_id,
        join_code=join_code,
        class_id=class_row.class_id if class_row else None,
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


def test_price_recommendation_context_centralizes_policy_output(client):
    context = get_price_recommendation_context('comfortable', Decimal('50.00'))

    assert context is not None
    assert context['policy_mode'] == 'comfortable'
    assert context['rent_weekly']['recommended'] == 28.75
    assert context['rent']['recommended'] == 125.01
    assert context['insurance_premium_weekly']['recommended'] == 3.5
    assert context['insurance_coverage']['multiplier_recommended'] == 5.0
    assert context['store_tiers']['premium']['max'] == 9.0


def test_convert_weekly_amount_to_frequency_supports_custom_schedules(client):
    assert convert_weekly_amount_to_frequency(Decimal('10.00'), 'weekly') == Decimal('10.00')
    assert convert_weekly_amount_to_frequency(Decimal('10.00'), 'monthly') == Decimal('43.48')
    assert convert_weekly_amount_to_frequency(
        Decimal('10.00'),
        'custom',
        custom_frequency_value=2,
        custom_frequency_unit='weeks',
    ) == Decimal('20.00')


def test_edit_insurance_policy_renders_shared_recommendation_text(client):
    admin, _, _, _ = _create_admin_with_block()
    policy = _create_insurance_policy(admin.id, 'Coverage', Decimal('40.00'), block='A', join_code='JOINPOLA')
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
    scoped_rent = RentSettings.query.filter_by(
        teacher_id=admin.id,
        class_id=economy.class_id,
        block='A',
    ).first()
    assert scoped_rent is not None
    assert scoped_rent.rent_amount == expected_rent


def test_rebalanced_rent_amount_does_not_backdate_current_coverage_due(client):
    _, _, rent_settings, _ = _create_admin_with_block()
    rent_settings.rent_amount = Decimal('620.00')
    rent_settings.updated_at = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

    coverage_due_date = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    prior_cycle_payment = RentPayment(
        amount_paid=Decimal('500.00'),
        payment_date=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
    )

    assert _is_coverage_period_paid(
        rent_settings,
        [prior_cycle_payment],
        coverage_due_date,
        include_late_fee=False,
    )


def test_join_code_cycle_locks_rent_rate_after_first_payment(client):
    admin, _, rent_settings, _ = _create_admin_with_block()
    join_code = "LOCKA1"
    lock_class = ClassEconomy(
        join_code=join_code,
        teacher_id=admin.id,
        created_by_admin_id=admin.id,
        display_name='Period A Lock',
    )
    db.session.add(lock_class)
    db.session.flush()
    coverage_due_date = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

    salt = get_random_salt()
    payer = Student(
        first_name="Rate",
        last_initial="L",
        block="A",
        salt=salt,
        username_hash=hash_username("rate-lock-payer", salt),
        pin_hash="test-pin",
    )
    db.session.add(payer)
    db.session.flush()
    seat = Seat(
        student_id=payer.id,
        class_id=lock_class.class_id,
        join_code=join_code,
        block='A',
        role='student',
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()

    payment_date = datetime(2026, 3, 5, 8, 0, tzinfo=timezone.utc)
    db.session.add(RentPayment(
        student_id=payer.id,
        seat_id=seat.id,
        class_id=lock_class.class_id,
        period="A",
        join_code=join_code,
        amount_paid=Decimal("500.00"),
        late_fee_charged=Decimal("0.00"),
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
    ))
    db.session.add(Transaction(
        seat_id=seat.id,
        student_id=payer.id,
        teacher_id=admin.id,
        class_id=lock_class.class_id,
        join_code=join_code,
        type="Rent Payment",
        amount=Decimal("-500.00"),
        timestamp=payment_date,
        description="Rent payment",
    ))
    db.session.commit()

    rent_settings.rent_amount = Decimal("620.00")
    rent_settings.updated_at = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)

    effective_amount = _get_effective_rent_amount_for_coverage_period(
        rent_settings,
        payments=[],
        coverage_due_date=coverage_due_date,
        join_code=join_code,
    )

    assert effective_amount == Decimal("500.00")


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

    response = client.post('/admin/run_payroll')

    assert response.status_code == 302
    db.session.refresh(rent_settings)
    db.session.refresh(settings_row)
    assert rent_settings.rent_amount == Decimal('610.00')
    assert settings_row.economy_pending_rebalance_json is None


def test_next_renewal_rebalance_schedules_rent_for_next_cycle(client):
    admin, _, rent_settings, economy = _create_admin_with_block()
    _login_admin(client, admin.id)
    db.session.add(FeatureSettings(teacher_id=admin.id, join_code='JOINPOLA', class_id=economy.class_id, block='A', economy_policy_mode='tight'))
    db.session.commit()

    response = client.post('/admin/economy-policy/rebalance', data={
        'block': 'A',
        'activation_mode': 'next_renewal',
        'selected_changes': ['rent'],
    })

    settings_row = FeatureSettings.query.filter_by(teacher_id=admin.id, block='A').first()
    payload = json.loads(settings_row.economy_pending_rebalance_json)
    scheduled_change = payload['changes'][0]

    assert response.status_code == 302
    assert payload['activation_mode'] == REBALANCE_ACTIVATION_NEXT_RENEWAL
    assert scheduled_change['type'] == 'rent'
    assert scheduled_change['effective_at'] is not None
    db.session.refresh(rent_settings)
    assert rent_settings.rent_amount == Decimal('500.00')


def test_activate_due_rebalances_applies_past_due_rent_change(client):
    admin, _, rent_settings, economy = _create_admin_with_block()
    settings_row = FeatureSettings(
        teacher_id=admin.id,
        join_code='JOINPOLA',
        class_id=economy.class_id,
        block='A',
        economy_policy_mode='tight',
        economy_pending_rebalance_json=json.dumps({
            'activation_mode': REBALANCE_ACTIVATION_NEXT_RENEWAL,
            'changes': [
                {
                    'type': 'rent',
                    'block': 'A',
                    'join_code': 'JOINPOLA',
                    'current_value': '500.00',
                    'new_value': '610.00',
                    'effective_at': '2026-03-01T00:00:00+00:00',
                }
            ],
        }),
    )
    db.session.add(settings_row)
    db.session.commit()

    activated, labels = activate_due_rebalances(
        admin.id,
        reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    db.session.commit()

    db.session.refresh(rent_settings)
    db.session.refresh(settings_row)
    assert activated == 1
    assert labels == ['Rent']
    assert rent_settings.rent_amount == Decimal('610.00')
    assert settings_row.economy_pending_rebalance_json is None


def test_activate_due_rebalances_keeps_rent_mutation_in_settings_row_class(client):
    admin, _, rent_settings_a, economy_a = _create_admin_with_block('A', 'JOINPOLA')

    economy_b = ClassEconomy(
        join_code='JOINPOLB',
        teacher_id=admin.id,
        created_by_admin_id=admin.id,
        display_name='Period B',
    )
    db.session.add(economy_b)
    db.session.flush()
    _create_teacher_block(admin.id, block='B', join_code='JOINPOLB', class_id=economy_b.class_id)

    rent_settings_b = RentSettings(
        teacher_id=admin.id,
        join_code='JOINPOLB',
        class_id=economy_b.class_id,
        block='B',
        is_enabled=True,
        rent_amount=Decimal('700.00'),
        frequency_type='monthly',
    )
    settings_row = FeatureSettings(
        teacher_id=admin.id,
        join_code='JOINPOLA',
        class_id=economy_a.class_id,
        block='A',
        economy_policy_mode='tight',
        economy_pending_rebalance_json=json.dumps({
            'activation_mode': 'next_payroll',
            'changes': [
                {
                    'type': 'rent',
                    # Malicious/mismatched payload scope should not redirect class mutation.
                    'block': 'B',
                    'join_code': 'JOINPOLB',
                    'current_value': '500.00',
                    'new_value': '610.00',
                }
            ],
        }),
    )
    db.session.add_all([rent_settings_b, settings_row])
    db.session.commit()

    activated, labels = activate_due_rebalances(
        admin.id,
        reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    db.session.commit()

    db.session.refresh(rent_settings_a)
    db.session.refresh(rent_settings_b)
    db.session.refresh(settings_row)
    assert activated == 1
    assert labels == ['Rent']
    assert rent_settings_a.rent_amount == Decimal('610.00')
    assert rent_settings_b.rent_amount == Decimal('700.00')
    assert settings_row.economy_pending_rebalance_json is None


def test_activate_due_rebalances_does_not_mutate_cross_class_insurance_policy(client):
    admin, _, _, economy_a = _create_admin_with_block('A', 'JOINPOLA')
    policy_b = _create_insurance_policy(admin.id, 'Cross Class Policy', '99.00', block='B', join_code='JOINPOLB')

    settings_row = FeatureSettings(
        teacher_id=admin.id,
        join_code='JOINPOLA',
        class_id=economy_a.class_id,
        block='A',
        economy_policy_mode='tight',
        economy_pending_rebalance_json=json.dumps({
            'activation_mode': 'next_payroll',
            'changes': [
                {
                    'type': 'insurance',
                    # Policy from another class for the same teacher.
                    'policy_id': policy_b.id,
                    'current_value': '99.00',
                    'new_value': '130.00',
                }
            ],
        }),
    )
    db.session.add(settings_row)
    db.session.commit()

    activated, labels = activate_due_rebalances(
        admin.id,
        reference_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    db.session.commit()

    db.session.refresh(policy_b)
    db.session.refresh(settings_row)
    assert activated == 0
    assert labels == []
    assert policy_b.premium == Decimal('99.00')
    assert settings_row.economy_pending_rebalance_json is None


def test_prepare_scheduled_rebalance_changes_sets_rent_effective_at(client):
    admin, _, rent_settings, _ = _create_admin_with_block()

    changes = prepare_scheduled_rebalance_changes(
        [{
            'type': 'rent',
            'block': 'A',
            'join_code': 'JOINPOLA',
            'current_value': '500.00',
            'new_value': '610.00',
        }],
        rent_settings=rent_settings,
        reference_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
    )

    assert len(changes) == 1
    assert changes[0]['effective_at'] is not None

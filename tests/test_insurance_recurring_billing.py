from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    Admin,
    InsurancePolicy,
    Student,
    StudentInsurance,
    StudentTeacher,
    TeacherBlock,
    Transaction,
)
from app.scheduled_tasks import process_insurance_billing_job, reset_insurance_billing_cycles
from app.utils.insurance_billing import (
    INSURANCE_BILLING_LAUNCH_CUTOFF,
    insurance_next_payment_due,
)
from app.utils.time import ensure_utc


def _build_teacher_student(join_code='INSJOIN1', block='A'):
    teacher = Admin(username=f"teacher_{join_code}", totp_secret="secret")
    db.session.add(teacher)
    db.session.flush()

    student = Student(first_name="Ins", last_initial="T", block=block, salt=b'salt')
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id, join_code=join_code))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        first_name='Ins',
        last_initial='T',
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b'salt',
        first_half_hash=f'hash-{join_code}',
    ))
    db.session.flush()
    return teacher, student


def _policy(teacher_id, code, title, premium='10.00', autopay=True, auto_cancel_nonpay_days=3, charge_frequency='monthly'):
    policy = InsurancePolicy(
        policy_code=code,
        teacher_id=teacher_id,
        title=title,
        description='',
        premium=Decimal(premium),
        charge_frequency=charge_frequency,
        autopay=autopay,
        auto_cancel_nonpay_days=auto_cancel_nonpay_days,
        claim_type='transaction_monetary',
        is_monetary=True,
    )
    db.session.add(policy)
    db.session.flush()
    return policy


def _enrollment(student_id, policy_id, join_code, *, purchase_date, next_payment_due, days_unpaid=0, payment_current=True, status='active'):
    enrollment = StudentInsurance(
        student_id=student_id,
        policy_id=policy_id,
        join_code=join_code,
        status=status,
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=next_payment_due,
        coverage_start_date=purchase_date,
        days_unpaid=days_unpaid,
        payment_current=payment_current,
    )
    db.session.add(enrollment)
    db.session.flush()
    enrollment.freeze_policy_snapshot(enrollment.policy)
    db.session.commit()
    return enrollment


def _deposit(student_id, teacher_id, join_code, amount):
    db.session.add(Transaction(
        student_id=student_id,
        teacher_id=teacher_id,
        join_code=join_code,
        amount=Decimal(amount),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()


def test_enrollment_reset_migration_only_resets_legacy_active_plans(app):
    with app.app_context():
        teacher, student = _build_teacher_student('LEGACY1')
        policy = _policy(teacher.id, 'LEGACY-POL', 'Legacy Coverage')

        legacy_purchase = INSURANCE_BILLING_LAUNCH_CUTOFF - timedelta(days=30)
        modern_purchase = INSURANCE_BILLING_LAUNCH_CUTOFF + timedelta(days=1)
        now = INSURANCE_BILLING_LAUNCH_CUTOFF + timedelta(days=2)

        legacy = _enrollment(
            student.id,
            policy.id,
            'LEGACY1',
            purchase_date=legacy_purchase,
            next_payment_due=legacy_purchase + timedelta(days=28),
        )
        modern = _enrollment(
            student.id,
            policy.id,
            'LEGACY1',
            purchase_date=modern_purchase,
            next_payment_due=modern_purchase + timedelta(days=28),
        )

        reset_count = reset_insurance_billing_cycles(now=now)

        db.session.refresh(legacy)
        db.session.refresh(modern)

        assert reset_count == 1
        assert ensure_utc(legacy.last_payment_date) == now
        assert ensure_utc(legacy.next_payment_due) == insurance_next_payment_due(now, policy.charge_frequency)
        assert legacy.payment_current is True
        assert legacy.days_unpaid == 0

        assert ensure_utc(modern.last_payment_date) == modern_purchase
        assert ensure_utc(modern.next_payment_due) == modern_purchase + timedelta(days=28)


def test_billing_job_charges_autopay_student_and_scopes_by_join_code(app):
    with app.app_context():
        teacher, student = _build_teacher_student('BILLA')
        db.session.add(TeacherBlock(
            teacher_id=teacher.id,
            block='B',
            join_code='BILLB',
            student_id=student.id,
            is_claimed=True,
            first_name='Ins',
            last_initial='T',
            last_name_hash_by_part=[],
            dob_sum=0,
            salt=b'salt',
            first_half_hash='hash-BILLB',
        ))
        db.session.commit()

        policy_a = _policy(teacher.id, 'AUTO-A', 'Coverage A', premium='10.00')
        policy_b = _policy(teacher.id, 'AUTO-B', 'Coverage B', premium='10.00')
        now = INSURANCE_BILLING_LAUNCH_CUTOFF + timedelta(days=10)

        enrollment_a = _enrollment(
            student.id,
            policy_a.id,
            'BILLA',
            purchase_date=now - timedelta(days=10),
            next_payment_due=now - timedelta(days=1),
        )
        enrollment_b = _enrollment(
            student.id,
            policy_b.id,
            'BILLB',
            purchase_date=now - timedelta(days=10),
            next_payment_due=now - timedelta(days=1),
        )
        _deposit(student.id, teacher.id, 'BILLA', '25.00')

        process_insurance_billing_job(now=now)

        db.session.refresh(enrollment_a)
        db.session.refresh(enrollment_b)

        assert enrollment_a.payment_current is True
        assert enrollment_a.days_unpaid == 0
        assert ensure_utc(enrollment_a.next_payment_due) == insurance_next_payment_due(now, policy_a.charge_frequency)
        assert Transaction.query.filter_by(
            student_id=student.id,
            join_code='BILLA',
            type='insurance_premium',
        ).count() == 1

        assert enrollment_b.payment_current is False
        assert enrollment_b.days_unpaid == 1
        assert Transaction.query.filter_by(
            student_id=student.id,
            join_code='BILLB',
            type='insurance_premium',
        ).count() == 0


def test_billing_job_manual_pay_policy_skipped_and_marked_overdue(app):
    with app.app_context():
        teacher, student = _build_teacher_student('MANPAY1')
        policy = _policy(teacher.id, 'MANUAL-1', 'Manual Coverage', premium='12.00', autopay=False)
        now = INSURANCE_BILLING_LAUNCH_CUTOFF + timedelta(days=10)

        enrollment = _enrollment(
            student.id,
            policy.id,
            'MANPAY1',
            purchase_date=now - timedelta(days=5),
            next_payment_due=now - timedelta(days=1),
        )
        _deposit(student.id, teacher.id, 'MANPAY1', '50.00')

        process_insurance_billing_job(now=now)

        db.session.refresh(enrollment)

        assert enrollment.payment_current is False
        assert enrollment.days_unpaid == 1
        assert enrollment.status == 'active'
        assert Transaction.query.filter_by(
            student_id=student.id,
            join_code='MANPAY1',
            type='insurance_premium',
        ).count() == 0


def test_billing_job_cancels_after_threshold(app):
    with app.app_context():
        teacher, student = _build_teacher_student('CANCEL1')
        policy = _policy(
            teacher.id,
            'CANCEL-POL',
            'Cancel Coverage',
            premium='8.00',
            autopay=False,
            auto_cancel_nonpay_days=2,
        )
        now = INSURANCE_BILLING_LAUNCH_CUTOFF + timedelta(days=10)

        enrollment = _enrollment(
            student.id,
            policy.id,
            'CANCEL1',
            purchase_date=now - timedelta(days=3),
            next_payment_due=now - timedelta(days=1),
            days_unpaid=1,
        )

        process_insurance_billing_job(now=now)

        db.session.refresh(enrollment)

        assert enrollment.payment_current is False
        assert enrollment.days_unpaid == 2
        assert enrollment.status == 'cancelled'
        assert ensure_utc(enrollment.cancel_date) == now

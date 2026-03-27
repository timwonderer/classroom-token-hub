"""
Tests for rent penalty reversal and cycle rate locking.

Covers:
- _get_locked_rent_amount_for_join_code_cycle returns first payer's base rate
- _has_active_rent_waiver / _is_student_coverage_period_paid respects waivers
- Admin reverse_cycle_penalties route refunds misapplied late fees
- Rent waiver creation stores join_code
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import db
from app.models import (
    Admin,
    RentPayment,
    RentSettings,
    RentWaiver,
    Student,
    TeacherBlock,
    Transaction,
    TransactionStatus,
)
from app.hash_utils import get_random_salt, hash_username
from app.routes.student import (
    _get_locked_rent_amount_for_join_code_cycle,
    _has_active_rent_waiver,
    _is_student_coverage_period_paid,
    RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin(suffix="rv"):
    admin = Admin(username=f"admin_{suffix}", totp_secret="TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()
    return admin


def _make_rent_settings(admin_id, block="A", amount=Decimal("100.00")):
    settings = RentSettings(
        teacher_id=admin_id,
        block=block,
        is_enabled=True,
        rent_amount=amount,
        frequency_type="monthly",
        grace_period_days=3,
        late_penalty_amount=Decimal("10.00"),
        late_penalty_type="once",
    )
    db.session.add(settings)
    db.session.flush()
    return settings


def _make_teacher_block(admin_id, block, join_code):
    """Create a TeacherBlock row representing the admin's own class period seat."""
    salt = get_random_salt()
    first_name = "Teacher"
    first_half = first_name[:len(first_name)//2].lower()
    tb = TeacherBlock(
        teacher_id=admin_id,
        block=block,
        first_name=first_name,
        last_initial="T",
        dob_sum=2000,
        salt=salt,
        first_half_hash=first_half,
        last_name_hash_by_part=[],
        join_code=join_code,
        is_claimed=False,
        is_teacher=True,
    )
    db.session.add(tb)
    db.session.flush()
    return tb


def _make_student(suffix="s"):
    salt = get_random_salt()
    student = Student(
        first_name="Test",
        last_initial="R",
        block="A",
        salt=salt,
        username_hash=hash_username(f"student_{suffix}", salt),
        pin_hash="test-pin",
    )
    db.session.add(student)
    db.session.flush()
    return student


def _add_payment_with_txn(student, join_code, amount_paid, late_fee, payment_date,
                           coverage_due_date, admin_id, block="A", is_void=False):
    """Create a RentPayment and matching Transaction (as the student route does)."""
    payment = RentPayment(
        student_id=student.id,
        period=block,
        join_code=join_code,
        amount_paid=amount_paid,
        late_fee_charged=late_fee,
        was_late=(late_fee > Decimal("0.00")),
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
    )
    db.session.add(payment)
    txn = Transaction(
        student_id=student.id,
        teacher_id=admin_id,
        join_code=join_code,
        type="Rent Payment",
        amount=-amount_paid,
        status=TransactionStatus.PENDING,
        timestamp=payment_date,
        description="Rent payment",
        is_void=is_void,
    )
    db.session.add(txn)
    db.session.flush()
    return payment, txn


# ---------------------------------------------------------------------------
# Tests: _get_locked_rent_amount_for_join_code_cycle
# ---------------------------------------------------------------------------

def test_locked_rate_returns_none_when_no_payments(client):
    """Returns None when there are no payments for the cycle."""
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    result = _get_locked_rent_amount_for_join_code_cycle("NOPAY", coverage)
    assert result is None


def test_locked_rate_uses_first_payer_base(client):
    """Returns the first valid payer's base (not MAX) when multiple students paid."""
    admin = _make_admin("lr1")
    join_code = "LOCKR1"
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)

    student_a = _make_student("lra")
    student_b = _make_student("lrb")

    # Student A pays $100 first (original rate, on time)
    _add_payment_with_txn(
        student_a, join_code,
        amount_paid=Decimal("100.00"), late_fee=Decimal("0.00"),
        payment_date=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
        coverage_due_date=coverage, admin_id=admin.id,
    )
    # Student B pays $150 later (after rate raise — higher base)
    _add_payment_with_txn(
        student_b, join_code,
        amount_paid=Decimal("150.00"), late_fee=Decimal("0.00"),
        payment_date=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        coverage_due_date=coverage, admin_id=admin.id,
    )
    db.session.commit()

    locked = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage)
    # Must be the FIRST payer's base ($100), not the maximum ($150)
    assert locked == Decimal("100.00")


def test_locked_rate_ignores_void_transactions(client):
    """Skips payments whose backing transaction is voided."""
    admin = _make_admin("lrvoid")
    join_code = "LOCKVOID"
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)

    student_a = _make_student("lrv_a")
    student_b = _make_student("lrv_b")

    # Voided first payment — should be skipped
    _add_payment_with_txn(
        student_a, join_code,
        amount_paid=Decimal("80.00"), late_fee=Decimal("0.00"),
        payment_date=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
        coverage_due_date=coverage, admin_id=admin.id,
        is_void=True,
    )
    # Valid second payment at $120
    _add_payment_with_txn(
        student_b, join_code,
        amount_paid=Decimal("120.00"), late_fee=Decimal("0.00"),
        payment_date=datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc),
        coverage_due_date=coverage, admin_id=admin.id,
    )
    db.session.commit()

    locked = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage)
    # Voided $80 skipped; first valid payer is $120
    assert locked == Decimal("120.00")


def test_locked_rate_extracts_base_excluding_late_fee(client):
    """Base amount is amount_paid minus late_fee_charged."""
    admin = _make_admin("lrfee")
    join_code = "LOCKFEE"
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)

    student = _make_student("lrfee_s")
    # Paid $110 = $100 base + $10 late fee
    _add_payment_with_txn(
        student, join_code,
        amount_paid=Decimal("110.00"), late_fee=Decimal("10.00"),
        payment_date=datetime(2026, 3, 6, 8, 0, tzinfo=timezone.utc),
        coverage_due_date=coverage, admin_id=admin.id,
    )
    db.session.commit()

    locked = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage)
    assert locked == Decimal("100.00")

# ---------------------------------------------------------------------------
# Tests: _has_active_rent_waiver and _is_student_coverage_period_paid
# ---------------------------------------------------------------------------

def test_waiver_marks_period_as_paid(client):
    """A student with an active waiver is considered paid for that coverage period."""
    admin = _make_admin("wv1")
    join_code = "WAIV1"
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    settings = _make_rent_settings(admin.id)
    student = _make_student("wv1_s")
    db.session.commit()

    # Waiver covers the coverage due date
    waiver = RentWaiver(
        student_id=student.id,
        join_code=join_code,
        waiver_start_date=coverage - timedelta(days=1),
        waiver_end_date=coverage + timedelta(days=5),
        periods_count=1,
        created_by_admin_id=admin.id,
    )
    db.session.add(waiver)
    db.session.commit()

    assert _has_active_rent_waiver(student.id, join_code, coverage) is True

    is_paid = _is_student_coverage_period_paid(
        settings, student.id, "A", join_code, coverage
    )
    assert is_paid is True


def test_waiver_does_not_apply_after_end_date(client):
    """An expired waiver does not count as active for a later coverage period."""
    admin = _make_admin("wv2")
    join_code = "WAIV2"
    coverage = datetime(2026, 5, 1, tzinfo=timezone.utc)
    settings = _make_rent_settings(admin.id)
    student = _make_student("wv2_s")
    db.session.commit()

    # Waiver only covers March, not May
    waiver = RentWaiver(
        student_id=student.id,
        join_code=join_code,
        waiver_start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        waiver_end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
        periods_count=1,
        created_by_admin_id=admin.id,
    )
    db.session.add(waiver)
    db.session.commit()

    assert _has_active_rent_waiver(student.id, join_code, coverage) is False


def test_waiver_scoped_to_join_code(client):
    """Waiver for one join_code does not apply to a different join_code."""
    admin = _make_admin("wv3")
    join_code_a = "WAIV3A"
    join_code_b = "WAIV3B"
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    settings = _make_rent_settings(admin.id)
    student = _make_student("wv3_s")
    db.session.commit()

    waiver = RentWaiver(
        student_id=student.id,
        join_code=join_code_a,
        waiver_start_date=coverage - timedelta(days=1),
        waiver_end_date=coverage + timedelta(days=5),
        periods_count=1,
        created_by_admin_id=admin.id,
    )
    db.session.add(waiver)
    db.session.commit()

    # Waiver is for join_code_a, not join_code_b
    assert _has_active_rent_waiver(student.id, join_code_b, coverage) is False


# ---------------------------------------------------------------------------
# Tests: admin reverse_cycle_penalties route
# ---------------------------------------------------------------------------

def _login_admin(client, admin_id, join_code):
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['current_join_code'] = join_code
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


def test_reverse_cycle_penalties_refunds_misapplied_late_fee(client, app):
    """Students who paid the locked rate on time get their late fees refunded."""
    with app.app_context():
        admin = _make_admin("rcp1")
        join_code = "RCP001"
        coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
        settings = _make_rent_settings(admin.id, amount=Decimal("150.00"))
        settings.first_rent_due_date = coverage
        _make_teacher_block(admin.id, "A", join_code)
        db.session.flush()

        # First payer paid $100 on time (original rate before it was raised to $150)
        first_student = _make_student("rcp1_first")
        _add_payment_with_txn(
            first_student, join_code,
            amount_paid=Decimal("100.00"), late_fee=Decimal("0.00"),
            payment_date=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            coverage_due_date=coverage, admin_id=admin.id,
        )

        # Second student paid $100 on time but was charged $10 late fee because
        # the system thought they owed $150 (rate was raised after first payment).
        second_student = _make_student("rcp1_second")
        second_pmt, _ = _add_payment_with_txn(
            second_student, join_code,
            amount_paid=Decimal("110.00"), late_fee=Decimal("10.00"),
            payment_date=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
            coverage_due_date=coverage, admin_id=admin.id,
        )
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        response = client.post(
            '/admin/rent/reverse-cycle-penalties',
            data={'settings_block': 'A'},
        )
        assert response.status_code == 302

        # Second student's RentPayment should now have late_fee_charged = 0
        db.session.refresh(second_pmt)
        assert second_pmt.late_fee_charged == Decimal("0.00")
        assert second_pmt.was_late is False

        # A refund transaction of $10 should exist for the second student
        refund_txn = Transaction.query.filter(
            Transaction.student_id == second_student.id,
            Transaction.join_code == join_code,
            Transaction.type == 'Rent Late Fee Reversal',
        ).first()
        assert refund_txn is not None
        assert refund_txn.amount == Decimal("10.00")


def test_reverse_cycle_penalties_keeps_genuine_late_fees(client, app):
    """Students who paid after the grace period keep their late fees."""
    with app.app_context():
        admin = _make_admin("rcp2")
        join_code = "RCP002"
        coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
        settings = _make_rent_settings(admin.id, amount=Decimal("100.00"))
        settings.first_rent_due_date = coverage
        _make_teacher_block(admin.id, "A", join_code)
        db.session.flush()

        # First student pays $100 on time → locked rate = $100
        first = _make_student("rcp2_first")
        _add_payment_with_txn(
            first, join_code,
            amount_paid=Decimal("100.00"), late_fee=Decimal("0.00"),
            payment_date=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            coverage_due_date=coverage, admin_id=admin.id,
        )

        # Second student pays LATE (after 3-day grace period) — legitimately late
        # Grace ends March 4; they paid March 6.
        second = _make_student("rcp2_second")
        late_pmt, _ = _add_payment_with_txn(
            second, join_code,
            amount_paid=Decimal("110.00"), late_fee=Decimal("10.00"),
            payment_date=datetime(2026, 3, 6, 9, 0, tzinfo=timezone.utc),
            coverage_due_date=coverage, admin_id=admin.id,
        )
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        response = client.post(
            '/admin/rent/reverse-cycle-penalties',
            data={'settings_block': 'A'},
        )
        assert response.status_code == 302

        # Second student's late fee should NOT be reversed (genuinely late)
        db.session.refresh(late_pmt)
        assert late_pmt.late_fee_charged == Decimal("10.00")
        assert late_pmt.was_late is True

        refund_txn = Transaction.query.filter(
            Transaction.student_id == second.id,
            Transaction.join_code == join_code,
            Transaction.type == 'Rent Late Fee Reversal',
        ).first()
        assert refund_txn is None

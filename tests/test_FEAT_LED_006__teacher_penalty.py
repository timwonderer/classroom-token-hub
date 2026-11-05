"""FEAT-LED-006: a teacher fines students (issue #1701, owner ruling 2026-11-04).

A fine is a Ledger penalty: a direct checking debit carrying the teacher's
reason, funded under SPEC-ECON-003 §4.5.1.1A, never an obligation and never a
fee. The teacher reviews each student's resolved outcome first; one submission
applies to every selected student or to none.
"""
from __future__ import annotations

import re
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.models import ObligationAssessment, Seat, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_balance_query_service import get_available_balances
from tests.helpers.canonical_classroom import _provision_roster_seat, login_student, login_teacher, provision_classroom
from tests.helpers.ledger import record_ledger_fixture

REASON = "Talking during the test"


def _classroom(client, app, key="chemistry_p1"):
    classroom = provision_classroom(key)
    login_teacher(client, classroom)
    return classroom


def _fund(classroom, seat_id, *, checking="0.00", savings="0.00", key):
    with FEATContext("FEAT-LED-001", idempotency_key=f"fine:seed:{key}"):
        for account, amount in (("checking", checking), ("savings", savings)):
            if Decimal(amount):
                record_ledger_fixture(seat_id=seat_id, class_id=classroom.class_id,
                                      amount=Decimal(amount), account_type=account)
    db.session.commit()


def _evolve(classroom, updates, key):
    teacher = db.session.get(Seat, classroom.teacher_seat_id)
    assert execute_evolve_economic_engine(
        canonical_context=CanonicalContext(
            user_id=teacher.user_id, class_id=classroom.class_id,
            seat_id=teacher.id, actor_role="teacher",
        ),
        class_id=classroom.class_id,
        updates=updates,
        feature_list=["banking"], idempotency_key=f"fine:evolve:{key}",
    ).success


def _protection(classroom, enabled, key):
    _evolve(classroom, {"overdraft_protection_enabled": enabled}, key)


def _review(client, public_ids, amount="4.00", reason=REASON):
    return client.post("/admin/payroll/fine/review", data={
        "student_ids": public_ids, "amount": amount, "reason": reason,
    })


def _confirm_fields(html):
    return {
        name: re.search(rf'name="{name}" value="([^"]*)"', html).group(1)
        for name in ("submission_token", "preview_digest")
    }


def _apply(client, public_ids, fields, amount="4.00", reason=REASON):
    return client.post("/admin/payroll/fine", data={
        "student_ids": public_ids, "amount": amount, "reason": reason, **fields,
    })


def _fine(client, public_ids, **kwargs):
    review = _review(client, public_ids, **kwargs)
    assert review.status_code == 200
    return _apply(client, public_ids, _confirm_fields(review.get_data(as_text=True)), **kwargs)


def _penalties(class_id, seat_id=None):
    query = Transaction.query.filter_by(class_id=class_id, type="penalty")
    if seat_id is not None:
        query = query.filter_by(seat_id=seat_id)
    return query.all()


def test_FEAT_LED_006__review_shows_band_and_outcome_and_writes_nothing(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _evolve(classroom, {"expected_weekly_hours": Decimal("5")}, "review-cwi")
        _fund(classroom, student.seat_id, checking="10.00", key="review")

    response = _review(client, [student.seat.public_id])

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f"Fine: {REASON}" in html
    assert "Recommended fine for this class" in html
    assert "$10.00" in html and "$6.00" in html
    with app.app_context():
        assert _penalties(classroom.class_id) == []


def test_FEAT_LED_006__fine_posts_a_penalty_the_student_sees(client, app):
    """Regression for #1701: a teacher could not fine a student at all."""
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _fund(classroom, student.seat_id, checking="10.00", key="happy")

    response = _fine(client, [student.seat.public_id])

    assert response.status_code == 302
    with app.app_context():
        (row,) = _penalties(classroom.class_id, student.seat_id)
        assert row.amount == Decimal("-4.00")
        assert row.description == f"Fine: {REASON}"
        assert row.account_type == "checking"
        assert row.actor_seat_id == classroom.teacher_seat_id
        assert getattr(row.mechanism, "value", row.mechanism) == "teacher"
        assert get_available_balances(student.seat_id, classroom.class_id) == (
            Decimal("6.00"), Decimal("0.00"),
        )
        assert ObligationAssessment.query.filter_by(seat_id=student.seat_id).count() == 0

    login_student(client, student)
    assert f"Fine: {REASON}" in client.get("/student/dashboard").get_data(as_text=True)


def test_FEAT_LED_006__fine_may_take_checking_below_zero_and_adds_no_fee(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _protection(classroom, True, "below-zero")
        _fund(classroom, student.seat_id, checking="2.00", savings="3.00", key="below-zero")

    assert _fine(client, [student.seat.public_id], amount="10.00").status_code == 302

    with app.app_context():
        # Savings ($3) can't cover the whole $8 shortfall, so it is untouched.
        assert get_available_balances(student.seat_id, classroom.class_id) == (
            Decimal("-8.00"), Decimal("3.00"),
        )
        assert Transaction.query.filter_by(
            class_id=classroom.class_id, seat_id=student.seat_id, type="overdraft_fee",
        ).count() == 0


def test_FEAT_LED_006__protection_moves_the_whole_shortfall_from_savings(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _protection(classroom, True, "protected")
        _fund(classroom, student.seat_id, checking="2.00", savings="8.00", key="protected")

    review = _review(client, [student.seat.public_id], amount="10.00")
    assert "$8.00" in review.get_data(as_text=True)  # shown as moved from savings
    _apply(client, [student.seat.public_id], _confirm_fields(review.get_data(as_text=True)), amount="10.00")

    with app.app_context():
        assert get_available_balances(student.seat_id, classroom.class_id) == (
            Decimal("0.00"), Decimal("0.00"),
        )


def test_FEAT_LED_006__out_of_band_amount_warns_but_applies(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _evolve(classroom, {"expected_weekly_hours": Decimal("5")}, "band-cwi")

    review = _review(client, [student.seat.public_id], amount="0.01")

    assert "Outside the recommended range" in review.get_data(as_text=True)
    _apply(client, [student.seat.public_id], _confirm_fields(review.get_data(as_text=True)), amount="0.01")
    with app.app_context():
        assert len(_penalties(classroom.class_id, student.seat_id)) == 1


def test_FEAT_LED_006__a_batch_with_an_unclaimed_seat_applies_to_nobody(client, app):
    classroom = _classroom(client, app)
    with app.app_context():
        with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"fine:unclaimed:{classroom.class_id}"):
            unclaimed = _provision_roster_seat(
                classroom.class_id, {"first_name": "Empty", "last_name": "Desk", "dedupe_code": None},
            )
        db.session.commit()
        public_ids = [s.seat.public_id for s in classroom.students[:2]] + [unclaimed.public_id]

    response = _fine(client, public_ids)

    assert response.status_code == 302
    with app.app_context():
        assert _penalties(classroom.class_id) == []


def test_FEAT_LED_006__double_submitted_confirmation_fines_once(client, app):
    classroom = _classroom(client, app)
    public_ids = [s.seat.public_id for s in classroom.students[:2]]
    review = _review(client, public_ids)
    fields = _confirm_fields(review.get_data(as_text=True))

    assert _apply(client, public_ids, fields).status_code == 302
    assert _apply(client, public_ids, fields).status_code == 302

    with app.app_context():
        for student in classroom.students[:2]:
            assert len(_penalties(classroom.class_id, student.seat_id)) == 1


def test_FEAT_LED_006__a_second_deliberate_identical_fine_applies(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]

    _fine(client, [student.seat.public_id])
    _fine(client, [student.seat.public_id])

    with app.app_context():
        assert len(_penalties(classroom.class_id, student.seat_id)) == 2


def test_FEAT_LED_006__a_balance_change_after_review_applies_nothing(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    review = _review(client, [student.seat.public_id])
    fields = _confirm_fields(review.get_data(as_text=True))
    with app.app_context():
        _fund(classroom, student.seat_id, checking="5.00", key="moved")

    response = _apply(client, [student.seat.public_id], fields)

    assert response.status_code == 200
    assert "Balances changed" in response.get_data(as_text=True)
    with app.app_context():
        assert _penalties(classroom.class_id) == []


def test_FEAT_LED_006__a_student_in_another_class_is_never_fined(client, app):
    other = _classroom(client, app, key="ap_csp_p3")
    classroom = _classroom(client, app)  # active class: chemistry_p1, same teacher
    mixed = [classroom.students[0].seat.public_id, other.students[0].seat.public_id]

    review = _review(client, mixed)
    response = _apply(client, mixed, {"submission_token": "t" * 32, "preview_digest": "x"})

    assert review.status_code == 302 and response.status_code == 302
    with app.app_context():
        assert _penalties(classroom.class_id) == []
        assert _penalties(other.class_id) == []


def test_FEAT_LED_006__a_student_cannot_fine(client, app):
    classroom = provision_classroom("chemistry_p1")
    student = classroom.students[0]
    login_student(client, student)

    review = _review(client, [classroom.students[1].seat.public_id])
    response = _apply(client, [classroom.students[1].seat.public_id],
                      {"submission_token": "t" * 32, "preview_digest": "x"})

    assert review.status_code in (302, 403) and response.status_code in (302, 403)
    with app.app_context():
        assert _penalties(classroom.class_id) == []


def test_FEAT_LED_006__a_reversal_restores_money_and_keeps_both_entries(client, app):
    classroom = _classroom(client, app)
    student = classroom.students[0]
    with app.app_context():
        _fund(classroom, student.seat_id, checking="10.00", key="reverse")
    _fine(client, [student.seat.public_id])
    with app.app_context():
        (penalty,) = _penalties(classroom.class_id, student.seat_id)
        penalty_id = penalty.id

    assert client.post(f"/admin/void-transaction/{penalty_id}").status_code == 302

    with app.app_context():
        penalty = db.session.get(Transaction, penalty_id)
        assert penalty.amount == Decimal("-4.00") and penalty.description == f"Fine: {REASON}"
        (reversal,) = Transaction.query.filter_by(original_transaction_id=penalty_id).all()
        assert reversal.amount == Decimal("4.00")
        assert get_available_balances(student.seat_id, classroom.class_id)[0] == Decimal("10.00")

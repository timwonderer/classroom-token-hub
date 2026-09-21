"""Payroll reversal is reachable, and it compensates rather than deletes.

Finding 28. DOM-PROD-001 §185 forbids correcting payroll by mutating attendance
history and §187 names reversal as the remedy instead. That remedy had no
surface: ``record_payroll_reversal`` appeared exactly once in the repository —
its own definition — with no route, service or test reaching it, while the
payroll template already rendered a REVERSAL badge for rows nothing could
produce. The read side anticipated what the write side never made.

Taken with finding 27 (attendance immutability now enforced in the database),
these close the operator decision of 2026-09-21: attendance is never corrected,
and reversing the payroll is the only remedy — so that remedy has to work.
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import PayrollEvent, Transaction
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _manual_credit(client, classroom, amount="25.00"):
    """Create a payroll lineage through the real admin surface."""
    student = classroom.students[0]
    # student_ids carries the seat's PUBLIC id, which is what the picker submits
    # and what _resolve_student_detail_seat resolves; a raw seat id is silently
    # skipped by the class-scope filter and applies to nobody.
    response = client.post(
        "/admin/payroll/manual-payment",
        data={
            "student_ids": student.seat.public_id,
            "amount": amount,
            "description": "Seed credit",
            "payment_type": "deposit",
        },
        follow_redirects=False,
    )
    return response, student


def _events(class_id, **kw):
    return PayrollEvent.query.filter_by(class_id=class_id, **kw).all()


def test_a_payroll_entry_can_be_reversed_from_the_payroll_page(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="payroll")

    _manual_credit(client, classroom)

    with app.app_context():
        original = _events(classroom.class_id, payroll_event_type="manual_credit")
        assert len(original) == 1, "seed credit did not produce a payroll event"
        event_id = original[0].id
        correlation_id = original[0].correlation_id

    response = client.post(f"/admin/payroll/event/{event_id}/reverse", data={"reason": "wrong attendance"})
    assert response.status_code == 302, response.data

    with app.app_context():
        reversals = _events(classroom.class_id, payroll_event_type="reversal")
        assert len(reversals) == 1, "no reversal payroll event was written"
        reversal = reversals[0]

        # A compensating entry, not a deletion: the original survives.
        assert db.session.get(PayrollEvent, event_id) is not None
        # The reversal carries the lineage of what it compensates.
        assert reversal.correlation_id == correlation_id
        assert reversal.target_seat_id == original[0].target_seat_id

        # The money moved with the record, in the opposite direction.
        txns = Transaction.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=reversal.target_seat_id,
        ).all()
        amounts = [Decimal(t.amount) for t in txns]
        assert any(a > 0 for a in amounts), amounts
        assert any(a < 0 for a in amounts), "no counter-entry was posted"
        assert sum(amounts) == Decimal("0.00"), f"reversal did not net to zero: {amounts}"


def test_an_entry_cannot_be_reversed_twice(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="payroll")
    _manual_credit(client, classroom)

    with app.app_context():
        event_id = _events(classroom.class_id, payroll_event_type="manual_credit")[0].id

    client.post(f"/admin/payroll/event/{event_id}/reverse")
    client.post(f"/admin/payroll/event/{event_id}/reverse")

    with app.app_context():
        assert len(_events(classroom.class_id, payroll_event_type="reversal")) == 1, (
            "a second reversal was written; the money would be returned twice"
        )


def test_a_reversal_cannot_itself_be_reversed(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="payroll")
    _manual_credit(client, classroom)

    with app.app_context():
        event_id = _events(classroom.class_id, payroll_event_type="manual_credit")[0].id
    client.post(f"/admin/payroll/event/{event_id}/reverse")

    with app.app_context():
        reversal_id = _events(classroom.class_id, payroll_event_type="reversal")[0].id

    client.post(f"/admin/payroll/event/{reversal_id}/reverse")

    with app.app_context():
        assert len(_events(classroom.class_id, payroll_event_type="reversal")) == 1


def test_reversal_is_scoped_to_the_active_class(app, client):
    """An event id from another class is not found, and nothing is written."""
    first = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=first.class_id, feature="payroll")
    _manual_credit(client, first)
    with app.app_context():
        foreign_event_id = _events(first.class_id, payroll_event_type="manual_credit")[0].id

    # A different teacher, a different class.
    second = initialize_as_teacher("ap_csp_p3", client, app)
    with app.app_context():
        enable_class_feature(class_id=second.class_id, feature="payroll")

    response = client.post(f"/admin/payroll/event/{foreign_event_id}/reverse")
    assert response.status_code == 404

    with app.app_context():
        assert _events(first.class_id, payroll_event_type="reversal") == []


def test_the_payroll_page_offers_the_control(app, client):
    """The remedy must be reachable by a teacher, not only by a test."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="payroll")
    _manual_credit(client, classroom)

    page = client.get("/admin/payroll").data.decode()
    assert "reverse_payroll_event" in page or "/reverse" in page, (
        "the payroll page renders no control for the only documented remedy"
    )

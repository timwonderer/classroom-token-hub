"""Retrying a failed bulk manual credit must not re-pay the students it already

credited (audit F5). Each student's credit used to carry a submission-wide
nonce freshly randomized on every POST, so a retry after a mid-batch failure
(a lock timeout on student 15 of 30, say) minted brand new idempotency keys
for every student and paid the first 14 a second time. The nonce is now
derived from the submission's own content within a bounded time window, so an
immediate retry of the identical batch replays the same per-seat ledger
effect instead of creating a new one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.models import PayrollEvent, Transaction
from app.services.ledger_balance_query_service import get_available_balance
from tests.helpers.canonical_classroom import login_teacher, provision_classroom
from tests.helpers.class_domain import manual_payroll


def test_retrying_the_same_batch_does_not_double_pay(client, app):
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    login_teacher(client, classroom)
    seats = [s.seat for s in classroom.students[:3]]

    args = dict(
        student_ids=[s.public_id for s in seats],
        description="Weekly participation bonus", amount="5.00",
    )
    first = manual_payroll(client, **args)
    assert first.status_code == 302

    with app.app_context():
        for seat in seats:
            assert get_available_balance(seat.id, classroom.class_id, "checking") == Decimal("5.00")

    # Simulate the exact retry a teacher performs after "Please try again":
    # the same form, submitted again, immediately.
    second = manual_payroll(client, **args)
    assert second.status_code == 302

    with app.app_context():
        for seat in seats:
            assert get_available_balance(seat.id, classroom.class_id, "checking") == Decimal("5.00"), (
                "a same-batch retry must not pay the student a second time"
            )
            assert Transaction.query.filter_by(
                class_id=classroom.class_id, seat_id=seat.id, type="manual_payment",
            ).count() == 1
            assert PayrollEvent.query.filter_by(
                class_id=classroom.class_id, target_seat_id=seat.id, payroll_event_type="manual_credit",
            ).count() == 1


def test_a_different_batch_is_not_treated_as_a_replay(client, app):
    """Control: changing the content (here, the amount) must still pay."""
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    login_teacher(client, classroom)
    seat = classroom.students[0].seat

    first = manual_payroll(client, student_ids=[seat.public_id], description="Bonus", amount="5.00")
    assert first.status_code == 302
    second = manual_payroll(client, student_ids=[seat.public_id], description="Bonus", amount="7.00")
    assert second.status_code == 302

    with app.app_context():
        assert get_available_balance(seat.id, classroom.class_id, "checking") == Decimal("12.00")
        assert Transaction.query.filter_by(
            class_id=classroom.class_id, seat_id=seat.id, type="manual_payment",
        ).count() == 2


def test_a_batch_retry_beyond_the_replay_window_pays_again(client, app, monkeypatch):
    """Control: the replay guard is a bounded time window, not a permanent one
    — the same weekly bonus, submitted again next week, must still pay."""
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    login_teacher(client, classroom)
    seat = classroom.students[0].seat
    args = dict(student_ids=[seat.public_id], description="Weekly bonus", amount="5.00")

    import app.routes.admin as admin_module
    from app.utils.canonical_temporal_resolver import utc_now

    base = utc_now()
    monkeypatch.setattr("app.utils.canonical_temporal_resolver.utc_now", lambda: base)
    assert manual_payroll(client, **args).status_code == 302

    from datetime import timedelta
    monkeypatch.setattr("app.utils.canonical_temporal_resolver.utc_now", lambda: base + timedelta(days=7))
    # A week later the teacher's session has expired, as it would in use: sign in again.
    login_teacher(client, classroom)
    assert manual_payroll(client, **args).status_code == 302

    with app.app_context():
        assert get_available_balance(seat.id, classroom.class_id, "checking") == Decimal("10.00")


def test_a_boundary_crossing_retry_does_not_double_pay(client, app, monkeypatch):
    """Audit F5 follow-up (Codex review on PR #1536): the replay nonce is
    bucketed to a 5-minute server-time window, so a batch that starts just
    before a bucket rolls over, credits some seats, and is retried a few
    seconds later — now in the next bucket — used to compute a different
    nonce and lose all memory of the seats it already paid, double-paying
    them. "Already applied" must also be checked against the immediately
    preceding bucket, not only the current one."""
    classroom = provision_classroom("chemistry_p1", with_payroll_settings=False)
    login_teacher(client, classroom)
    seats = [s.seat for s in classroom.students[:3]]
    description = "Weekly participation bonus"
    amount = "5.00"
    args = dict(student_ids=[s.public_id for s in seats], description=description, amount=amount)

    import app.routes.admin as admin_module

    now = datetime.now(timezone.utc)
    bucket_start = (int(now.timestamp()) // 300) * 300
    just_before_boundary = datetime.fromtimestamp(bucket_start + 298, tz=timezone.utc)
    just_after_boundary = just_before_boundary + timedelta(seconds=4)
    assert int(just_before_boundary.timestamp() // 300) != int(just_after_boundary.timestamp() // 300), (
        "test setup must straddle a real 5-minute bucket boundary"
    )

    # The mid-batch failure (audit F5's original scenario): the *same* full
    # selection is submitted both times — a real retry reselects nothing —
    # but the third seat's credit raises (a lock timeout, a dropped
    # connection) after the first two have already committed in their own
    # FEAT transaction, exactly as the route's docstring describes.
    real_record_payroll_event = admin_module.record_payroll_event
    calls = {"n": 0}

    def _flaky_record_payroll_event(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated mid-batch failure (audit F5)")
        return real_record_payroll_event(*a, **kw)

    monkeypatch.setattr("app.utils.canonical_temporal_resolver.utc_now", lambda: just_before_boundary)
    monkeypatch.setattr(admin_module, "record_payroll_event", _flaky_record_payroll_event)
    first = manual_payroll(client, **args)
    assert first.status_code == 302  # the route's except-block still redirects

    # The retry: the identical full batch, submitted a few seconds later —
    # now past the bucket boundary — with the failure no longer reproducing.
    monkeypatch.setattr(admin_module, "record_payroll_event", real_record_payroll_event)
    monkeypatch.setattr("app.utils.canonical_temporal_resolver.utc_now", lambda: just_after_boundary)
    second = manual_payroll(client, **args)
    assert second.status_code == 302

    with app.app_context():
        for seat in seats:
            assert get_available_balance(seat.id, classroom.class_id, "checking") == Decimal("5.00"), (
                "a retry that crosses a bucket boundary must not double-pay "
                "the seats already credited before the rollover"
            )
            assert PayrollEvent.query.filter_by(
                class_id=classroom.class_id, target_seat_id=seat.id,
                payroll_event_type="manual_credit",
            ).count() == 1

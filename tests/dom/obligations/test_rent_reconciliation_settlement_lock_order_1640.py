"""#1640 regression: rent reconciliation (FEAT-OBL-002) must never invert ledger
settlement's (FEAT-LED-003) lock order.

Settlement locks one context's seat, then its class, in that order
(INV-LED-015, ``app/services/ledger_settlement_service.py::settle_balances``).
Before this fix, reconciliation processed its whole class roster's
``ObligationAssessment`` inserts one seat at a time, in ascending seat-ID
order: the very FIRST insert implicitly pinned a ``FOR KEY SHARE`` lock on the
class row (``ObligationAssessment.class_id`` is a foreign key), well before a
LATER roster seat was ever touched. A settlement run already holding that
later seat ``FOR UPDATE``, and waiting on the class row reconciliation now
holds, formed exactly the circular wait Postgres's deadlock detector reported
in production (#1640):

    settlement: holds seat(N)         -> waits on class(Y)
    reconciliation: holds class(Y)    -> waits on seat(N)

The fix (DOM-LED-001 §VII's multi-seat rule, the paragraph following
INV-LED-017) makes reconciliation lock its WHOLE roster, ascending by seat ID,
via ``lock_ledger_seats``, before any class-scoped work — the same
"seats first, then class" order settlement itself uses. Neither side can then
hold a later resource while waiting on an earlier one, so the cycle above is
structurally impossible.

This test reproduces the real race with two genuine concurrent transactions
and real Postgres locks (not a mock): it asserts reconciliation blocks on the
contended SEAT rather than ever acquiring the class row while settlement
waits on it, and that both sides complete without Postgres reporting a
deadlock. Reverting the ``lock_ledger_seats`` call this fix adds to
``reconcile_rent`` makes this test hang until Postgres's deadlock detector
kills one side with ``DeadlockDetected`` (Pattern 7: confirmed by running this
test against the pre-fix code before trusting it as a regression test).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Event
from time import monotonic

from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.models import ClassEconomy, Seat
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize

_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _setup_rent_class(classroom):
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    customize_rent_settings(
        classroom.class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE,
        grace_period_days=3,
        rent_amount=Decimal("50.00"),
        satisfaction_benefits=[],
        late_penalty_amount=Decimal("0.00"),
    )


def test_rent_reconciliation_does_not_deadlock_ledger_settlement(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom)
        class_id = classroom.class_id
        seat_ids = sorted(student.seat.id for student in classroom.students)
    # chemistry_p1 provisions 4 claimed student seats (tests/helpers/canonical_identities.py):
    # a roster of 1 can never show a class-first/seat-first ordering conflict.
    assert len(seat_ids) >= 2
    contended_seat_id = seat_ids[-1]

    held, attempted, release = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def settlement_scope():
        with app.app_context():
            try:
                with FEATContext("FEAT-LED-003", idempotency_key="deadlock-1640-settlement"):
                    pids["settlement"] = db.session.execute(
                        text("SELECT pg_backend_pid()")
                    ).scalar_one()
                    # Mirrors settle_balances' own lock order (INV-LED-015): the
                    # seat anchor is acquired first, and held through the window
                    # this test uses to let reconciliation contend for it.
                    Seat.query.filter_by(
                        id=contended_seat_id, class_id=class_id
                    ).with_for_update().one()
                    held.set()
                    assert release.wait(10)
                    ClassEconomy.query.filter_by(class_id=class_id).with_for_update().one()
                return "accepted"
            finally:
                db.session.remove()

    def reconciliation_scope():
        with app.app_context():
            try:
                pids["reconciliation"] = db.session.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                attempted.set()
                execute_reconcile_rent(class_id, idempotency_key="deadlock-1640-reconcile")
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        settlement = pool.submit(settlement_scope)
        try:
            assert held.wait(10)
            reconciliation = pool.submit(reconciliation_scope)
            assert attempted.wait(10)

            # Reconciliation must be the one waiting — blocked specifically on
            # the seat settlement already holds — and never itself hold the
            # class row while settlement is waiting to acquire it. If
            # reconciliation instead locked the class first (the pre-fix
            # behavior), pg_blocking_pids would never report it waiting on
            # settlement's seat lock, and the SELECT ... FOR UPDATE NOWAIT
            # below would fail with "could not obtain lock" instead of
            # succeeding.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["reconciliation"]}
                ).scalar_one()
                if pids["settlement"] in blockers:
                    break
                assert monotonic() < deadline, (
                    "Reconciliation never blocked on the seat settlement holds; "
                    "it may have locked the class first instead (the #1640 bug)."
                )
                Event().wait(.01)

            # The class row is still free while reconciliation waits on the
            # seat: settlement has not even attempted it yet. A third
            # connection (NOWAIT, so a would-be contender raises instead of
            # joining the queue) proves nothing already holds or queues on it.
            with db.engine.begin() as connection:
                connection.execute(
                    text("SELECT class_id FROM classes WHERE class_id=:class_id FOR UPDATE NOWAIT"),
                    {"class_id": class_id},
                ).one()
        finally:
            release.set()
        assert settlement.result(timeout=15) == "accepted"
        assert reconciliation.result(timeout=15) == "accepted"

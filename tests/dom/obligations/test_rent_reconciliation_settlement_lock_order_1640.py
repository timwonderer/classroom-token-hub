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
from app.feats.identity_feat import bind_authenticated_student_to_class, unclaim_student_seat
from app.feats.prod import record_payroll_event
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.hash_utils import hash_claim_name
from app.models import ClassEconomy, Seat
from app.services.attendance_service import close_due_attendance_intervals
from app.services.classroom_setup import create_roster_student_seat
from app.services.context_resolver import CanonicalContext
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


def test_unclaim_student_seat_does_not_deadlock_rent_reconciliation(app):
    """A teacher unclaiming a roster seat, concurrent with rent reconciliation,
    must never deadlock (#1640-adjacent, found in review of the fix above).

    ``unclaim_student_seat`` (FEAT-IDEN-006) used to lock the class row before
    the student seat — the opposite of this PR's new reconciliation roster
    lock (seat(s), then class, per DOM-LED-001 §VII). Unclaim holding the
    class while waiting on a seat reconciliation's roster lock already holds,
    while reconciliation holds that seat and waits on the class via its
    ``BillCycle`` insert, is the same circular wait #1640 closed — with
    unclaim as the other side instead of ledger settlement. The fix brings
    unclaim to the same seat-then-class order.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom)
        class_id = classroom.class_id
        student = classroom.students[-1]
        seat_id = student.seat.id
        expected_generation = student.seat.claim_generation
        first_name, last_name = student.first_name, student.last_name
        teacher_ctx = CanonicalContext(
            user_id=classroom.teacher_user.id, class_id=class_id,
            seat_id=classroom.teacher_seat.id, actor_role="teacher",
        )

    held, release, attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def holder_scope():
        # Stands in for a concurrent transaction already holding this roster
        # seat — the same role rent reconciliation's own ascending roster lock
        # plays, already proven correct by the sibling test above. A bare
        # connection of its own (never db.session) is used because neither
        # production function being tested here has a pause point to
        # synchronize against: this is the same reason the sibling test above
        # mirrors settlement's lock manually instead of invoking
        # settle_balances. (An earlier version of this test held the seat on
        # a bare connection and then released it BEFORE calling the real
        # unclaim_student_seat() — Codex's directed review on this PR caught
        # that the assertion window closed before unclaim's real call even
        # started, so it proved nothing about unclaim's own lock order. This
        # version keeps the hold alive through the entire measurement window,
        # with the REAL unclaim_student_seat() as the contender.)
        with app.app_context():
            try:
                with db.engine.connect() as holder_conn:
                    with holder_conn.begin():
                        pids["holder"] = holder_conn.execute(
                            text("SELECT pg_backend_pid()")
                        ).scalar_one()
                        holder_conn.execute(
                            text(
                                "SELECT id FROM seats WHERE id=:id AND "
                                "class_id=:class_id FOR UPDATE"
                            ),
                            {"id": seat_id, "class_id": class_id},
                        )
                        held.set()
                        assert release.wait(10)
                return "accepted"
            finally:
                db.session.remove()

    def unclaim_scope():
        with app.app_context():
            try:
                pids["unclaim"] = db.session.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                attempted.set()
                unclaim_student_seat(
                    canonical_context=teacher_ctx, seat_id=seat_id,
                    expected_generation=expected_generation,
                    first_name=first_name, last_name=last_name,
                    correlation_id="deadlock-1640-unclaim",
                    idempotency_key="test:deadlock-1640:unclaim-inner",
                )
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(holder_scope)
        try:
            assert held.wait(10)
            unclaim = pool.submit(unclaim_scope)
            assert attempted.wait(10)

            # Unclaim must be the one waiting, blocked on the seat the holder
            # already holds — and, while it waits, must NOT already hold the
            # class row (the pre-fix behavior: class locked first, then
            # blocked trying to lock the seat). A third connection with
            # NOWAIT proves the class row is genuinely free, not queued
            # behind unclaim.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["unclaim"]}
                ).scalar_one()
                if pids.get("holder") in blockers:
                    break
                assert monotonic() < deadline, (
                    "unclaim_student_seat never blocked on the seat the "
                    "holder holds; the two paths may no longer share a lock "
                    "order."
                )
                Event().wait(.01)

            with db.engine.begin() as connection:
                connection.execute(
                    text("SELECT class_id FROM classes WHERE class_id=:class_id FOR UPDATE NOWAIT"),
                    {"class_id": class_id},
                ).one()
        finally:
            release.set()
        assert holder.result(timeout=15) == "accepted"
        assert unclaim.result(timeout=15) == "accepted"


def test_bind_authenticated_student_to_class_does_not_deadlock_settlement(app):
    """An authenticated student joining a second class, concurrent with ledger
    settlement holding the unclaimed seat they are about to claim, must never
    deadlock (#1640-adjacent, Codex finding on PR #1832's own review).

    ``bind_authenticated_student_to_class`` (FEAT-IDEN-005) locked the class
    row (``ClassEconomy.query...with_for_update()``) before locking the join
    code's unclaimed seats -- the opposite of settlement's seat-then-class
    order (INV-LED-015). Rent reconciliation's own fix above (#1640) widened
    its lock set to every seat in the class, claimed or not, which means an
    unclaimed seat this bind path is about to lock can now also be a seat a
    concurrent reconciliation (or, as tested here, settlement -- the simpler
    production function to mirror directly) sweep already holds. The fix
    brings this bind path to the same seat(s)-then-class order.
    """
    source = initialize("chemistry_p1", app)
    target = initialize("ap_csp_p3", app)
    first_name, last_name = "Unclaimed", "Joiner"
    with app.app_context():
        class_id = target.class_id
        principal_user_id = source.students[0].user.id
        join_code = target.join_code
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="bind-deadlock-1640:seed"):
            new_seat = create_roster_student_seat(
                class_id=class_id, first_name=first_name, last_name=last_name,
                claim_first_name_hash=hash_claim_name(first_name, class_id=class_id, field="first"),
                claim_last_name_hash=hash_claim_name(last_name, class_id=class_id, field="last"),
            )
        db.session.commit()
        seat_id = new_seat.id

    held, release, attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def settlement_scope():
        # Mirrors settle_balances' own lock order (INV-LED-015): the seat
        # anchor is acquired first, and held through the window this test
        # uses to let the bind path contend for it.
        with app.app_context():
            try:
                with FEATContext("FEAT-LED-003", idempotency_key="bind-deadlock-1640-settlement"):
                    pids["settlement"] = db.session.execute(
                        text("SELECT pg_backend_pid()")
                    ).scalar_one()
                    Seat.query.filter_by(id=seat_id, class_id=class_id).with_for_update().one()
                    held.set()
                    assert release.wait(10)
                    ClassEconomy.query.filter_by(class_id=class_id).with_for_update().one()
                return "accepted"
            finally:
                db.session.remove()

    def bind_scope():
        with app.app_context():
            try:
                pids["bind"] = db.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                attempted.set()
                result = bind_authenticated_student_to_class(
                    user_id=principal_user_id, join_code=join_code,
                    first_name=first_name, last_name=last_name,
                    correlation_id="corr-bind-deadlock-1640",
                    idempotency_key="bind-deadlock-1640-bind",
                )
                assert result.success, result
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        settlement = pool.submit(settlement_scope)
        try:
            assert held.wait(10)
            bind = pool.submit(bind_scope)
            assert attempted.wait(10)

            # The bind path must be the one waiting, blocked specifically on
            # the seat settlement already holds, and must NOT already hold the
            # class row while settlement waits to acquire it.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["bind"]}
                ).scalar_one()
                if pids["settlement"] in blockers:
                    break
                assert monotonic() < deadline, (
                    "bind_authenticated_student_to_class never blocked on the "
                    "seat settlement holds; it may have locked the class "
                    "first instead (the #1640-adjacent bug)."
                )
                Event().wait(.01)

            with db.engine.begin() as connection:
                connection.execute(
                    text("SELECT class_id FROM classes WHERE class_id=:class_id FOR UPDATE NOWAIT"),
                    {"class_id": class_id},
                ).one()
        finally:
            release.set()
        assert settlement.result(timeout=15) == "accepted"
        assert bind.result(timeout=15) == "accepted"


def test_teacher_manual_credit_does_not_deadlock_reconciliation_holding_teacher_seat(app):
    """A teacher issuing a manual credit, concurrent with rent reconciliation
    holding the teacher's own seat, must never deadlock (#1640-adjacent,
    Codex finding on PR #1832's own review).

    ``_record_payroll_event_impl`` (FEAT-PROD-003) locks the target seat and
    the class before inserting ``PayrollEvent`` -- but that insert carries a
    foreign key to ``actor_seat_id`` (the acting teacher's seat), so Postgres
    takes an implicit ``FOR KEY SHARE`` lock on it at insert time, well after
    the class is already locked. Rent reconciliation's #1640 fix widened its
    lock set to every seat in the class, the teacher's own seat included --
    which reconciliation never touched before -- so a reconciliation sweep
    that already holds the teacher's seat can now race a manual credit into
    the same circular wait #1640 closed elsewhere. The fix locks the actor
    seat together with the target seat, ascending, before the class.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom)
        class_id = classroom.class_id
        teacher_seat_id = classroom.teacher_seat.id
        student = classroom.students[0]
        target_seat_id = student.seat.id
        teacher_ctx = CanonicalContext(
            user_id=classroom.teacher_user.id, class_id=class_id,
            seat_id=teacher_seat_id, actor_role="teacher",
        )

    held, release, attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def holder_scope():
        # Stands in for reconciliation's own ascending roster lock already
        # holding the teacher's seat specifically (proven correct by the
        # sibling tests above; mirrored here with a bare connection since
        # neither production function has a pause point to synchronize
        # against).
        with app.app_context():
            try:
                with db.engine.connect() as holder_conn:
                    with holder_conn.begin():
                        pids["holder"] = holder_conn.execute(
                            text("SELECT pg_backend_pid()")
                        ).scalar_one()
                        holder_conn.execute(
                            text(
                                "SELECT id FROM seats WHERE id=:id AND "
                                "class_id=:class_id FOR UPDATE"
                            ),
                            {"id": teacher_seat_id, "class_id": class_id},
                        )
                        held.set()
                        assert release.wait(10)
                return "accepted"
            finally:
                db.session.remove()

    def credit_scope():
        with app.app_context():
            try:
                pids["credit"] = db.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                attempted.set()
                record_payroll_event(
                    ctx=teacher_ctx, target_seat_id=target_seat_id,
                    payroll_event_type="manual_credit", mechanism="TEACHER",
                    amount=Decimal("5.00"),
                    correlation_id="corr-payroll-deadlock-1640",
                    idempotency_key="payroll-deadlock-1640-credit",
                )
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(holder_scope)
        try:
            assert held.wait(10)
            credit = pool.submit(credit_scope)
            assert attempted.wait(10)

            # The manual credit must be the one waiting, blocked specifically
            # on the teacher seat the holder already holds, and must NOT
            # already hold the class row while the holder waits on it.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["credit"]}
                ).scalar_one()
                if pids["holder"] in blockers:
                    break
                assert monotonic() < deadline, (
                    "record_payroll_event never blocked on the teacher seat "
                    "the holder holds; it may have locked the class first "
                    "instead (the #1640-adjacent bug)."
                )
                Event().wait(.01)

            with db.engine.begin() as connection:
                connection.execute(
                    text("SELECT class_id FROM classes WHERE class_id=:class_id FOR UPDATE NOWAIT"),
                    {"class_id": class_id},
                ).one()
        finally:
            release.set()
        assert holder.result(timeout=15) == "accepted"
        assert credit.result(timeout=15) == "accepted"


def test_attendance_closure_does_not_deadlock_concurrent_payroll_on_teacher_seat(app):
    """A scheduled attendance closure, concurrent with a payroll run already
    holding the teacher's own seat, must never deadlock (#1640-adjacent,
    CodeRabbit finding on PR #1832's own review of commit cbd7b3b9).

    ``close_due_attendance_intervals`` (and ``close_due_hanging_hall_pass``,
    called from ``enforce_daily_limits_job``) append closures attributing them
    to the teacher's seat as ``actor_seat_id`` -- an implicit ``FOR KEY
    SHARE`` lock Postgres takes at insert time. Locking only the student
    target here, ahead of the explicit, ascending actor-and-target lock
    #1640's payroll fix now takes, left the two paths free to acquire the two
    seats in opposite orders whenever the teacher's seat id happened to be
    lower than the student's -- the same circular wait #1640 closed
    elsewhere, with a scheduled attendance closure as the other side instead
    of reconciliation. The fix locks both seats ascending here too, matching
    payroll's own order -- proven here by holding whichever of the two seats
    sorts first and asserting the closure blocks on exactly that one,
    regardless of whether it is the teacher's seat or the student's.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        class_id = classroom.class_id
        teacher_seat_id = classroom.teacher_seat.id
        target_seat_id = classroom.students[0].seat.id
        teacher_ctx = CanonicalContext(
            user_id=classroom.teacher_user.id, class_id=class_id,
            seat_id=teacher_seat_id, actor_role="teacher",
        )
    contended_seat_id = min(teacher_seat_id, target_seat_id)
    other_seat_id = max(teacher_seat_id, target_seat_id)

    held, release, attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def holder_scope():
        # Stands in for a concurrent payroll run that has already locked
        # whichever of the two seats sorts first (proven correct by the
        # sibling manual-credit test above; mirrored here with a bare
        # connection since the production function has no pause point of its
        # own to synchronize against).
        with app.app_context():
            try:
                with db.engine.connect() as holder_conn:
                    with holder_conn.begin():
                        pids["holder"] = holder_conn.execute(
                            text("SELECT pg_backend_pid()")
                        ).scalar_one()
                        holder_conn.execute(
                            text(
                                "SELECT id FROM seats WHERE id=:id AND "
                                "class_id=:class_id FOR UPDATE"
                            ),
                            {"id": contended_seat_id, "class_id": class_id},
                        )
                        held.set()
                        assert release.wait(10)
                return "accepted"
            finally:
                db.session.remove()

    def closure_scope():
        with app.app_context():
            try:
                with FEATContext("FEAT-PROD-001", idempotency_key="attendance-deadlock-1640-closure"):
                    # Read inside FEATContext.__enter__'s transaction, not
                    # before it: __enter__ rolls back any prior transaction
                    # before opening its own, which can hand the next
                    # statement a different pooled connection -- recording
                    # the PID too early binds it to a connection that never
                    # performs the closure's lock statements (CodeRabbit
                    # review on PR #1832, commit f0478037).
                    pids["closure"] = db.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    attempted.set()
                    close_due_attendance_intervals(
                        ctx=teacher_ctx, seat_id=target_seat_id,
                        as_of_utc=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    )
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(holder_scope)
        try:
            assert held.wait(10)
            closure = pool.submit(closure_scope)
            assert attempted.wait(10)

            # The closure must be the one waiting, blocked specifically on
            # whichever seat sorts first -- never the other seat first,
            # which would mean it is locking in an order that can invert
            # against payroll's.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["closure"]}
                ).scalar_one()
                if pids["holder"] in blockers:
                    break
                assert monotonic() < deadline, (
                    "close_due_attendance_intervals never blocked on the "
                    "seat that sorts first; it may lock the two seats in an "
                    "order that can invert against payroll's (the "
                    "#1640-adjacent bug)."
                )
                Event().wait(.01)

            # Blocking on the lower-id seat alone doesn't prove ascending
            # order -- a reversed implementation could lock the higher-id
            # seat FIRST and then block on the lower one, which the check
            # above cannot distinguish from the correct order (CodeRabbit
            # review on PR #1832, commit f0478037). Prove the higher-id seat
            # is genuinely still unlocked: a separate connection must be able
            # to take it with FOR UPDATE NOWAIT while the closure is blocked.
            with db.engine.connect() as prober_conn:
                with prober_conn.begin():
                    prober_conn.execute(
                        text(
                            "SELECT id FROM seats WHERE id=:id AND "
                            "class_id=:class_id FOR UPDATE NOWAIT"
                        ),
                        {"id": other_seat_id, "class_id": class_id},
                    )
        finally:
            release.set()
        assert holder.result(timeout=15) == "accepted"
        assert closure.result(timeout=15) == "accepted"

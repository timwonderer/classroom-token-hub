"""F6 and F7: hall-pass submission and approval each take a serializing lock.

F6 — Concurrent hall-pass requests can create duplicate pending reservations.
Before the fix, ``submit_hall_pass_request`` only locked a seat's existing
pending-request row (via ``clear_pending_hall_pass_requests_for_seat``'s
``with_for_update()``). A seat with no pending row yet has nothing for that to
lock, so two concurrent submissions for the same seat could both read "no
pending request", both find the same available grant, and both insert — two
pending rows reserving one pass, rather than the second genuinely replacing
the first. The fix locks the seat row itself, unconditionally, as the first
statement in the FEAT.

F7 — "Max students out" limit can be exceeded. Before the fix, the
queue/simultaneous-limit check in ``_enforce_hall_pass_settings`` counted
today's hall-pass logs with no class-wide lock, so two concurrent approvals
for two different students in the same class could each read the same
"currently out" count before either had inserted its row, and both pass the
limit check. The fix locks the class row first.

Both locks are proven against the emitted SQL (same technique as
``test_transfer_concurrency_guard.py``'s
``test_J1__transfer_takes_an_exclusive_lock_on_the_seat_row``), not by holding
the row externally and waiting for a lock timeout: ``pending_actions`` and
``hall_pass_logs`` both carry a foreign key to the row these fixes lock
(``seats`` / ``classes``), so an INSERT into either already takes an implicit
``FOR KEY SHARE`` lock on the parent row regardless of whether the explicit
fix is present — exactly the false-proof the docstring on that existing test
warns about: "something locks the row ... true with or without the fix."
Asserting the statement text, and that it appears *before* the read it is
meant to protect, is what actually distinguishes "fixed" from "not fixed"; a
first pass of this test file using the hold-elsewhere/lock-timeout pattern was
caught passing unchanged with the fix reverted, which is why it was replaced
with this.

The last test (the queue-limit one) IS decided correctly by a plain
behavioral assertion with no locking tooling, and reverting the fix was
confirmed to fail it.

PR #1550 review — lock ORDER, not just presence. Taking both locks
correctly still deadlocks if two code paths take them in opposite order:
PostgreSQL aborts one side, and here that abort surfaced as an API 500.
Two such inversions were found and fixed, each proven the same
statement-order way as F6/F7 above:

* ``approve_hall_pass_request`` locked the pending-request row
  (``pop_pending_hall_pass_request``) before the seat (inside
  ``_record_hall_pass_log_impl``), the opposite of submission's
  Seat -> pending-request order — a resubmission racing an approval of the
  same seat's request could deadlock.
* ``_record_hall_pass_log_impl`` locked ClassEconomy (F7's count lock)
  before the seat, the opposite of the ledger's Seat -> ClassEconomy order
  (``execute_account_transfer``, ``allocate_creation_posting_sequence``) —
  an approval racing a transfer for the same student could deadlock.

Both are now Seat-first, matching every other lock pair in this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def seat(app):
    with app.app_context():
        # provision_classroom() already seeds HallPassSettings (Bathroom,
        # max_queue=10, max_queue_limit=10) — see PROVISIONED_HALL_PASS_TYPES
        # in tests/helpers/canonical_classroom.py.
        classroom = provision_classroom("chemistry_p1")
        db.session.commit()
        student = classroom.students[0]
        teacher = db.session.get(Seat, classroom.teacher_seat_id)
        yield {
            "class_id": classroom.class_id,
            "seat_id": student.seat_id,
            "student": CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                        seat_id=student.seat_id, actor_role="student"),
            "teacher": CanonicalContext(user_id=teacher.user_id, class_id=classroom.class_id,
                                        seat_id=teacher.id, actor_role="teacher"),
        }


@contextmanager
def captured_statements():
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(" ".join(statement.split()))

    sa.event.listen(db.engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        sa.event.remove(db.engine, "before_cursor_execute", record)


def _first_index(statements, *needles):
    for i, stmt in enumerate(statements):
        if all(n in stmt for n in needles):
            return i
    return None


def test_F6__submitting_a_hall_pass_request_locks_the_seat_before_checking_or_inserting(app, seat):
    """The seat SELECT carries FOR UPDATE, and comes before the pending-request
    insert. Without it, two concurrent submissions for a seat with no pending
    row yet can both read "no pending request" and both insert — see the
    module docstring for why holding the row externally does not distinguish
    this from the unfixed code.
    """
    from app.feats.hall_pass_request_feat import submit_hall_pass_request

    with app.app_context():
        grant_seat = db.session.get(Seat, seat["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="f6-grant"):
            grant_hall_passes(grant_seat, 1)
        db.session.commit()

        with captured_statements() as statements:
            # submit_hall_pass_request is itself @requires_feat_context; an
            # outer FEATContext here would be forbidden nesting.
            submit_hall_pass_request(
                ctx=seat["student"], destination="Bathroom",
                requested_at_utc=datetime.now(timezone.utc),
                idempotency_key="f6-submit",
            )
        db.session.rollback()

        lock_index = _first_index(statements, "FROM seats", "FOR UPDATE")
        insert_index = _first_index(statements, "INSERT INTO pending_actions")
        assert lock_index is not None, "submission did not lock the seat row; see F6"
        assert insert_index is not None, "submission never reached the pending-request insert"
        assert lock_index < insert_index, (
            "the seat lock must be taken before the pending-request insert, "
            "or it does not close the F6 race"
        )


def test_F7__approving_a_hall_pass_locks_the_class_before_counting_who_is_out(app, seat):
    """The class SELECT carries FOR UPDATE, and comes before the "currently
    out" count. Without it, two concurrent approvals for different students in
    the same class can both read the same count before either has inserted its
    row — see the module docstring for why holding the row externally does not
    distinguish this from the unfixed code.
    """
    from app.feats.prod import record_hall_pass_log

    with app.app_context():
        grant_seat = db.session.get(Seat, seat["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="f7-grant"):
            grant_hall_passes(grant_seat, 1)
        db.session.commit()

        with captured_statements() as statements:
            record_hall_pass_log(
                ctx=seat["teacher"], requested_by_seat_id=seat["seat_id"],
                approved_by_seat_id=seat["teacher"].seat_id, destination="Bathroom",
                reason="teacher_approved", idempotency_key="f7-approve",
            )
        db.session.rollback()

        lock_index = _first_index(statements, "FROM classes", "FOR UPDATE")
        count_index = _first_index(statements, "FROM hall_pass_logs")
        assert lock_index is not None, "approval did not lock the class row; see F7"
        assert count_index is not None, "approval never reached the currently-out count"
        assert lock_index < count_index, (
            "the class lock must be taken before the currently-out count, "
            "or it does not close the F7 race"
        )


def test_F7__approved_but_not_left_pass_still_counts_against_the_queue_limit(app, seat):
    """A second approval must fail once the limit is reached by an approved,
    not-yet-"left" pass — not just by passes someone has already walked out
    with. Before the fix, ``currently_out`` only counted the "left" state, so
    rapid-fire approvals (no one had tapped out yet) always read a count of
    zero and all succeeded, defeating the limit entirely.
    """
    from app.feats.prod import record_hall_pass_log
    from app.models import HallPassSettings

    with app.app_context():
        # hall_pass_settings is an append-only policy repository (migration
        # c9e0f1a2b3c4) — a tighter limit is a new row with a later
        # effective_date, not an UPDATE of the provisioned one.
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"f7b-tighten:{seat['class_id']}"):
            predecessor = HallPassSettings.query.filter_by(
                class_id=seat["class_id"], availability_state="IN_USE",
            ).first()
            if predecessor is not None:
                predecessor.availability_state = "RETIRED"
                db.session.flush()
            db.session.add(HallPassSettings(
                class_id=seat["class_id"],
                max_queue_limit=1,
                pass_type_payload=[{"pass_name": "Bathroom", "max_queue": 1, "consume_pass": True}],
                effective_date=datetime.now(timezone.utc),
            ))
        db.session.commit()

        grant_seat = db.session.get(Seat, seat["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="f7b-grant"):
            grant_hall_passes(grant_seat, 2)
        db.session.commit()

        # First approval succeeds and occupies the only slot, even though
        # nobody has tapped "Left Class" yet.
        record_hall_pass_log(
            ctx=seat["teacher"], requested_by_seat_id=seat["seat_id"],
            approved_by_seat_id=seat["teacher"].seat_id, destination="Bathroom",
            reason="teacher_approved", idempotency_key="f7b-approve-1",
        )
        db.session.commit()

        # A second approval for the same (or another) student must be refused
        # against the now-exhausted limit, not silently allowed because no one
        # has "left" yet.
        with pytest.raises(ValueError, match="queue limit"):
            record_hall_pass_log(
                ctx=seat["teacher"], requested_by_seat_id=seat["seat_id"],
                approved_by_seat_id=seat["teacher"].seat_id, destination="Bathroom",
                reason="teacher_approved", idempotency_key="f7b-approve-2",
            )
        db.session.rollback()


def test_PR1550_review__approving_a_request_locks_the_seat_before_the_pending_row(app, seat):
    """``approve_hall_pass_request`` must lock the seat row before it locks
    (and deletes) the pending-request row.

    ``submit_hall_pass_request`` locks Seat, then the seat's pending-request
    rows (``clear_pending_hall_pass_requests_for_seat``). Before this fix,
    ``approve_hall_pass_request`` locked the pending-request row first
    (``pop_pending_hall_pass_request``) and only locked the seat afterwards
    (inside ``_record_hall_pass_log_impl``) — the opposite order. A student
    resubmitting a request while a teacher approves the existing one for the
    same seat could then deadlock: PostgreSQL aborts one side, and the API
    surfaced the approval's abort as a 500 (PR #1550 review).
    """
    from app.feats.hall_pass_request_feat import approve_hall_pass_request, submit_hall_pass_request

    with app.app_context():
        grant_seat = db.session.get(Seat, seat["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="pr1550-grant"):
            grant_hall_passes(grant_seat, 1)
        db.session.commit()

        request = submit_hall_pass_request(
            ctx=seat["student"], destination="Bathroom",
            requested_at_utc=datetime.now(timezone.utc),
            idempotency_key="pr1550-submit",
        )
        db.session.commit()

        with captured_statements() as statements:
            approve_hall_pass_request(
                ctx=seat["teacher"], request_id=request.request_id,
                idempotency_key="pr1550-approve",
            )
        db.session.rollback()

        seat_lock_index = _first_index(statements, "FROM seats", "FOR UPDATE")
        pending_lock_index = _first_index(statements, "FROM pending_actions", "FOR UPDATE")
        assert seat_lock_index is not None, "approval did not lock the seat row"
        assert pending_lock_index is not None, "approval never locked the pending-request row"
        assert seat_lock_index < pending_lock_index, (
            "approval must lock the seat before the pending-request row, "
            "matching submission's order, or the two can deadlock"
        )


def test_PR1550_review__recording_a_hall_pass_log_locks_the_seat_before_the_class(app, seat):
    """``_record_hall_pass_log_impl`` must lock the seat before it locks the
    class (via ``_enforce_hall_pass_settings``).

    ``execute_account_transfer`` and ``allocate_creation_posting_sequence``
    both lock Seat then ClassEconomy. Before this fix, recording a hall-pass
    log locked ClassEconomy first (F7's class-wide count lock) and the seat
    only afterwards — the opposite order — so an approval racing a transfer
    for the same student could deadlock (PR #1550 review).
    """
    from app.feats.prod import record_hall_pass_log

    with app.app_context():
        grant_seat = db.session.get(Seat, seat["seat_id"])
        with FEATContext("FEAT-TEST-ENTITLEMENT", idempotency_key="pr1550b-grant"):
            grant_hall_passes(grant_seat, 1)
        db.session.commit()

        with captured_statements() as statements:
            record_hall_pass_log(
                ctx=seat["teacher"], requested_by_seat_id=seat["seat_id"],
                approved_by_seat_id=seat["teacher"].seat_id, destination="Bathroom",
                reason="teacher_approved", idempotency_key="pr1550b-approve",
            )
        db.session.rollback()

        seat_lock_index = _first_index(statements, "FROM seats", "FOR UPDATE")
        class_lock_index = _first_index(statements, "FROM classes", "FOR UPDATE")
        assert seat_lock_index is not None, "recording the log did not lock the seat"
        assert class_lock_index is not None, "recording the log did not lock the class"
        assert seat_lock_index < class_lock_index, (
            "the seat lock must be taken before the class lock, matching the "
            "ledger's Seat -> ClassEconomy order, or the two can deadlock"
        )

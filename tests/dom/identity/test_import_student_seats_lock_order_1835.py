"""#1835 regression: a teacher roster import must never invert ledger
settlement's (or reconciliation's) seat-then-class lock order.

``import_student_seats`` (FEAT-IDEN-006, ``app/feats/identity_feat.py``) used
to lock the class row (``ClassEconomy.query...with_for_update()``) before
``_ensure_distinct_claim_codes`` locked any *pre-existing* unclaimed seat
sharing an imported row's claim-name hash -- the same class-before-seat
inversion #1640/PR #1832 closed for ``unclaim_student_seat``,
``activate_student_credentials``, and ``bind_authenticated_student_to_class``.
It is an independently discoverable instance of the same lock-order bug
class, not a new risk introduced by that PR: ledger settlement
(``FEAT-LED-003``) can hold any unclaimed seat with pending activity
regardless of claim state, and the import path could then end up holding the
class row while blocked on a seat settlement already holds.

The fix locks every pre-existing unclaimed seat an import batch's claim-name
groups will touch (ascending by id) before locking the class, matching
INV-LED-015 / DOM-LED-001 §VII's seats(s)-then-class rule.

This test reproduces the real race with a genuine concurrent transaction and
real Postgres locks (not a mock): it asserts the import blocks on the
pre-existing namesake seat rather than ever acquiring the class row while the
holder waits on it. Reverting the pre-lock step this fix adds to
``import_student_seats`` makes the final probe below fail with
``LockNotAvailable`` instead of succeeding (Pattern 7: confirmed by running
this test against the pre-fix code before trusting it as a regression test).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic

from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.identity_feat import import_student_seats
from app.hash_utils import hash_claim_name
from app.services.classroom_setup import create_roster_student_seat
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize


def test_import_student_seats_does_not_deadlock_concurrent_settlement(app):
    """A teacher roster import, concurrent with ledger settlement holding a
    pre-existing unclaimed namesake seat, must never deadlock (#1835).
    """
    classroom = initialize("chemistry_p1", app)
    first_name, last_name = "Namesake", "Student"
    with app.app_context():
        class_id = classroom.class_id
        teacher_ctx = CanonicalContext(
            user_id=classroom.teacher_user.id, class_id=class_id,
            seat_id=classroom.teacher_seat.id, actor_role="teacher",
        )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="import-deadlock-1835:seed"):
            existing_seat = create_roster_student_seat(
                class_id=class_id, first_name=first_name, last_name=last_name,
                claim_first_name_hash=hash_claim_name(first_name, class_id=class_id, field="first"),
                claim_last_name_hash=hash_claim_name(last_name, class_id=class_id, field="last"),
            )
        db.session.commit()
        existing_seat_id = existing_seat.id

    held, release, attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def holder_scope():
        # Stands in for a concurrent ledger settlement sweep that already
        # holds the pre-existing unclaimed namesake seat the import is about
        # to touch via _ensure_distinct_claim_codes.
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
                            {"id": existing_seat_id, "class_id": class_id},
                        )
                        held.set()
                        assert release.wait(10)
                return "accepted"
            finally:
                db.session.remove()

    def import_scope():
        with app.app_context():
            try:
                pids["import"] = db.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                attempted.set()
                import_student_seats(
                    canonical_context=teacher_ctx,
                    rows=[{"first_name": first_name, "last_name": last_name, "notes": None}],
                    correlation_id="corr-import-deadlock-1835",
                    idempotency_key="import-deadlock-1835-import",
                )
                return "accepted"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(holder_scope)
        try:
            assert held.wait(10)
            importer = pool.submit(import_scope)
            assert attempted.wait(10)

            # The import must be the one waiting, blocked specifically on the
            # pre-existing namesake seat the holder already holds, and must
            # NOT already hold the class row while the holder waits on it.
            deadline = monotonic() + 5
            while True:
                blockers = db.session.execute(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["import"]}
                ).scalar_one()
                if pids["holder"] in blockers:
                    break
                assert monotonic() < deadline, (
                    "import_student_seats never blocked on the pre-existing "
                    "namesake seat the holder holds; it may have locked the "
                    "class first instead (the #1835 bug)."
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
        assert importer.result(timeout=15) == "accepted"

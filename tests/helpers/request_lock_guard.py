"""Runtime guard: a request must not leave row locks held past its response.

Incident OPS-DB-001 (2026-09-30): the claim route took ``classes``/``seats``
``FOR UPDATE`` outside any FEAT and never ended that transaction, so the locks
lived until request teardown. The app's ``after_request`` trace writer, on its
own connection, then waited on its own request forever.

A static scan cannot tell a lock that a FEAT commits from one a helper leaves
open: the same ``with_for_update()`` call is correct in one place and the
defect in the other. The database can tell. Taking any row lock (``FOR UPDATE``,
``FOR SHARE``, ``FOR KEY SHARE``) or writing any row assigns the transaction an
id, and ``pg_current_xact_id_if_assigned()`` reports it. A request whose session
had no assigned id when it started, and has one when its response is finished,
is carrying row locks or uncommitted writes into ``after_request`` and teardown.

The comparison is against the request's own start so that state a test seeded
in the shared session before the request is never charged to the route.
"""
from __future__ import annotations

from sqlalchemy import text

from app.extensions import db


def assigned_transaction_id(session) -> str | None:
    """The session's assigned transaction id, or None. Never opens a transaction."""
    sess = session() if callable(session) and not hasattr(session, "in_transaction") else session
    if not sess.in_transaction():
        return None
    try:
        return sess.execute(text("SELECT pg_current_xact_id_if_assigned()::text")).scalar()
    except Exception:  # an aborted transaction cannot be asked; report nothing
        return None


def leaked_row_locks(before: str | None, after: str | None) -> bool:
    """True when the request itself acquired a transaction id it did not release."""
    return after is not None and after != before


class RequestLockGuard:
    """Records each request that finished still holding row locks it took."""

    def __init__(self):
        self.violations: list[str] = []
        self._before: str | None = None

    def started(self, sender, **extra):
        self._before = assigned_transaction_id(db.session)

    def finished(self, sender, response, **extra):
        from flask import request

        after = assigned_transaction_id(db.session)
        if leaked_row_locks(self._before, after):
            self.violations.append(f"{request.method} {request.path} -> {response.status_code}")

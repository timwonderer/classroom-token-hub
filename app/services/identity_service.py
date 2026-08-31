"""Identity service — canonical User/Seat resolution helpers.

Scope: resolving who an actor is. No domain logic (balances, entitlements, etc.).
"""

from __future__ import annotations

from app.models import Seat


def resolve_seat_for_context(*, user_id: int, class_id: str, seat_id: int | None = None) -> Seat | None:
    """Resolve one seat only within an already-established class context."""
    if not user_id or not class_id:
        return None
    query = Seat.query.filter(Seat.user_id == user_id, Seat.class_id == class_id)
    if seat_id is not None:
        query = query.filter(Seat.id == seat_id)
    return query.first()

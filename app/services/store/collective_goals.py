"""Collective-goal state — the single read authority.

Three separate places need to agree on the answer to "has this goal been met?":
the student store (which draws the progress bar), the teacher store (which draws
the same bar per class), and the expiry sweep (which decides whose money gets
returned when a goal lapses). Before this module they disagreed: the student
route counted every ``GRANTED`` event while the teacher route additionally
required ``acquisition_type == "PURCHASE"``. A teacher-issued direct grant
therefore moved the student's bar but not the teacher's.

That disagreement stops being cosmetic the moment a sweep reads it, because the
count decides whether anyone is refunded. The ``PURCHASE`` filter is the correct
one and is what this module applies: a goal is a buy-in, and a seat that did not
pay did not join it (DOM-STORE-001 §5).

Everything here counts over ``product_lineage_uuid``, never ``policy_uuid`` — a
goal belongs to the product, so editing the listing mid-drive must not reset the
class to zero.
"""

from __future__ import annotations

from collections.abc import Collection

from app.extensions import db
from app.models import EntitlementEvent, Seat, StoreProduct
from sqlalchemy.orm import aliased


def count_class_size(class_id: str) -> int:
    """Number of claimed student seats in the class.

    This is the denominator for a ``whole_class`` goal. Unclaimed seats are
    excluded — an empty desk cannot buy in, so counting it would make the goal
    permanently unreachable.
    """
    if not class_id:
        return 0
    return int(
        db.session.query(db.func.count(db.func.distinct(Seat.id)))
        .filter(
            Seat.class_id == class_id,
            Seat.claimed_at.isnot(None),
            Seat.role == "student",
        )
        .scalar()
        or 0
    )


def count_goal_participants(
    class_id: str,
    lineage_uuids: Collection[str],
) -> dict[str, int]:
    """Count distinct seats that have bought into each goal lineage.

    Returns ``{product_lineage_uuid: seat_count}``, omitting lineages with no
    participants. Distinct on ``target_seat_id`` because a collective goal is a
    headcount: buying twice does not make one student into two.

    Only open ``GRANTED`` rows are counted. Once an unmet goal is expired, its
    buy-ins receive terminal ``EXPIRED`` events and no longer contribute to a
    live progress projection; the goal is therefore cleared rather than
    displaying progress for a product that is no longer active.
    """
    lineages = [uuid for uuid in lineage_uuids if uuid]
    if not lineages or not class_id:
        return {}

    terminal_event = aliased(EntitlementEvent)
    terminal = (
        db.session.query(terminal_event.event_id)
        .filter(
            terminal_event.class_id == class_id,
            terminal_event.entitlement_id == EntitlementEvent.entitlement_id,
            terminal_event.event_type.in_(("CONSUMED", "EXPIRED", "REVOKED")),
        )
        .correlate(EntitlementEvent)
    )
    rows = (
        db.session.query(
            EntitlementEvent.product_id,
            db.func.count(db.func.distinct(EntitlementEvent.target_seat_id)).label(
                "seat_count"
            ),
        )
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id.in_(lineages),
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
            ~terminal.exists(),
        )
        .group_by(EntitlementEvent.product_id)
        .all()
    )
    return {row.product_id: int(row.seat_count or 0) for row in rows}


def resolve_goal_target(item: StoreProduct, class_size: int | None) -> int:
    """Resolve how many buy-ins this goal needs.

    A ``whole_class`` target floats with the roster, so it is resolved at read
    time rather than frozen onto the product. A ``fixed`` target is whatever the
    teacher typed.

    Returns 0 when the target cannot be resolved — an unconfigured ``fixed``
    goal, or a ``whole_class`` goal in a class with no claimed seats. Callers
    must treat 0 as "not yet answerable" and never as "already met"; see
    :func:`is_goal_met`.
    """
    if item.collective_goal_type == "whole_class":
        return int(class_size or 0)
    return int(item.collective_goal_target or 0)


def is_goal_met(participant_count: int, target: int) -> bool:
    """Whether a goal has been reached.

    Fails closed on an unresolvable target (``target <= 0``). The alternative —
    treating 0 as satisfied — would make an unconfigured goal read as complete
    and, at sweep time, silently deny refunds to everyone who bought in.
    """
    if target <= 0:
        return False
    return participant_count >= target

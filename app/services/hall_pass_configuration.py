from __future__ import annotations

from app.extensions import db
from app.models import HallPassSettings
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver


def _current_hall_pass_settings(class_id: str) -> HallPassSettings | None:
    """The hall-pass policy currently in force for a class, or None.

    A pure read. The previous ``_get_or_create`` variant inserted a default row
    as a side effect of being asked a question, which both wrote from a read
    path and minted an unretired policy nobody submitted. Callers that need a
    starting point when no policy exists use the class defaults instead.

    Deterministic by construction: ``effective_date`` collides for rows written
    in the same request, so ``id`` supplies the total order.
    """
    return (
        HallPassSettings.query
        .filter_by(class_id=class_id, availability_state='IN_USE')
        .order_by(HallPassSettings.effective_date.desc(), HallPassSettings.id.desc())
        .first()
    )


def save_hall_pass_setup_config(
    *,
    user_id: int,
    class_id: str,
    hall_pass_enabled: bool,
    pass_type_payload: list[dict],
    max_queue_limit: int = 10,
    updated_at=None,
    correlation_id: str,
    idempotency_key: str,
) -> HallPassSettings:
    """Record a hall-pass configuration submission as a NEW immutable row.

    DOM-POL-001 §VI.1: a submission is a new contract, never an edit. This
    already inserted a new row per save; what was missing is retiring the
    predecessor, without which the class accumulated several rows all claiming
    to be current and the reader picked one by sort order.
    """
    if not isinstance(pass_type_payload, list) or any(set(item) != {"pass_name", "max_queue", "consume_pass"} for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if any(not isinstance(item["pass_name"], str) or not isinstance(item["max_queue"], int) or item["max_queue"] < 0 or not isinstance(item["consume_pass"], bool) for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if not isinstance(max_queue_limit, int) or max_queue_limit < 0:
        raise ValueError("Invalid max queue limit")
    # Retire the predecessor BEFORE the insert is flushed so the partial unique
    # index never observes two IN_USE rows for the class.
    predecessor = _current_hall_pass_settings(class_id)
    if predecessor is not None:
        predecessor.availability_state = 'RETIRED'
        db.session.flush()

    settings = HallPassSettings(
        class_id=class_id,
        availability_state='IN_USE',
        max_queue_limit=max_queue_limit,
        pass_type_payload=pass_type_payload,
        effective_date=updated_at or canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="current_time"
        ).canonical_now_utc,
    )
    db.session.add(settings)
    db.session.flush()
    return settings



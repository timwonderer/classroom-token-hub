"""Ledger-owned command reservation and replay service boundary.

This is the canonical effect-plan reservation writer. Versioned serialization utilities
remain pure and preserve accepted historical command identities.
"""

import hashlib
import json
from decimal import Decimal

from app.extensions import db
from app.models import LedgerCommandReservation, Transaction
from sqlalchemy.exc import IntegrityError
from app.utils.transaction_idempotency import (
    FINGERPRINT_VERSION,
    IDEMPOTENT_TRANSACTION_TYPES,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    _command_fingerprint,
    amount_is_fingerprinted,
    fingerprint_matches_reservation,
)

_FINGERPRINT_EFFECT_KEYS = (
    "seat_id",
    "target_seat_id",
    "actor_seat_id",
    "mechanism",
    "amount",
    "account_type",
    "type",
    "original_transaction_id",
    "policy_id",
)


def _replay_fingerprint(
    effects: list[dict], version: int, canonical_intent=None
) -> str:
    """Serialize a command's effect plan under one fingerprint version."""
    if len(effects) == 1 and version < 4:
        effect = effects[0]
        return _command_fingerprint(
            target_seat_id=effect.get("target_seat_id"),
            actor_seat_id=effect.get("actor_seat_id"),
            amount=effect.get("amount"),
            account_type=effect.get("account_type"),
            type=effect.get("type"),
            original_transaction_id=effect.get("original_transaction_id"),
            policy_id=effect.get("policy_id"),
            version=version,
        )
    if version < 3:
        raise ValueError(
            "Legacy multi-effect reservations require the seat-ownership migration."
        )
    keys = _FINGERPRINT_EFFECT_KEYS + (
        (
            "compensation_origin_locator",
            "compensation_amount_cents",
            "correction_intent_locator",
        )
        if version >= 4
        else ()
    )
    if version >= 5:
        keys += ("compensation_subtype",)
    fields = []
    for effect in effects:
        field = {key: effect.get(key) for key in keys}
        if version >= 4:
            field["mechanism"] = getattr(
                field["mechanism"], "value", field["mechanism"]
            )
        if version >= 4 and field["amount"] is not None:
            field["amount"] = str(Decimal(field["amount"]).quantize(Decimal("0.01")))
        if not amount_is_fingerprinted(field["type"], version):
            field["amount"] = None
        if version >= 4:
            field["compensation_amount_cents"] = (
                field.get("compensation_amount_cents") or 0
            )
        fields.append(field)
    return hashlib.sha256(
        json.dumps(
            {"effects": fields, "intent": canonical_intent} if version >= 4 else fields,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()


def _assert_replay_matches(
    reservation, effects: list[dict], canonical_intent=None
) -> None:
    if not fingerprint_matches_reservation(
        reservation,
        lambda version: _replay_fingerprint(effects, version, canonical_intent),
    ):
        raise ValueError(
            "Replay fingerprint mismatch for existing Ledger command reservation."
        )


def create_idempotent_transaction(**kwargs):
    """Create or replay one effect through the command-reservation boundary."""
    from app.feats.base import get_active_feat_name

    idempotency_key = kwargs.pop("idempotency_key", None)
    class_id = kwargs.get("class_id")
    feat_code = get_active_feat_name()
    if not idempotency_key or not class_id or not feat_code:
        raise ValueError("Idempotent Ledger effects require class, FEAT, and key.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key must be a non-empty string.")
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError("Idempotency key exceeds the maximum allowed length.")
    if kwargs.get("type") not in IDEMPOTENT_TRANSACTION_TYPES:
        raise ValueError(
            f"Transaction type '{kwargs.get('type')}' is not enabled for idempotent creation."
        )
    effects, created = create_reserved_effects(
        class_id=class_id,
        feat_code=feat_code,
        idempotency_key=idempotency_key,
        effects=[kwargs],
    )
    return effects[0], created


def create_reserved_effects(
    *,
    class_id: str,
    feat_code: str,
    idempotency_key: str,
    effects: list[dict],
    canonical_intent=None,
) -> tuple[list[Transaction], bool]:
    """Create or replay one reservation owning multiple Ledger effects."""
    if not class_id or not feat_code or not idempotency_key or not effects:
        raise ValueError("A reserved command requires class, FEAT, key, and effects.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key must be a non-empty string.")
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError("Idempotency key exceeds the maximum allowed length.")
    fingerprint = _replay_fingerprint(effects, FINGERPRINT_VERSION, canonical_intent)
    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation:
        _assert_replay_matches(reservation, effects, canonical_intent)
        effects = (
            Transaction.query.filter_by(command_reservation_id=reservation.id)
            .order_by(Transaction.id.asc())
            .all()
        )
        if not effects:
            raise RuntimeError("Ledger command reservation has no committed effects.")
        return effects, False
    reservation = LedgerCommandReservation(
        class_id=class_id,
        feat_code=feat_code,
        idempotency_key=idempotency_key,
        replay_fingerprint=fingerprint,
        fingerprint_version=FINGERPRINT_VERSION,
    )
    try:
        with db.session.begin_nested():
            db.session.add(reservation)
            db.session.flush()
    except IntegrityError:
        reservation = LedgerCommandReservation.query.filter_by(
            class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
        ).one()
        _assert_replay_matches(reservation, effects, canonical_intent)
        effects = (
            Transaction.query.filter_by(command_reservation_id=reservation.id)
            .order_by(Transaction.id.asc())
            .all()
        )
        if not effects:
            raise RuntimeError("Ledger command reservation has no committed effects.")
        return effects, False
    from app.services.ledger_posting_service import create_pending_transaction

    created = [
        create_pending_transaction(command_reservation=reservation, **effect)
        for effect in effects
    ]
    db.session.flush()
    return created, True


__all__ = [
    "FINGERPRINT_VERSION",
    "_command_fingerprint",
    "create_idempotent_transaction",
    "create_reserved_effects",
    "replay_reserved_reversal",
]


def replay_reserved_charge(
    *,
    class_id,
    feat_code,
    idempotency_key,
    seat_id,
    actor_seat_id,
    principal_type,
    canonical_intent,
):
    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation is None:
        return None
    rows = (
        Transaction.query.filter_by(command_reservation_id=reservation.id)
        .order_by(Transaction.id)
        .all()
    )
    candidates = [
        row
        for row in rows
        if row.type == principal_type
        and row.amount_cents < 0
        and row.account_type == "checking"
    ]
    if (
        len(candidates) != 1
        or candidates[0].seat_id != seat_id
        or candidates[0].actor_seat_id != actor_seat_id
    ):
        raise ValueError("Replay fingerprint mismatch for charge scope or principal.")
    keys = _FINGERPRINT_EFFECT_KEYS + (
        "compensation_origin_locator",
        "compensation_amount_cents",
        "correction_intent_locator",
        "compensation_subtype",
    )
    effects = [{key: getattr(row, key) for key in keys} for row in rows]
    _assert_replay_matches(reservation, effects, canonical_intent)
    return {"principal": candidates[0], "effects": tuple(rows), "created": False}



def replay_reserved_reversal(*, original, principal, actor_seat_id, mechanism,
                             compensation_subtype, idempotency_key):
    """Verify accepted reversal effects under their original serializer.

    Resolve exact replay before current pricing/balances. Rebuild the accepted
    vector with current requested authority and structured reason, without
    changing any effect or inferring a missing historical reason.
    """
    from app.feats.base import get_active_feat_name

    reservation = LedgerCommandReservation.query.filter_by(
        id=principal.command_reservation_id, class_id=original.class_id,
        feat_code=get_active_feat_name(), idempotency_key=idempotency_key,
    ).one_or_none()
    if reservation is None:
        raise ValueError("Replay fingerprint mismatch for reversal reservation.")
    rows = Transaction.query.filter_by(command_reservation_id=reservation.id).order_by(Transaction.id).all()
    keys = _FINGERPRINT_EFFECT_KEYS + (
        "compensation_origin_locator", "compensation_amount_cents",
        "correction_intent_locator", "compensation_subtype",
    )
    effects = []
    for row in rows:
        effect = {key: getattr(row, key) for key in keys}
        effect.update(actor_seat_id=actor_seat_id, mechanism=mechanism)
        if row.id == principal.id:
            effect["compensation_subtype"] = compensation_subtype
        effects.append(effect)
    if principal.id not in {row.id for row in rows}:
        raise ValueError("Replay fingerprint mismatch for reversal effects.")
    _assert_replay_matches(reservation, effects, canonical_intent=None)
    return principal

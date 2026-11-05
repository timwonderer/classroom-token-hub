"""Teacher penalty (fine) plans: SPEC-ECON-003 §4.5.1.1 and §4.5.1.1A, FEAT-LED-006.

A penalty is a direct checking debit. It is never an obligation and never
generates a fee, so every plan resolves with ``fee_authority="NONE"``. The
caller supplies the Class Configuration banking directive (FEAT-LED-000 §XI.5).
Read-only: nothing here posts.
"""

import hashlib
from decimal import Decimal

from app.models import _quantize_currency
from app.services.ledger_resolution_service import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
)

PENALTY_TYPE = "penalty"
PENALTY_FEAT = "FEAT-LED-006"


def penalty_description(reason: str) -> str:
    """The text the student sees on the ledger row."""
    return f"Fine: {reason.strip()}"[:255]


def penalty_idempotency_key(submission_token: str, seat_id: int) -> str:
    return f"penalty:{submission_token}:{seat_id}"


def resolve_penalty_plans(*, class_id, seat_ids, amount, reason, actor_seat_id, banking_directive):
    """One resolved plan per seat, in ascending seat order."""
    amount = _quantize_currency(Decimal(amount))
    if amount <= 0:
        raise ValueError("A penalty must be a positive amount.")
    description = penalty_description(reason)
    return tuple(
        resolve_intended_ledger_plan(
            plan=build_intended_ledger_plan(
                seat_id=seat_id,
                class_id=class_id,
                debit_amount=amount,
                description=description,
                transaction_type=PENALTY_TYPE,
                actor_seat_id=actor_seat_id,
                target_seat_id=seat_id,
                mechanism="teacher",
                canonical_intent=(PENALTY_TYPE, seat_id, str(amount), description),
            ),
            banking_directive=banking_directive,
            fee_authority="NONE",
        )
        for seat_id in sorted(set(seat_ids))
    )


def penalty_preview_digest(resolved_plans) -> str:
    """Identity of what the teacher confirmed: each seat's balances and funding."""
    material = "|".join(
        ":".join(
            str(v)
            for v in (
                r.intended_plan.seat_id,
                r.intended_plan.debit_amount,
                r.checking_before,
                r.savings_before,
                r.recovery_transfer_amount,
            )
        )
        for r in resolved_plans
    )
    return hashlib.sha256(material.encode()).hexdigest()

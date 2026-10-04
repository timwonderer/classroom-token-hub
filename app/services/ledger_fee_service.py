"""Ledger-owned explicitly authorized fee command; caller supplies Class/Identity inputs."""

from decimal import Decimal
from app.services.ledger_resolution_service import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
    apply_resolved_ledger_plan,
)


def apply_overdraft_fee_if_needed(
    seat, *, banking_directive, actor_seat_id, force=False, idempotency_key=None
):
    from app.services.ledger_recovery_service import lock_recovery_scope

    lock_recovery_scope(seat.class_id, seat.id)
    from app.feats.base import get_active_feat_name
    from app.services.ledger_command_service import replay_reserved_charge

    intent = ("OVERDRAFT_FEE", bool(force))
    if idempotency_key:
        prior = replay_reserved_charge(
            class_id=seat.class_id,
            feat_code=get_active_feat_name(),
            idempotency_key=idempotency_key,
            seat_id=seat.id,
            actor_seat_id=actor_seat_id,
            principal_type="overdraft_fee",
            canonical_intent=intent,
        )
        if prior:
            return (True, abs(Decimal(prior["principal"].amount)))
    intended = build_intended_ledger_plan(
        seat_id=seat.id,
        class_id=seat.class_id,
        debit_amount=Decimal("0.00"),
        description="Overdraft fee",
        transaction_type="overdraft_fee",
        actor_seat_id=actor_seat_id,
        target_seat_id=seat.id,
        mechanism="system",
        fee_actor_seat_id=actor_seat_id,
        canonical_intent=intent,
    )
    resolved = resolve_intended_ledger_plan(
        plan=intended,
        banking_directive=banking_directive,
        fee_authority="EXPLICIT_FEE",
        force_overdraft_fee=force,
    )
    result = apply_resolved_ledger_plan(
        resolved_plan=resolved, idempotency_key=idempotency_key
    )
    return (result.get("accepted", False), resolved.overdraft_fee_amount)

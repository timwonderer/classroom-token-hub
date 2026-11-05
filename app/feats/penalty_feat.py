"""FEAT-LED-006: Apply Teacher Penalty.

A teacher fines one or more students in one submission. Every seat's debit,
and any overdraft-protection transfer funding it, commits in this one FEAT
transaction or none does: a fine is never applied to part of a selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.feats.base import get_active_feat_name, requires_feat_context
from app.models import ClassEconomy, LedgerCommandReservation, Transaction
from app.services.class_configuration_query_service import get_banking_directive
from app.services.ledger_penalty_service import (
    PENALTY_TYPE,
    penalty_batch_identity,
    penalty_idempotency_key,
    penalty_preview_digest,
    penalty_token_prefix,
    resolve_penalty_plans,
)
from app.services.ledger_recovery_service import lock_ledger_seats
from app.services.ledger_resolution_service import apply_resolved_ledger_plan


class PenaltyRefused(ValueError):
    """The submission cannot be applied; the message is teacher-facing."""


class PenaltyPreviewChanged(Exception):
    """Balances moved after the teacher reviewed the fine; nothing was applied."""


@dataclass(frozen=True)
class PenaltyResult:
    transactions: tuple[Transaction, ...]
    replayed: bool


@requires_feat_context("FEAT-LED-006")
def execute_teacher_penalty(
    *,
    class_id: str,
    seat_ids: list[int],
    amount: Decimal,
    reason: str,
    actor_seat_id: int,
    expected_preview_digest: str,
    correlation_id: str,
    idempotency_key: str,
) -> PenaltyResult:
    """``idempotency_key`` is the submission token minted when the teacher reviewed."""
    if not seat_ids:
        raise PenaltyRefused("Select at least one student to fine.")
    if not (reason or "").strip():
        raise PenaltyRefused("Enter the reason for the fine.")

    seats = lock_ledger_seats(class_id, seat_ids)
    excluded = [s for s in seats if s.role != "student" or s.claimed_at is None or s.user_id is None]
    if excluded:
        # Unclaimed seats take part in no economic activity; refuse the whole
        # submission rather than quietly fining only some of the selection.
        raise PenaltyRefused(
            f"{len(excluded)} selected student(s) have not claimed their account and "
            "can't be fined. Nothing was applied; remove them and review again."
        )

    if not re.fullmatch(r"[0-9a-f]{32}", idempotency_key or ""):
        raise PenaltyRefused("The fine could not be applied. Review it again.")
    # Serializes submissions that share a token, so the check below sees any
    # that committed first (DOM-LED-001 lock order: seats, then ClassEconomy).
    ClassEconomy.query.filter_by(class_id=class_id).with_for_update().one()
    batch = penalty_batch_identity([s.id for s in seats], amount, reason)
    keys = {seat.id: penalty_idempotency_key(idempotency_key, batch, seat.id) for seat in seats}
    existing = LedgerCommandReservation.query.filter(
        LedgerCommandReservation.class_id == class_id,
        LedgerCommandReservation.feat_code == get_active_feat_name(),
        LedgerCommandReservation.idempotency_key.startswith(penalty_token_prefix(idempotency_key)),
    ).all()
    if existing:
        # A token belongs to the one batch it was reviewed for: the same batch
        # replays; any other selection, amount or reason is refused.
        if {r.idempotency_key for r in existing} != set(keys.values()):
            raise PenaltyRefused(
                "This review was already used for a different fine, so nothing more was "
                "applied. Review the fine again to apply it."
            )
        rows = (
            Transaction.query.filter_by(command_reservation_id=r.id, type=PENALTY_TYPE).one()
            for r in existing
        )
        return PenaltyResult(tuple(sorted(rows, key=lambda row: row.seat_id)), replayed=True)

    resolved = resolve_penalty_plans(
        class_id=class_id,
        seat_ids=list(keys),
        amount=amount,
        reason=reason,
        actor_seat_id=actor_seat_id,
        banking_directive=get_banking_directive(class_id),
    )
    if penalty_preview_digest(resolved) != expected_preview_digest:
        raise PenaltyPreviewChanged()

    rows = tuple(
        apply_resolved_ledger_plan(
            resolved_plan=plan, idempotency_key=keys[plan.intended_plan.seat_id]
        )["principal"]
        for plan in resolved
    )
    return PenaltyResult(rows, replayed=False)


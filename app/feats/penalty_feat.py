"""FEAT-LED-006: Apply Teacher Penalty.

A teacher fines one or more students in one submission. Every seat's debit,
and any overdraft-protection transfer funding it, commits in this one FEAT
transaction or none does: a fine is never applied to part of a selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.feats.base import get_active_feat_name, requires_feat_context
from app.models import LedgerCommandReservation, Transaction, _quantize_currency
from app.services.class_configuration_query_service import get_banking_directive
from app.services.ledger_penalty_service import (
    PENALTY_TYPE,
    penalty_description,
    penalty_idempotency_key,
    penalty_preview_digest,
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

    keys = {seat.id: penalty_idempotency_key(idempotency_key, seat.id) for seat in seats}
    existing = LedgerCommandReservation.query.filter(
        LedgerCommandReservation.class_id == class_id,
        LedgerCommandReservation.feat_code == get_active_feat_name(),
        LedgerCommandReservation.idempotency_key.in_(keys.values()),
    ).all()
    if existing:
        return PenaltyResult(_replayed_rows(existing, keys, amount, reason), replayed=True)

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


def _replayed_rows(reservations, keys, amount, reason):
    """A resubmitted token returns what it posted, or refuses if it now means something else."""
    if len(reservations) != len(keys):
        raise PenaltyRefused("This fine was already applied to a different selection of students.")
    rows = tuple(
        Transaction.query.filter_by(command_reservation_id=r.id, type=PENALTY_TYPE).one()
        for r in reservations
    )
    if any(
        row.amount != -_quantize_currency(Decimal(amount)) or row.description != penalty_description(reason)
        for row in rows
    ):
        raise PenaltyRefused("This fine was already applied with a different amount or reason.")
    return tuple(sorted(rows, key=lambda row: row.seat_id))

"""Ledger-owned internal transfer service surface.

Transfer FEATs depend on this module rather than importing the mixed Ledger
service directly. The implementation remains Ledger-owned; this module is the
canonical service boundary for transfer creation and proof.
"""

from app.services.ledger_balance_query_service import TransferProofResult, verify_transfer
from app.services.ledger_command_service import create_reserved_effects
from app.models import Transaction
from app.models import _quantize_currency


def build_transfer_effect_pair(
    *, seat_id: int, class_id: str, target_seat_id: int | None = None,
    actor_seat_id: int | None = None, mechanism: str = "self",
    correlation_id: str | None = None, amount, from_account: str, to_account: str,
    withdraw_description: str, deposit_description: str,
) -> list[dict]:
    """Build the two-leg effect vector for an internal account transfer.

    Pure constructor (DOM-LED-001 INV-LED-014): returns the effect dicts a
    caller passes to ``create_reserved_effects``. Reserves, posts, and commits
    nothing itself, so both the standalone student-initiated transfer and the
    bundled overdraft-protection funding legs can compose it into their own
    reservation call.
    """
    target_seat_id = seat_id if target_seat_id is None else target_seat_id
    actor_seat_id = seat_id if actor_seat_id is None else actor_seat_id
    if from_account not in {"checking", "savings"} or to_account not in {"checking", "savings"}:
        raise ValueError("Internal transfers require checking/savings account types.")
    if from_account == to_account:
        raise ValueError("Internal transfers require distinct source and destination accounts.")
    quantized_amount = _quantize_currency(amount)
    if quantized_amount <= 0:
        raise ValueError("Internal transfer amount must be greater than zero.")
    common = dict(
        class_id=class_id, target_seat_id=target_seat_id, actor_seat_id=actor_seat_id,
        mechanism=mechanism, correlation_id=correlation_id,
    )
    return [
        dict(
            common, seat_id=seat_id, account_type=from_account,
            amount=-quantized_amount, type="Withdrawal", description=withdraw_description,
        ),
        dict(
            common, seat_id=seat_id, account_type=to_account,
            amount=quantized_amount, type="Deposit", description=deposit_description,
        ),
    ]


def create_transfer_pair(
    *, seat_id: int, class_id: str, amount,
    from_account: str, to_account: str, withdraw_description: str,
    deposit_description: str, idempotency_key: str | None = None,
) -> tuple[Transaction, Transaction]:
    """Create one reservation owning exactly two pending transfer effects."""
    from app.feats.base import get_active_feat_name, get_idempotency_key

    if not class_id or not seat_id:
        raise ValueError("FATAL: Internal transfer requires explicit class_id and seat_id.")
    idempotency_key = idempotency_key or get_idempotency_key()
    feat_code = get_active_feat_name()
    if not idempotency_key or not feat_code:
        raise ValueError("Internal transfers require a command idempotency reservation.")
    effects = build_transfer_effect_pair(
        seat_id=seat_id, class_id=class_id, mechanism="self",
        amount=amount, from_account=from_account, to_account=to_account,
        withdraw_description=withdraw_description, deposit_description=deposit_description,
    )
    rows, _created = create_reserved_effects(
        class_id=class_id, feat_code=feat_code,
        idempotency_key=idempotency_key, effects=effects,
    )
    return rows[0], rows[1]


__all__ = [
    "TransferProofResult",
    "build_transfer_effect_pair",
    "create_transfer_pair",
    "verify_transfer",
]

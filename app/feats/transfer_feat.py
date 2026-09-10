from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import Seat
from app.services.ledger_balance_query_service import get_available_balance
from app.services.ledger_transfer_service import create_transfer_pair


class InsufficientFunds(Exception):
    """The source account cannot cover the transfer at the moment of posting."""

    def __init__(self, from_account: str):
        super().__init__(f"Insufficient {from_account} funds.")
        self.from_account = from_account


@dataclass
class TransferResult:
    withdrawal_transaction_id: int
    deposit_transaction_id: int
    amount: Decimal
    from_account: str
    to_account: str


def execute_account_transfer(
    *,
    seat_id: int,
    class_id: str,
    user_id: int,
    amount: Decimal,
    from_account: str,
    to_account: str,
) -> TransferResult:
    """Ledger-led FEAT for student checking/savings transfers.

    The seat row is locked before the balance is read so that two concurrent
    transfers serialize behind each other instead of both reading the same
    pre-transfer balance and both passing the sufficiency check. Callers cannot
    supply the guarantee themselves: the route's idempotency key is fresh per
    request, so the UNIQUE(class_id, feat_code, idempotency_key) reservation
    does not collapse a double submit either. Store purchase already locks the
    same row for the same reason.
    """
    seat = (
        db.session.query(Seat)
        .filter(Seat.id == seat_id, Seat.class_id == class_id)
        .with_for_update()
        .one_or_none()
    )
    if seat is None:
        raise ValueError("FATAL: Transfer seat is outside the transaction class scope.")

    if get_available_balance(seat_id, class_id, from_account) < amount:
        raise InsufficientFunds(from_account)

    withdraw_tx, deposit_tx = create_transfer_pair(
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=amount,
        from_account=from_account,
        to_account=to_account,
        withdraw_description=f"Transfer to {to_account}",
        deposit_description=f"Transfer from {from_account}",
    )
    return TransferResult(
        withdrawal_transaction_id=withdraw_tx.id,
        deposit_transaction_id=deposit_tx.id,
        amount=amount,
        from_account=from_account,
        to_account=to_account,
    )

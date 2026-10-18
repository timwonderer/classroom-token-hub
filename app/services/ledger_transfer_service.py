"""Ledger-owned internal transfer service surface.

Transfer FEATs depend on this module rather than importing the mixed Ledger
service directly. The implementation remains Ledger-owned; this module is the
canonical service boundary for transfer creation and proof.
"""

from app.services.ledger_balance_query_service import TransferProofResult, verify_transfer
from app.services.ledger_command_service import FINGERPRINT_VERSION, _command_fingerprint
from app.utils.transaction_idempotency import fingerprint_matches_reservation
from app.services.ledger_posting_service import create_pending_transaction
from app.extensions import db
from app.models import LedgerCommandReservation, Transaction
from app.models import _quantize_currency


def build_transfer_effect_pair(
    *, seat_id: int, class_id: str, target_seat_id: int | None = None,
    actor_seat_id: int | None = None, mechanism: str = "self",
    correlation_id: str | None = None, amount, from_account: str, to_account: str,
    withdraw_description: str, deposit_description: str,
) -> list[dict]:
    """Build the two-leg effect vector for an internal account transfer.

    Pure constructor (DOM-LED-001 INV-LED-014): returns the effect dicts a
    caller passes to ``create_pending_transaction``. Reserves, posts, and
    commits nothing itself, so both the standalone student-initiated transfer
    and the bundled overdraft-protection funding legs can compose it into
    their own reservation call. This does NOT change how either caller
    reserves or fingerprints the pair — see ``create_transfer_pair`` for why
    the standalone path keeps its own dedicated replay serializer
    (SPEC-LED-002 §4.2).
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
    """Create one reservation owning exactly two pending transfer effects.

    The internal-transfer family retains its own dedicated
    ``_command_fingerprint`` replay serializer across every fingerprint
    version (SPEC-LED-002 §4.2: "the internal-transfer family retains its
    existing canonical `_command_fingerprint` representation"), never the
    general effect-plan ``_replay_fingerprint`` used by
    ``create_reserved_effects``. A reservation accepted before this module
    took its current shape must still replay-match on retry, so this command
    reserves and fingerprints itself rather than delegating to the general
    multi-effect primitive; only the two effects' shared field construction
    is delegated to ``build_transfer_effect_pair``.
    """
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
    quantized_amount = effects[1]["amount"]  # the deposit leg's positive magnitude

    def fingerprint_for(version):
        return _command_fingerprint(
            target_seat_id=seat_id, actor_seat_id=seat_id, amount=quantized_amount,
            account_type=f"{from_account}->{to_account}", type="internal_transfer",
            original_transaction_id=None, policy_id=None, version=version,
        )

    fingerprint = fingerprint_for(FINGERPRINT_VERSION)
    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation:
        if not fingerprint_matches_reservation(reservation, fingerprint_for):
            raise ValueError("Replay fingerprint mismatch for existing transfer reservation.")
        rows = Transaction.query.filter_by(command_reservation_id=reservation.id).order_by(Transaction.id.asc()).all()
        if len(rows) != 2:
            raise RuntimeError("Transfer reservation does not have exactly two effects.")
        return rows[0], rows[1]
    reservation = LedgerCommandReservation(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key,
        replay_fingerprint=fingerprint, fingerprint_version=FINGERPRINT_VERSION,
    )
    db.session.add(reservation)
    db.session.flush()
    withdraw_tx = create_pending_transaction(command_reservation=reservation, **effects[0])
    deposit_tx = create_pending_transaction(command_reservation=reservation, **effects[1])
    db.session.flush()
    return withdraw_tx, deposit_tx


__all__ = [
    "TransferProofResult",
    "build_transfer_effect_pair",
    "create_transfer_pair",
    "verify_transfer",
]

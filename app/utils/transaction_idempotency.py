import hashlib
import json

from app.models import Transaction


IDEMPOTENT_TRANSACTION_TYPES = frozenset(
    {
        # The canonical compensating type (FEAT-LED-002 §III.2.1). The business
        # reason a reversal was raised for is persisted in
        # Transaction.compensation_subtype, not here.
        "REVERSAL",
        "insurance_reimbursement",
        "insurance_premium",
        "purchase",
        "refund",
        "overdraft_fee",
        "payroll",
        "payroll_correction",
        "manual_payment",
        "bug_reward",
        "issue_reversal",
        "issue_compensation",
        "rent_payment",
        "Interest",
        "void_item_removed",
    }
)

IDEMPOTENCY_KEY_PREFIX = "txn"
MAX_IDEMPOTENCY_KEY_LENGTH = 128

# Version 1 fingerprinted every effect's amount. Version 2 is byte-identical
# except that an Interest effect's amount is encoded as null: interest is a
# period-keyed command recomputed from a live balance on every retry, and
# SPEC-LED-002 §4.1 requires values that legitimately change across retries to
# be excluded. §4.2 makes that serializer change a new version, and a
# reservation accepted under version 1 is still compared under version 1.
# Version 3 removes authentication principal material from multi-effect commands.
# Version 4 effect-plan commands bind the immutable vector and originating
# business intent. Transfer-family and retained v1–v3 serializers remain exact.
FINGERPRINT_VERSION = 4
SUPPORTED_FINGERPRINT_VERSIONS = frozenset({1, 2, 3, 4})
_AMOUNT_EXCLUDED_FROM_FINGERPRINT_TYPES = frozenset({"Interest"})


def amount_is_fingerprinted(type, version):
    """Whether an effect's amount participates in the version's fingerprint."""
    if version not in SUPPORTED_FINGERPRINT_VERSIONS:
        raise ValueError(f"Unsupported Ledger fingerprint version: {version!r}")
    return version < 2 or type not in _AMOUNT_EXCLUDED_FROM_FINGERPRINT_TYPES


def fingerprint_matches_reservation(reservation, fingerprint_for_version):
    """Compare a replayed command against a reservation under its own version.

    The supplied command is serialized under the version the reservation was
    accepted with; the stored digest is never re-derived under the current
    version (SPEC-LED-002 §4.2). An unknown version fails closed (§6.3).
    """
    version = reservation.fingerprint_version
    if version not in SUPPORTED_FINGERPRINT_VERSIONS:
        return False
    return reservation.replay_fingerprint == fingerprint_for_version(version)


def _normalize_key_part(value):
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def build_transaction_idempotency_key(*parts):
    normalized_parts = [
        _normalize_key_part(part)
        for part in parts
        if part is not None and str(part).strip() != ""
    ]
    return ":".join([IDEMPOTENCY_KEY_PREFIX, *normalized_parts])


def insurance_reimbursement_key(claim_id):
    return build_transaction_idempotency_key(
        "insurance", "claim", claim_id, "reimbursement"
    )


def store_purchase_refund_key(purchase_id, reason):
    return build_transaction_idempotency_key(
        "refund", "store-purchase", purchase_id, reason
    )


def purchase_transaction_key(student_id, class_id, item_id, client_idempotency_token):
    return build_transaction_idempotency_key(
        "purchase",
        "student",
        student_id,
        "class",
        class_id,
        "item",
        item_id,
        client_idempotency_token,
    )


def void_refund_key(transaction_id):
    return build_transaction_idempotency_key(
        "void", "transaction", transaction_id, "refund"
    )


def get_idempotent_transaction(
    idempotency_key, class_id=None, seat_id=None, type=None, feat_code=None
):
    if not idempotency_key:
        return None

    query = Transaction.query.filter(Transaction.idempotency_key == idempotency_key)
    if class_id:
        query = query.filter(Transaction.class_id == class_id)

    if seat_id:
        query = query.filter(Transaction.seat_id == seat_id)
    if type:
        query = query.filter(Transaction.type == type)
    if feat_code:
        query = query.filter(Transaction.feat_code == feat_code)

    return query.first()


def _command_fingerprint(
    *,
    target_seat_id,
    actor_seat_id,
    amount,
    account_type,
    type,
    original_transaction_id,
    policy_id,
    version=FINGERPRINT_VERSION,
):
    # correlation_id is deliberately absent. It is a per-request lineage value
    # (SPEC-LED-002 §4.1), and the one caller that carries a prior correlation
    # forward also supplies original_transaction_id, which already pins it.
    representation = {
        "account_type": account_type,
        "actor_seat_id": actor_seat_id,
        "amount": str(amount) if amount_is_fingerprinted(type, version) else None,
        "original_transaction_id": original_transaction_id,
        "policy_id": policy_id,
        "target_seat_id": target_seat_id,
        "type": type,
    }
    encoded = json.dumps(
        representation, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

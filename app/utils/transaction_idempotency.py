from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction


IDEMPOTENT_TRANSACTION_TYPES = frozenset({
    "insurance_reimbursement",
    "refund",
})

IDEMPOTENCY_KEY_PREFIX = "txn"
MAX_IDEMPOTENCY_KEY_LENGTH = 128


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
    return build_transaction_idempotency_key("insurance", "claim", claim_id, "reimbursement")


def student_item_refund_key(student_item_id, reason):
    return build_transaction_idempotency_key("refund", "student-item", student_item_id, reason)


def void_refund_key(transaction_id):
    return build_transaction_idempotency_key("void", "transaction", transaction_id, "refund")


def get_idempotent_transaction(idempotency_key):
    if not idempotency_key:
        return None
    return Transaction.query.filter(Transaction.idempotency_key == idempotency_key).first()


def create_idempotent_transaction(*, idempotency_key, **transaction_kwargs):
    transaction_type = transaction_kwargs.get("type")
    if transaction_type not in IDEMPOTENT_TRANSACTION_TYPES:
        raise ValueError(f"Transaction type '{transaction_type}' is not enabled for idempotent creation.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key must be a non-empty string.")
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(
            f"Idempotency key exceeds max length of {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )

    existing = get_idempotent_transaction(idempotency_key)
    if existing:
        return existing, False

    try:
        with db.session.begin_nested():
            transaction = Transaction(idempotency_key=idempotency_key, **transaction_kwargs)
            db.session.add(transaction)
            db.session.flush()
            return transaction, True
    except IntegrityError:
        existing = get_idempotent_transaction(idempotency_key)
        if existing:
            return existing, False
        raise

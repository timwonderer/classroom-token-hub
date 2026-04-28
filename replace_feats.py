print("Realignment: Rewriting Feats")
import os
os.system("rm -rf app/feats/*")
os.makedirs("app/feats", exist_ok=True)
with open("app/feats/__init__.py", "w") as f:
    f.write("")

with open("app/feats/base.py", "w") as f:
    f.write("""
from functools import wraps
from app.extensions import db
from app.models import OperationalEvent, AuditLog

def feat_shell(domain, level="INFO"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                db.session.commit()
                return result
            except Exception as e:
                db.session.rollback()
                raise e
        return wrapper
    return decorator
""")

with open("app/feats/transfer_feat.py", "w") as f:
    f.write("""
from app.extensions import db
from app.models import LedgerTransaction, LedgerBalanceSnapshot
from .base import feat_shell
import uuid

@feat_shell(domain="LEDGER")
def execute_transfer(from_seat_id, to_seat_id, amount_cents, idempotency_key):
    if amount_cents <= 0:
        raise ValueError("Transfer amount must be positive")

    correlation_id = str(uuid.uuid4())

    tx_out = LedgerTransaction(
        seat_id=from_seat_id,
        amount_cents=-amount_cents,
        status="POSTED",
        category="MANUAL",
        correlation_id=correlation_id,
        idempotency_key=f"{idempotency_key}_out"
    )
    tx_in = LedgerTransaction(
        seat_id=to_seat_id,
        amount_cents=amount_cents,
        status="POSTED",
        category="MANUAL",
        correlation_id=correlation_id,
        idempotency_key=f"{idempotency_key}_in"
    )

    db.session.add(tx_out)
    db.session.add(tx_in)

    # Update balances (assuming simple read-modify-write for now, would normally use locking)
    for seat_id, amt in [(from_seat_id, -amount_cents), (to_seat_id, amount_cents)]:
        bal = db.session.get(LedgerBalanceSnapshot, seat_id)
        if not bal:
            bal = LedgerBalanceSnapshot(seat_id=seat_id, posted_balance_cents=0, last_event_id=0)
            db.session.add(bal)
        bal.posted_balance_cents += amt
""")

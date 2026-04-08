"""
Invariant: Transaction State Validity

Verifies that every transaction row carries a valid status value.
Valid states are: 'PENDING', 'POSTED', 'VOID' (uppercase — the DB stores the
enum labels as defined in migrations/versions/ec84c1f59c15_add_ledger_and_settlement_models.py).
Any unknown status value indicates either a migration bug or direct DB manipulation.

Table: transaction (singular) — Transaction.__tablename__ = 'transaction'
"""

from sqlalchemy import text
from app.extensions import db

VALID_STATUSES = frozenset({"PENDING", "POSTED", "VOID"})


def run():
    try:
        rows = db.session.execute(text("""
            SELECT DISTINCT status
            FROM transaction
            WHERE status NOT IN ('PENDING', 'POSTED', 'VOID')
        """)).fetchall()

        if rows:
            invalid = [str(r[0]) for r in rows]
            return {
                "name": "transaction_state_validity",
                "status": "FAIL",
                "details": f"Invalid status value(s) found: {invalid}",
                "invalid_statuses": invalid,
            }

        return {"name": "transaction_state_validity", "status": "PASS"}

    except Exception as e:
        return {
            "name": "transaction_state_validity",
            "status": "FAIL",
            "details": str(e),
        }

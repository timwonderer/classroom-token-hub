"""
Invariant: Transaction State Validity

Verifies that every transaction row carries a valid status value.
Valid states are: 'pending', 'posted', 'void'.
Any unknown status value indicates either a migration bug or direct DB manipulation.
"""

from sqlalchemy import text
from app.extensions import db

VALID_STATUSES = frozenset({"pending", "posted", "void"})


def run():
    try:
        rows = db.session.execute(text("""
            SELECT DISTINCT status
            FROM transactions
            WHERE status NOT IN ('pending', 'posted', 'void')
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

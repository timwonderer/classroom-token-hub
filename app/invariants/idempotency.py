"""
Invariant: Idempotency Key Uniqueness

Verifies that no idempotency_key appears more than once in the transaction table.
The database enforces this via a unique constraint, but this check validates the
invariant at the application layer and catches any constraint bypasses.

Table: transaction (singular) — Transaction.__tablename__ = 'transaction'
"""

from sqlalchemy import text
from app.extensions import db


def run():
    try:
        rows = db.session.execute(text("""
            SELECT idempotency_key, COUNT(*) AS occurrence_count
            FROM transaction
            WHERE idempotency_key IS NOT NULL
            GROUP BY idempotency_key
            HAVING COUNT(*) > 1
        """)).fetchall()

        if rows:
            return {
                "name": "idempotency_key_uniqueness",
                "status": "FAIL",
                "details": f"{len(rows)} duplicate idempotency key(s) detected",
                "duplicate_count": len(rows),
            }

        return {"name": "idempotency_key_uniqueness", "status": "PASS"}

    except Exception as e:
        return {
            "name": "idempotency_key_uniqueness",
            "status": "FAIL",
            "details": str(e),
        }

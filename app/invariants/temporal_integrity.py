"""
Invariant: Temporal Integrity

Verifies that time-ordered fields on transactions are logically consistent:
  - posted_at must not be earlier than the transaction's creation timestamp.

Only POSTED transactions are checked (non-posted rows have NULL posted_at by
design). The status filter uses the uppercase DB enum label 'POSTED'.

Table: transaction (singular) — Transaction.__tablename__ = 'transaction'
Status enum: uppercase in DB ('POSTED') per
  migrations/versions/ec84c1f59c15_add_ledger_and_settlement_models.py
"""

from sqlalchemy import text
from app.extensions import db


def run():
    try:
        rows = db.session.execute(text("""
            SELECT id, timestamp, posted_at
            FROM transaction
            WHERE status = 'POSTED'
              AND posted_at IS NOT NULL
              AND posted_at < timestamp
        """)).fetchall()

        if rows:
            return {
                "name": "temporal_integrity",
                "status": "FAIL",
                "details": f"{len(rows)} transaction(s) where posted_at < created timestamp",
                "failure_count": len(rows),
                "violation_count": len(rows),
            }

        return {"name": "temporal_integrity", "status": "PASS"}

    except Exception as e:
        return {
            "name": "temporal_integrity",
            "status": "FAIL",
            "details": "Invariant query failed",
            "failure_count": 1,
        }

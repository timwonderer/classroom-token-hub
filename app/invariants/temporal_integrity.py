"""
Invariant: Temporal Integrity

Verifies that time-ordered fields on transactions are logically consistent:
  - posted_at must not be earlier than the transaction's creation timestamp.

Transactions with NULL posted_at (PENDING/VOID) are excluded.
"""

from sqlalchemy import text
from app.extensions import db


def run():
    try:
        rows = db.session.execute(text("""
            SELECT id, timestamp, posted_at
            FROM transactions
            WHERE status = 'posted'
              AND posted_at IS NOT NULL
              AND posted_at < timestamp
        """)).fetchall()

        if rows:
            return {
                "name": "temporal_integrity",
                "status": "FAIL",
                "details": f"{len(rows)} transaction(s) where posted_at < created timestamp",
                "violation_count": len(rows),
            }

        return {"name": "temporal_integrity", "status": "PASS"}

    except Exception as e:
        return {
            "name": "temporal_integrity",
            "status": "FAIL",
            "details": str(e),
        }

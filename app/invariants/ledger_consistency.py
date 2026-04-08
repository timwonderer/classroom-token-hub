"""
Invariant: Ledger ↔ BalanceCache Consistency

Verifies that the sum of POSTED transaction amount_cents per (student, join_code,
account_type) matches the values stored in BalanceCache. A mismatch indicates
silent corruption of the balance cache or a bug in the settlement path.

Table: transaction (singular) — Transaction.__tablename__ = 'transaction'
Status enum: uppercase in DB ('PENDING', 'POSTED', 'VOID') per
  migrations/versions/ec84c1f59c15_add_ledger_and_settlement_models.py
"""

from sqlalchemy import text
from app.extensions import db


def run():
    try:
        rows = db.session.execute(text("""
            SELECT
                bc.student_id,
                bc.join_code,
                COALESCE(SUM(
                    CASE WHEN t.account_type = 'checking'
                         AND t.status = 'POSTED'
                         AND t.join_code IS NOT NULL
                         AND NOT t.is_void
                    THEN t.amount_cents ELSE 0 END
                ), 0) AS computed_checking_cents,
                COALESCE(SUM(
                    CASE WHEN t.account_type = 'savings'
                         AND t.status = 'POSTED'
                         AND t.join_code IS NOT NULL
                         AND NOT t.is_void
                    THEN t.amount_cents ELSE 0 END
                ), 0) AS computed_savings_cents,
                bc.posted_checking_balance_cents,
                bc.posted_savings_balance_cents
            FROM balance_cache bc
            LEFT JOIN transaction t
                ON t.student_id = bc.student_id
                AND t.join_code = bc.join_code
            GROUP BY
                bc.student_id,
                bc.join_code,
                bc.posted_checking_balance_cents,
                bc.posted_savings_balance_cents
            HAVING
                COALESCE(SUM(
                    CASE WHEN t.account_type = 'checking'
                         AND t.status = 'POSTED'
                         AND t.join_code IS NOT NULL
                         AND NOT t.is_void
                    THEN t.amount_cents ELSE 0 END
                ), 0) != bc.posted_checking_balance_cents
                OR
                COALESCE(SUM(
                    CASE WHEN t.account_type = 'savings'
                         AND t.status = 'POSTED'
                         AND t.join_code IS NOT NULL
                         AND NOT t.is_void
                    THEN t.amount_cents ELSE 0 END
                ), 0) != bc.posted_savings_balance_cents
        """)).fetchall()

        if rows:
            return {
                "name": "ledger_balance_consistency",
                "status": "FAIL",
                "details": f"{len(rows)} balance cache mismatch(es) detected",
                "mismatch_count": len(rows),
            }

        return {"name": "ledger_balance_consistency", "status": "PASS"}

    except Exception as e:
        return {
            "name": "ledger_balance_consistency",
            "status": "FAIL",
            "details": str(e),
        }

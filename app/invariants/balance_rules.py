"""
Invariant: Balance Rules

Verifies that no balance violates the economy's rules:
  - Savings balance must never be negative.
  - Checking balance may only be negative if overdraft protection is enabled
    for that class (join_code) in BankingSettings.
"""

from sqlalchemy import text
from app.extensions import db


def run():
    violations = []

    try:
        # Rule 1: Savings balance is never negative
        savings_violations = db.session.execute(text("""
            SELECT student_id, join_code, posted_savings_balance_cents
            FROM balance_cache
            WHERE posted_savings_balance_cents < 0
        """)).fetchall()

        if savings_violations:
            violations.append(
                f"{len(savings_violations)} student(s) with negative savings balance"
            )

        # Rule 2: Checking balance may only be negative if overdraft protection is enabled
        checking_violations = db.session.execute(text("""
            SELECT bc.student_id, bc.join_code, bc.posted_checking_balance_cents
            FROM balance_cache bc
            LEFT JOIN banking_settings bs ON bs.join_code = bc.join_code
            WHERE bc.posted_checking_balance_cents < 0
              AND (bs.overdraft_protection_enabled IS NULL
                   OR bs.overdraft_protection_enabled = FALSE)
        """)).fetchall()

        if checking_violations:
            violations.append(
                f"{len(checking_violations)} student(s) with negative checking balance"
                " and no overdraft protection"
            )

        if violations:
            return {
                "name": "balance_rules",
                "status": "FAIL",
                "details": "; ".join(violations),
            }

        return {"name": "balance_rules", "status": "PASS"}

    except Exception as e:
        return {
            "name": "balance_rules",
            "status": "FAIL",
            "details": str(e),
        }

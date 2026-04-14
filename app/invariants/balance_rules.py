"""
Invariant: Balance Rules

Verifies that no balance violates the economy's rules:
  - Savings balance must never be negative.
  - Checking balance may only be negative if overdraft protection is enabled
    for that class (join_code) in BankingSettings.

RLS note: banking_settings is protected by Row-Level Security keyed on
app.current_teacher_id. This endpoint runs without a tenant session context,
so the banking_settings join uses INNER JOIN — only classes where we can
confirm overdraft_protection_enabled = FALSE are flagged as violations.
Classes whose banking_settings are not visible (RLS-filtered or not yet
configured) are not flagged to avoid false positives. This means the check
may under-report negative checking violations when RLS filters the settings
rows; a per-teacher invariant run or a privileged DB role would close this gap.

Table: transaction (singular) — Transaction.__tablename__ = 'transaction'
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

        savings_count = len(savings_violations)
        if savings_violations:
            violations.append(
                f"{savings_count} student(s) with negative savings balance"
            )

        # Rule 2: Checking balance may only be negative if overdraft protection
        # is explicitly enabled. INNER JOIN so we only flag when we can confirm
        # the setting is FALSE — avoids false positives when RLS filters rows.
        checking_violations = db.session.execute(text("""
            SELECT bc.student_id, bc.join_code, bc.posted_checking_balance_cents
            FROM balance_cache bc
            INNER JOIN banking_settings bs ON bs.join_code = bc.join_code
            WHERE bc.posted_checking_balance_cents < 0
              AND bs.overdraft_protection_enabled = FALSE
        """)).fetchall()

        checking_count = len(checking_violations)
        if checking_violations:
            violations.append(
                f"{checking_count} student(s) with negative checking balance"
                " and overdraft protection explicitly disabled"
            )

        if violations:
            return {
                "name": "balance_rules",
                "status": "FAIL",
                "details": "; ".join(violations),
                "failure_count": savings_count + checking_count,
            }

        return {"name": "balance_rules", "status": "PASS"}

    except Exception as e:
        return {
            "name": "balance_rules",
            "status": "FAIL",
            "details": "Invariant query failed",
            "failure_count": 1,
        }

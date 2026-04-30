#!/usr/bin/env python3
"""Verify migration squash state for Wave 2 without extra Python deps."""

import os
import subprocess
import sys
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set")

EXPECTED_TABLES = {
    "users", "seats", "classes", "identity_profiles", "user_invite_tokens", "user_recovery_tokens",
    "class_features", "feature_settings", "hall_pass_settings", "rent_settings", "payroll_settings",
    "payroll_rewards", "payroll_fines", "banking_settings", "attendance_sessions", "hall_pass_logs",
    "seat_attendance_state", "assessment_events", "obligation_lifecycle", "obligation_satisfaction",
    "obligation_reversal", "entitlement_events", "ledger_transaction", "ledger_balance_snapshot",
    "store_items", "store_item_visibility", "store_purchases", "redemption_events", "operational_events",
    "audit_log", "incident_events", "incident_summary", "alert_events", "invariant_run_events",
    "job_events", "health_check_events", "interpretation_snapshots", "interpretation_annotations",
    "issues", "issue_status_history", "issue_resolution_actions", "ticket_correlation_packs",
    "announcements", "issue_categories",
}


def verify_head_is_0001() -> None:
    result = subprocess.run(["flask", "db", "heads"], check=True, capture_output=True, text=True)
    output = result.stdout.strip()
    if output != "0001 (head)":
        raise AssertionError(f"Expected single head '0001 (head)', got: {output}")


def fetch_public_tables() -> set[str]:
    query = (
        "SELECT table_name "
        "FROM information_schema.tables "
        "WHERE table_schema = 'public' "
        "ORDER BY table_name;"
    )
    result = subprocess.run(
        ["psql", DATABASE_URL, "-t", "-A", "-c", query],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def verify_canonical_tables_exist() -> None:
    found = fetch_public_tables()
    missing = sorted(EXPECTED_TABLES - found)
    if missing:
        raise AssertionError(f"Missing canonical tables: {', '.join(missing)}")


def main() -> int:
    verify_head_is_0001()
    verify_canonical_tables_exist()
    print("OK: head is 0001 and all 44 canonical tables exist")
    return 0


if __name__ == "__main__":
    sys.exit(main())

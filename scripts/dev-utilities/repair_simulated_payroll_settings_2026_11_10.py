#!/usr/bin/env python3
"""One-time, idempotent repair for the persistent tests/simulated/ database
(SIMULATED_DB_URL) that was 19 migrations behind head, blocked on
migration a7e3c9d1f5b2 ("Make payroll_settings the effective-dated sole
payroll authority"). Issue #1710.

Test infra only. This script refuses to run against anything that doesn't
look like a local simulated/test database (see _assert_safe_target below),
and it never touches production.

## What was wrong

a7e3c9d1f5b2's own preflight (see
migrations/versions/a7e3c9d1f5b2_payroll_settings_effective_dated_authority.py)
refuses to guess at ambiguous or incomplete payroll_settings data rather than
silently inventing a mapping. Two kinds of stale rows in this local database
tripped it, both leftovers from old test runs with no real meaning:

1. 9 `payroll_settings` rows (old "Chemistry" classroom_initializer fixture
   classes, each with zero `payroll_event` rows) had `first_pay_date IS NULL`.
   This script backfills `first_pay_date := created_at` -- the same rule the
   migration's own docstring already uses for `effective_date`, and
   defensible here specifically because nothing ever read these rows.

2. One orphaned RETIRED `payroll_settings` row (policy_uuid
   f367154e-eb85-46d6-a6e7-7c110f599a72, class_id
   6135423f-80cf-43ec-9ce3-4e05ffb98fad -- "Rabbit Hole 101") from a
   mid-test settings change, never referenced by any `payroll_event` (by
   `policy_version_id` or by `policy_uuid` -- verified 0 references either
   way before this script existed). This script deletes it.

## The incident: "Rabbit Hole 101" was not junk

After fixing the above, the upgrade chain progressed, then stopped at a
*different*, later migration gate: e7c2a9d4f610 ("Derive posting from scoped
reconciliation, freeze creation sequence and origin"), which explicitly
refuses to backfill `ledger_transaction.posting_sequence`
("no backfill authorized" -- that migration's own text, a deliberate
human-review gate on financial data, not something this script works
around). The cause was 3 `ledger_transaction` rows with no posting_sequence,
all in the same class 6135423f-80cf-43ec-9ce3-4e05ffb98fad.

That class was investigated, misidentified as dead test-run junk (every
other class in the world was checked and had zero issues/claims/hall-pass
logs, so it looked like an isolated leftover), and -- after an explicit
owner decision -- deleted outright: `DELETE FROM classes WHERE
class_id = '6135423f-80cf-43ec-9ce3-4e05ffb98fad'` (cascading through every
FK'd table: seats, payroll_settings, payroll_event, all 23
ledger_transaction rows, hall_pass_logs, insurance_claims, class_features,
economic_engine, etc.).

That was a mistake. The class was not junk: it was
tests/simulated/test_group_d_pages.py's deliberately-curated anchor fixture
-- the only class in the persistent world with an issue, both insurance
claims, and a hall-pass log, which is exactly why that file picked it.
Worse, this whole persistent world (tests/simulated/conftest.py) is seeded
*once* from a production snapshot and never rebuilt, so there is no script
that can regenerate "Rabbit Hole 101" as it was. No local backup existed
either. The loss (that specific issue, both insurance claims, the hall-pass
log, and the identities behind teacher seat 1 / student seat 3 "Jordan Lee")
is permanent on this machine.

## The actual fix / mitigation

Not a data restoration (impossible) -- a code hardening of the file that
depended on it. tests/simulated/test_group_d_pages.py previously hard-coded
CLASS_ID, TEACHER_SEAT_ID, STUDENT_SEAT_ID, STUDENT_PUBLIC_ID, ISSUE_ID, and
POLICY_UUID as literal constants: a single point of failure against exactly
this kind of loss. It now resolves all of them find-or-create, at run time,
through real production FEATs/routes/service functions (never hand-assembled
ORM rows) -- the same convention the file's own announcement/claim helpers
already used, extended one level up to the anchor class and its two seats:

  - _find_or_create_anchor_classroom(): reuses a "Group D Accessibility
    Fixture"-tagged class if one already exists in the world, or provisions
    a fresh one via create_teacher/create_class/_provision_roster_seat/
    create_student_user_for_seat (the same production service functions
    test_group_l_pages.py already uses for its own anchor), then ensures the
    'insurance' class feature is enabled (app/routes/student.py's
    enforce_student_feature_gates 404s student.file_claim/view_policy
    otherwise).
  - _find_or_create_issue(): files a real issue via FEAT-SUP-001's
    create_issue when none exists for the anchor student, then escalates it
    through the real /admin/issues/<ref>/escalate route when it isn't
    already escalated -- required because admin.view_issue only shows
    student-authored tickets while sysadmin.view_issue only shows escalated
    or teacher-authored ones; the two are only simultaneously true for a
    student ticket the teacher has escalated.
  - _find_or_create_active_policy_uuid(): reuses the fixture insurance
    policy's existing active (GRANTED, not yet CONSUMED/EXPIRED/REVOKED)
    entitlement for the anchor student, or purchases a fresh one via the
    real purchase FEAT.

A future loss of any of these rows -- even the whole anchor class again --
now self-heals on the next test run instead of needing another incident.
See tests/simulated/test_group_d_pages.py's own module docstring for the
full account, and CHANGELOG.md for the summary entry.

## Running this script

    python scripts/dev-utilities/repair_simulated_payroll_settings_2026_11_10.py --database-url "$SIMULATED_DB_URL"

Every statement is scoped by the exact condition it fixes, so this is safe
to run more than once -- a second run reports 0 rows changed. It only ever
touches `payroll_settings`; it does NOT re-attempt the class deletion (that
already happened, is covered above for the record, and is not something to
retroactively "fix" by running more DELETEs).
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


ORPHANED_PAYROLL_SETTINGS_POLICY_UUID = "f367154e-eb85-46d6-a6e7-7c110f599a72"
ORPHANED_PAYROLL_SETTINGS_CLASS_ID = "6135423f-80cf-43ec-9ce3-4e05ffb98fad"


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


def _assert_safe_target(database_url: str) -> None:
    """Refuse anything that doesn't look like a local simulated/test database.

    This is a blunt, conservative check (not a security boundary) matching
    this project's "dev DB is protected, never run destructive ops against
    anything that isn't obviously a scratch/test database" convention.

    Checks the parsed host and database name specifically, not the whole URL
    string -- a substring search over the full URL is bypassable by a
    "test"/"localhost" token anywhere in it (credentials, query parameters),
    which would authorize this against a real, remote, or non-test database.
    """
    url = make_url(database_url)
    host = (url.host or "").lower()
    database = (url.database or "").lower()
    looks_local = host in _LOOPBACK_HOSTS
    looks_test = "test" in database or "simulated" in database
    if not (looks_local and looks_test):
        print(
            "Refusing to run: --database-url does not look like a local "
            "test/simulated database (expected host in "
            f"{sorted(_LOOPBACK_HOSTS)!r} AND 'test' or 'simulated' in the "
            "database name). This script never runs against production.",
            file=sys.stderr,
        )
        sys.exit(1)


def repair(database_url: str) -> None:
    _assert_safe_target(database_url)
    engine = create_engine(database_url)
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("payroll_settings")}

    # a7e3c9d1f5b2 drops availability_state and payroll_event.policy_version_id,
    # and makes first_pay_date NOT NULL. Once it has run, there is nothing left
    # for this script to do -- it predates that migration and exists to unblock
    # it, not to run again afterward.
    if "availability_state" not in columns:
        print(
            "payroll_settings.availability_state does not exist: a7e3c9d1f5b2 "
            "has already run on this database. Nothing to repair."
        )
        return

    with engine.begin() as conn:
        deleted = conn.execute(
            text(
                """
                DELETE FROM payroll_settings
                WHERE policy_uuid = :policy_uuid
                  AND class_id = :class_id
                  AND availability_state = 'RETIRED'
                  AND NOT EXISTS (
                      SELECT 1 FROM payroll_event e
                      WHERE e.class_id = payroll_settings.class_id
                        AND (e.policy_version_id = 1 OR e.policy_uuid = payroll_settings.policy_uuid)
                  )
                """
            ),
            {"policy_uuid": ORPHANED_PAYROLL_SETTINGS_POLICY_UUID, "class_id": ORPHANED_PAYROLL_SETTINGS_CLASS_ID},
        ).rowcount
        print(f"Deleted {deleted} orphaned RETIRED payroll_settings row(s)")

        backfilled = conn.execute(
            text(
                """
                UPDATE payroll_settings
                SET first_pay_date = created_at
                WHERE first_pay_date IS NULL
                  AND pay_schedule_type = 'biweekly'
                  AND NOT EXISTS (SELECT 1 FROM payroll_event e WHERE e.class_id = payroll_settings.class_id)
                """
            )
        ).rowcount
        print(f"Backfilled first_pay_date on {backfilled} payroll_settings row(s)")

    with engine.connect() as conn:
        null_first_pay_date = conn.execute(
            text("SELECT count(*) FROM payroll_settings WHERE first_pay_date IS NULL")
        ).scalar()
        ambiguous_classes = conn.execute(
            text(
                """
                SELECT count(*) FROM (
                    SELECT e.class_id FROM payroll_event e WHERE e.policy_version_id IS NOT NULL
                    GROUP BY e.class_id
                    HAVING (SELECT count(*) FROM payroll_settings ps WHERE ps.class_id = e.class_id) <> 1
                ) x
                """
            )
        ).scalar()

    print(f"Remaining payroll_settings rows with NULL first_pay_date: {null_first_pay_date}")
    print(f"Remaining ambiguous classes (payroll_event without exactly 1 payroll_settings row): {ambiguous_classes}")
    if null_first_pay_date or ambiguous_classes:
        print("a7e3c9d1f5b2's preflight will still refuse. Investigate before running `flask db upgrade`.")
        sys.exit(1)
    print("a7e3c9d1f5b2's preflight conditions are clear.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True, help="e.g. $SIMULATED_DB_URL")
    args = parser.parse_args()
    repair(args.database_url)


if __name__ == "__main__":
    main()

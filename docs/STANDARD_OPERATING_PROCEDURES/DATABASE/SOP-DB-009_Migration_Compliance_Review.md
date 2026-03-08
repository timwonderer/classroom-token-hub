# Migration Compliance Review Report

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DB-009| 1.2 | 2026-03-08 | 1.1 |Normative|

**Branch:** `codex/v2.0`
**Status:** Current-state readiness summary for v2 live testing

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Executive Summary

The earlier migration-compliance audit remains historically useful, but it should not be read as the current branch-status summary. The current v2 branch is merge-consolidated, the active heads are resolved in repo, and the PostgreSQL test suite passes. The remaining migration concern is operational: documenting and rehearsing the exact upgrade, verification, and rollback workflow before live testing and production.

## VI. Current State

### Confirmed Now

- Active engineering branch is `codex/v2.0`.
- Current repository migration heads are resolved by `e8f1a2b3c4d5_merge_remaining_v2_heads.py`.
- Membership constraint hardening is present in `a11213ca4afb_harden_class_economy_membership_checks.py`.
- Full PostgreSQL suite passes on the v2 test database:
  - `664 passed, 1 skipped`

### Still Important

- Historical migration idempotency concerns still exist in older parts of the migration chain.
- A green test suite does not replace upgrade rehearsal on the dev/migration database.
- Production safety depends on the runbooks in `SOP-DEP-022` and `SOP-DEP-023`, not on repository state alone.

## VII. Remaining Exceptions and Readiness Gaps

### Required Before Live Testing

- Rehearse `flask db upgrade` on the team-configured v2 dev/migration database.
- Confirm head state and `alembic_version` before and after rehearsal.
- Run the PostgreSQL test suite on the team-configured test database.
- Execute the smoke-route checklist from the v2 live-test runbook.

### Required Before Production

- Confirm backup and restore workflow.
- Confirm operator rollback decision points.
- Re-run migration validation on a production-like snapshot or staging-equivalent environment.

## VIII. Current Compliance Interpretation

- The old audit remains a historical catalog of migration-policy debt.
- The current v2 release-readiness question is narrower:
  - is the active migration graph coherent?
  - can operators rehearse upgrade and verification safely?
  - are the remaining exceptions documented and accepted before live testing?

## IX. Required Validation Commands

```bash
flask db heads
flask db current
flask db upgrade
DATABASE_URL=<team-test-db-url> pytest -q
```

## X. Owner Action

Before live testing, attach the output of the live-test runbook and record:

- head state before upgrade
- head state after upgrade
- smoke-check result
- rollback decision: not needed / needed / blocked
## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

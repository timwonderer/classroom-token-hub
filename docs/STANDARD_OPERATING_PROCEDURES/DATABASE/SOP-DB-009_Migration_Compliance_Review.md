# Migration Compliance Review Report

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-009       | 1.3     | 2026-03-31     | 1.2        | Normative       |

**Branch:** `codex/v2.0`
**Status:** Current-state readiness summary for v2 live testing

## I. Purpose
To serve as the compliance review report for database migrations prior to v2 deployment tracking readiness and unresolved operational gaps.

## II. Scope
Current v2 live-test preparations concerning the database state and testing runs.

## III. Authority Level
Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_Core_Invariants.md`
- `SOP-DB-011_Migration_Specifications.md`

## V. Executive Summary

The earlier migration-compliance audit remains historically useful, but it should not be read as the current branch-status summary. The current v2 branch is merge-consolidated, the active heads are resolved in repo, and the PostgreSQL test suite passes. The remaining migration concern is operational: documenting and rehearsing the exact upgrade, verification, and rollback workflow before live testing and production.

## VI. Current State

### Confirmed Now

- Active engineering branch is `codex/v2.0`.
- Current repository migration heads are resolved by `e8f1a2b3c4d5_merge_remaining_v2_heads.py`.
- Membership constraint hardening is present in `a11213ca4afb_harden_class_economy_membership_checks.py`.
- Local rehearsal on 2026-03-30 confirmed:
  - `flask db heads` -> `q9r0s1t2u3v4 (head)`
  - `flask db current` -> `q9r0s1t2u3v4 (head)`
  - `DATABASE_URL=<team-dev-migration-db-url> flask db upgrade` completed without revision drift

### Current Validation Baseline

- The latest PostgreSQL validation run on 2026-03-31 passed:
  - `708 passed, 1 skipped`
- Repository-side blocker triage is complete for the current branch state.

### Still Blocking Final Operational Closure

- Manual smoke-route execution still requires the named operator record from the live-test rehearsal.
- If the rehearsal uses the solo-operator exception from `SOP-DEP-022`, the record must explicitly document that exception and its required conditions instead of naming a separate independent verifier.
- Final Thread 3 closure still depends on the adjacent launch threads landing and validating cleanly.

### Still Important

- Historical migration idempotency concerns still exist in older parts of the migration chain.
- A green test suite does not replace upgrade rehearsal on the dev/migration database.
- Production safety depends on the runbooks in `SOP-DEP-022` and `SOP-DEP-023`, not on repository state alone.

## VII. Remaining Exceptions and Readiness Gaps

### Required Before Live Testing

- Capture named operator confirmation in the rehearsal record.
- If a separate verifier is unavailable, document solo-operator exception usage and confirm the additional solo-mode conditions from `SOP-DEP-022`.
- Execute the smoke-route checklist from the v2 live-test runbook and record the result now that automated validation is green again.

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
bash scripts/check-migrations.sh
DATABASE_URL=<team-dev-migration-db-url> flask db upgrade
DATABASE_URL=<team-dev-migration-db-url> flask db current
DATABASE_URL=<team-test-db-url> pytest -q
```

## X. Owner Action

Before live testing, attach the output of the live-test runbook and record:

- head state before upgrade
- head state after upgrade
- smoke-check result
- rollback decision: not needed / needed / blocked
- operator confirmation
- independent verifier confirmation, or explicit solo-operator exception record

## XI. Deferral Boundary

- This compliance review is a current-state readiness summary, not a full rewrite of the historical migration audit record.
- Broader migration-policy cleanup, taxonomy changes, and architecture-driven documentation restructuring remain deferred until the post-port refactor targets are ready.

## XII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.

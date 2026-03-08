# v2 Production Transition Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-023| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

Provide the explicit operator workflow for moving the current v2 branch from live-test candidate to production transition.

## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Preconditions

- `codex/v2.0` is the approved deployment branch.
- Live-test runbook has been executed successfully.
- Migration compliance status has been reviewed.
- Backup, maintenance window, and rollback contacts are confirmed.
- Team-owned production and pre-production database targets are identified before any migration step begins.

## VI. Pre-Production Checklist

1. Enable maintenance mode if the deployment requires a protected window.
2. Verify current production backup or snapshot and test restore instructions.
3. Confirm migration head state and target revision.
4. Confirm operator sign-off from engineering and operations.
5. Reconfirm smoke checklist and escalation path.

## VII. Upgrade Flow

1. Put the environment into maintenance mode.
2. Apply migrations.
3. Deploy application code.
4. Run post-deploy smoke checks before reopening the app.

## VIII. Post-Migration Verification

Verify:

- app boots normally
- teacher and student login pages load
- current-class switching works
- class-scoped admin actions respect membership
- hall-pass verification path works with public teacher identifier
- no unexpected migration head drift is present

## IX. Rollback Policy

- If migration fails before app reopen, rollback to the pre-deploy backup/snapshot.
- If post-deploy smoke checks fail and cannot be corrected within the maintenance window, rollback.
- If migration is structurally successful but business behavior is incorrect, hold maintenance mode until rollback or fix-forward is approved.

## X. Sign-Off Record

Record:

- deployment time
- operator
- branch SHA
- migration result
- smoke-check status
- reopen time
- rollback decision
## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

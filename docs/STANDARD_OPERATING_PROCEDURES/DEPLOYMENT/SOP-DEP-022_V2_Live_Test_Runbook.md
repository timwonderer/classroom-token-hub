# v2 Live-Test Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-022| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

Provide the exact operator workflow for preparing the current v2 branch for live testing.

## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Environment Truth

- Branch: `codex/v2.0`
- Dev/migration DB: the team-configured v2 dev database for migration rehearsal
- Test DB: the team-configured PostgreSQL test database used for v2 validation

## VI. Pre-Live-Test Checklist

1. Confirm branch and clean worktree.
2. Confirm migration head state:

```bash
flask db heads
flask db current
```

3. Rehearse migration upgrade on the team-configured dev/migration DB:

```bash
DATABASE_URL=<team-dev-migration-db-url> flask db upgrade
```

4. Run the full PostgreSQL test suite:

```bash
DATABASE_URL=<team-test-db-url> pytest -q
```

5. Record the result and confirm it matches or exceeds the latest validated baseline:
   - `664 passed, 1 skipped`

## VII. Smoke Routes

Verify these paths manually after upgrade:

- `/admin/login`
- `/student/login`
- `/docs`
- teacher current-class switching
- student add-class and switch-class flows
- admin export in a selected class
- hall-pass verification by public teacher identifier

## VIII. Seed and Fixture Expectations

- Use canonical v2 class scope:
  - `ClassEconomy`
  - admin `ClassMembership`
  - student `ClassMembership`
- Do not assume TeacherBlock-only authority for class access.

## IX. Backup and Rollback Decision

Before live testing:

1. Confirm a recoverable snapshot or backup of the live-test target database exists.
2. If migration rehearsal fails, stop and rollback before exposing testers.
3. If smoke checks fail after upgrade, revert to backup or hold the environment in maintenance mode until resolved.

## X. Required Output Record

Capture and store:

- migration head state before upgrade
- migration head state after upgrade
- pytest summary
- smoke-check status
- final go/no-go decision for live testing
## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

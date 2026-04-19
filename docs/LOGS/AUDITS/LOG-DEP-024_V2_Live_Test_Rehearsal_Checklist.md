# LOG-DEP-024: V2 Live-Test Rehearsal Checklist

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-DEP-024 | 1.0 | 2026-04-01 | N/A | Informative |

## I. Purpose

Provide a repo-tracked checklist and fill-in artifact for the v2 live-test rehearsal described in `SOP-DEP-022_V2_Live_Test_Runbook.md`.

## II. Scope

Use this checklist when executing the live-test rehearsal for `codex/v2.0` against the configured v2 dev/migration database and PostgreSQL test database.

## III. Dependencies

- `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-009_Migration_Compliance_Review.md`
- `docs/development/tracking/V2_LAUNCH_READINESS_MATRIX.md`

## IV. Operator Checklist
> [!NOTE]
> Make a copy of this document to record findings of live test rehearsal. This document shall remain as a reference. 

Mark each item when complete.

### 1. Branch and Environment

- [ ] Current branch is `codex/v2.0`
- [ ] Worktree is clean
- [ ] `.env` points to the intended v2 dev/migration database
- [ ] PostgreSQL test database target is identified for validation run

### 2. Pre-Upgrade Commands

- [ ] `flask db heads`
- [ ] `flask db current`
- [ ] `bash scripts/check-migrations.sh`

Record outputs:

```text
flask db heads:

flask db current:

bash scripts/check-migrations.sh:

```

### 3. Migration Rehearsal

- [ ] `DATABASE_URL=<team-dev-migration-db-url> flask db upgrade`
- [ ] `DATABASE_URL=<team-dev-migration-db-url> flask db current`
- [ ] No revision drift or unexpected migration error occurred

Record outputs:

```text
DATABASE_URL=<team-dev-migration-db-url> flask db upgrade:

DATABASE_URL=<team-dev-migration-db-url> flask db current:

```

### 4. PostgreSQL Validation

- [ ] `DATABASE_URL=<team-test-db-url> pytest -q`
- [ ] Result meets or exceeds current baseline

Record result:

```text
DATABASE_URL=<team-test-db-url> pytest -q:
Expected baseline: 708 passed, 1 skipped
Actual result:
```

### 5. Manual Smoke Routes

- [ ] `/admin/login`
- [ ] `/student/login`
- [ ] `/docs`
- [ ] `POST /admin/current-class`
- [ ] `/student/add-class`
- [ ] `POST /student/switch-class/<join_code>`
- [ ] `/admin/export-students?join_code=<owned-join-code>`
- [ ] `/verify/hallpass/<teacher_public_token>`

Record results:

```text
/admin/login:
/student/login:
/docs:
POST /admin/current-class:
/student/add-class:
POST /student/switch-class/<join_code>:
/admin/export-students?join_code=<owned-join-code>:
/verify/hallpass/<teacher_public_token>:
```

### 6. Ownership and Sign-Off

- [ ] Primary operator recorded
- [ ] Independent verifier recorded, or solo-operator exception documented
- [ ] Engineering escalation owner recorded
- [ ] Go/no-go decision recorded

## V. Rehearsal Record

Fill this out during the rehearsal and finalize it after commit SHA is known.

```text
Live-Test Rehearsal Record
Date:
Branch: codex/v2.0
Commit SHA:
Primary operator:
Independent verifier:
Solo-operator exception used: yes / no
Engineering escalation owner:
Database target:

Pre-upgrade checks
- flask db heads:
- flask db current:
- bash scripts/check-migrations.sh:

Upgrade
- DATABASE_URL=<team-dev-migration-db-url> flask db upgrade:
- DATABASE_URL=<team-dev-migration-db-url> flask db current:

Test suite
- DATABASE_URL=<team-test-db-url> pytest -q:

Smoke routes
- /admin/login:
- /student/login:
- /docs:
- POST /admin/current-class:
- /student/add-class:
- POST /student/switch-class/<join_code>:
- /admin/export-students?join_code=<owned-join-code>:
- /verify/hallpass/<teacher_public_token>:

Decision
- Live-test go/no-go:
- Follow-up issues:
- Operator confirmation:
- Independent verifier confirmation:
- Solo-operator exception notes:
```

## VI. Finalization Notes

- Execute the rehearsal first.
- Commit the validated branch state.
- Populate `Commit SHA` with `git rev-parse HEAD`.
- Keep this artifact immutable after finalization for the rehearsed commit.

## VII. Amendment

Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.

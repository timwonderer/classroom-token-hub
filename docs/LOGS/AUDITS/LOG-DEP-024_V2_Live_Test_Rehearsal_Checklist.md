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
- `docs/development/V2_LAUNCH_READINESS_MATRIX.md`

## IV. Operator Checklist

Mark each item when complete.

### 1. Branch and Environment

- [x] Current branch is `codex/v2.0`
- [x] Worktree is clean
- [x] `.env` points to the intended v2 dev/migration database
- [x] PostgreSQL test database target is identified for validation run

### 2. Pre-Upgrade Commands

- [x] `flask db heads`
- [x] `flask db current`
- [x] `bash scripts/check-migrations.sh`

Record outputs:

```text
flask db heads:
2bde3e5f00ac (head)
flask db current:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
2bde3e5f00ac (head)
bash scripts/check-migrations.sh:
┌────────────────────────────────────────────────────┐
│   Database Migration Pre-Flight Check             │
└────────────────────────────────────────────────────┘

🔍 Checking for multiple migration heads...
   Found 1 migration head(s)
✓ Single migration head: 2bde3e5f00ac
  Message: Add bypass_cwi_warnings to store_items, rent_settings, and insurance_policies

🔍 Validating migration file syntax...
   Validated 183 migration file(s)

❌ Migration validation errors:
   • o5p6q7r8s9t0_prepare_seats_for_identity_overhaul.py: Missing upgrade() function
   • o5p6q7r8s9t0_prepare_seats_for_identity_overhaul.py: Missing downgrade() function
   • l2m3n4o5p6q7_strict_feature_and_hall_pass_settings_scope.py: Missing upgrade() function
   • l2m3n4o5p6q7_strict_feature_and_hall_pass_settings_scope.py: Missing downgrade() function
   • i9j0k1l2m3n4_converge_class_scope_to_canonical_anchor.py: Missing upgrade() function
   • i9j0k1l2m3n4_converge_class_scope_to_canonical_anchor.py: Missing downgrade() function
   • j0k1l2m3n4o5_scope_payroll_cache_by_class.py: Missing upgrade() function
   • j0k1l2m3n4o5_scope_payroll_cache_by_class.py: Missing downgrade() function
   • n4o5p6q7r8s9_contract_class_lifecycle_and_feature_rows.py: Missing upgrade() function
   • n4o5p6q7r8s9_contract_class_lifecycle_and_feature_rows.py: Missing downgrade() function
```

### 3. Migration Rehearsal

- [x] `DATABASE_URL=<team-dev-migration-db-url> flask db upgrade`
- [x] `DATABASE_URL=<team-dev-migration-db-url> flask db current`
- [x] No revision drift or unexpected migration error occurred

Record outputs:

```text
DATABASE_URL=<team-dev-migration-db-url> flask db upgrade:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
DATABASE_URL=<team-dev-migration-db-url> flask db current:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
2bde3e5f00ac (head)
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


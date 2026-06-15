# LOG-ARC-050 V2 Live-Test Rehearsal Report 04-03-2026

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-ARC-050| 1.1 | 2026-04-03 | 1.0 | Informative |

## I. Purpose

Provide a report on v2 live-test rehearsal described in `SOP-DEP-022_V2_Live_Test_Runbook.md`.

## II. Scope

Configured v2 dev/migration database and PostgreSQL test database using codex/v2.0 branch.

## III. Dependencies

- `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-009_Migration_Compliance_Review.md`
- `docs/TRACKING/V2_LAUNCH_READINESS_MATRIX.md`



## IV. Live-Test Rehearsal Record
**Contextual Information:**
- Date: April 3, 2026
- Branch: codex/v2.0
- Commit SHA: 2b5d914a455e83935a08258ad079aafcdf59fd26

**Chain-of-Custody:**
- Primary operator: Timothy Chang (@timwonderer)
- [x] Check for Solo-Operator Exception. Skip to **Database target** subsection.
- Independent verifier: N/A
- Engineering escalation owner: N/A

**Database Information:**
- Database target: classroom_economy

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
✓ All migration files are valid

┌────────────────────────────────────────────────────┐
│   ✓ All Migration Checks Passed                   │
└────────────────────────────────────────────────────┘

✓ Safe to deploy

```

### 3. Migration Rehearsal

- [x] `DATABASE_URL=<team-dev-migration-db-url> flask db upgrade`
- [x] `DATABASE_URL=<team-dev-migration-db-url> flask db current`
- [x] No revision drift or unexpected migration error occurred

Record outputs:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy flask db upgrade:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy flask db current:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
2bde3e5f00ac (head)
```

### 4. PostgreSQL Validation

- [x] `DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy_test pytest -q`
- [x] Result meets or exceeds current baseline

Record result:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy_test pytest -q:
Expected baseline: 708 passed, 1 skipped
Actual result:
================== 720 passed, 1 skipped in 388.87s (0:06:28) ==================

Final rerun result after remediation:
================== 720 passed, 1 skipped in 388.87s (0:06:28) ==================
```

### 5. Manual Smoke Routes

- [x] `/admin/login`
- [x] `/student/login`
- [x] `/docs`
- [x] `POST /admin/current-class`
- [x] `/student/add-class`
- [x] `POST /student/switch-class/<join_code>`
- [x] `/admin/export-students?join_code=<owned-join-code>`
- [x] `/verify/hallpass/<teacher_public_token>`

Record results:

```text
/admin/login: 200
/student/login: 200
/docs: 200
POST /admin/current-class: 200
/student/add-class: 200
POST /student/switch-class/<join_code>: 200
/admin/export-students?join_code=<owned-join-code>: 200
/verify/hallpass/<teacher_public_token>: 200

Behavioral assertions from final rerun:
- student claim/setup completed successfully
- student username setup completed successfully
- student joined a second class successfully
- class switch persisted correctly with no snap-back to the original class
- class-scoped seat and membership records were present for the exercised join codes
- teacher-as-student account reused one identity across classes while materializing class-local access
```
### Decision
#### Initial rehearsal result: `NO-GO`
#### Rerun result after remediation: `GO`
#### Final live-test go/no-go: `GO`
#### Defects found during initial rehearsal, now resolved:
  - Migration pre-flight validation falsely reported missing `upgrade()` / `downgrade()` functions in multiple migration files.
  - PostgreSQL validation encountered transient test-database contention and reported `3 failed, 713 passed, 1 skipped` before remediation.
  - Manual smoke route HTTP `200` responses masked blocking behavioral defects in student claim, class creation/class selection, TASA identity handling, and class switching.
  - Existing local dev rows created before the fixes required cleanup/backfill because some claimed `TeacherBlock` rows had no matching v2 `Seat` or `ClassMembership`.
#### Operator confirmation:
Initial rehearsal exposed the defects listed above. After remediation, migration validation passed, the full pytest suite passed, and the manual smoke route completed successfully end-to-end. Final status is based on the successful rerun recorded against the clean committed SHA above.
#### Independent verifier confirmation: N/A
#### Solo-operator exception notes: 
Solo operator performed the initial rehearsal, identified blocking defects during smoke execution, applied remediation, and completed the final successful rerun with automated validation and manual smoke confirmation.
```

## VI. Finalization Notes

- Execute the rehearsal first.
- Commit the validated branch state.
- Populate `Commit SHA` with `git rev-parse HEAD`.
- Keep this artifact immutable after finalization for the rehearsed commit.

## VII. Amendment

Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.

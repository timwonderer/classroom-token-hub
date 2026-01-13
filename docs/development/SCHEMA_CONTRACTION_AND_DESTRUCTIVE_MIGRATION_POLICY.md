# Schema Contraction & Destructive Migration Policy

> [!WARNING]
> All destructive schema changes (column/table removal, relationship deletion, FK removal) MUST adhere to this policy.
> Violations constitute a breach of engineering standards and require explicit exception approval.

⸻

## 1. Governing Principle

Schema deletion is not a refactor. It is a *high-risk operational change* with delayed failure modes.

Therefore, destructive schema changes require staged compatibility windows designed to surface hidden dependencies **early, loudly, and reversibly**.



## 2. Mandatory Pattern: Expand and Contract

All schema element removal MUST follow a minimum three-release sequence.
Skipping phases is prohibited.

### Phase 1: Expand (Release N) 

Goal: Decouple application logic from the legacy schema element.

Requirements:
- New schema elements (if replacing) exist alongside the legacy element.
- Application reads from and/or writes to the new schema.
- Legacy schema element remains present and populated, or is safely ignored.
- NO destructive migrations are permitted in this release.

### Phase 2: Contract Code (Release N+1)

Goal: Prove runtime independence from the legacy schema.

Requirements:
- The legacy attribute/column is removed from the SQLAlchemy model definition.
- The database column remains physically present.
- The application must operate fully without the attribute.
- Any hidden usage (runtime kwargs, templates, legacy logic) must fail loudly.

> [!NOTE]
> This phase intentionally converts silent coupling into immediate runtime failure while rollback remains trivial (code-only revert, no database restore).

### Phase 3: Contract Database (Release N+2)

Goal: Permanent cleanup of unused schema.

Requirements:
- A migration drops the legacy column/table.
- This migration MUST be isolated (no unrelated changes).
- down_revision MUST align exactly with the expected migration head to avoid branch divergence.

## 3. Migration Robustness Requirements

### 3.1 Constraint Name Agnosticism

Rule: Migrations MUST NOT assume constraint names.

> [!CAUTION]
> Constraint names vary across environments (engine versions, historical migrations).
Hardcoded names are a known cause of production migration failure.

Requirement:
- Constraints MUST be discovered dynamically via database inspection.
- Dropping constraints by assumed name is prohibited.

Non-compliant example:
```python   
op.drop_constraint('students_teacher_id_fkey', 'students', type_='foreignkey')
```

Compliant pattern:
```python       
from sqlalchemy import inspect

bind = op.get_bind()
inspector = inspect(bind)

for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

### 3.2 Data Migration Safety

- Batching: Large updates MUST b    e batched to avoid prolonged locks.
- Idempotency: Migrations SHOULD be re-runnable when feasible (IF EXISTS, conditional checks).

## 4. Migration Rehearsal Policy

> [!WARNING]
> Destructive migrations MUST be rehearsed against a production-like clone prior to merge.

Minimum fidelity:
- Database engine (Postgres)
- Engine version
- Full schema history

Verification:
- upgrade succeeds
- downgrade succeeds (unless explicitly declared irreversible)

Exception Handling:
- If rehearsal is not possible, the PR MUST be labeled:
`UNSAFE: NO MIGRATION REHEARSAL`
- Proceeding without rehearsal constitutes explicit acceptance of elevated production risk.

## 5. Testing Policy for Schema Changes

### 5.1 Prohibition on Mechanical Test Fixes

> [!WARNING]
> Tests failing due to schema/model changes MUST NOT be “fixed” mechanically.

Disallowed behavior:
- Removing constructor arguments without reviewing test intent.

Required action:
- Re-evaluate what the test was proving.
- Rewrite the test to validate the behavior without relying on deprecated schema.

### 5.2 Mandatory Workflow Coverage

Before merging destructive schema changes, the following workflows MUST have valid, non-mocked, route-level test coverage:
- Account claiming (student onboarding)
- Money transfers (payments, peer-to-peer)
- Student creation (including association flows)
- Admin / teacher-scoped student operations

> [!WARNING]
> These paths frequently contain legacy logic and are often exercised only in production.

## 6. Smoke Testing Requirement

> [!WARNING]
> Critical workflows MUST be smoke-tested before merging destructive schema changes.

Acceptable methods:
- Automated smoke tests
- Manual verification when automation does not yet exist

> [!CAUTION]
> Unit tests often mock the ORM or database layer. This is the very boundary that fails during schema contraction.

## 7. Scope of This Policy

This document IS:
- A governing policy for destructive schema changes
- A source of enforcement authority for reviews and CI gates

This document IS NOT:
- An Alembic implementation guide
- A CI configuration manual
- A replacement for incident response documentation

## 8. Policy Summary

- Compatibility windows are mandatory.
- Silence during testing is not evidence of safety.
- Schema deletion must be staged to fail **early, loudly, and reversibly**.

Status: Canonical, locked-in policy.    
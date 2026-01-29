# Migration Specifications

This document consolidates all policies, best practices, and guides related to database migrations, schema changes, and deprecation patterns for the Classroom Economy application.

---

# Table of Contents

1. [Schema Change Policy](#1-schema-change-policy)
   - [Schema Change Gate](#schema-change-gate)
   - [Schema Contraction & Destructive Migration Policy](#schema-contraction--destructive-migration-policy)
2. [Migration Best Practices](#2-migration-best-practices)
   - [Core Principle: Idempotency](#core-principle-migrations-must-be-idempotent)
   - [Required Checks](#required-checks-before-schema-changes)
   - [Downgrade Functions](#downgrade-functions)
   - [Testing & Review](#migration-review-checklist)
3. [Migration Guide & Troubleshooting](#3-migration-guide--troubleshooting)
   - [Branch Consolidation & Multiple Heads](#branch-consolidation--multiple-heads)
   - [Verification Commands](#verification-commands)
4. [Deprecation Standards](#4-deprecation-standards)
   - [Deprecated Symbols Registry](#deprecated-symbols-registry)
   - [Deprecated Code Patterns](#deprecated-code-patterns)

---

# 1. Schema Change Policy

## Schema Change Gate

**Purpose:**  
This gate is **PR‑blocking by design**. A schema-affecting PR that does not explicitly pass this gate **MUST NOT** be merged.

### When This Gate Applies

This gate is REQUIRED if a pull request includes **any** of the following:

- Dropping or renaming a column
- Dropping or renaming a table
- Removing or changing foreign keys
- Replacing one-to-one or one-to-many relations with association tables
- Removing model attributes that map to existing database columns

### PR Classification (Required)

Every schema-affecting PR MUST declare **exactly one** classification at the top of the PR description:

- [ ] **EXPAND** – Additive, backward-compatible (no removals)
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal, DB schema unchanged
- [ ] **CONTRACT (DATABASE)** – Destructive migration only

### Mandatory Checklist (PR-Blocking)

#### Expand / Contract Compliance
- [ ] This PR represents **only one phase** of Expand / Contract
- [ ] No destructive DB changes are included in EXPAND or CONTRACT (CODE ONLY)
- [ ] CONTRACT (DATABASE) PR contains **no unrelated code changes**

#### Model & Runtime Safety
- [ ] Legacy attributes removed from models (if applicable)
- [ ] Application boots and runs without legacy attributes
- [ ] No runtime access to deprecated attributes remains

#### Deprecated Symbol Audit
- [ ] All deprecated attributes/columns are listed explicitly
- [ ] No deprecated symbols appear in application code
- [ ] Any allowlisted exceptions (tests/migrations) are documented

#### Migration Robustness
- [ ] No constraint names are hardcoded
- [ ] Constraints are discovered dynamically via inspection
- [ ] Migrations are idempotent where feasible

#### Migration Rehearsal
- [ ] Migration rehearsed on production-like clone
- [ ] `upgrade` succeeds
- [ ] `downgrade` succeeds **or** migration declared irreversible
- **If rehearsal not performed:**
    - [ ] PR labeled **UNSAFE: NO MIGRATION REHEARSAL**

#### Testing Requirements
- [ ] No tests were fixed mechanically
- [ ] Tests affected by schema change were re-evaluated for intent
- **Mandatory workflows verified:**
    - [ ] Account claiming
    - [ ] Money transfer
    - [ ] Student creation / association
    - [ ] Admin / teacher-scoped operations

## Schema Contraction & Destructive Migration Policy

> [!WARNING]
> All destructive schema changes (column/table removal, relationship deletion, FK removal) MUST adhere to this policy.

### Governing Principle

Schema deletion is not a refactor. It is a *high-risk operational change*. Therefore, destructive schema changes require staged compatibility windows designed to surface hidden dependencies **early, loudly, and reversibly**.

### Mandatory Pattern: Expand and Contract

All schema element removal MUST follow a minimum three-release sequence.

#### Phase 1: Expand (Release N)
*Goal: Decouple application logic from the legacy schema element.*
- New schema elements exist alongside the legacy element.
- Application reads/writes to the new schema.
- Legacy schema element remains present and populated.
- **NO destructive migrations permitted.**

#### Phase 2: Contract Code (Release N+1)
*Goal: Prove runtime independence from the legacy schema.*
- The legacy attribute/column is removed from the SQLAlchemy model definition.
- The database column remains physically present.
- The application must operate fully without the attribute.
- Any hidden usage must fail loudly.

#### Phase 3: Contract Database (Release N+2)
*Goal: Permanent cleanup of unused schema.*
- A migration drops the legacy column/table.
- This migration MUST be isolated (no unrelated changes).
- `down_revision` MUST align exactly with the expected migration head.

### Migration Robustness Requirements

#### Constraint Name Agnosticism
**Rule:** Migrations MUST NOT assume constraint names. Constraints MUST be discovered dynamically via database inspection.

*Compliant pattern:*
```python
from sqlalchemy import inspect
bind = op.get_bind()
inspector = inspect(bind)
for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

---

# 2. Migration Best Practices

This section outlines best practices for creating safe, idempotent migrations.

## Core Principle: Migrations Must Be Idempotent

**Idempotent migrations** can be run multiple times without causing errors. This prevents failures when:
1. Schema changes were applied manually.
2. Previous runs failed partially.
3. Migrations from different branches are merged.

## Required Checks Before Schema Changes

### 1. Check if Columns Exist Before Adding
```python
def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    if not column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.add_column(sa.Column('column_name', sa.Integer()))
```

### 2. Check if Foreign Keys Exist
```python
def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys
```

### 3. Check if Indexes Exist
```python
def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes
```

## Downgrade Functions
Downgrade functions should also be idempotent and check for existence before dropping.

## Migration Review Checklist
- [ ] All `add_column` calls check if column exists first.
- [ ] All `create_foreign_key` calls check if FK exists first.
- [ ] All `create_index` calls check if index exists first.
- [ ] Downgrade function mirrors upgrade with existence checks.
- [ ] Migration handles ENUM types correctly (PostgreSQL).

---

# 3. Migration Guide & Troubleshooting

## Branch Consolidation & Multiple Heads

### The "Multiple Heads" Issue
If multiple branches create migrations from the same base, Alembic sees "multiple heads".
**Solution:** Create a **merge migration** using `flask db merge heads`.

### Common Commands

```bash
flask db current          # Show current migration
flask db history          # Show migration history
flask db upgrade          # Apply pending migrations
flask db downgrade <rev>  # Rollback to specific revision
```

## Verification Commands

After upgrading, verify changes in the database:

```sql
-- Verify migration history
SELECT * FROM alembic_version;
```

---

# 4. Deprecation Standards

## Deprecated Symbols Registry

This registry tracks symbols that are **explicitly prohibited** from appearing in application code.

The authoritative, machine-enforced list lives in:
`docs/development/DEPRECATED_SYMBOLS.txt`

### Current Deprecated Symbols
| Symbol | Reason | Status |
|------|--------|--------|
| `teacher_id` | Legacy single-tenant coupling replaced by StudentTeacher association | Active |

## Deprecated Code Patterns

### 1. `datetime.utcnow()` (Python 3.12+)
**Issue:** Deprecated in favor of `datetime.now(datetime.UTC)`.
**Fix:**
```python
from datetime import datetime, UTC
timestamp = datetime.now(UTC)
```

### 2. `Query.get()` (SQLAlchemy 2.0+)
**Issue:** Deprecated in favor of `session.get(Model, id)`.
**Fix:**
```python
# OLD
student = Student.query.get(student_id)
# NEW
from app.extensions import db
student = db.session.get(Student, student_id)
```

# Migration Compliance Review Report

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-009       | 1.0     | 2026-03-01     | N/A        | Normative                 |

**Branch:** `claude/review-migration-compliance-9Qj73`
**Date:** 2026-02-04
**Reviewer:** Claude Code Agent
**Status:** 🔴 **CRITICAL ISSUES FOUND**

---

## Executive Summary

A comprehensive audit of all 107 migration files revealed **significant compliance violations** with the project's migration idempotency and safety requirements as documented in:

- `.claude/rules/database-migrations.md`
- `docs/development/MIGRATION_BEST_PRACTICES.md`
- `docs/development/SCHEMA_CHANGE_MD.md`
- `docs/development/SCHEMA_CONTRACTION_AND_DESTRUCTIVE_MIGRATION_POLICY.md`

### Key Findings

- ✅ **Compliant Migrations:** ~15 (14%)
- ❌ **Non-Compliant Migrations:** ~40+ (37%)
- ⚠️ **Partially Compliant:** ~5 (5%)
- ℹ️ **Merge Migrations:** ~47 (44%)

### Risk Assessment

**CRITICAL RISK:** If the database state becomes out of sync with migration history (common scenarios: hotfix scripts, manual schema changes, failed migrations), **30+ migrations will fail** when attempting to re-run `flask db upgrade`.

This violates the core principle from `MIGRATION_BEST_PRACTICES.md`:

> **Idempotent migrations** can be run multiple times without causing errors or data corruption. This is critical because:
> 1. Schema changes may have been applied manually in production to fix urgent issues
> 2. Previous migration runs may have partially completed before failing
> 3. The same migration may exist in multiple branches that get merged

---

## Detailed Findings

### CRITICAL Issues (Will Cause Deployment Failures)

#### 1. Tables Created Without `table_exists` Check

**Risk:** `psycopg2.errors.DuplicateTable: relation "table_name" already exists`

| Migration File | Line | Tables Created | Impact |
|----------------|------|----------------|---------|
| `2b5e304b912b_add_tapevent_model.py` | 21-30 | `tap_events` | P0 - Core feature |
| `a1b2c3d4e5f6_add_rent_system.py` | 21-45 | `rent_settings`, `rent_payments` | P1 - Major feature |
| `a2b3c4d5e6f7_add_insurance_system_tables.py` | 21-83 | `insurance_policies`, `student_insurance`, `insurance_claims` | P1 - Major feature |
| `f2g3h4i5j6k7_add_teacher_blocks_table.py` | 22-53 | `teacher_blocks` | P0 - Critical multi-tenancy |
| `7ed94f24520a_add_systemadmin_model.py` | 21-27 | `system_admins` | P0 - Security feature |
| `8f4a660d5082_add_store_item_models_and_remove_.py` | 21-46 | `store_items`, `student_items` | P1 - Major feature |
| `f5a1e3e4d7c8_add_hall_pass_models.py` | 25-36 | `hall_pass_logs` | P1 - Feature |
| `i6j7k8l9m0n1_add_payroll_settings_rewards_fines.py` | 21-55 | `payroll_settings`, `payroll_rewards`, `payroll_fines` | P0 - Core economy |
| `l9m0n1o2p3q4_add_banking_settings.py` | 21-53 | `banking_settings` | P1 - Major feature |
| `a1b2c3d4e5f7_add_student_blocks_and_tap_deletion.py` | 21-32 | `student_blocks` | P0 - Critical multi-tenancy |
| `1a4ee2388d62_add_teacher_analytics.py` | 21-90 | `analytics_alerts`, `analytics_events`, `analytics_snapshots` | P2 - Analytics |
| **+ 4 more migrations** | | Various | |

#### 2. Columns Added Without `column_exists` Check

**Risk:** `psycopg2.errors.DuplicateColumn: column "column_name" of relation "table_name" already exists`

This is the **exact error** that the project documentation references as a real-world incident.

| Migration File | Line | Columns Added | Table | Impact |
|----------------|------|-----------------|-------|---------|
| `1e2f3a4b5c6d_add_username_lookup_hash.py` | 20 | `username_lookup_hash` | `students` | P0 - Security feature |
| `3e1b8bd76b40_add_block_column_to_hall_pass_settings_.py` | 18 | `block` | `hall_pass_settings` | P1 - Multi-tenancy |
| `2060c104e884_add_display_name_and_class_label.py` | 22, 26 | `display_name`, `class_label` | `teacher_blocks` | P1 - UX feature |
| `a7b8c9d0e1f2_add_is_long_term_goal_to_store_items.py` | 24 | `is_long_term_goal` | `store_items` | P2 - Feature |
| `m0n1o2p3q4r5_add_bundle_and_bulk_discount_to_store.py` | 21-32 | 8 columns | `store_items`, `student_items` | P1 - Major feature |
| `f5a1e3e4d7c8_add_hall_pass_models.py` | 22 | `hall_passes` | `students` | P1 - Feature |
| `aa5697e97c94_add_join_code_to_tap_events.py` | 20 | `join_code` | `tap_events` | P0 - Multi-tenancy fix |
| **+ 2 more migrations** | | Various | Various | |

#### 3. Indexes Created Without `index_exists` Check

**Risk:** `psycopg2.errors.DuplicateObject: relation "index_name" already exists`

| Migration File | Line | Indexes | Impact |
|----------------|------|---------|---------|
| `f2g3h4i5j6k7_add_teacher_blocks_table.py` | 56-58 | 3 indexes | P0 - Performance |
| `d1e2f3a4b5c6_add_block_association_tables.py` | 49-60 | 4 indexes | P0 - Performance |
| `aa5697e97c94_add_join_code_to_tap_events.py` | 21 | `ix_tap_events_join_code` | P0 - Multi-tenancy |
| `a1b2c3d4e5f7_add_student_blocks_and_tap_deletion.py` | 35-36 | 2 indexes | P0 - Performance |
| `b4c5d6e7f8g9_add_deletion_request_model.py` | 39-40 | 2 indexes | P1 - Feature |

#### 4. Foreign Keys Created Without `foreign_key_exists` Check

**Risk:** `psycopg2.errors.DuplicateObject: constraint "fk_name" for relation "table_name" already exists`

| Migration File | Line | Foreign Key | Impact |
|----------------|------|-------------|---------|
| `a1b2c3d4e5f7_add_student_blocks_and_tap_deletion.py` | 44 | `fk_tap_events_deleted_by` | P0 - Data integrity |

#### 5. Constraints Created Without Checking

| Migration File | Line | Constraint | Impact |
|----------------|------|-----------|---------|
| `1e2f3a4b5c6d_add_username_lookup_hash.py` | 21 | `uq_students_username_lookup_hash` | P0 - Security |

### MAJOR Issues (Violate Best Practices)

#### 6. Hardcoded Constraint Names (Violates Section 3.1 of SCHEMA_CONTRACTION_AND_DESTRUCTIVE_MIGRATION_POLICY.md)

> **Policy Violation:**
> "Rule: Migrations MUST NOT assume constraint names... Hardcoded names are a known cause of production migration failure."

| Migration File | Line | Issue |
|----------------|------|-------|
| `1e2f3a4b5c6d_add_username_lookup_hash.py` | 26 | `batch_op.drop_constraint('uq_students_username_lookup_hash', ...)` |

**Correct Pattern (from policy):**
```python
from sqlalchemy import inspect

bind = op.get_bind()
inspector = inspect(bind)

for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

#### 7. Column Type Changes Without State Verification

| Migration File | Line | Issue |
|----------------|------|-------|
| `9e7a8d4f5c6b_encrypt_student_first_name.py` | 21-25 | Alters column type without checking current type |

---

## Compliant Migrations (Examples to Follow)

These migrations demonstrate proper implementation of best practices:

### ✅ Excellent Example: `00212c18b0ac_add_join_code_to_transaction.py`

```python
def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    if not column_exists('transactions', 'join_code'):
        with op.batch_alter_table('transactions', schema=None) as batch_op:
            batch_op.add_column(sa.Column('join_code', sa.String(10), nullable=True))
        print("✅ Added join_code column to transactions")
    else:
        print("⚠️  Column 'join_code' already exists on 'transactions', skipping...")
```

**Why this is good:**

- ✅ Defines helper function
- ✅ Checks before adding
- ✅ Informative logging
- ✅ Idempotent - can run multiple times
- ✅ Checks in downgrade too

### ✅ Excellent Example: `w2x3y4z5a6b7_add_teacher_id_to_settings_tables.py`

This migration (reviewed earlier) demonstrates:

- ✅ `column_exists()` helper
- ✅ `foreign_key_exists()` helper
- ✅ Checks before adding columns
- ✅ Checks before creating FKs
- ✅ Backfills data safely
- ✅ Idempotent upgrade AND downgrade
- ✅ Clear logging

### ✅ Good Example: `dd4ee5ff6aa7_add_student_verification_recovery.py`

```python
def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def upgrade():
    if not table_exists('recovery_requests'):
        op.create_table('recovery_requests', ...)
        print("✅ Created recovery_requests table")
    else:
        print("⚠️  Table 'recovery_requests' already exists, skipping...")
```

---

## Impact on Recent Work

### Analysis of Recent Commits (Last 10)

```
23e2f67 Fix URL redirection bypass via backslash normalization (#899)
31db2bb Bump alembic from 1.17.2 to 1.18.0 (#846)
11419c9 Consolidate safe dependabot updates (#907)
83ba615 Consolidate Copilot security autofixes (#906)
b4acb6e Potential fixes for code scanning alerts (#897)
ab245bb Add comprehensive migration validation script (#895)
71927d8 docs: Reorganize documentation structure (#893)
```

**Good News:** No new migrations were added in the recent commits that violate the policies.

**Observation:** Commit `ab245bb` added a migration validation script, which suggests awareness of migration quality issues. However, the script doesn't validate idempotency.

### Current Branch Status

- ✅ Working tree is clean
- ✅ No uncommitted model changes
- ✅ No new migrations need to be created
- ❌ Existing migrations need to be fixed for idempotency

---

## Compliance with Documentation Standards

### ❌ Violations of `.claude/rules/database-migrations.md`

The "Golden Rules" state:

1. ✅ NEVER modify `app/models.py` without creating a migration
   - **Status:** COMPLIANT (no model changes without migrations)

2. ❌ ALWAYS test migrations before committing (upgrade AND downgrade)
   - **Status:** UNKNOWN (cannot verify historical testing)

3. ✅ NEVER edit old migrations after they're merged to main
   - **Status:** COMPLIANT (no evidence of editing old migrations)

4. ❌ ALWAYS review auto-generated migrations before committing
   - **Status:** VIOLATED (40+ migrations lack idempotency checks)

5. ✅ NEVER skip migrations
   - **Status:** COMPLIANT (each schema change has a migration)

### ❌ Violations of `docs/development/MIGRATION_BEST_PRACTICES.md`

Section: "Core Principle: Migrations Must Be Idempotent"

> "Idempotent migrations can be run multiple times without causing errors or data corruption."

**Status:** 40+ migrations (37%) are NOT idempotent and will fail on re-run.

**Real-World Example Cited in Docs:**

> "We recently hit `psycopg2.errors.DuplicateColumn: column "join_code" of relation "student_blocks" already exists` while running `flask db upgrade` because a hotfix script had already added the column."

**Current State:** Multiple migrations would cause this exact error.

### ❌ Violations of `docs/development/SCHEMA_CHANGE_MD.md`

Section 3.4: "Migration Robustness"

Checklist items:

- ❌ No constraint names are hardcoded
  - **Status:** VIOLATED (at least 1 migration uses hardcoded constraint name)
- ❌ Constraints are discovered dynamically via inspection
  - **Status:** VIOLATED
- ❌ Migrations are idempotent where feasible
  - **Status:** VIOLATED (40+ non-idempotent migrations)

### ⚠️ Partial Compliance with `SCHEMA_CONTRACTION_AND_DESTRUCTIVE_MIGRATION_POLICY.md`

Section 3.1: "Constraint Name Agnosticism"

> "Rule: Migrations MUST NOT assume constraint names... Hardcoded names are a known cause of production migration failure."

**Status:** At least 1 violation found in `1e2f3a4b5c6d_add_username_lookup_hash.py`

---

## Breaking Changes Assessment

### Are There Breaking Changes?

**Definition of Breaking Change (per policy):**

- Dropping or renaming a column
- Dropping or renaming a table
- Removing or changing foreign keys
- Removing model attributes that map to existing database columns

**Analysis of Recent Work:**

✅ **NO BREAKING CHANGES DETECTED** in:

- Last 10 commits
- Current working tree
- Recent migrations

**All recent work is EXPAND-only** (additive, backward-compatible).

However, the **lack of idempotency** is itself a form of operational breaking change because:

1. **Deployment Fragility:** Migrations cannot be safely re-run
2. **Recovery Complexity:** Hotfix scenarios require manual intervention
3. **Testing Limitations:** Cannot test upgrade/downgrade cycles reliably

---

## Recommendations

### P0 - Critical (Must Fix Before Next Deployment)

#### 1. Create Standardized Migration Template

**File:** `migrations/migration_template.py`

```python
"""Migration template with idempotency helpers

Revision ID: ${revision}
Revises: ${down_revision}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def constraint_exists(table_name, constraint_name):
    """Check if a unique constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.

    Use this instead of hardcoding FK names in downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return [
        fk for fk in inspector.get_foreign_keys(table_name)
        if column_name in fk['constrained_columns']
    ]

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # Example: Add a column with idempotency check
    if not column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.add_column(sa.Column('column_name', sa.String(100), nullable=True))
        print("✅ Added column_name to table_name")
    else:
        print("⚠️  Column 'column_name' already exists on 'table_name', skipping...")

def downgrade():
    # Example: Drop a column with idempotency check
    if column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.drop_column('column_name')
        print("❌ Dropped column_name from table_name")
    else:
        print("⚠️  Column 'column_name' does not exist on 'table_name', skipping...")
```

#### 2. Update Migration Documentation

**File:** `.claude/rules/database-migrations.md`

Add to "The Golden Rules":

```markdown
6. **ALWAYS include idempotency helpers** in every migration
7. **NEVER use hardcoded constraint names** - discover dynamically
8. **ALWAYS check existence before CREATE operations**
```

Add to "Complete Migration Workflow" before Step 4:

```markdown
### Step 3.5: Copy Idempotency Helpers

From the migration template, copy ALL helper functions:
- `table_exists()`
- `column_exists()`
- `index_exists()`
- `foreign_key_exists()`
- `constraint_exists()`
- `get_foreign_keys_by_column()`

These are MANDATORY for all migrations.
```

#### 3. Create Migration Linter Script

**File:** `scripts/lint_migrations.py`

```python
#!/usr/bin/env python3
"""
Migration linter to enforce idempotency and safety best practices.

Usage:
    python scripts/lint_migrations.py
    python scripts/lint_migrations.py migrations/versions/abc123_migration.py
"""

import re
import sys
from pathlib import Path

REQUIRED_HELPERS = [
    'column_exists',
    'index_exists',
    'foreign_key_exists',
    'table_exists'
]

UNSAFE_PATTERNS = [
    (r'op\.create_table\s*\(', 'create_table without table_exists check'),
    (r'op\.add_column\s*\(', 'add_column without column_exists check'),
    (r'op\.create_index\s*\(', 'create_index without index_exists check'),
    (r'op\.create_foreign_key\s*\(', 'create_foreign_key without foreign_key_exists check'),
    (r'op\.drop_constraint\s*\(\s*["\'][\w_]+["\']', 'drop_constraint with hardcoded name'),
]

def lint_migration(filepath):
    """Lint a single migration file."""
    errors = []
    warnings = []

    with open(filepath, 'r') as f:
        content = f.read()

    # Check for helper functions
    has_helpers = {}
    for helper in REQUIRED_HELPERS:
        has_helpers[helper] = f'def {helper}(' in content

    # Check for unsafe patterns
    for pattern, message in UNSAFE_PATTERNS:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1

            # Check if there's an existence check nearby
            # Look for 'if not <helper_name>' within 5 lines before
            context_start = max(0, content.rfind('\n', 0, match.start() - 100))
            context = content[context_start:match.start()]

            has_check = any(f'if not {helper}(' in context for helper in REQUIRED_HELPERS)
            has_check = has_check or 'if not table_exists(' in context

            if not has_check:
                errors.append(f"  Line {line_num}: {message}")

    return errors, warnings

def main():
    if len(sys.argv) > 1:
        # Lint specific file
        migrations = [Path(sys.argv[1])]
    else:
        # Lint all migrations
        migrations_dir = Path('migrations/versions')
        migrations = sorted(migrations_dir.glob('*.py'))
        migrations = [m for m in migrations if not m.name.startswith('__')]

    total_errors = 0
    total_warnings = 0

    for migration_file in migrations:
        errors, warnings = lint_migration(migration_file)

        if errors or warnings:
            print(f"\n❌ {migration_file.name}")
            for error in errors:
                print(f"  ERROR: {error}")
                total_errors += 1
            for warning in warnings:
                print(f"  WARNING: {warning}")
                total_warnings += 1

    print(f"\n{'='*70}")
    print(f"Total: {total_errors} errors, {total_warnings} warnings")

    if total_errors > 0:
        print("\n❌ Migration linting FAILED")
        print("See MIGRATION_BEST_PRACTICES.md for guidance")
        sys.exit(1)
    else:
        print("\n✅ All migrations passed linting")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

### P1 - High Priority (Fix Soon)

#### 4. Retrofit Existing Migrations

**Approach:** Add idempotency checks to the 40+ non-compliant migrations.

**Strategy:**

1. Create a script to automatically add helpers to migrations
2. Manually review each migration's upgrade/downgrade
3. Test each migration individually

**DO NOT** edit old migrations that have been deployed to production. Instead:

- Document which migrations lack idempotency in this report
- Add checks to NEW migrations going forward
- For production: maintain a "skip list" of migrations that must be manually handled

#### 5. Add CI/CD Gate

**File:** `.github/workflows/migration-lint.yml`

```yaml
name: Migration Linting

on:
  pull_request:
    paths:
      - 'migrations/versions/**'
      - 'app/models.py'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install alembic sqlalchemy
      - name: Lint migrations
        run: python scripts/lint_migrations.py
      - name: Check migration heads
        run: bash scripts/check-migration-heads.sh
```

### P2 - Standard Priority (Improve Over Time)

#### 6. Create Migration Testing Framework

**File:** `tests/test_migration_idempotency.py`

Test that migrations can be run multiple times:

```python
def test_migration_idempotency():
    """Test that migrations can be run twice without error."""
    # Run upgrade
    flask_db.upgrade()

    # Run upgrade again (should not fail)
    flask_db.upgrade()

    # Run downgrade
    flask_db.downgrade()

    # Run downgrade again (should not fail)
    flask_db.downgrade()
```

#### 7. Documentation Updates

Add section to `MIGRATION_BEST_PRACTICES.md`:

```markdown
## Pre-Merge Checklist

Before merging a PR with migrations:

- [ ] All helper functions included
- [ ] All CREATE operations have existence checks
- [ ] All DROP operations have existence checks
- [ ] No hardcoded constraint names
- [ ] Migration tested: upgrade → downgrade → upgrade
- [ ] Migration linter passes
- [ ] Migration heads check passes
```

---

## Action Plan

### Immediate Actions (This Session)

1. ✅ Create this compliance review report
2. ⏳ Create migration template with all helpers
3. ⏳ Create migration linter script
4. ⏳ Update `.claude/rules/database-migrations.md` with new requirements
5. ⏳ Commit and push changes

### Follow-Up Actions (Next PR)

6. Add CI/CD workflow for migration linting
7. Create migration testing framework
8. Update all documentation with new requirements

### Long-Term Actions (Next Sprint)

9. Retrofit existing migrations (carefully)
10. Create automated migration generation tool that includes helpers
11. Add migration quality metrics to monitoring

---

## Conclusion

### Summary

This branch (`claude/review-migration-compliance-9Qj73`) itself has:

✅ **No Breaking Changes**
✅ **No New Migrations**
✅ **No Model Changes**
✅ **Clean Working Tree**

However, the **comprehensive audit** revealed:

❌ **40+ migrations (37%) are not idempotent**
❌ **Violations of documented best practices**
❌ **High risk of deployment failures**
❌ **Technical debt in migration quality**

### Compliance Status

| Policy Document | Compliance Status |
|-----------------|-------------------|
| `.claude/rules/database-migrations.md` | ⚠️ Partial (4/5 rules) |
| `MIGRATION_BEST_PRACTICES.md` | ❌ Non-Compliant (idempotency) |
| `SCHEMA_CHANGE_MD.md` | ❌ Non-Compliant (3/3 checks fail) |
| `SCHEMA_CONTRACTION_AND_DESTRUCTIVE_MIGRATION_POLICY.md` | ⚠️ Partial (constraint names) |

### Recommendations

**DO NOT** merge this branch as-is without addressing the idempotency issues found.

**RECOMMENDED NEXT STEPS:**

1. Implement the migration template and linter (P0)
2. Update documentation to make idempotency mandatory (P0)
3. Add CI/CD gate to prevent future violations (P1)
4. Consider retrofitting critical migrations (P1)

### Risk Mitigation

Until all migrations are retrofitted:

**For Production Deployments:**

1. Maintain manual checklist of non-idempotent migrations
2. Verify database state before running migrations
3. Have rollback plan ready
4. Test migrations on staging clone first

**For Development:**

1. Use migration linter on all new migrations
2. Make idempotency helpers mandatory in PR reviews
3. Add migration quality to code review checklist

---

**Report Generated:** 2026-02-04
**Audit Scope:** 107 migration files
**Time Spent:** Comprehensive review
**Next Action:** Implement standardized migration template and linter

**Approval Status:** ⏳ Pending implementation of fixes

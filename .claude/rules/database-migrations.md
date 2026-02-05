# Database Migration Rules

**CRITICAL:** This project uses Alembic for database migrations. Following these rules prevents data loss, schema conflicts, and deployment failures.

---

## The Golden Rules

1. **NEVER modify `app/models.py` without creating a migration**
2. **ALWAYS test migrations before committing** (upgrade AND downgrade)
3. **NEVER edit old migrations after they're merged to main**
4. **ALWAYS review auto-generated migrations** before committing
5. **NEVER skip migrations** - each schema change needs its own migration
6. **ALWAYS include idempotency helpers** in every migration (table_exists, column_exists, index_exists, foreign_key_exists)
7. **NEVER use hardcoded constraint names** - discover dynamically via inspection
8. **ALWAYS check existence before CREATE operations** (tables, columns, indexes, foreign keys)

---

## Complete Migration Workflow

⚠️ **CRITICAL:** The project has experienced recurring "multiple heads" errors during deployment because migrations were created without syncing with main first. **ALWAYS follow this complete workflow.**

### Step 0: Sync with Main (CRITICAL - DO THIS FIRST)

**Before creating ANY migration, ALWAYS sync with the latest code:**

```bash
# 1. Pull latest changes from main
git fetch origin main
git merge origin/main
```

**Why this matters:** If someone else created a migration while you were working, creating a new migration without syncing first will cause "multiple heads" - two parallel migration chains that can't be automatically resolved.

### Step 1: Verify Single Migration Head

```bash
# Check for migration heads
flask db heads  # MUST show exactly 1 head
```

**If you see multiple heads:**

```bash
# Create a merge migration FIRST
flask db merge heads -m "Merge migration heads"

# Test the merge
flask db upgrade
flask db downgrade
flask db upgrade

# Now you have a single head and can proceed
```

### Step 2: Check Current Revision

```bash
# Note the current revision ID
flask db current
```

**Save this revision ID** - you'll verify it in Step 5.

### Step 3: Modify the Model

Edit `app/models.py` to make your schema change:

```python
# Example: Adding a new field
class Student(db.Model):
    # ... existing fields ...
    email = db.Column(db.String(255), nullable=True)  # NEW FIELD
```

### Step 4: Generate the Migration

```bash
flask db migrate -m "Add email field to Student model"
```

This creates a new file in `migrations/versions/` with a random ID like `abc123def456_add_email_field_to_student_model.py`

### Step 5: Copy Idempotency Helpers (CRITICAL - NEW REQUIREMENT)

**⚠️ MANDATORY:** Every migration MUST include idempotency helpers to prevent deployment failures.

**Copy the helper functions from `migrations/migration_template.py.mako`:**

```python
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

def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []
```

**Why this is critical:** See MIGRATION_COMPLIANCE_REVIEW.md for details on the 40+ non-idempotent migrations that cause deployment failures.

### Step 6: IMMEDIATELY Verify the Migration

**Open the generated migration file and check:**

1. **Verify `down_revision` matches the revision from Step 2**

```python
# In migrations/versions/abc123def456_add_email_field_to_student_model.py

# This MUST match the output of `flask db current` from Step 2
down_revision = 'xyz789...'  # Should match your current revision

# If it doesn't match, STOP and DELETE this migration file
# Then restart from Step 0 - someone else created a migration
```

2. **Verify there's no `depends_on`** (unless you specifically need it)

**If the `down_revision` is wrong:**
- DELETE the generated migration file
- Go back to Step 0 and sync with main again
- Someone else created a migration while you were working

### Step 7: Review and Wrap Generated Operations

**IMPORTANT:** Alembic auto-generates migrations but they're not always perfect. YOU MUST REVIEW AND WRAP IN EXISTENCE CHECKS.

Open the generated file and modify:

✅ **Wrap all CREATE operations in existence checks**

**BEFORE (Auto-generated - UNSAFE):**
```python
def upgrade():
    # NOT IDEMPOTENT - will fail if column exists
    op.add_column('student', sa.Column('email', sa.String(length=255), nullable=True))
```

**AFTER (Your responsibility - SAFE):**
```python
def upgrade():
    # IDEMPOTENT - safe to run multiple times
    if not column_exists('student', 'email'):
        op.add_column('student', sa.Column('email', sa.String(length=255), nullable=True))
        print("✅ Added email column to student")
    else:
        print("⚠️  Column 'email' already exists on 'student', skipping...")
```

✅ **Wrap downgrade operations too**
```python
def downgrade():
    # Check before dropping
    if column_exists('student', 'email'):
        op.drop_column('student', 'email')
        print("❌ Dropped email column from student")
    else:
        print("⚠️  Column 'email' does not exist on 'student', skipping...")
```

**Required Patterns:**

| Operation | Required Check |
|-----------|----------------|
| `op.create_table(...)` | `if not table_exists("table_name"):` |
| `op.add_column(...)` | `if not column_exists("table", "column"):` |
| `op.create_index(...)` | `if not index_exists("table", "index"):` |
| `op.create_foreign_key(...)` | `if not foreign_key_exists("table", "fk"):` |
| `op.drop_constraint(...)` | Use `get_foreign_keys_by_column()`, not hardcoded names |

✅ **Check for data migrations if needed**
```python
def upgrade():
    # Schema change
    op.add_column('transaction', sa.Column('join_code', sa.String(10), nullable=True))

    # Data migration (if needed)
    op.execute("""
        UPDATE transaction t
        SET join_code = (
            SELECT tb.join_code
            FROM teacher_block tb
            WHERE tb.teacher_id = t.teacher_id
            LIMIT 1
        )
    """)

    # Make column non-nullable after backfill
    op.alter_column('transaction', 'join_code', nullable=False)
```

### Step 8: Run Migration Linter

**⚠️ NEW REQUIREMENT:** Validate migration before committing.

```bash
python scripts/lint_migrations.py migrations/versions/abc123def456_*.py
```

This checks for:
- Missing idempotency helpers
- Unsafe CREATE operations without existence checks
- Hardcoded constraint names
- Other best practice violations

**If linting fails:** Fix the issues before proceeding. See `docs/development/migration-specifications.md` for examples.

### Step 9: Test the Upgrade

```bash
flask db upgrade
```

**Check:**
- No errors during migration
- Database schema matches your model
- Verify with `psql` or database client if needed

### Step 10: Test the Downgrade

```bash
flask db downgrade
```

**Check:**
- Migration reverses cleanly
- No data loss (if data migration involved, check carefully)
- Database returns to previous state

### Step 11: Re-upgrade for Development

```bash
flask db upgrade
```

Your database should now be at the latest version.

### Step 12: Verify Single Head (CRITICAL)

```bash
flask db heads  # MUST still show exactly 1 head
```

**If you see multiple heads now:** Something went wrong. You may need to create a merge migration.

**Quick check script:**
```bash
bash scripts/check-migration-heads.sh
```

### Step 13: Run Tests

```bash
pytest tests/
```

**All tests must pass** before committing the migration.

### Step 14: Commit

```bash
git add app/models.py migrations/versions/abc123def456_*.py
git commit -m "Add email field to Student model with migration"
```

---

## Migration Naming Conventions

Use descriptive names that clearly state what changed:

### Adding Columns
```bash
flask db migrate -m "Add email field to Student model"
flask db migrate -m "Add join_code to Transaction table"
```

### Creating Tables
```bash
flask db migrate -m "Create RecoveryRequest table"
flask db migrate -m "Create StudentRecoveryCode table"
```

### Removing Columns
```bash
flask db migrate -m "Remove deprecated field from StoreItem"
```

### Renaming
```bash
flask db migrate -m "Rename student_id to user_id in Transaction"
```

### Relationships
```bash
flask db migrate -m "Add foreign key relationship between Student and Teacher"
```

### Complex Changes
```bash
flask db migrate -m "Add join_code scoping to all financial tables"
```

---

## Common Scenarios

### Scenario 1: Adding a Required Field to Existing Table

**Problem:** Can't add `nullable=False` to a table with existing data.

**Solution:** Two-step migration

```python
# Migration 1: Add column as nullable
def upgrade():
    op.add_column('student', sa.Column('email', sa.String(255), nullable=True))

def downgrade():
    op.drop_column('student', 'email')
```

```python
# Migration 2 (after backfilling data): Make non-nullable
def upgrade():
    # Ensure all rows have values first
    op.execute("UPDATE student SET email = 'default@example.com' WHERE email IS NULL")
    op.alter_column('student', 'email', nullable=False)

def downgrade():
    op.alter_column('student', 'email', nullable=True)
```

### Scenario 2: Renaming a Column

```python
def upgrade():
    op.alter_column('transaction', 'student_id', new_column_name='user_id')

def downgrade():
    op.alter_column('transaction', 'user_id', new_column_name='student_id')
```

### Scenario 3: Adding Foreign Key

```python
def upgrade():
    # Add column first
    op.add_column('transaction', sa.Column('join_code', sa.String(10)))

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_transaction_join_code',  # Constraint name
        'transaction',                # Source table
        'teacher_block',              # Target table
        ['join_code'],               # Source columns
        ['join_code']                # Target columns
    )

def downgrade():
    op.drop_constraint('fk_transaction_join_code', 'transaction', type_='foreignkey')
    op.drop_column('transaction', 'join_code')
```

### Scenario 4: Data Migration

When you need to transform existing data:

```python
def upgrade():
    # Create new column
    op.add_column('student', sa.Column('full_name', sa.String(255)))

    # Migrate data
    connection = op.get_bind()
    connection.execute("""
        UPDATE student
        SET full_name = first_name || ' ' || last_initial
    """)

    # Make non-nullable if needed
    op.alter_column('student', 'full_name', nullable=False)

def downgrade():
    op.drop_column('student', 'full_name')
```

---

## Migration Chain Issues

### Problem: Multiple Heads

If you see: `ERROR: Multiple heads are present`

**Cause:** Two migrations were created in parallel (different branches)

**Solution:** Create a merge migration

```bash
flask db merge heads -m "Merge migration heads"
```

Review the generated merge migration, then:

```bash
flask db upgrade
pytest tests/
git add migrations/versions/merge_*.py
git commit -m "Merge migration heads"
```

### Problem: Broken Migration Chain

If migrations are out of order:

1. **DO NOT edit old migrations**
2. Create a new corrective migration
3. Test thoroughly

```bash
flask db migrate -m "Fix migration chain issue"
# Review and test
flask db upgrade
flask db downgrade
flask db upgrade
pytest tests/
```

---

## What NOT to Do

### ❌ NEVER: Modify models without migration

```python
# DON'T DO THIS
class Student(db.Model):
    email = db.Column(db.String(255))  # Added without migration
```

**Result:** Database schema won't match models, queries will fail in production.

### ❌ NEVER: Edit old migrations

```python
# DON'T EDIT: migrations/versions/abc123_old_migration.py
# Even if you find a bug, create a NEW migration to fix it
```

**Result:** Breaks migration history, causes deployment failures.

### ❌ NEVER: Skip migration testing

```bash
# DON'T DO THIS
flask db migrate -m "changes"
git commit -m "update"  # WITHOUT testing upgrade/downgrade
```

**Result:** Broken migrations in production, potential data loss.

### ❌ NEVER: Use generic migration names

```bash
# BAD
flask db migrate -m "update database"
flask db migrate -m "changes"
flask db migrate -m "fix"

# GOOD
flask db migrate -m "Add join_code to Transaction table"
flask db migrate -m "Create RecoveryRequest model with foreign keys"
```

### ❌ NEVER: Commit failing migrations

```bash
# If this fails:
flask db upgrade

# DON'T commit the migration
# Fix it first or delete and regenerate
```

---

## Production Deployment

### Pre-Deployment Checklist

Before deploying migrations to production:

- [ ] All migrations tested locally (upgrade + downgrade)
- [ ] Full test suite passes (`pytest`)
- [ ] Migration tested on staging environment
- [ ] Backup plan ready (downgrade tested)
- [ ] Downtime window scheduled if needed (for large data migrations)

### Deployment Commands

```bash
# On production server
cd /path/to/classroom-economy
source venv/bin/activate

# Backup database FIRST
pg_dump classroom_economy > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
flask db upgrade

# Verify
flask db current

# Run smoke tests
pytest tests/test_critical.py
```

### Rollback Procedure

If something goes wrong:

```bash
# Downgrade to previous version
flask db downgrade

# Or restore from backup
psql classroom_economy < backup_YYYYMMDD_HHMMSS.sql

# Investigate issue
# Fix migration
# Test thoroughly
# Redeploy
```

---

## Debugging Migrations

### Check Current Version

```bash
flask db current
```

### View Migration History

```bash
flask db history
```

### Stamp Database (Use with Caution)

If you need to mark a migration as applied without running it:

```bash
flask db stamp head  # Mark as latest version
flask db stamp <revision_id>  # Mark specific version
```

**WARNING:** Only use `stamp` if you're certain the database schema matches.

### Show SQL Without Executing

```bash
flask db upgrade --sql
flask db downgrade --sql
```

---

## Quick Reference

```bash
# Generate migration
flask db migrate -m "Description"

# Lint migration (NEW - REQUIRED)
python scripts/lint_migrations.py migrations/versions/abc123*.py

# Apply migrations
flask db upgrade

# Revert last migration
flask db downgrade

# Show current version
flask db current

# Show migration history
flask db history

# Merge multiple heads
flask db merge heads -m "Merge description"

# Show SQL without executing
flask db upgrade --sql

# Check migration heads (detect multiple heads early)
bash scripts/check-migration-heads.sh
```

---

## Summary Checklist

Every time you change database schema:

1. ✅ **SYNC WITH MAIN FIRST:** `git fetch origin main && git merge origin/main`
2. ✅ **Verify single head:** `flask db heads` (must show exactly 1)
3. ✅ **Note current revision:** `flask db current`
4. ✅ Modify model in `app/models.py`
5. ✅ Generate migration: `flask db migrate -m "clear description"`
6. ✅ **COPY IDEMPOTENCY HELPERS** from `migrations/migration_template.py.mako`
7. ✅ **IMMEDIATELY verify `down_revision` matches Step 3**
8. ✅ **WRAP ALL CREATE OPERATIONS** in existence checks (column_exists, table_exists, etc.)
9. ✅ Review generated migration file
10. ✅ **RUN MIGRATION LINTER:** `python scripts/lint_migrations.py migrations/versions/abc*.py`
11. ✅ Test upgrade: `flask db upgrade`
12. ✅ Test downgrade: `flask db downgrade`
13. ✅ Re-upgrade: `flask db upgrade`
14. ✅ **Verify single head:** `flask db heads` (still must show exactly 1)
15. ✅ Run tests: `pytest tests/`
16. ✅ Commit model + migration together
17. ✅ Update `docs/technical-reference/database_schema.md` if significant change
18. ✅ Update `CHANGELOG.md`

**NEW REQUIREMENTS (2026-02-04):**
- All migrations MUST include idempotency helpers
- All CREATE operations MUST check existence first
- Migration linter MUST pass before committing
- See `MIGRATION_COMPLIANCE_REVIEW.md` for full audit report

---

**Last Updated:** 2025-12-13
**Migrations Count:** 83 (and growing)
**Database:** PostgreSQL with Alembic

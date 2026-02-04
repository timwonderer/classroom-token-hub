# Database Migration Specifications

> [!IMPORTANT]
> This is the **Single Source of Truth** for all database migration policies, best practices, and workflows in the Classroom Economy project. All contributors must adhere to these standards.

---

## 1. The Golden Rules

1.  **NEVER modify `app/models.py` without creating a migration.**
2.  **ALWAYS test migrations before committing** (upgrade AND downgrade).
3.  **NEVER edit old migrations after they're merged to main.**
4.  **ALWAYS review auto-generated migrations** before committing.
5.  **NEVER skip migrations** - each schema change needs its own migration.
6.  **ALWAYS include idempotency helpers** in every migration.
7.  **NEVER use hardcoded constraint names** - discover dynamically.
8.  **ALWAYS check existence before CREATE operations.**

---

## 2. Migration Best Practices

### Core Principle: Migrations Must Be Idempotent

**Idempotent migrations** can be run multiple times without causing errors or data corruption. This is critical because:
1.  Schema changes may have been applied manually in production to fix urgent issues.
2.  Previous migration runs may have partially completed before failing.
3.  The same migration may exist in multiple branches that get merged.

### Required Idempotency Checks

#### 1. Check if Columns Exist Before Adding
```python
def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade():
    if not column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.add_column(sa.Column('column_name', sa.Integer(), nullable=True))
        print("✅ Added column_name to table_name")
    else:
        print("⚠️ Column 'column_name' already exists, skipping...")
```

#### 2. Check if Foreign Keys Exist Before Creating
```python
def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys
```

#### 3. Check if Indexes Exist Before Creating
```python
def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes
```

#### 4. Downgrade Safety
Downgrade functions must also be idempotent:
```python
def downgrade():
    if column_exists('table_name', 'column_name'):
        with op.batch_alter_table('table_name', schema=None) as batch_op:
            batch_op.drop_column('column_name')
```

---

## 3. Schema Change Policy

### Schema Change Gate
This gate is **PR‑blocking by design**. A schema-affecting PR that does not explicitly pass this gate **MUST NOT** be merged.

**Applies when:**
- Dropping or renaming a column/table.
- Removing or changing foreign keys.
- Replacing relations with association tables.
- Removing model attributes mapping to columns.

### PR Classification (Required in PR Description)
- [ ] **EXPAND** – Additive, backward-compatible (no removals).
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal, DB schema unchanged.
- [ ] **CONTRACT (DATABASE)** – Destructive migration only.

### Schema Contraction & Destructive Migration Policy

> [!WARNING]
> Schema deletion is not a refactor. It is a **high-risk operational change**.

All destructive schema changes MUST follow the **Expand and Contract** pattern over three releases:

1.  **Phase 1: Expand (Release N)**
    - New schema elements exist alongside legacy ones.
    - Application supports both or migrates to new.
    - Legacy elements remain present and populated.
    - **NO destructive migrations.**

2.  **Phase 2: Contract Code (Release N+1)**
    - Legacy attribute/column removed from Code models.
    - DB column remains physically present.
    - Application operates fully without legacy attribute.
    - Hidden usage must fail loudly.

3.  **Phase 3: Contract Database (Release N+2)**
    - Migration drops the legacy column/table.
    - Usage: `flask db migrate -m "Contract: drop legacy column"`
    - Must be a dedicated, isolated migration.

### Constraint Name Agnosticism
**Rule:** Migrations MUST NOT assume constraint names. They vary across environments.

**Correct Pattern:**
```python
from sqlalchemy import inspect
bind = op.get_bind()
inspector = inspect(bind)

for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

---

## 4. Migration Workflow Guide

### Complete Workflow

1.  **Sync with Main**:
    ```bash
    git fetch origin main && git merge origin/main
    ```
2.  **Verify Single Head**:
    ```bash
    flask db heads  # Must show exactly 1 head
    ```
3.  **Modify Model**: Edit `app/models.py`.
4.  **Generate Migration**:
    ```bash
    flask db migrate -m "Description of change"
    ```
5.  **Review Migration File**:
    - Check `down_revision` matches previous head.
    - **Add Idempotency Helpers** (copied from template or examples above).
    - ensure `upgrade()` and `downgrade()` use existence checks.
6.  **Test Locally**:
    ```bash
    flask db upgrade
    flask db downgrade
    flask db upgrade
    ```
7.  **Run Tests**: `pytest tests/`

### Branch Consolidation & Multiple Heads
If you see "multiple heads" (e.g., from merging feature branches):
1.  **Merge Heads**:
    ```bash
    flask db merge heads -m "Merge migration heads"
    ```
2.  **Verify**: Ensure the merge migration handles any overlapping changes idempotently.

### Production Deployment Checklist
- [ ] All migrations tested locally (upgrade + downgrade).
- [ ] Migration rehearsed on staging/production-like clone.
- [ ] Backup plan ready.
- [ ] Downtime scheduled if needed (for large data migrations).

---

## 5. Deprecation Standards

### Deprecated Symbols Registry
The authoritative list lives in `docs/development/DEPRECATED_SYMBOLS.txt`. Use this to track symbols prohibited from application code.

### common Deprecated Patterns

1.  **`datetime.utcnow()`**: Deprecated.
    - **Use**: `datetime.now(datetime.UTC)` (Python 3.12+ style) or timezone-aware objects.
2.  **`Query.get()`**: Deprecated in SQLAlchemy 2.0+.
    - **Use**: `db.session.get(Model, id)`.

---

## 6. Resources
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Inspector API](https://docs.sqlalchemy.org/en/20/core/reflection.html)

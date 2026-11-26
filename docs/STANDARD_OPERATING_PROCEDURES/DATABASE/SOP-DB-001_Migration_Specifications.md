# Database Migration Specifications

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-001       | 1.9     | 2026-11-24     | 1.8 | Normative |

> [!IMPORTANT]
> This is the **Single Source of Truth** for all database migration policies, best practices, and workflows in the Classroom Economy project. All contributors must adhere to these standards.

---

## I. Purpose
To be the Single Source of Truth for all database migration policies, best practices, and workflows in the Classroom Economy project. Idempotency is strict and enforced.

## II. Scope
All Alembic migrations authored by developers modifying the application database.

## III. Authority Level
Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `SOP-DB-003_Schema_Change_Proposals.md`

## V. The Golden Rules

1.  **NEVER modify `app/models.py` without creating a migration.**
2.  **ALWAYS test migrations before committing** (upgrade AND downgrade).
3.  **NEVER edit a migration in the supported lineage after it is merged to main.** The only
    exception is a Replay-Safety Correction under §V.A, which may not be used to change what a merged
    migration intends to do. There are no others. Removing revisions from the supported lineage is
    not an edit; it is a baseline replacement, permitted only under §V.C. (§V.B is retired and kept
    as provenance only.)
4.  **ALWAYS review auto-generated migrations** before committing.
5.  **NEVER skip migrations** - each schema change needs its own migration.
6.  **ALWAYS include idempotency helpers** in every migration (`table_exists`, `column_exists`, etc.).
7.  **NEVER use hardcoded constraint names** - discover dynamically via inspection.
8.  **ALWAYS check existence before CREATE operations** (tables, columns, indexes, foreign keys).

### V.A Replay-Safety Correction (First Exception to Rule 3)

A merged migration MUST NOT otherwise be modified.

`INV-CORE-000` §II places all migrations within its scope, and its invariants are cumulative. Rule 3
therefore cannot require preserving an execution path that destroys state a superior `INV` or `DOM`
document protects (`INV-CORE-001` §III). A migration whose existence checks cannot distinguish its
historical input from its own output presents exactly that path when it is re-applied.

A merged migration MAY receive a replay-safety correction, meaning a change that makes it strictly
less destructive on replay. It qualifies only when **all** of the following are proven:

1. **Protected state is at risk.** Its existing replay behavior can destroy, rewrite, or invalidate
   state protected by an `INV` or `DOM` document, and the protecting clause is cited. A replay that
   is merely untidy, that errors, or that adds drift without destroying, rewriting, or invalidating
   protected state does not qualify.
2. **No forward remedy exists.** No forward corrective migration can eliminate the behavior, because
   the defect exists within execution of the historical revision itself.
3. **First execution is unchanged.** The correction does not alter the migration's behavior when it
   is applied to its intended predecessor schema.
4. **The intended transformation is unchanged.** A fresh upgrade through the corrected revision
   produces the same intended schema and data transformation as the merged revision.
5. **The destructive replay is gone.** Replay and re-upgrade prove the destructive behavior has been
   eliminated.
6. **The exception is acknowledged.** The exception and its production risk are explicitly recorded
   under `SOP-DB-003` §IX.

This exception MUST NOT be used to change a historical migration's intended schema, introduce new
application behavior, correct ordinary forward migration defects that can be repaired by a
subsequent revision, or avoid creating a corrective migration.

#### Evidence

Each condition is proven by execution, not by argument, and reported with its exact command and
scope (`INV-ARC-017` §V). At minimum:

- **Conditions 3 and 4:** the merged and corrected revisions, run against the intended predecessor
  schema, emit the same mutating statements and leave the same schema and rows; and a fresh upgrade
  through the full chain yields a schema identical to the one the merged revision yields.
- **Condition 5:** a test seeds the protected state through its canonical write paths, re-applies
  the corrected revision over the migrated schema, and asserts the state survives. The test is
  watched failing against the merged revision.
- Upgrade, downgrade, re-upgrade, and head validation, per `INV-ARC-017` §VI.

#### Recording

- The corrected migration carries a comment naming this section and the date of the correction.
- The PR description and `CHANGELOG.md` cite the protecting clause, the evidence for each condition,
  and the production-risk acknowledgment required by `SOP-DB-003` §IX.

#### Independent Evaluation

Each candidate is evaluated on its own evidence. Resemblance to a migration already corrected under
this section is not evidence that a candidate qualifies, and a prior correction is not precedent
for another.


### V.B Bootstrap-Replay Correction (retired in v1.9; provenance)

> [!NOTE]
> **Retired as an operational exception (v1.9).** §V.B answered a defect of a baseline built from
> live ORM metadata, the architecture §V.C.2 now prohibits. Its two corrections (`3a69db4907b4`,
> `8f1a2c3d4b5e`) are pre-launch revisions, held unchanged in `migrations/archive/v2_prelaunch/` and
> outside the supported lineage (§V.C), so they are no longer load-bearing and no new correction can
> arise. Golden Rule 3 names no exception under this section. The text, register and rationale below
> are kept unchanged as the record of the decisions made under it. Issue #1649 and PR #1834, which
> pursued the deferred reconstruction, are superseded by the baseline replacement; their findings are
> kept in `docs/ops/audits/BASELINE_REPLACEMENT_2026-11-24.md`.

A merged migration MUST NOT otherwise be modified. This exception is narrower than §V.A: it permits
one shape of change only — a guard that makes a historical operation a no-op when the schema element
it operates on is absent — and it permits that only because of a defect in the baseline migration.

#### The condition it exists for

Until 2026-09-28, `0001_bootstrap` materialized the baseline by calling `metadata.create_all` against
the **current** ORM metadata. The frozen baseline replaced that (see *Standing remedy* below), and
the rest of this subsection describes the bootstrap as it was, which the register's corrections
were made against. Its own docstring states the consequence: "deleting a model retroactively removes a
table that existed at baseline time — and later migrations in the chain still legitimately reference
it." The revision graph is unchanged by such a deletion, so nothing signals that a historical
revision has lost its precondition.

The live bootstrap remedied this for whole **tables**, in `_create_retired_baseline_tables`. It had
no equivalent remedy for **columns**. A column present at baseline time and since removed
from the ORM is therefore absent on a fresh chain, and the historical migration that alters it
raises. That failure is not a defect in the historical migration; it is the bootstrap presenting a
schema the migration was never written against.

This is a replay **error**, not destruction, so it does not and cannot qualify under §V.A —
condition 1 there excludes "a replay that is merely untidy, that errors, or that adds drift without
destroying, rewriting, or invalidating protected state." Nothing in §V.A covers it, and §V.A must
not be stretched to cover it.

#### Conditions

A merged migration MAY receive a bootstrap-replay correction. It qualifies only when **all** of the
following are proven:

1. **The failure is a bootstrap artifact.** The operation fails because `0001_bootstrap` materialized
   current ORM metadata in which the target schema element no longer exists. The element must be
   shown absent from today's models and required by the historical revision.
2. **The failure is an error, not destruction.** No state is destroyed, rewritten, or invalidated.
   A correction that prevents destruction is a §V.A matter and is evaluated there instead.
3. **No forward remedy exists.** No later migration can supply the precondition, because the failure
   occurs within the execution of the historical revision itself.
4. **The guard is the whole change.** The correction adds only an existence check, and the
   existence-check helper it needs. It changes no operation, no order, no value, and no downgrade
   behavior.
5. **First execution is unchanged.** Where the element is present — every database already migrated
   through this revision, and any replay against the schema the revision was written for — the guard
   is satisfied and the original statements execute identically.
6. **The intended end state is unchanged.** The correction MUST NOT alter the schema or data
   transformation the merged revision intends. Where the element exists, the intended end state is
   still reached. Where it does not, the migration declines; it MUST NOT substitute a different
   operation on a differently-named element to reach an equivalent-looking result.
7. **The chain still replays to a single head.** A full upgrade against an empty schema reaches
   head, and `flask db heads` reports exactly one. Where the corrected revision's own downgrade is
   reachable from head, a downgrade and re-upgrade across it is also proven. It is not always
   reachable: this chain contains revisions that refuse downgrade by design (`SOP-DEP-001` §XIV), so
   a downgrade walk past one of those is unavailable and MUST NOT be claimed as evidence.

#### Prohibited uses

This exception MUST NOT be used to:

- change a historical migration's intended schema or data transformation;
- retarget a historical operation onto a renamed or replacement column;
- repair a defect that a forward corrective migration can repair;
- tidy, modernize, or re-lint a merged migration;
- prevent a destructive replay — that is §V.A, and it must meet §V.A's conditions on its own
  evidence;
- avoid fixing the bootstrap. The correct structural remedy is a frozen baseline (see §V.B
  *Standing remedy* below). Each correction under this section is an acknowledged deferral of that
  remedy, not a substitute for it.

#### Evidence

Proven by execution, not by argument, and reported with its exact command and scope
(`INV-ARC-017` §V). At minimum:

- **Condition 1:** the element's absence from current ORM metadata, and the replay failure itself.
- **Conditions 5 and 6:** a fresh upgrade through the full chain reaches the same schema as before
  the correction; and where the element is present the revision emits the same mutating statements.
- **Condition 7:** a full upgrade against an empty schema, and `flask db heads` showing exactly
  one head. State plainly whether the revision's own downgrade is reachable from head, and if it is
  not, say so rather than reporting a downgrade that was never run.

#### Recording

- The corrected migration carries a comment naming this section and stating which element is absent
  and why.
- The PR description and `CHANGELOG.md` record the correction and the deferral of the standing
  remedy.
- Each correction is listed in the register below. The register is the complete set; a correction
  absent from it is an unrecorded edit to a merged migration and a Rule 3 violation.

#### Standing remedy (freeze landed 2026-09-28; reconstruction deferred)

> [!NOTE]
> **Freeze landed 2026-09-28 (v1.4).** `0001_bootstrap` no longer reads the ORM. It executes
> `migrations/baseline/0001_baseline_schema.sql`, the exact schema the live-model bootstrap
> produced on that date. A fresh chain was shown to reach a byte-identical schema, both after step 0
> and at head, compared with `pg_dump --schema-only`. The exact commands, scope and hashes are in
> `docs/ops/audits/BASELINE_FREEZE_2026-09-28.md`. From that date a model change can no longer
> reach back into step 0. The trigger was the conversion of `users.id` to a UUID: the live bootstrap
> would have created a UUID `users.id` beneath historical migrations that add integer foreign keys
> to it. That is a type change, not an absent element, so §V.B could not cover it.
>
> This is a freeze of the 2026-09-28 schema, **not** a reconstruction of the original baseline.
> Elements removed from the ORM before that date are still absent at step 0, so the two corrections
> in the register below remain load-bearing. What remains of the remedy is the reconstruction; no
> new §V.B correction can arise from a model change made after the freeze.

The full remedy is a baseline that reconstructs the schema as it stood when the historical
migrations were written, so each one executes against the schema it was written against. The
freeze above stopped new drift; the reconstruction is still open, tracked as post-launch
architectural debt in issue #1649 (carried from the post-launch tracker, archived 2026-10-22, and
before it the pre-launch ship tracker, archived 2026-09-28). The bootstrap is itself a
merged migration, so the remedy is a baseline replacement, not an edit under this section.

*Superseded (v1.9):* the reconstruction was not performed. §V.C replaced the baseline instead, so the
supported lineage no longer replays the revisions this remedy concerned.

#### Register of corrections

| Revision | Absent element | Historical operation | Corrected |
|----------|----------------|----------------------|-----------|
| `3a69db4907b4` | `announcements.user_id` | backfill delete + `alter_column(nullable=False)` | 2026-09-17 |
| `8f1a2c3d4b5e` | `policy_transitions.created_by` (table retired 2026-09-30) | `create_foreign_key("fk_policy_transitions_created_by")` | 2026-09-17 |

**`3a69db4907b4` — Clean up announcement model.** Announcement authorship moved from a `User` to a
`Seat`; `announcements` now carries `created_by_seat_id` and no `user_id`. The bootstrap therefore
creates the table without `user_id`, and `alter_column('announcements', 'user_id', nullable=False)`
raises on a fresh chain. The correction wraps the backfill delete and the `alter_column` in
`column_exists('announcements', 'user_id')`. The unguarded `alter_column` on `class_id` is
untouched, because `class_id` still exists. No row is destroyed that was not already destroyed: on
a fresh chain there are no rows, and where `user_id` exists the original delete runs unchanged.

*Known and deliberately not corrected:* this revision's `downgrade()` ends with an unguarded
`alter_column('announcements', 'user_id', nullable=True)`, which carries the same defect in the
reverse direction. It is left alone for two reasons. Condition 4 permits only the guard on the
operation that fails, and this one does not fail — it is unreachable: `c7a7b8c9d0e1` sits later in
the chain and raises on downgrade by design, so no downgrade from head can arrive at this revision.
Guarding an unreachable statement would be tidying a merged migration, which the prohibition list
forbids. If the frozen-baseline remedy lands, this disappears with the rest of the problem; if a
future change ever makes that downgrade reachable, it becomes a live candidate and must be evaluated
on its own evidence.

**`8f1a2c3d4b5e` — Add policy transition created_by FK.** The same rename: `policy_transitions`
carried `created_by_seat_id` and no `created_by`. (1.6: the table itself was retired by operator ruling
2026-09-30 and is dropped by `dd52b19d48d8`; the frozen baseline still creates it at step 0, so this
historical revision replays unchanged and the correction stays load-bearing.) The revision adds a foreign key on `created_by`,
which cannot exist on a fresh chain. The correction returns early unless
`column_exists("policy_transitions", "created_by")`, and adds the `column_exists` helper the file
lacked. The pre-existing `foreign_key_exists` guard is preserved beneath it.

Neither correction retargets its operation onto `created_by_seat_id`. That column is created by the
bootstrap with its constraints already in place, and rewriting a historical revision to constrain a
column that did not exist when it was written would change its intended end state, which condition 6
forbids.

#### Independent Evaluation

Each candidate is evaluated on its own evidence. The register is a record of past decisions, not
precedent: resemblance to a listed correction is not evidence that a candidate qualifies.

---

### V.C Schema Eras and Baseline Replacement

#### V.C.1 Definitions

1. **Schema era.** A period of supported persistence continuity. It begins at an *era baseline*
   and includes every revision descended from it. Eras are independent of software version
   numbering; a change is classified and numbered by `SOP-DB-004` whether or not it touches an era
   boundary.
2. **Era baseline.** A validated, frozen, hashed schema artifact under `migrations/baseline/`, and
   the single Alembic revision (`down_revision = None`) that executes it after checking its
   SHA-256. It is the only root of the supported lineage.
3. **Supported lineage.** The era baseline and every revision in `migrations/versions/`. These are
   the only revisions an installation may be at.
4. **Release schema bundle.** `migrations/fresh/<revision>/`: the installation artifact that creates
   a new database directly at a release revision (`docs/self-hosting/fresh-database.md`). It is
   derived from the supported lineage at that revision and never maintained as an independent schema
   definition.
5. **Provenance.** Superseded migration files, baselines, registers and records, kept under
   `migrations/archive/` and `docs/ops/audits/` for engineering history. **Historical preservation
   is not operational support.** Nothing in provenance is executed, imported, linked into the
   lineage, tested for executable compatibility, or upgradable from.

#### V.C.2 Rules

1. **The era baseline executes only on a database with no application-owned object.** Before it
   runs, the database may hold exactly these infrastructure objects and nothing else:
   - the `public` schema and PostgreSQL's system schemas (`pg_catalog`, `information_schema`,
     `pg_toast` and other `pg_*` schemas);
   - the `plpgsql` extension;
   - Alembic's `public.alembic_version` table with no rows, its primary key `alembic_version_pkc`,
     and the row and array types PostgreSQL creates for that table.

   Any other schema, extension, event trigger, or any relation, type, function, operator, operator
   class, operator family, collation, conversion, extended-statistics object or text-search object
   (configuration, dictionary, template or parser) in `public` is application-owned or unknown,
   and the baseline refuses, naming what it found. It never skips. A database without a supported
   revision and with objects in it is unknown, not baselined.
2. The era baseline's `downgrade()` raises and it is listed in `migrations/forward_only_register.txt`.
3. The era baseline is a frozen artifact, never a materialization of live ORM metadata. (Live
   metadata at step 0 is the defect §V.B existed to patch.)
4. Upgrade obligations hold within the era. Downgrade and re-upgrade obligations hold where a
   revision supports them (Golden Rule 2; `SOP-DB-004` §V.5–§V.6).
5. Cross-era migration compatibility is neither presumed nor guaranteed. A database recorded at a
   revision outside the supported lineage is refused, not repaired.
6. Every release schema bundle reproduces, digest for digest, the schema and reference state of the
   supported lineage replayed to its revision, and CI enforces it.

#### V.C.3 Establishing a new era

A new era requires an explicit owner decision recorded in this section. It is announced in
`CHANGELOG.md` and to operators far enough in advance for them to conclude their existing classroom
economies; the decision sets the notice period. The announcement precedes the first release that
refuses the previous era.

#### V.C.4 Baseline replacement within an era

Replacing an era's baseline without starting a new era requires all of:

1. explicit owner authorization;
2. a baseline revision identifier that already exists in the supported lineage, so no supported
   installation is re-stamped;
3. every later revision byte-identical, shown by hash;
4. demonstrated equivalence, by execution (`INV-ARC-017` §V): the new baseline reproduces the schema
   the replaced chain produced at that revision; production's catalog matches the supported lineage
   at production's revision; the replay path and the release bundle agree; populated synthetic
   databases upgrade equivalently through both lineages; unsupported revisions and unknown
   databases fail closed;
5. an audit record under `docs/ops/audits/` that states separately what production historically
   executed, what the supported lineage contains, and what fresh installations execute;
6. preservation of the superseded artifacts as provenance (§V.C.1(5)).

A release announcement naming the retired revisions is sufficient notice for a replacement within an
era when no known supported installation is at a retired revision. That does not relax §V.C.3.

#### V.C.5 The v2 era

| | |
|---|---|
| Era began | 2026-09-26, the public v2.0.0 launch (`26d1792b5`), the start of supported persistence continuity |
| Era baseline | `d7a3e9b1c5f2` — `migrations/baseline/d7a3e9b1c5f2_v2_launch_schema.sql` (SHA-256 `3ee2db4a…813528f`) |
| Baseline replaced | 2026-11-24, under §V.C.4 (`docs/ops/audits/BASELINE_REPLACEMENT_2026-11-24.md`) |
| Provenance | `migrations/archive/v2_prelaunch/` (171 revisions, the 2026-09-28 frozen SQL, the prior registers); `migrations/archive/v1_196_migrations/` (v1) |

Historical facts, which this section does not rewrite:

- **2026-04-29**: the v1 migrations were squashed into a v2 development baseline, revision `0001`
  (`672ee361c`), which materialized the live ORM. This was a developmental milestone of the v1 → v2
  clean break, not the start of supported persistence continuity: no v1 data was migrated and no
  supported installation existed.
- **2026-09-26**: production was recreated empty and built by `flask db upgrade` at `26d1792b5`:
  revision `0001` materialized the live ORM, then 170 revisions ran to `d7a3e9b1c5f2`
  (`docs/ops/audits/TRANSITION_2026-09-26_26d1792b5.md`).
- **2026-09-27**: revision `0001` began executing the frozen 2026-09-28 SQL instead
  (`docs/ops/audits/BASELINE_FREEZE_2026-09-28.md`). Production never executed it.
- **2026-11-24**: the supported lineage begins at the launch baseline; fresh installations still
  initialize from their release schema bundle.

## VI. Migration Best Practices

### Core Principle: Migrations Must Be Idempotent

**Idempotent migrations** can be run multiple times without causing errors or data corruption. This is critical because:

1.  Schema changes may have been applied manually in production to fix urgent issues.
2.  Previous migration runs may have partially completed before failing.
3.  The same migration may exist in multiple branches that get merged.

### Required Idempotency Helpers

Every migration MUST include these helper functions to enable safe existence checks:

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

### Usage Patterns

#### Upgrade Safety
```python
def upgrade():
    # IDEMPOTENT - Safe to run multiple times
    if not column_exists('student', 'email'):
        op.add_column('student', sa.Column('email', sa.String(length=255), nullable=True))
        print("✅ Added email column to student")
    else:
        print("⚠️  Column 'email' already exists on 'student', skipping...")
```

#### Downgrade Safety
```python
def downgrade():
    # Check before dropping
    if column_exists('student', 'email'):
        op.drop_column('student', 'email')
        print("❌ Dropped email column from student")
    else:
        print("⚠️  Column 'email' does not exist on 'student', skipping...")
```

---

## VII. Implementation Guidelines

### Migration Naming Conventions
Use descriptive names that clearly state changes:

- **Add Column:** `flask db migrate -m "Add join_code to Transaction table"`
- **Create Table:** `flask db migrate -m "Create RecoveryRequest table"`
- **Remove Column:** `flask db migrate -m "Remove deprecated field from StoreItem"`
- **Renaming:** `flask db migrate -m "Rename student_id to user_id in Transaction"`
- **Relationship:** `flask db migrate -m "Add foreign key between Student and Teacher"`

### Common Scenarios

#### 1. Adding a Required Field to Existing Table
**Problem:** Cannot add `nullable=False` to a table with existing data.
**Solution:**

1.  Add column as `nullable=True`.
2.  Backfill data (UPDATE).
3.  Alter column to `nullable=False`.

```python
def upgrade():
    # 1. Add nullable
    if not column_exists('student', 'email'):
        op.add_column('student', sa.Column('email', sa.String(255), nullable=True))
    
    # 2. Backfill
    op.execute("UPDATE student SET email = 'default@example.com' WHERE email IS NULL")
    
    # 3. Make required
    op.alter_column('student', 'email', nullable=False)
```

#### 2. Renaming a Column
```python
def upgrade():
    op.alter_column('transaction', 'student_id', new_column_name='user_id')

def downgrade():
    op.alter_column('transaction', 'user_id', new_column_name='student_id')
```

#### 3. Data Migration
When transforming existing data:
```python
def upgrade():
    op.add_column('student', sa.Column('full_name', sa.String(255)))
    
    connection = op.get_bind()
    connection.execute("""
        UPDATE student
        SET full_name = first_name || ' ' || last_initial
    """)
```

---

## VIII. Policy Standards

### Schema Change Gate
This gate is **PR‑blocking**.

**Applies when:**

- Dropping/Renaming columns or tables
- Removing/Changing Foreign Keys
- Replacing relations

**PR Classification:**

- [ ] **EXPAND** – Additive, backward-compatible
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal
- [ ] **CONTRACT (DATABASE)** – Destructive migration

### Schema Contraction Policy ("Expand and Contract")

**Phase 1: Expand (Release N)**

- New elements exist alongside legacy.
- Schema supports both; the application writes only the new form (`SOP-DB-004` §VII–VIII).
- NO destructive migrations.

**Phase 2: Contract Code (Release N+1)**

- Legacy removed from Code models.
- DB column remains.
- Application operates without legacy.

**Phase 3: Contract Database (Release N+2)**

- Migration drops legacy column/table.
- Isolated migration.

### Constraint Name Agnosticism
**Rule:** NEVER use hardcoded constraint names.
**Pattern:**
```python
from sqlalchemy import inspect
bind = op.get_bind()
inspector = inspect(bind)
for fk in inspector.get_foreign_keys('students'):
    if fk['referred_table'] == 'admins':
        op.drop_constraint(fk['name'], 'students', type_='foreignkey')
```

---

## IX. Workflows

### Standard Cycle
1.  **Sync:** `git fetch origin main && git merge origin/main`
2.  **Verify Head:** `flask db heads` (Must be 1)
3.  **Code:** Modify `app/models.py`
4.  **Generate:** `flask db migrate -m "Description"`
5.  **Review & Guard:**
    - Verify `down_revision`
    - **Add Idempotency Helpers**
    - Wrap `op` calls in existence checks
6.  **Lint:** `python scripts/lint_migrations.py`
7.  **Test:** `flask db upgrade` → `flask db downgrade` → `flask db upgrade`
8.  **Commit:** Git allowlist model and migration files

### Fixing "Multiple Heads"
1.  `flask db merge heads -m "Merge migration heads"`
2.  Review generated merge file.
3.  `flask db upgrade`
4.  Test and commit.

### Deployment Checklist
- [ ] Migrations tested locally (upgrade + downgrade)
- [ ] Idempotency verified
- [ ] Staging rehearsal complete
- [ ] Backup plan ready

---

## X. Deprecation Standards

**Registry:** `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-002_Deprecated_Symbols_Registry.md`

**Deprecated Patterns:**

- `datetime.utcnow()` → `datetime.now(datetime.UTC)`
- `Query.get()` → `db.session.get(Model, id)`

---

## XI. Resources
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Inspector API](https://docs.sqlalchemy.org/en/20/core/reflection.html)
## XII. Amendment

### Revision History

> [!NOTE]
> v1.1 (2026-09-14) adds §V.A, a named exception to Golden Rule 3. Rule 3 is not weakened:
> merged migrations are still never edited. §V.A defines the one circumstance in which following
> Rule 3 literally would preserve an execution path that destroys state protected by a superior
> `INV` or `DOM` document, and it prohibits every other use.
>
> v1.3 (2026-09-17) adds §V.B, a second named exception, narrower than the first. It exists because
> `0001_bootstrap` builds the baseline from *today's* ORM metadata rather than from a frozen
> snapshot, so a schema element removed from the ORM after a historical migration was written is
> absent when that migration replays — and the migration fails on a schema it was never written
> for. §V.B permits only the guard that declines the operation in that case. It may not change what
> the migration does when the element is present, and it may not alter the migration's intended end
> state. Golden Rule 3 now names two exceptions and no others.

> v1.7 (2026-10-06): Phase 1 of the Schema Contraction Policy no longer says the application supports
> both forms. Physical schema coexistence is permitted; dual-write, fallback and heuristic
> interpretation are not (`SOP-DB-004` §VII, owner ruling 2026-10-06). No other rule changes.
>
> v1.8 (2026-10-22): the baseline reconstruction is tracked in issue #1649; the post-launch tracker
> it named is archived. No rule changes.
>
> v1.9 (2026-11-24): adds §V.C, Schema Eras and Baseline Replacement (owner rulings 2026-11-24). The
> supported v2 lineage begins at the v2.0.0 launch baseline `d7a3e9b1c5f2`; the 171 pre-launch
> revisions and the 2026-09-28 frozen SQL become provenance. §V.B is retired as an exception and kept
> as provenance; Golden Rule 3 now names §V.A only.

Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.

# Baseline freeze evidence, 2026-09-28

Evidence for replacing `0001_bootstrap`'s live-ORM `metadata.create_all` with the frozen schema in
`migrations/baseline/0001_baseline_schema.sql` (SOP-DB-001 §V.B *Standing remedy*). This follows the
evidence practice of INV-ARC-017 §V: exact commands, scope and results.

## Claim

A fresh migration chain through the frozen bootstrap produces the same schema as a chain through the
live-ORM bootstrap it replaces, both immediately after revision `0001` and at head.

## Scope

- **Code under comparison:** commit `7f2bb2562` (`fix/teacher-ticket-categories`, head revision
  `e1c7a4b9d2f3`). Both sides use the models as they stood before the `users.id` UUID change. The only
  difference between the two sides is `migrations/versions/0001_bootstrap.py`.
- **Server:** PostgreSQL 14.18 (local). **Dump tool:** `pg_dump` 17.5.
- **Databases:** four empty throwaway databases, one per run.
- **Compared object:** the whole `public` schema, excluding `alembic_version` at step 0, with comment
  lines and psql meta lines removed. Nothing else is excluded.

## Source trees

All four runs used a single git worktree, detached at `7f2bb2562`.

- **Live-ORM side** (`cth_freeze_base_test`, `cth_freeze_old_test`): ran with a clean working tree
  at `7f2bb2562`, before any file was changed.
- **Frozen side** (`cth_freeze_b2_test`, `cth_freeze_new_test`): ran from the same worktree after the
  freeze was written. At that point `git status --porcelain --ignored` (excluding `__pycache__`)
  showed exactly two differences from `7f2bb2562`:

  ```
   M migrations/versions/0001_bootstrap.py
  !! migrations/baseline/
  ```

  Both files are byte-identical to the versions committed in `70ed32883` and at the head of #1433:

  | File | SHA-256 (first 16), worktree = `70ed32883` = PR head |
  |---|---|
  | `migrations/versions/0001_bootstrap.py` | `50a81a191340530a` |
  | `migrations/baseline/0001_baseline_schema.sql` | `ac82a43c16dc392e` |

The only thing that differs between the two sides is therefore the bootstrap under test, and the
frozen side is the code this PR ships. The step-0 schema on the frozen side comes from the SQL file
alone, because the frozen bootstrap does not import the models.

## Procedure

`$R` is the Postgres server URL without a database name. Each database starts empty.

```bash
# 1. Live-ORM bootstrap (merged 0001), step 0 only and full chain
DATABASE_URL="$R/cth_freeze_base_test" flask db upgrade 0001
DATABASE_URL="$R/cth_freeze_old_test"  flask db upgrade

# 2. Capture the frozen baseline from the step-0 database
pg_dump "$R/cth_freeze_base_test" --schema-only --no-owner --no-privileges --no-comments \
  --exclude-table=alembic_version -n public > baseline_raw.sql
#    Then remove session settings (SET ..., set_config, CREATE SCHEMA public, comments). Also restore
#    the 13 CHECK constraints to the `column IN (...)` form they were created with, because
#    re-executing pg_dump's deparsed `= ANY ((ARRAY[...])::text[])` form stores a different
#    deparse. The result is migrations/baseline/0001_baseline_schema.sql.

# 3. Frozen bootstrap, step 0 only and full chain
DATABASE_URL="$R/cth_freeze_b2_test"  flask db upgrade 0001
DATABASE_URL="$R/cth_freeze_new_test" flask db upgrade

# 4. Compare
D() { pg_dump "$R/$1" --schema-only --no-owner --no-privileges -n public "${@:2}" | grep -v '^--\|^\\'; }
D cth_freeze_base_test --exclude-table=alembic_version > b_old.sql
D cth_freeze_b2_test   --exclude-table=alembic_version > b_new.sql
D cth_freeze_old_test  > head_old.sql
D cth_freeze_new_test  > head_new.sql
diff b_old.sql b_new.sql && diff head_old.sql head_new.sql
```

## Result

`diff` produced no output for either pair.

| Artifact | Lines | SHA-256 (first 16) |
|---|---|---|
| `b_old.sql`, step 0, live-ORM bootstrap | 2734 | `a7d63d5755b0417b` |
| `b_new.sql`, step 0, frozen bootstrap | 2734 | `a7d63d5755b0417b` |
| `head_old.sql`, head `e1c7a4b9d2f3`, live-ORM bootstrap | 3283 | `a384b9041c3a63d0` |
| `head_new.sql`, head `e1c7a4b9d2f3`, frozen bootstrap | 3283 | `a384b9041c3a63d0` |
| `migrations/baseline/0001_baseline_schema.sql` as committed | 1812 | `ac82a43c16dc392e` |

A first attempt, before the CHECK constraints were restored, differed only in 9 CHECK constraints.
They had the same names and the same allowed values and deparsed differently. That is the reason for
the rewrite in step 2.

The dumps themselves are not committed: `*.sql` is ignored except for the baseline file, and they
are reproducible with the procedure above.

## What this does not show

The freeze fixes the schema that the live bootstrap produced **on 2026-09-28**. It is not a
reconstruction of the baseline as it stood when the historical migrations were written. The two
§V.B corrections therefore remain necessary.

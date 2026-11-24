# Baseline reconstruction evidence, 2026-11-24

Evidence for closing issue #1649 (`SOP-DB-001` §V.B *Standing remedy*) by reconstructing
`migrations/baseline/0001_baseline_schema.sql` so the two registered Bootstrap-Replay Corrections
(`3a69db4907b4`, `8f1a2c3d4b5e`) replay against the schema they were actually written for. This is a
follow-up to, and does not amend, `BASELINE_FREEZE_2026-09-28.md`. It follows the same evidence
practice (`INV-ARC-017` §V): exact commands, scope and results.

## Claim

1. The reconstructed baseline differs from the frozen 2026-09-28 baseline **only** by the two
   elements the register names: `announcements.user_id` and `policy_transitions.created_by`, added
   back in the form they had immediately before the commit that removed each one.
2. A fresh chain through the reconstructed baseline reaches, at head, a schema byte-identical to a
   fresh chain through the pre-reconstruction (frozen) baseline. The two chains diverge only at step
   0, by exactly the two added elements, and converge again by the time either of the two corrected
   revisions has run.
3. Where the element is present, `3a69db4907b4` and `8f1a2c3d4b5e` execute the branch their
   `column_exists`/`foreign_key_exists` guard was written to protect — not the skip branch — so the
   two corrections registered under `SOP-DB-001` §V.B no longer carry the chain on a fresh database.

## Git archaeology

Both elements were found by `git log -S`/`--follow` on `app/models.py`, cross-referenced against the
migration that performed each rename:

- **`announcements.user_id`.** Introduced with the model (commit `8193291b`, "Add teacher
  announcement system"). Commit `180a55a7` ("Phase 9 legacy deletion and Phase 10 certification",
  #1313) changed it from `nullable=True` to `nullable=False` and is the same commit that authored
  migration `3a69db4907b4`. Commit `27c2a7f0` ("Enforce seat-owned lifecycles and scoped identity
  lookup") renamed it to `created_by_seat_id` (FK retargeted from `users.id` to `seats.id`) and is
  the same commit that authored migration `c7a7b8c9d0e1`, which performs the live rename
  (`_replace_author`).
- **`policy_transitions.created_by`.** Introduced as a bare `db.Column(db.Integer, nullable=True)`
  (no foreign key) in commit `3ddf973a` ("Scaffold policy lineage tables for wave 4 class config"),
  the same commit that authored migration `c4e36a4ab2f1` (table creation, guarded by
  `table_exists`). Commit `513c3f81` ("Enforce FEAT boundaries and canonicalize insurance
  redemptions") added `db.ForeignKey('users.id')` to the column and is the direct ancestor commit of
  migration `8f1a2c3d4b5e` ("add fk for policy_transitions.created_by", one day later), whose entire
  job is adding that foreign key. Commit `27c2a7f0` later renamed it to `created_by_seat_id` (FK
  retargeted to `seats.id`), authoring `c7a7b8c9d0e1`'s rename of this column too.

## Scope check: no third element

Commit `27c2a7f0` (which authored `c7a7b8c9d0e1`) also renamed `store_products.user_id` to
`created_by_seat_id`, and dropped (not renamed) `ledger_transaction.user_id`,
`attendance_sessions.target_user_id`, `payroll_event.target_user_id`, `issues.sysadmin_id`, and
`audit_events.teacher_id`. Each of the migrations that still names one of these six elements
(`b7c41e9a2f30`, `93de308c02c0`, `b2c3d4e5f8a`, `c3d4e5f8a9b`, `d4e5f6a7b8c`, `f83ba4e63062`,
`042824e29710`) was confirmed, by walking the `down_revision` graph from each candidate to
`c7a7b8c9d0e1`, to be its **ancestor** — it ran while the element still existed, before
`c7a7b8c9d0e1` removed it in the same migration chain. None of them needs a §V.B correction.
`store_products` additionally recreates itself from scratch behind its own pre-existing
`table_exists` guard (`b7c41e9a2f30`), which already no-ops once the table exists in the
frozen/reconstructed baseline shape, independent of this reconstruction. The register's two rows are
therefore the complete set; no further gap was found.

## Baseline edit

`migrations/baseline/0001_baseline_schema.sql`:

- `announcements`: added `user_id integer` (nullable, no `NOT NULL`) immediately after `id`, and
  `ADD CONSTRAINT announcements_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON
  DELETE CASCADE` alongside the other `announcements` foreign keys. `created_by_seat_id` and its
  existing foreign key are untouched; the two columns coexist in the baseline only so
  `3a69db4907b4` can act on `user_id` before `c7a7b8c9d0e1` backfills `created_by_seat_id` from it
  and drops it, reproducing the original chain's intent.
- `policy_transitions`: added `created_by integer` (nullable, **no** foreign key) immediately after
  `created_at`. `created_by_seat_id` is untouched. No foreign key is added for `created_by` because
  `8f1a2c3d4b5e`'s entire purpose is adding that foreign key — giving it one in the baseline would
  make the guarded `create_foreign_key` call redundant rather than replaying the historical
  operation.

No other line of the baseline file changed.

## Scope

- **Code under comparison:** this PR's branch, head revision `4fad9d362d0d`. The only difference
  between the "old" and "new" runs below is `migrations/baseline/0001_baseline_schema.sql`; the "old"
  file is the one this PR replaces (identical to the pre-reconstruction `main`).
- **Server:** PostgreSQL 16 (local). **Dump tool:** `pg_dump` (matching server major version).
- **Databases:** four empty throwaway databases, one per run, plus a fifth used only to stop the
  chain mid-way and inspect intermediate state (not part of the schema comparison).
- **Compared object:** the whole `public` schema, excluding `alembic_version`, with comment lines and
  psql meta lines removed via `grep -v '^--\|^\\'`. Nothing else excluded.

## Procedure

```bash
# 0. Save both baseline variants
git show HEAD:migrations/baseline/0001_baseline_schema.sql > old_baseline.sql   # pre-reconstruction
cp migrations/baseline/0001_baseline_schema.sql new_baseline.sql               # reconstructed

# 1. Old baseline: step 0 and full chain
cp old_baseline.sql migrations/baseline/0001_baseline_schema.sql
DATABASE_URL=".../cth_1649_old_base" flask db upgrade 0001
DATABASE_URL=".../cth_1649_old_head" flask db upgrade

# 2. New baseline: step 0 and full chain
cp new_baseline.sql migrations/baseline/0001_baseline_schema.sql
DATABASE_URL=".../cth_1649_new_base" flask db upgrade 0001
DATABASE_URL=".../cth_1649_new_head" flask db upgrade

# 3. Compare
D() { pg_dump "$1" --schema-only --no-owner --no-privileges -n public --exclude-table=alembic_version \
      | grep -v '^--\|^\\'; }
D cth_1649_old_base > old_base.sql;  D cth_1649_new_base > new_base.sql
D cth_1649_old_head > old_head.sql;  D cth_1649_new_head > new_head.sql
diff old_base.sql new_base.sql   # expected: exactly the two added elements
diff old_head.sql new_head.sql   # expected: no output

# 4. Confirm the guards take the present branch (new baseline only, separate database)
DATABASE_URL=".../cth_1649_check" flask db upgrade 8f1a2c3d4b5e
psql cth_1649_check -c "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                         WHERE conname='fk_policy_transitions_created_by'"
DATABASE_URL=".../cth_1649_check" flask db upgrade 3a69db4907b4
psql cth_1649_check -c "\d announcements"   # user_id column must read "not null"

# 5. Single head
flask db heads
```

## Result

`diff old_base.sql new_base.sql` showed exactly the two added elements (the new `user_id` column and
its foreign key on `announcements`, and the new `created_by` column on `policy_transitions`) and
nothing else. `diff old_head.sql new_head.sql` produced no output.

| Artifact | Lines | SHA-256 |
|---|---|---|
| `old_base.sql`, step 0, pre-reconstruction baseline | 2735 | `03f935968ea26618…` |
| `new_base.sql`, step 0, reconstructed baseline | 2742 | `872275bb8da2f27b…` |
| `old_head.sql`, head `4fad9d362d0d`, pre-reconstruction baseline | 3440 | `e0e93a43b01b5f50…` |
| `new_head.sql`, head `4fad9d362d0d`, reconstructed baseline | 3440 | `e0e93a43b01b5f50…` |

`old_head.sql` and `new_head.sql` have the identical SHA-256, confirming claim 2.

**Guard branch confirmation (claim 3).** Stopping a fresh chain built from the reconstructed baseline
at `8f1a2c3d4b5e` and inspecting `pg_constraint` showed `fk_policy_transitions_created_by` present
with definition `FOREIGN KEY (created_by) REFERENCES users(id)` — the guard's `if not
column_exists(...): return` did not fire, and the `if not foreign_key_exists(...)` branch ran
`create_foreign_key` as originally written. Stopping the same chain at `3a69db4907b4` and inspecting
`announcements` showed `user_id` as `integer NOT NULL` — the guarded `alter_column(...,
nullable=False)` executed, not the skip. Both corrections' guarded branches are therefore provably
dead code on a fresh chain going forward, while remaining correct (taking the skip branch) for any
database that was migrated before this reconstruction landed.

`flask db heads` reported exactly one head (`4fad9d362d0d`) both before and after the baseline edit.

### Downgrade reachability

Per `SOP-DB-001` §V.B condition 7, a downgrade across a corrected revision is proven only when it is
reachable from head. It is not, for either correction: `c7a7b8c9d0e1` (an ancestor of both
`3a69db4907b4` and `8f1a2c3d4b5e` in the revision graph) refuses its own downgrade
(`raise RuntimeError('Irreversible schema cleanup...')`), so no downgrade walk starting at head can
reach either corrected revision. This was already true before the reconstruction and is unchanged by
it; no downgrade across either correction is claimed as evidence here.

## Test suite

The full suite (`pytest`, no path filter) was run against the reconstructed baseline. See the PR
description for the run's outcome; `tests/conftest.py` rebuilds the schema from this migration chain
for every test session, so a passing full run exercises the reconstructed baseline for every test in
the repository, not only the migration-focused ones named above.

## What this does not show

This reconstruction does not re-verify the 2026-09-28 freeze itself (see
`BASELINE_FREEZE_2026-09-28.md` for that evidence) and does not search for ORM drift unrelated to the
two elements in the register — the "Scope check" section above is the search that was done, limited
to elements touched by the same commit (`27c2a7f0`) that caused the two registered gaps. A different,
independent drift elsewhere in the schema's history is out of scope for this change.

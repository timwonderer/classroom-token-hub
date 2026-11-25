# Migration Archive

## v1_196_migrations

- Archive date: 2026-04-30
- Archived from: `migrations/versions/`
- Archived count: 196 migration files
- Prior Alembic head before squash: `db80eb72e775`

This archive preserves the pre-squash migration history used before the v2 bootstrap baseline.

## v2_prelaunch

- Archive date: 2026-11-24 (SOP-DB-001 v1.9 §V.C)
- Archived from: `migrations/versions/`, `migrations/baseline/`, `migrations/forward_only_register.txt`, `migrations/lint_baseline.txt`
- Archived count: 171 revision files (root `0001` through launch head `d7a3e9b1c5f2`), the 2026-09-28 frozen SQL `baseline/0001_baseline_schema.sql`, and the two registers as they stood before the replacement
- Every file is byte-identical to its last operational version (`docs/ops/audits/BASELINE_REPLACEMENT_2026-11-24.md`)

The developmental v2 chain that led to the public v2.0.0 launch on 2026-09-26. Production was built
through it once, from empty, at launch. The supported lineage now begins at the launch baseline
`d7a3e9b1c5f2` in `migrations/versions/`, which reproduces this chain's schema at that revision.

Historical preservation is not operational support. Nothing here is executed, imported, linked into
the lineage or upgradable from; `versions/d7a3e9b1c5f2_add_insurance_recurring_billing_terms.py` is
the original launch-head file, whose revision id lives on as the baseline.

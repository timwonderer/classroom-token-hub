# v2 launch baseline replacement, 2026-11-24

Evidence for replacing the developmental v2 chain with the v2.0.0 launch baseline as the root of the
supported lineage (`SOP-DB-001` v1.9 §V.C.4). Follows the evidence practice of `INV-ARC-017` §V:
exact commands, scope and results. Owner rulings of 2026-11-24: feasibility, preliminary validation
authorization, and implementation authorization.

**Status at writing:** implemented on branch `feat/v2-launch-baseline` from `main` `fde9a6537`.
Validated as recorded below, including the full test suite (V6).
Not merged, released or deployed. Production was read, never changed.

## 1. Three facts kept apart

| | Fact | Source |
|---|---|---|
| **What production executed** | On 2026-09-26 the public schema was recreated empty and `flask db upgrade` ran at `26d1792b5` (v2.0.0). Revision `0001` materialized the live ORM, and 170 revisions followed to `d7a3e9b1c5f2`, giving 46 tables. Every later revision (21, to `a0faf8b2a35d` at v2.5.0) ran as an ordinary upgrade. Production never executed the 2026-09-28 frozen baseline: that shipped in v2.0.1 (`70ed32883`, not an ancestor of `v2.0.0`). | `TRANSITION_2026-09-26_26d1792b5.md`; `git merge-base --is-ancestor` |
| **What the supported lineage contains** | Root `d7a3e9b1c5f2`, which executes `migrations/baseline/d7a3e9b1c5f2_v2_launch_schema.sql` (SHA-256 `3ee2db4aca20f39ac00ea8e8aa982e3e66c635590692bd5326381b585813528f`), then the 21 post-launch revisions, unchanged. | this change |
| **What a fresh installation executes** | The release schema bundle for its release (`migrations/fresh/<revision>/`, `scripts/fresh_database.py`). The bundle is unchanged by this replacement. | `docs/self-hosting/fresh-database.md` |

The 2026-04-29 squash (`672ee361c`, 196 v1 revisions to `migrations/archive/v1_196_migrations/`)
began v2 *development*. Supported persistence continuity began at the public launch, and production
was wiped at that point.

## 2. Artifact provenance

The baseline SQL is `pg_dump` 14.24 `--schema-only --no-owner --no-privileges
--exclude-table=public.alembic_version`, taken from an empty PostgreSQL 14.24 database migrated to
`d7a3e9b1c5f2` by the pre-replacement chain on `main`. Normalization:

- session `SET`/`set_config` lines, `\restrict` markers and comments removed;
- `generate_fresh_database.installable_ddl()` applied, which restores the varchar `IN (...)` form
  `SOP-DB-001` records;
- a provenance header added.

The migration checks the SHA-256 before executing the file. It executes the file on the DBAPI
cursor without parameters, so `%` is literal, and only after confirming the database holds nothing
beyond the `SOP-DB-001` §V.C.2(1) infrastructure set.

## 3. Validation

Environment: local PostgreSQL 14.24 (production runs 14.24), `pg_dump` 14.24. Disposable `*_test`
databases only. Synthetic identities only (the `SPEC-TEST-001` canonical roster). Production was
read through the read-only connection, using catalog queries plus one hash over the 15 rows of the
`issue_categories` reference table.

| ID | Proves | Result |
|---|---|---|
| V1 | Production ≡ supported lineage | **Pass.** At production's revision `a0faf8b2a35d`, catalog fingerprints (counts and MD5 over sorted `name\|md5(definition)`) match the old-chain replay and the new-lineage replay. All 9 object classes match: 555 columns, 200 constraints with validation state, 249 indexes, 23 triggers, 22 functions with full bodies, 9 enums, 27 sequences, 74 relations, 1 extension. The secondary catalog query also matches: schema `public` only, 0 RLS policies, 0 rules, no comments, no non-default collations, no reloptions, 0 event triggers, 0 database settings, 47 tables. `issue_categories` matches: 15 rows, MD5 `db0a8aa63eb01ab79e06ee4e24b82df3`. Not compared: ownership, grants and sequence positions, which belong to the deployment and the data rather than the lineage. |
| V2 | Launch schema is reproducible | **Pass.** `flask db upgrade d7a3e9b1c5f2` from the `v2.0.0` tag (its own venv, SQLAlchemy 2.0.52 / Alembic 1.18.5, live-ORM bootstrap) and from `main` (frozen-SQL bootstrap) give byte-identical schema dumps: SHA-256 `6c5ca2a6e1502234…`, 2270 lines, 46 tables, no rows outside `alembic_version`. |
| V3 | Baseline artifact correctness | **Pass.** New lineage to `d7a3e9b1c5f2` gives dump `6c5ca2a6e1502234…`, identical to the `v2.0.0` tag. |
| V4 | Replay ≡ release bundle ≡ old lineage | **Pass.** New lineage to `a0faf8b2a35d` reproduces the committed bundle's `schema_sha256` `36c0f9a8…`. New and old lineages to head `4fad9d362d0d` give identical dumps (`70d4b21c8416d15f…`, 2391 lines). |
| V5 | Post-launch compatibility on populated data | **Pass.** See §4. |
| V6 | Operational equivalence: full suite | **Pass, one failure not caused by this change.** Full `pytest` at `ce251b0b2` (this branch with `main` merged) on an isolated database, with the schema rebuilt through the new lineage: 6257 passed, 16 skipped, 1 failed, in 53 min. The failure is `tests/dom/docs/test_documentation_index_complete.py::test_every_numbered_document_is_indexed`: `FEAT-IDEN-009` and `FEAT-LED-003` exist but SOP-DOC-001 does not list them. The same gap is on `origin/main`, and this change touches neither document. The later guard extension (`5d0e91547`) was verified by its targeted tests: 57 passed, plus a mutation check. |
| V7 | Post-launch migration tests on the new lineage | **Pass.** 650 passed: the post-launch migration tests (`test_users_id_uuid_migration`, `test_payroll_settings_authority_migration`, `test_policy_lineage_retirement_migration`, `test_penalty_vocabulary_migration`, `test_bug_reward_vocabulary_migration`, `test_insurance_date_release_migration`, `test_configuration_migration`, `test_migration_revision_generation`, `test_attendance_migration_rerun`) and all of `tests/dom/core`, `tests/dom/identity`, `tests/dom/support`. A further 173 passed in the changed and new files. CLI walk head → `a0faf8b2a35d` → head → `c8f1a2b3d490` succeeded. |
| V8 | Fail closed | **Pass.** (a) A database stamped `7c3d4e5f6a7b`: `Can't locate revision identified by '7c3d4e5f6a7b'`, nothing changed. (b) An unversioned database holding one table: the baseline refuses with "Found: relation seats, type _seats, type seats", nothing changed. (c) `flask db downgrade base` from the baseline refuses; revision unchanged. Also proven in `tests/dom/core/test_v2_era_baseline.py` against the real test database, including each permitted and forbidden object class. A deliberate mutation (refusal disabled) turned two of those tests red. |
| V9 | No cross-era obligation | **Pass.** No live revision's `down_revision` names an archived revision. No live source under `app/`, `scripts/`, `tests/`, `infra/`, `.github/` or `migrations/versions/` imports or executes an archived artifact. Both detectors have mutation proofs. |
| V10 | Registers and head | **Pass.** `flask db heads` = `4fad9d362d0d`, single root `d7a3e9b1c5f2`. `test_forward_only_revision_register.py` passes with the baseline added and the 28 pre-launch entries moved to the archive copy. `lint_migrations.py --baseline` reports 22 files, 0 errors, 0 warnings, with an empty baseline. |
| V11 | Forward-only boundaries | **Pass.** All 21 post-launch files are byte-identical to `origin/main` (`git hash-object`). All 171 archived revision files, the 2026-09-28 SQL and both archived registers are byte-identical to their last operational versions. The `c8f1a2b3d490` downgrade still refuses ("Forward-only insurance succession"). |
| V12 | Lasting assertions relocated | **Pass.** See §5. |

## 4. V5: populated synthetic equivalence

**Source state.** An empty database was migrated to `d7a3e9b1c5f2` by the `v2.0.0` tag, then
populated by the v2.0.0 application's own code and test helpers, each write inside its FEAT context:

- four classes, two of them the same teacher's, with a cross-teacher class and the Unicode roster;
- 15 students, 19 seats, 18 users;
- ledger payroll credits, checking → savings transfers and settled snapshots: 45 transactions and 30 snapshots;
- payroll settings through `upsert_payroll_settings`, which also wrote 4 `policy_versions` rows that post-launch `dd52b19d48d8` retires;
- store products, support tickets with correlation packs;
- 45 audit events on 4 chains.

The launch-era provisioning helper hand-builds a payroll-settings row without `first_pay_date`
("In production, teachers would configure these via UI"). Post-launch `a7e3c9d1f5b2` refuses such
rows. Both lineages refused identically, with "4 payroll_settings row(s) have no first_pay_date".
The seed was then corrected to date that row as the admin form, the only production writer, always
does. No migration and no assertion was loosened.

**Common start.** The old-lineage database is a template copy of the source. The new-lineage
database was built by the new baseline, then given the source's data (`pg_dump --data-only
--disable-triggers`, `alembic_version` excluded). Full schema-and-data dumps of source, old and new
were byte-identical before upgrading (`a893bbe341c10b0d…`).

**Upgrade.** Each database was upgraded to head `4fad9d362d0d` by its own tree: `main` for old,
the branch for new. Both exited 0.

**Deterministic equivalence.** The full dumps differ in 88 lines, all from two legitimate sources:

- `users.id` UUIDs generated by `gen_random_uuid()` in `f4b8d2a6c1e9`, and every foreign key carrying them;
- the `created_at` that `e1c7a4b9d2f3` takes from `now()` for the three categories it seeds.

Users were mapped between the two lineages by `username_lookup_hash`, which is deterministic: 18 of
18, a bijection. The seed timestamp was substituted. After that, the dumps are **byte-identical**:
44 lines normalized, nothing else differing. Byte identity covers encrypted values (copied
ciphertext, never re-encrypted), sequence positions, and audit digests and HMACs.

**Semantic preservation (source → old → new).** All of these are unchanged:

- ledger totals per class and account (MD5 `6b8c85be…`);
- balance snapshots (`42b7d27a…`);
- audit event hashes (45, `84b42a13…`);
- chain heads (`fbea16ce…`);
- seat → user joins (19);
- profile → seat joins (15).

The current code's `app.utils.audit_verifier.verify_chain` reports every chain `VERIFIED` (12, 12,
9, 12 events) on both lineages.

## 5. V12: retired tests and where their assertions went

| Retired | What it asserted | Where it went |
|---|---|---|
| `tests/dom/identity/test_claim_artifact_migration.py` | One-time cleanup of claim artifacts by `c1a1b2d3e4f5` | Transformation of pre-launch data that no supported database holds; provenance |
| `tests/dom/identity/test_recovery_session_migration.py` | `f4d4e5f6a7b8` adds nullable recovery-setup columns | `test_v2_era_baseline.py::test_student_recovery_session_columns_exist` |
| `tests/dom/identity/test_request_trace_migration.py` | `a5e5f6a7b8c9` binds traces to their class; no seat key | `::test_request_trace_lives_and_dies_with_its_class_only` |
| `test_seat_owned_records.py`, 5 tests replaying `c7a7b8c9d0e1` | Author mapping and legacy replay refusal during that migration | Migration mechanics; provenance. The end state stays covered by the file's runtime tests (`test_shipped_schema_has_only_identity_principal_references`, `test_authors_cannot_be_borrowed_from_another_class`, and others) |
| `test_support_permissions.py::test_permission_migration_defaults_old_rows_to_no_consent` | `issues.support_permissions` defaults to no consent | `::test_support_permissions_default_to_no_consent` |
| `test_support_permissions.py::test_support_seat_revision_scopes_the_ticket_without_a_key_to_seats` | `class_public_id` required; no key to seats | `::test_support_ticket_is_class_scoped_without_a_key_to_seats` |
| `test_no_cross_domain_seat_foreign_keys.py::test_the_removal_revision_does_not_restore_the_key_on_downgrade` | An unreachable downgrade of archived `d9e1f3a5b7c9` | The guard now also scans the era baseline SQL, with its own mutation proof |
| `test_teacher_signup_staging.py::test_migration_creates_encrypted_staging_and_is_repeatable` | Staging table holds only nonce hash, ciphertext and expiry | Same file, `test_staging_table_holds_only_encrypted_payload`, against the migrated schema |
| `test_insurance_claim_service.py::test_migration_revision_chain_links_to_head` | `a7b8c9d0e1f3`'s parent | Provenance |
| `test_insurance_claim_type_taxonomy.py::test_migration_mapping_matches_canonical_taxonomy` | `d4e5f6a7b8c9`'s inlined mapping | Provenance; the canonical taxonomy keeps its own tests |
| `test_migration_idempotency.py`, 5 replays of `b7c41e9a2f30`, `f1a2c3d4e5b6`, `a3b4c5d6e7f8`, `6b2c3d4e5f6a`, `7c3d4e5f6a7b` | Replaying those revisions over head destroys nothing | Those revisions cannot execute against any database any more (V8); provenance |

Kept and redirected: `test_migration_validator.py` reads two archived files as text, since it tests
the validator rather than the migrations. `test_forward_only_revision_register.py` now names
`d7a3e9b1c5f2` instead of archived `c7a7b8c9d0e1`, with a size floor of 8. The retired policy-lineage
guard now allowlists the baseline SQL; the archive was already excluded from its scan.

## 6. Known database revisions (read-only census)

Every database on the development host was read, `alembic_version` only. The development database
`classroom_economy` is at head `4fad9d362d0d`. Four local databases are at revisions outside the new
lineage:

- `classroom_economy_browser_cert` at `68e4cabff66e`;
- `cth_redteam` at `8357d4036478`;
- `production_dev` (retired v1-era development database) at `0b1c2d3e4f5a`;
- `canonical_v2_seed` at `b4c5d6e7f8g9,g1h2i3j4k5l6`, ids that never existed in either lineage.

None is a supported installation. They are reported, not changed. No staging host is known. No
attempt was made to discover independent self-hosted installations; the self-hosting installer has
only ever installed at `a0faf8b2a35d`, which is supported.

## 7. Classification (`SOP-DB-004` §VI)

| Value | Classification | Basis |
|---|---|---|
| Migration class | `M4 CONTRACT-DATABASE` | The change contains a forward-only revision: the baseline's `downgrade()` raises, where `d7a3e9b1c5f2`'s did not. |
| Historical state | `H0 UNAFFECTED` | No row is read differently, rewritten or removed. |
| Risk | High | Required by M4. It also changes a foundational installation and validation path. |
| Version | MINOR | §X.3 |
| Production effect | None | No DDL or data change. Production stays at `a0faf8b2a35d`, a revision in both trees. |

## 8. PR #1834 and issue #1649: findings preserved

PR #1834 (open, unmerged) reconstructed two columns in the 2026-09-28 frozen SQL so the two §V.B
corrections would replay against their original schema. Its archaeology, kept here because the PR
will be closed:

- **`announcements.user_id`:** introduced in `8193291b`; changed from nullable to `NOT NULL` in
  `180a55a7`, the commit that authored `3a69db4907b4`; renamed to `created_by_seat_id` (FK
  `users.id` → `seats.id`) in `27c2a7f0`, the commit that authored `c7a7b8c9d0e1`.
- **`policy_transitions.created_by`:** introduced as a bare `Integer` with no FK in `3ddf973a`
  (with `c4e36a4ab2f1`); gained `ForeignKey('users.id')` in `513c3f81`, the direct ancestor of
  `8f1a2c3d4b5e`; renamed in `27c2a7f0`.
- **Scope check:** `27c2a7f0` also renamed `store_products.user_id` and dropped five other principal
  columns. Every migration naming them is an ancestor of `c7a7b8c9d0e1`, so those two were the
  complete set.

All of it concerns revisions now in provenance. The replacement removes the class of defect, a
baseline later than the revisions replayed over it, rather than repairing instances of it. #1834 is
superseded and #1649 is resolved by this change once it is accepted.

## 9. Reproduction

`docs/ops/audits/evidence/2026-11-24_baseline-replacement/` holds:

- the catalog fingerprint queries (`catalog_fingerprint_agg.sql`, `catalog_fingerprint.sql` and
  `catalog_gaps.sql`; read-only, catalog only);
- the V5 seed (`v5_seed.py`, which runs from a `v2.0.0` worktree with that tag's requirements and
  test-only keys);
- the normalization (`v5_normalize.py`).

Every step above can be rerun against any PostgreSQL 14 server with disposable `*_test` databases.

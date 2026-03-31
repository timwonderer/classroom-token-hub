# V2 Main Reconciliation Tracker

**Last Updated:** 2026-03-30
**Source Branches:** `codex/v2.0` vs `origin/main`
**Diff Snapshot:** `git rev-list --left-right --count codex/v2.0...origin/main` -> `143 51`
**Purpose:** Current source of truth for features present on `origin/main` that have not yet been intentionally reconciled into `codex/v2.0`.

This tracker replaces the partial main-feature note previously embedded in `LOG-ARC-049`. `LOG-ARC-049` remains a historical readiness artifact; this document is the active parity tracker.

## Classification Vocabulary

- `must-port before live test`
- `must-port before production`
- `safe to defer`
- `landed on codex/v2.0`

## Port Strategy Vocabulary

- `cherry-pick`
- `manual port`
- `defer`

## Reconciliation Method

1. Start from unique `origin/main` commits relative to `codex/v2.0`.
2. Group by shipped behavior, not commit count.
3. Inspect touched code, migrations, tests, and docs for each cluster.
4. Classify by v2 launch impact.
5. Write implementation-ready steps for all `must-port` clusters.

## Feature Cluster Inventory

| Cluster | Source commits / PRs | Feature summary | Affected subsystems | Migration impact | Test impact | Doc impact | Classification | Port strategy | Rationale |
|---|---|---|---|---|---|---|---|---|---|
| Economy policy scheduling and rent-cycle locking | `589d6ba7` (`#1077`), `67a23022` (`#1103`), `a84da5a1` (`#1104`), `bac180ab` (`#1105`) | Refines economy policy mode, rebalance timing, CWI warning bypass controls, per-join-code rent rate locking, and penalty reversal behavior | `app/routes/admin.py`, `app/routes/student.py`, `app/utils/economy_balance.py`, `app/utils/economy_policy.py`, `app/utils/economy_rebalance.py`, admin economy/rent templates, JS | Core policy/rebalance/rent-locking behavior is already in v2; the remaining `main` delta is the CWI warning bypass flags from `3f4a5b6c7d8e_add_cwi_warning_bypass_flags.py` | `tests/test_economy_policy_mode.py`, `tests/test_rent_penalty_reversal.py`, related economy API tests | `CHANGELOG.md`, `README.md`, economy feature/domain docs | `must-port before live test` | `manual port` | Treat this as a narrow remaining delta, not a full unported cluster. Rent-cycle locking and penalty reversal are already landed on `codex/v2.0` |
| Insurance modularization and tiered setup flow | `8b967da6` (`#1090`), `3a9d6e92` (`#1092`), `1f8e06d7` (`#1093`), `2cddd34c` (`#1095`), `1a3be409` (`#1096`) and follow-up fix/docs commits in the same series | Moves insurance products to modular tiered design, finalizes teacher guidance, and fixes form-mode transitions | `app/forms.py`, `app/models.py`, `app/routes/admin.py`, `app/routes/student.py`, insurance templates, economy policy helpers | New `main` migration `g9h0i1j2k3l4_modularize_insurance_products.py`; requires schema comparison against current v2 insurance tables before porting | `tests/test_insurance_modularization.py`, `tests/test_insurance_snapshots.py`, `tests/test_economy_policy_mode.py` | Insurance feature docs and teacher guidance copy | `must-port before production` | `manual port` | v2 already has its own tenancy and identity refactors. Insurance behavior matters, but it is safer to reconcile after live-test hardening items |
| Insurance pricing snapshots, approval caps, and claim time-limit gate | `4f7f5647` (`#1097`), `ae2eb662` (`#1099`), `f670f53f` (`#1102`) | Adds economy snapshots for insurance pricing, fixes variable approval-cap handling, and changes claim time-limit evaluation to filing timestamp with teacher override | `app/models.py`, `app/routes/admin.py`, `app/utils/economy_policy.py`, `app/utils/economy_balance.py`, admin claim/policy templates | New `main` migrations: `h0i1j2k3l4m_add_economy_snapshot_table.py`, `k1l2m3n4o5p6_add_time_limit_override_to_claims.py` | `tests/test_insurance_snapshots.py`, `tests/test_insurance_security.py`, `tests/test_economy_policy_mode.py` | Insurance workflow/security docs | `must-port before production` | `manual port` | These are important correctness and claims-handling fixes, but they are schema-heavy and should be applied intentionally against the v2 schema, not merged blindly before the first live-test pass |
| Transaction idempotency and frozen analytics payloads | `6de59151` (`#1100`) | Hardens transaction idempotency and stores analysis payloads with economy snapshots | `app/routes/admin.py`, `app/routes/api.py`, `app/utils/transaction_idempotency.py`, `app/utils/store.py`, economy health UI | Landed on `codex/v2.0` via v2-native migrations `p6q7r8s9t0u1_add_transaction_idempotency_key.py` and `q9r0s1t2u3v4_add_economy_snapshot_table.py` | `tests/test_transaction_idempotency.py`, `tests/test_economy_api.py`, `tests/test_void_transaction_rules.py` | Minimal doc updates on `main`; runtime impact is larger than doc impact | `landed on codex/v2.0` | `manual port` | Landed and verified on 2026-03-30. Remaining economy-health follow-up work is tracked separately from this cluster |
| Rent waivers, perk suppression, pending-transaction settlement, and sysadmin logging fixes | `8a87f8fc` (`#1107`), `da7d9336` (`#1108`), `5bf90899` (`#1109`) | Expands rent-waiver scope, suppresses misapplied perk grants, tightens transaction settlement behavior, and fixes related sysadmin/error logging | `app/routes/admin.py`, `app/routes/student.py`, `app/routes/api.py`, `app/utils/banking.py`, `app/utils/transaction_idempotency.py`, `app/routes/system_admin.py`, rent/shop templates, settlement script | Landed on `codex/v2.0`; no additional DB migration was required beyond the idempotency/snapshot wave | `tests/test_add_rent_waiver_route.py`, `tests/test_rent_item_types.py`, `tests/test_banking_core.py`, `tests/test_decimal_precision.py`, `tests/test_error_logging.py`, `tests/test_sysadmin_grafana_auth.py`, `tests/test_void_transaction_rules.py` | Deployment guide and rent-facing UI copy changed on `main` | `landed on codex/v2.0` | `manual port` | Landed and verified on 2026-03-30. `tests/test_error_logging.py` remains a broader polish/follow-up area, not a blocker for this landed wave |
| Collective goal reactivation instance codes | `4c664f0d` (`#1110`) | Prevents stale collective-goal progress from carrying across reactivation by introducing instance codes and updated reset behavior | `app/models.py`, `app/routes/admin.py`, `app/routes/api.py`, `app/routes/student.py`, `app/utils/store.py` | New `main` migrations: `a4b5c6d7e8f9_add_collective_goal_instance_codes.py`, `b5c6d7e8f9g0_merge_collective_instance_and_cwi_heads.py` | `tests/test_collective_goal_expiration.py` | No major active-doc dependency yet | `must-port before production` | `manual port` | Correctness bug, but narrower feature surface than the live-test blockers above |
| Student support/store UX and privacy/logging polish | `29a59d91` (`#1088`), `e8da1dcc`, `b8fb169d`, `0717586a` | Simplifies support/store UI, improves issue display readability, and refreshes privacy/error-retention disclosures | `app/routes/student.py`, `app/routes/api.py`, `app/__init__.py`, `app/services/tlcp.py`, templates, CSS, `wsgi.py` | No DB migration | `tests/test_error_logging.py`, `tests/test_rent_item_types.py`, `tests/test_rent_privileges_overdue.py` | `templates/privacy.html`, user-facing copy | `safe to defer` | `defer` | Useful polish, but not required to establish v2 tenancy or launch safety |
| Teacher decision history and observer-account specs | `2cf98c74` (`#1087`) | Adds teacher decision-history views plus draft specs for observer accounts and decision logs | `app/models.py`, `app/routes/admin.py`, `app/routes/student.py`, support templates | No DB migration in the sampled commit | `tests/test_pr1086_issue_views.py` | New docs under `docs/development/` | `safe to defer` | `defer` | Valuable future scope, not part of the current v2 launch contract |
| Transfer submission hardening | `649e7c5b` (`#1085`) | Hardens student transfer submission flow and related feature-flag behavior | `app/routes/student.py`, `templates/layout_student.html`, `templates/student_transfer.html` | No DB migration | `tests/test_transfer_legacy_transactions.py`, `tests/test_feature_flag_enforcement.py` | No active launch doc dependency | `must-port before production` | `manual port` | User-facing correctness fix with lower launch risk than the economy and waiver clusters |
| Maintenance workflow security fix | `f930541e` (`#1084`) | Fixes template-injection risk in maintenance/deploy GitHub workflows | `.github/workflows/deploy.yml`, `.github/workflows/toggle-maintenance.yml` | No app DB migration | Workflow-level validation only | Security-sensitive operational docs may need cross-reference only | `must-port before production` | `cherry-pick` | Isolated workflow change with minimal coupling to v2 runtime code |
| Teacher announcement visibility and v1 sunset messaging | `369459a1` (`#1083`), `26479888`, `76d4def4` | Fixes teacher visibility for system-wide announcements and updates v1 sunset messaging in README/docs site | `app/routes/admin.py`, `templates/admin_dashboard.html`, `docs/index.html`, `README.md` | No DB migration | Existing announcements coverage plus manual teacher-dashboard check | README/docs-site messaging | `must-port before production` | `manual port` | The announcement fix is product-facing; sunset messaging is doc-only, but the code change should not be lost |
| Safe dependency upgrades | `6e9378ff` (`#1101`) | Updates `pytz`, `qrcode`, `redis`, and workflow ssh-agent usage | `requirements.txt`, GitHub workflows | No app DB migration | Normal dependency and CI validation | Security audit note on `main` | `safe to defer` | `defer` | Worth revisiting, but not a v2-specific launch gate |

## Must-Port Backlog

The sections below are implementation-ready planning notes for all clusters not classified as `safe to defer`.

### 1. Economy policy scheduling and rent-cycle locking

**Target behavior**

- Preserve the existing v2 `current_join_code` and membership-based authority model.
- Port `main`'s improved rent-cycle locking, next-cycle rebalance timing, penalty reversal behavior, and CWI warning bypass controls without reintroducing teacher-global assumptions.
- Keep all economy-health calculations scoped to the selected class context.

**Files and subsystems to change**

- `app/routes/admin.py`
- `app/routes/student.py`
- `app/utils/economy_balance.py`
- `app/utils/economy_policy.py`
- `app/utils/economy_rebalance.py`
- `templates/admin_economy_health.html`
- `templates/admin_rent_settings.html`
- `static/js/economy-balance.js`

**Migration handling**

- Compare `main` migration `3f4a5b6c7d8e_add_cwi_warning_bypass_flags.py` against the current v2 schema.
- If the fields do not exist on `codex/v2.0`, implement a fresh v2-native migration instead of cherry-picking the original file.
- Do not replay `main`'s already-diverged policy-mode migration chain.

**Merge/conflict risk**

- High. `codex/v2.0` already contains separate economy-policy and class-scope changes.
- Treat helper extraction and route-level behavior as manual reconciliation work.

**Required tests**

- Port or adapt `tests/test_economy_policy_mode.py`
- Port `tests/test_rent_penalty_reversal.py`
- Re-run related economy API and rent-display coverage on v2

**Operational verification**

- Verify rent penalties do not reverse incorrectly after rebalance changes.
- Verify class A rebalance changes do not mutate class B rent cycles.
- Verify CWI bypass controls are visible only where intended.

### 2. Transaction idempotency and frozen analytics payloads

**Status:** Landed on `codex/v2.0` on 2026-03-30

**What landed**

- `app/utils/transaction_idempotency.py`
- purchase/refund/void wiring in `app/routes/api.py` and `app/routes/admin.py`
- v2-native migrations `p6q7r8s9t0u1_add_transaction_idempotency_key.py` and `q9r0s1t2u3v4_add_economy_snapshot_table.py`
- frozen economy analysis payload caching in `app/routes/admin.py`
- updated regression coverage in `tests/test_transaction_idempotency.py`, `tests/test_economy_api.py`, and `tests/test_void_transaction_rules.py`

**Verification completed**

- duplicate replay tests for transaction flows
- frozen snapshot reuse / override bypass / recompute-on-input-change tests
- migration lint and repo validator pass for the new v2-native schema path

### 3. Rent waivers, perk suppression, settlement, and sysadmin logging

**Status:** Landed on `codex/v2.0` on 2026-03-30

**What landed**

- multi-scope waivers in `app/routes/admin.py` and `templates/admin_rent_settings.html`
- waiver-aware rent display and perk suppression in `app/routes/student.py` and `templates/student_rent.html`
- settlement sweep helpers in `app/utils/banking.py` and `scripts/settle_pending_transactions.py`
- sysadmin Grafana/session fixes in `app/auth.py` and `app/routes/system_admin.py`
- supporting regressions in `tests/test_add_rent_waiver_route.py`, `tests/test_rent_item_types.py`, `tests/test_banking_core.py`, `tests/test_decimal_precision.py`, `tests/test_sysadmin_grafana_auth.py`, and `tests/test_void_transaction_rules.py`

**Follow-up note**

- `tests/test_error_logging.py` remains a broader polish/follow-up area and is not the gating item for this landed wave

### 4. Insurance modularization and tiered setup flow

**Target behavior**

- Teacher-facing insurance setup supports the modular tiered design and the finalized tiered guidance flow from `main`.
- Simple/advanced mode transitions remain stable.

**Files and subsystems to change**

- `app/forms.py`
- `app/models.py`
- `app/routes/admin.py`
- `app/routes/student.py`
- `templates/admin_insurance.html`
- `templates/admin_edit_insurance_policy.html`
- `templates/student_file_claim.html`

**Migration handling**

- Diff `g9h0i1j2k3l4_modularize_insurance_products.py` against current v2 insurance tables.
- Write a v2-native migration if the schema has already moved independently.

**Merge/conflict risk**

- High. Insurance models, forms, and policy calculations overlap with other `main` insurance clusters.
- Land this before the snapshot/cap/time-limit cluster if both are selected for the same implementation wave.

**Required tests**

- Port `tests/test_insurance_modularization.py`
- Update `tests/test_insurance_snapshots.py`
- Update `tests/test_economy_policy_mode.py` where insurance pricing surfaces through economy logic

**Operational verification**

- Switch between simple and advanced setup modes without dropping saved state.
- Confirm marketplace and claim views show the expected modular product labels and coverage values.

### 5. Insurance pricing snapshots, approval caps, and claim time-limit gate

**Target behavior**

- Claim time-limit checks use filing timestamp, not the wrong event timestamp.
- Teachers can apply the explicit override path when warranted.
- Variable approval caps and pricing snapshots behave consistently with the modularized insurance model.

**Files and subsystems to change**

- `app/models.py`
- `app/routes/admin.py`
- `app/utils/economy_balance.py`
- `app/utils/economy_policy.py`
- `templates/admin_process_claim.html`
- `templates/admin_insurance.html`

**Migration handling**

- Compare `h0i1j2k3l4m_add_economy_snapshot_table.py` and `k1l2m3n4o5p6_add_time_limit_override_to_claims.py` with the v2 branch before implementing.
- If the snapshot table lands earlier with the idempotency cluster, consolidate schema work into a single coherent v2 migration path.

**Merge/conflict risk**

- High because it overlaps both insurance modularization and economy snapshot work.
- Do not cherry-pick commits independently; implement as a coordinated insurance/economy follow-up wave.

**Required tests**

- Update `tests/test_insurance_snapshots.py`
- Port claim-gate coverage from `tests/test_insurance_security.py`
- Verify any changed economy-policy assertions

**Operational verification**

- File claims around the time-limit boundary and confirm filing-time semantics.
- Exercise teacher override and confirm it is explicit, auditable, and not the default path.

### 6. Collective goal reactivation instance codes

**Target behavior**

- Reactivating a collective goal should start a new logical instance instead of inheriting stale progress from a prior one.

**Files and subsystems to change**

- `app/models.py`
- `app/routes/admin.py`
- `app/routes/api.py`
- `app/routes/student.py`
- `app/utils/store.py`

**Migration handling**

- Implement instance-code fields with a v2-native migration.
- Merge-head handling on `main` should not be replayed verbatim if the v2 migration graph has moved.

**Merge/conflict risk**

- Moderate.
- Business logic is narrower than the economy-policy and insurance clusters, but schema coordination still matters.

**Required tests**

- Port `tests/test_collective_goal_expiration.py`

**Operational verification**

- Reactivate a completed or expired collective goal and confirm prior contributions do not reappear in the new run.

### 7. Transfer submission hardening

**Target behavior**

- Student transfer submission should reject malformed or stale paths cleanly and respect the intended feature-flag constraints.

**Files and subsystems to change**

- `app/routes/student.py`
- `templates/layout_student.html`
- `templates/student_transfer.html`

**Migration handling**

- None expected.

**Merge/conflict risk**

- Moderate because student session handling already changed on v2.
- Manual port required to preserve the seat/user-context work already present on `codex/v2.0`.

**Required tests**

- Port relevant `tests/test_transfer_legacy_transactions.py` cases
- Update `tests/test_feature_flag_enforcement.py`

**Operational verification**

- Submit transfer flows from active and stale session contexts and confirm the right validation and error behavior.

### 8. Maintenance workflow security fix

**Target behavior**

- Maintenance/deploy workflows should not allow the templating behavior fixed on `main`.

**Files and subsystems to change**

- `.github/workflows/deploy.yml`
- `.github/workflows/toggle-maintenance.yml`

**Migration handling**

- None.

**Merge/conflict risk**

- Low.

**Required tests**

- Workflow review plus a dry-run style inspection in CI if available.

**Operational verification**

- Confirm maintenance toggling still works after the workflow change.

### 9. Teacher announcement visibility and v1 sunset messaging

**Target behavior**

- Teachers should see intended system-wide announcements.
- v1 sunset messaging should remain consistent across README and docs site copy.

**Files and subsystems to change**

- `app/routes/admin.py`
- `templates/admin_dashboard.html`
- `docs/index.html`
- `README.md`

**Migration handling**

- None.

**Merge/conflict risk**

- Low to moderate.

**Required tests**

- Reuse or add announcement coverage where teacher visibility is asserted.

**Operational verification**

- Confirm a system-wide announcement renders for a teacher on the dashboard.

## Deferred Clusters

These remain visible but are not launch-gating under the current v2 standard:

- Student support/store UX and privacy/logging polish
- Teacher decision history and observer-account specs
- Safe dependency upgrades

If one of these becomes product scope for v2 launch, reclassify it explicitly rather than quietly porting it.

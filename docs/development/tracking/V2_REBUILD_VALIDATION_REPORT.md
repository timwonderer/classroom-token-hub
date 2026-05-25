# V2 Rebuild Validation Report

**Generated:** 2026-05-24  
**Branch:** `claude/wonderful-shannon-aQa0v`  
**Against:** `V2_Full_compliance_migration_plan.md`  
**Methodology:** Direct code inspection, migration chain analysis, model audit, service/FEAT write-path tracing

### Post-Report Update (2026-05-24, `codex/v2.0`)

- Closed the FEAT compliance finding for economy snapshot persistence:
  - `app/routes/admin.py` `/api/economy/analyze` is now wrapped in `@feat_shell("FEAT-ADMN-001")`
  - `_get_frozen_economy_analysis_payload(...)` no longer calls `db.session.commit()`; it uses `db.session.flush()` and relies on FEAT transaction ownership
  - analyze endpoint error path now explicitly calls `db.session.rollback()` before returning `500`
- Validation:
  - `pytest -q tests/test_economy_api.py -k "analyze_endpoint_"` → `7 passed`
- Added explicit guardrail coverage for the deferred Wave 3 structural table drops:
  - `scripts/wave3_identity_drop_surface_guardrail.py`
  - `docs/development/tracking/wave3_identity_drop_surface_baseline.json`
  - `tests/test_wave3_identity_drop_surface_guardrail.py`
  - baseline-census confirms current deferred coupling is explicit and now blocked from expansion unless baseline is intentionally re-cut after approved reductions
- Landed first approved reduction slice and refreshed baseline:
  - `app/routes/student.py` no longer directly references `RecoveryRequest` / `StudentRecoveryCode`; student recovery accesses were routed through `app/services/recovery_bridge_service.py`
  - targeted validation: `pytest -q tests/test_recovery_bridge_service.py` → `3 passed`
  - baseline re-cut in `wave3_identity_drop_surface_baseline.json` after verified reductions
- Landed major follow-on reduction slice on admin/runtime recovery paths:
  - `app/routes/admin.py` recovery flow now uses `app/services/recovery_bridge_service.py` for recovery-request/code lifecycle operations instead of direct `RecoveryRequest` / `StudentRecoveryCode` symbol access
  - `app/utils/student_deletion.py` recovery-code cleanup now routes through bridge service
  - targeted validation: `pytest -q tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `6 passed`
  - baseline re-cut confirms `RecoveryRequest` and `StudentRecoveryCode` runtime symbol couplings are removed from `app/**`
- Landed passkey/onboarding decoupling slice:
  - `app/routes/admin.py` now routes passkey credential and onboarding lifecycle operations through `app/services/admin_identity_bridge_service.py`
  - `app/routes/system_admin.py` no longer carries `TeacherOnboarding` symbol dependency
  - targeted validation: `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `10 passed`
  - baseline re-cut confirms `AdminCredential` and `TeacherOnboarding` runtime symbol couplings are removed from `app/**`
- Landed invite-code decoupling slice:
  - `app/routes/system_admin.py` invite-code management now routes through `app/services/admin_identity_bridge_service.py`
  - `app/routes/admin.py` and `app/routes/system_admin.py` no longer carry `AdminInviteCode` symbol dependencies
  - targeted validation: `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `11 passed`
  - baseline re-cut confirms `AdminInviteCode` runtime symbol couplings are removed from `app/**`
- Landed low-risk session principal key reduction slice on docs/main surfaces:
  - `app/routes/main.py` removed direct `session` fallback checks for `is_admin` / `admin_id` / `student_id` in home redirect flow; routing now uses explicit resolver checks (`get_current_admin`, `get_current_seat`)
  - `app/routes/docs.py` removed direct `admin_id` / `student_id` fallback checks in docs audience and user-role resolution paths; sysadmin context now requires both `is_system_admin` and `sysadmin_id`
  - `app/utils/helpers.py` `has_internal_docs_session()` now resolves internal-auth state through auth resolvers instead of direct `admin_id` / `student_id` key checks
  - targeted validation: `pytest -q tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `18 passed`
  - guardrail confirms reductions:
    - `session_keys.admin_id` reduced from `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py`
    - `session_keys.student_id` reduced from `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py`
    - `session_keys.is_admin` reduced from `app/routes/main.py`
- Landed session principal key reduction slice on API/TLCP/sysadmin resolver surfaces:
  - added `get_current_system_admin()` in `app/auth.py` so sysadmin context is explicitly resolved (flag + id + row), not inferred from raw keys
  - `app/routes/api.py` no longer performs direct `is_admin` / `admin_id` / `is_system_admin` checks for `/api/set-timezone`; `/api/attendance/history` no longer falls back to raw `admin_id`
  - `app/services/tlcp.py` actor context now resolves student/admin/sysadmin identity through explicit auth helpers rather than direct principal-key checks
  - `app/__init__.py` maintenance bypass sysadmin detection and current-sysadmin template injection now use resolver-backed sysadmin context
  - targeted validation:
    - `python3 -m py_compile app/auth.py app/routes/api.py app/services/tlcp.py app/__init__.py` → pass
    - `pytest -q tests/test_tlcp_actor_context_resolution.py tests/test_timezone_fix.py tests/test_api_fixes.py tests/test_api_attendance_history.py tests/test_maintenance_bypass.py tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `41 passed`
  - guardrail confirms reductions:
    - `session_keys.admin_id` reduced from `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.is_admin` reduced from `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.is_system_admin` reduced from `app/__init__.py`, `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.student_id` reduced from `app/services/tlcp.py`

---

## Executive Summary

The v2 rebuild is **substantially advanced through Wave 4** with high-quality work delivered in routing authority, class-scope enforcement, analytics canonicalization, and FEAT infrastructure. Waves 5–10 (domain schema migrations) have not been executed — canonical tables exist as defined stubs but all runtime writes still target legacy tables. The FEAT execution layer is the standout achievement: `FEATContext` is robust, commit enforcement is wired at app boot, and route-level commits have been eliminated across all non-admin routes.

| Wave | Domain | Status | Confidence |
|------|--------|--------|-----------|
| 1 | Canonical Model Foundation | ✅ COMPLETE | High |
| 2 | Bootstrap Migration Squash | ✅ COMPLETE | High |
| 3 | Identity Domain (behavioral) | ✅ COMPLETE (re-scoped) | High |
| 3 | Identity Domain (table drops) | ❌ DEFERRED | N/A |
| 4 | Class Configuration | ✅ COMPLETE | High |
| 5 | Ledger Domain | ❌ NOT STARTED | — |
| 6 | Attendance Domain | ❌ NOT STARTED | — |
| 7 | Obligations Domain | ⚠️ PARTIAL (behavioral only) | Medium |
| 8 | Store Domain | ❌ NOT STARTED | — |
| 9 | Operations + Interpretation | ⚠️ PARTIAL (infrastructure only) | Low |
| 10 | Support Domain | ❌ NOT STARTED | — |
| 11 | Post-Launch Completion | ⚠️ PARTIAL | Low |
| 12 | Final Validation | ❌ NOT STARTED | — |

**Current migration head:** `a91cf11e8b2d` (9 migrations in `versions/`, linear chain, single head ✅)  
**Tables in `models.py`:** ~60 (target: 44 canonical)  
**Canonical tables written at runtime:** 0 of 44 (feats still write to legacy tables)

---

## Wave 1 — Canonical Model Foundation

### Claimed Deliverables

| Deliverable | Status | Notes |
|---|---|---|
| `app/models_canonical.py` with all 44 ORM classes | ✅ EXISTS (46 classes) | PolicyVersion + PolicyTransition added in Wave 4 |
| `tests/domain/test_smoke.py` imports all 44 classes | ✅ EXISTS | Covers 44 of 46 — PolicyVersion/PolicyTransition not in smoke test |
| `docs/development/archive/tracking/V2_SCHEMA_GAP_AUDIT.md` | ✅ EXISTS | Complete per-table audit present |

### Gaps

- `test_smoke.py` asserts `len(models) == 44` but `models_canonical.py` now defines 46 classes. `PolicyVersion` and `PolicyTransition` are not imported or tested by the smoke test. The assertion will pass (as it tests a hardcoded list), but the two additions are unvalidated.
- No regression: Wave 1 added no schema changes, so existing tests were unaffected.

---

## Wave 2 — Bootstrap Migration Squash

### Claimed Deliverables

| Deliverable | Status | Notes |
|---|---|---|
| 196 legacy migrations archived to `migrations/archive/v1_196_migrations/` | ✅ EXISTS — 196 files confirmed | |
| `migrations/archive/README.md` with squash date + prior head | ✅ EXISTS | Correct archival metadata |
| `migrations/versions/0001_bootstrap.py` with `down_revision = None` | ✅ EXISTS | Correct structure |
| `0001_bootstrap.py` creates both legacy + canonical tables with guards | ✅ VERIFIED | Uses `metadata.create_all(..., checkfirst=True)` for both model sets |
| `scripts/verify_migration_squash.py` validates head + 44 canonical tables | ✅ EXISTS | Checks 44 expected canonical table names |
| Single migration head after squash | ✅ VERIFIED | Head is `a91cf11e8b2d` (linear chain; Wave 2 head was `0001`, advanced by subsequent waves as expected) |

### Gaps

- `verify_migration_squash.py` checks for head `0001`, which is no longer current (expected, as later waves advance the head). The script should be treated as historical Wave 2 evidence, not an ongoing validator.
- The bootstrap uses `metadata.create_all()` with `checkfirst=True` rather than individual `op.create_table()` with `table_exists()` guards. This is functionally equivalent but deviates from the migration standards in `.claude/rules/database-migrations.md`. No correctness issue.

---

## Wave 3 — Identity Domain

Wave 3 was re-scoped during execution. The original plan called for activating `User`/`Seat` as the primary auth path and dropping all legacy auth tables. The executed work focused on routing authority, class-scope enforcement, and single-context UI enforcement — deferring the structural auth table drops.

### Routing & Authority (Executed — Complete)

| Deliverable | Status | Evidence |
|---|---|---|
| `class_economies` → `classes` rename migration (`0002a`) | ✅ COMPLETE | `migrations/versions/0002a_rename_class_economies.py`; 37 FK references updated |
| `get_current_seat()`, `get_current_class_id()`, `get_current_user()`, `require_seat_context()` in `app/auth.py` | ✅ COMPLETE | `auth.py` lines 338–429 |
| Feature gate: admin feature pages gated via `@admin_bp.before_request` | ✅ COMPLETE | `admin.py` lines 402–457; disabled pages render `admin_feature_disabled.html` |
| Feature gate: student receives hard `abort(404)` for disabled features | ✅ COMPLETE | `student.py` lines 147–166; `STUDENT_FEATURE_ENDPOINTS` covers 10 routes |
| Single-context enforcement: no request-level `join_code` class switching in admin/analytics | ✅ COMPLETE | `analytics.py` uses `resolve_current_class_context()`; no `resolve_current_join_code()` |
| Route commit elimination: `student.py`, `analytics.py`, `system_admin.py`, `api.py` | ✅ COMPLETE | 0 `db.session.commit()` calls in any of these four files |
| `student_detail()` no longer accepts `?join_code=` override | ✅ COMPLETE | Route auto-resolves from student context |
| Legacy claim flow: `join_code + first_name + last_name` (no DOB) | ✅ COMPLETE | `student.py` lines 549–698; dedupe code for name collisions |
| `last_active_class_id` on `User` model with migration | ✅ COMPLETE | `models.py` line 192; migration `8357d4036478` |
| `scripts/policy_guardrails.py` | ✅ COMPLETE | File exists |
| Test files: `test_feature_flag_enforcement.py`, `test_teacher_student_flow.py`, `test_class_context_and_switching.py`, `test_legacy_student_claim.py` | ✅ COMPLETE | All 4 exist |

### Structural Auth Migration (Original Plan — Deferred)

| Original Wave 3 Deliverable | Status |
|---|---|
| `0002_identity_domain.py` migration (drops legacy auth tables) | ❌ DOES NOT EXIST |
| `User` activated as primary auth principal | ❌ NOT DONE — login still resolves `Admin`/`Student` via session `admin_id`/`student_id` |
| Legacy auth tables dropped: `teachers`, `students`, `student_teachers`, `student_blocks`, `teacher_blocks`, `class_memberships`, `recovery_requests`, `student_recovery_codes`, `teacher_onboarding`, `teacher_credentials` | ❌ ALL STILL IN SCHEMA |
| `tests/domain/test_identity.py` | ❌ DOES NOT EXIST |

**Critical Gap:** The Wave 3 exit criteria as re-scoped are met. But the original structural work — activating `User`/`Seat` as the primary auth path and dropping legacy identity tables — was fully deferred. This is the largest structural gap in the rebuild. Until this work is done, the system runs dual identity (legacy `Admin`/`Student` + canonical `User`/`Seat`) which is the planned transitional state.

---

## Wave 4 — Class Configuration

All Wave 4 deliverables are validated complete.

### Claimed Deliverables

| Deliverable | Status | Evidence |
|---|---|---|
| Analytics resolves enrollment via `ClassMembership` by `class_id` (not legacy teacher roster) | ✅ COMPLETE | `analytics_engine.py` lines 108–111; joins `ClassMembership.class_id` |
| `get_active_policy_mode_for_class(class_id)` in `economy_policy.py` | ✅ COMPLETE | Line 602 |
| `get_analytics_policy(mode)` in `economy_policy.py` | ✅ COMPLETE | Line 614 |
| `get_feature_settings_row_for_class(class_id)` in `economy_policy.py` | ✅ COMPLETE | Line 565 |
| Analytics activity queries filter by `Transaction.class_id`, `TapEvent.class_id` | ✅ COMPLETE | `analytics_engine.py` lines 176, 190, 232, 552, 708 |
| `Student.get_checking_balance()` + `.get_savings_balance()` require `class_id + seat_id` | ✅ COMPLETE | `models.py` lines 491, 498; raises `ValueError` if either missing |
| `PolicyVersion` + `PolicyTransition` ORM classes in `models.py` + `models_canonical.py` | ✅ COMPLETE | `models.py` lines 2997–3054; `models_canonical.py` lines 64–71 |
| Migration `c4e36a4ab2f1_add_policy_lineage_tables.py` | ✅ EXISTS | Idempotent; FK wiring correct |
| `FeatureSettings.economy_pending_rebalance_json` dropped from ORM + migration `d2f9f1d9be2e` | ✅ COMPLETE | Column absent from `FeatureSettings`; migration exists |
| `FeatureSettings.teacher_id`, `.join_code`, `.block` dropped from ORM + migration `a91cf11e8b2d` | ✅ COMPLETE | Columns absent; migration exists |
| `uq_feature_settings_teacher_join_code_block` uniqueness dropped + migration `f84c7ad2c1aa` | ✅ COMPLETE | Constraint absent; `class_id` is now `unique=True` on column |
| `activate_due_rebalances()` uses `policy_transitions` exclusively (no JSON fallback) | ✅ COMPLETE | `economy_rebalance.py` line 483 confirms JSON fallback retired |
| Dual-write policy transitions for rebalance scheduling | ✅ COMPLETE | `_create_policy_transitions_for_changes()` in `economy_rebalance.py` |

### Gaps

None identified. Wave 4 is the highest-quality completed wave.

---

## Wave 5 — Ledger Domain

### Status: ❌ NOT STARTED

Canonical models are defined in `models_canonical.py` (`LedgerTransaction`, `LedgerBalanceSnapshot`) but all runtime writes still target legacy tables.

| Check | Finding |
|---|---|
| `ledger_service.py` imports | `from app.models import BalanceCache, Transaction, TransactionStatus, ClassEconomy` |
| `balance_service.py` imports | `from app.models import BalanceCache, Transaction, TransactionStatus` |
| FEATs writing to ledger | All FEATs delegate to `ledger_service` → writes go to `transaction` (legacy) |
| Migration `0003_ledger_domain.py` or `0004_ledger_domain.py` | ❌ DOES NOT EXIST |
| `transaction` table in `models.py` | ✅ STILL PRESENT (`__tablename__ = 'transaction'`, line 817) |
| `balance_cache` table in `models.py` | ✅ STILL PRESENT (`__tablename__ = 'balance_cache'`, line 1093) |

**Remaining work:** Port `ledger_service.py` and `balance_service.py` to `LedgerTransaction`/`LedgerBalanceSnapshot`; update FEATs; create Wave 5 migration; drop legacy ledger tables.

---

## Wave 6 — Attendance Domain

### Status: ❌ NOT STARTED

| Check | Finding |
|---|---|
| `attendance_service.py` imports | `from app.models import HallPassLog, StudentTeacher, TapEvent, TeacherBlock` |
| `tap_feat.py` in `app/feats/` | ❌ DOES NOT EXIST |
| `tap_events` table in `models.py` | ✅ STILL PRESENT (`__tablename__ = 'tap_events'`, line 1154) |
| Migration `0005_attendance_domain.py` | ❌ DOES NOT EXIST |
| `AttendanceSession`, `SeatAttendanceState` in `models_canonical.py` | ✅ Defined (lines 104–116) but unused at runtime |
| `FEAT-ATTN-001`, `FEAT-ATTN-002` in FEAT registry | ✅ Both registered in `base.py` |
| INV-ARC-007: `GET /api/student-status` is read-only | ✅ DONE — `POST /api/student-status/reconcile` exists at `api.py:2940` |

**Positive finding:** The `GET /api/student-status` / `POST /api/student-status/reconcile` split is implemented, partially satisfying INV-ARC-007 for the student polling path.

**Remaining work:** Create `tap_feat.py`; port `attendance_service.py` to canonical tables; create Wave 6 migration; drop `tap_events`.

---

## Wave 7 — Obligations Domain

### Status: ⚠️ PARTIAL (Behavioral contracts implemented; schema migration not done)

The behavioral pre-work claimed in the Wave 3 cross-wave section is verified:

| Behavioral Contract | Status | Evidence |
|---|---|---|
| Rent prepay cycle model with `coverage_start_time`, `coverage_end_time` | ✅ IMPLEMENTED | `RentPayment` model has both columns |
| `cycle_idempotency_key` on rent payments | ✅ IMPLEMENTED | Column present in `RentPayment` |
| `has_received_rent_exemption` on `Seat` | ✅ IMPLEMENTED | Column in `Seat` model |
| Class-local temporal enforcement (insurance waiting period) | ✅ IMPLEMENTED | `app/utils/time.py` helpers: `get_class_cycle_start_utc`, `get_class_today_range` |
| `rent_cycle_feat.py` with FEAT shell | ✅ IMPLEMENTED | File exists in `app/feats/` |

| Schema Migration Check | Status |
|---|---|
| `obligations_service.py` imports | `from app.models import InsuranceClaim, RentPayment, StudentInsurance` — still legacy |
| Migration `0006_obligations_domain.py` | ❌ DOES NOT EXIST |
| `AssessmentEvent`, `ObligationLifecycle`, etc. in `models_canonical.py` | ✅ Defined (lines 119–141) but unused at runtime |
| Feats writing to canonical obligation tables | ❌ NOT DONE — writing to `rent_payments`, `insurance_claims`, `student_insurance` |
| Legacy tables dropped | ❌ NOT DONE |

**Remaining work:** Port `obligations_service.py` to canonical obligation tables; update `rent_payment_feat.py`, `insurance_claim_feat.py`, `insurance_purchase_feat.py`; create Wave 7 migration; drop legacy obligation tables.

---

## Wave 8 — Store Domain

### Status: ❌ NOT STARTED

| Check | Finding |
|---|---|
| `store_service.py` imports | `from app.models import RentItem, Student, StudentItem, TeacherBlock` |
| `student_items` table in `models.py` | ✅ STILL PRESENT (`__tablename__ = 'student_items'`, line 1419) |
| Migration `0007_store_domain.py` | ❌ DOES NOT EXIST |
| `StorePurchase`, `RedemptionEvent`, `StoreItemVisibility` in `models_canonical.py` | ✅ Defined (lines 159–171) but unused at runtime |
| `FEAT-STOR-001` through `FEAT-STOR-005` in registry | ✅ All registered |
| `store_purchase_feat.py` | ✅ EXISTS but writes to legacy `StudentItem` via `store_service` |

**Remaining work:** Port `store_service.py` to canonical store tables; update `store_purchase_feat.py`; create Wave 8 migration; drop `student_items`, `store_item_blocks`.

---

## Wave 9 — Operations + Interpretation Domains

### Status: ⚠️ PARTIAL (Infrastructure exists; canonical write paths not wired)

| Check | Finding |
|---|---|
| Canonical ops models in `models_canonical.py` | ✅ All 8 defined (`OperationalEvent`, `AuditLog`, `IncidentEvent`, `IncidentSummary`, `AlertEvent`, `InvariantRunEvent`, `JobEvent`, `HealthCheckEvent`) |
| `audit_service.py` / `operational_event_service.py` | ✅ Both exist |
| `base.py` calls `audit_protected()` after FEAT flush | ✅ Wired at `base.py` lines 333–375 |
| Migration `0008_operations_domain.py` | ❌ DOES NOT EXIST |
| Legacy analytics tables dropped (`actor_request_trace`, `error_events`, `error_logs`, `analytics_alerts`, `user_reports`) | ❌ ALL STILL IN `models.py` |
| Interpretation: `InterpretationSnapshot`, `InterpretationAnnotation` in canonical | ✅ Defined but unused |
| Migration `0009_interpretation_domain.py` | ❌ DOES NOT EXIST |
| Legacy analytics models still in `models.py` | `analytics_alerts`, `analytics_snapshots`, `analytics_events`, `actor_request_trace`, `error_events`, `error_logs`, `user_reports` — all present |

**Positive finding:** `audit_service.emit_audit_event()` requires FEAT context (enforced). The audit infrastructure is the most production-ready of the unexecuted domain waves.

---

## Wave 10 — Support Domain

### Status: ❌ NOT STARTED

| Check | Finding |
|---|---|
| `issues` table legacy columns | `join_code` and `teacher_id` still present in `Issue` model |
| Migration `0010_support_domain.py` | ❌ DOES NOT EXIST |
| Canonical support classes in `models_canonical.py` | ✅ All 6 defined (lines 224–251) but map to the same legacy tables |

---

## Wave 11 — Post-Launch Completion

### Status: ⚠️ PARTIAL

| Deliverable | Status |
|---|---|
| Adversarial harness (`scripts/adversarial/`) | ✅ COMPLETE — 6+ scripts, sanitized evidence protocol |
| Phase 1 adversarial scorecard passing | ✅ VERIFIED — all detectors PASS (cross-class, lineage, runtime, GET-mutation) |
| INV-ARC-007: `GET /api/student-status` is write-free | ✅ DONE |
| INV-ARC-007: remaining sweep complete | ❌ NOT DONE — 1 violation remains in `admin.py:2107` (`db.session.commit()` in economy snapshot persistence outside FEAT) |
| `app/routes/admin.py` decomposition into sub-blueprints | ❌ NOT DONE — `admin.py` is 12,862 lines; no sub-blueprints exist |
| Backup/restore rehearsal | ❌ NOT DONE |
| Operator sign-off flow (`user_invite_tokens`) | ❌ NOT DONE |
| Sysadmin audit | ❌ NOT DONE |
| `V2_CLASS_ID_INVARIANT_BACKLOG` closure | ❌ NOT DONE |
| Full-repo INV-ARC-015 sweep | ❌ NOT DONE |

---

## Wave 12 — Final Validation

### Status: ❌ NOT STARTED

Final gate criteria are all failing:

| Gate | Required | Current |
|---|---|---|
| Exactly 44 canonical tables in schema | 44 | ~60+ (models.py has ~60 table-owning classes) |
| `models.py` is re-export only | Yes | Still defines all legacy models |
| `app/auth.py` — clean `User`/`Seat` path | Yes | Still resolves `Admin`/`Student` as primary |
| 0 failing tests | 0 | ~123 failing (per plan baseline) |
| All domain tests in `tests/domain/` | Yes | Only `test_smoke.py` exists there |

---

## FEAT Layer Compliance

This is the most thoroughly completed infrastructure component.

| Check | Status | Evidence |
|---|---|---|
| `FEATContext` class with commit enforcement | ✅ COMPLETE | `base.py` lines 107–244 |
| `feat_shell()` decorator | ✅ COMPLETE | `base.py` lines 392–425 |
| `FEATContextError` on unauthorized commit | ✅ COMPLETE | `base.py` lines 439–486 (before_flush + before_commit hooks) |
| `init_feat_enforcement(app)` called at boot | ✅ COMPLETE | `app/__init__.py` |
| FEAT registry with all domain codes | ✅ COMPLETE | LED, IDEN, STOR, ATTN, ADMN, OBL codes all registered |
| `db.session.commit()` in `student.py`, `analytics.py`, `api.py`, `system_admin.py` | ✅ 0 violations | Confirmed by search |
| `db.session.commit()` in `admin.py` | ❌ 1 violation | `admin.py:2107` — economy snapshot persistence |

**One remaining INV-ARC-007 / FEAT violation:** `admin.py` line 2107 directly commits a snapshot record outside FEAT context in `_get_frozen_economy_analysis_payload()`.

---

## Schema State Audit

### Tables in `app/models.py` (current, ~60 total)

**Canonical-aligned (should survive to v2):**
`users`, `seats`, `classes`, `identity_profiles`, `class_features`, `feature_settings`, `hall_pass_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `rent_settings`, `banking_settings`, `hall_pass_logs`, `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_pack`, `issue_categories`, `announcements`, `store_items`, `redemption_audit_logs`, `class_memberships`, `policy_versions`, `policy_transitions`

**Legacy (targeted for drop in Waves 5–10):**
`transaction`, `balance_cache`, `tap_events`, `rent_payments`, `rent_waivers`, `rent_items`, `insurance_policies`, `insurance_policy_blocks`, `student_insurance`, `insurance_claims`, `student_items`, `store_item_blocks`

**Legacy auth (targeted for drop in Wave 3 structural — deferred):**
`teachers`, `students`, `teacher_blocks`, `student_teachers`, `student_blocks`, `recovery_requests`, `student_recovery_codes`, `teacher_credentials`, `teacher_onboarding`, `teacher_invite_codes`

**Legacy observability (targeted for drop in Wave 9):**
`analytics_alerts`, `analytics_snapshots`, `analytics_events`, `actor_request_trace`, `error_logs`, `error_events`, `user_reports`

**Non-canonical additions (not in DOM-CORE-002 target list):**
`audit_events`, `chain_heads`, `integrity_status`, `economy_snapshot`, `payroll_cache`

---

## Key Findings and Gaps

### Confirmed Achievements

1. **FEAT execution layer** is production-quality: `FEATContext`, registry, commit enforcement, `before_flush`/`before_commit` hooks, and `feat_shell` are all wired.
2. **Single-context class authority** is enforced across all admin/student/analytics routes — no request-level `join_code` class switching.
3. **Feature toggle gating** is complete: admin sees disabled page, student gets hard 404.
4. **Route commit elimination** is complete for student/analytics/api/system_admin routes (4 files, 0 violations).
5. **Wave 4 FeatureSettings canonicalization** is complete and clean — legacy scope columns dropped, policy lineage tables wired, rebalance activation is transition-native.
6. **Temporal contracts** (INV-ARC-015) are implemented for attendance, rent, insurance, and analytics.
7. **Class-scope enforcement** throughout analytics, balance reads, and settings resolution is solid.

### Critical Gaps

1. **All domain writes are still legacy.** Waves 5–8 have not been executed. `ledger_service`, `attendance_service`, `obligations_service`, and `store_service` all import and write to legacy tables. The canonical tables defined in `models_canonical.py` are empty database stubs never written to at runtime.

2. **Wave 3 structural migration not done.** Legacy auth tables (`teachers`, `students`, `student_blocks`, etc.) and the legacy auth path (`Admin`/`Student` as session principals) are fully intact. `User`/`Seat` are supplementary identity layers, not the primary auth path.

3. **`tests/domain/` is nearly empty.** Only `test_smoke.py` exists. None of the per-domain test files (`test_identity.py`, `test_attendance.py`, `test_obligations.py`, `test_store.py`, `test_operations.py`, `test_support.py`) have been created.

4. **`admin.py` is a 12,862-line monolith.** Wave 11 decomposition into sub-blueprints has not started.

5. **One FEAT compliance violation remains:** `admin.py:2107` commits outside FEAT context in the economy snapshot path.

6. **`verify_migration_squash.py` is stale.** It still checks for head `0001` and does not reflect the current `a91cf11e8b2d` head.

7. **`test_smoke.py` does not cover `PolicyVersion` and `PolicyTransition`** (added in Wave 4 to `models_canonical.py`). The file asserts `len(models) == 44` with a hardcoded list, which will pass incorrectly without exercising the two new additions.

---

## Recommended Next Steps (Priority Order)

1. **Fix `admin.py:2107`** — wrap the economy snapshot commit in a `FEATContext` (small scope, closes the one remaining FEAT violation).

2. **Execute Wave 5 (Ledger)** — this is the highest-leverage next wave. All other domain writes depend on the ledger; getting this right enables Waves 6–8 to follow cleanly. Port `ledger_service.py` and `balance_service.py`, create the migration, redirect feats.

3. **Create `tap_feat.py` and execute Wave 6 (Attendance)** — `FEAT-ATTN-001/002` are already in the registry; the feat file just needs to be created and `attendance_service.py` ported.

4. **Update `test_smoke.py`** to include `PolicyVersion` and `PolicyTransition` (2-line fix).

5. **Execute Wave 7 (Obligations)** — behavioral contracts are already implemented; only the schema migration and service port remain.

6. **Execute Waves 8–10** in sequence (Store → Operations → Support).

7. **Wave 3 structural completion** — activate `User`/`Seat` as the primary auth path and drop legacy identity tables. This is the largest remaining architectural risk.

8. **Create per-domain tests** in `tests/domain/` for each completed wave.

9. **Decompose `admin.py`** (Wave 11) — 12,862 lines is a maintenance and review liability.

---

*This report was produced by direct code inspection on 2026-05-24. All findings are based on file content, not runtime behavior.*

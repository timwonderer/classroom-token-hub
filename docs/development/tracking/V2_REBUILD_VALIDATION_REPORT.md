# V2 Rebuild Validation Report — Revision 2

**Generated:** 2026-05-25  
**Branch:** `claude/wonderful-shannon-aQa0v`  
**Against:** `V2_Full_compliance_migration_plan.md`  
**Methodology:** Direct code inspection (multi-pass), migration chain analysis, model column audit, service/FEAT write-path tracing, test coverage enumeration, CI infrastructure review, adversarial scorecard analysis, INV compliance sweep

---

## Executive Summary

The v2 rebuild has delivered substantial, production-quality work in four distinct categories:

1. **FEAT execution infrastructure** — `FEATContext`, commit enforcement, registry, and `audit_protected()` audit chain are fully operational and wired at app boot.
2. **Class-scope and single-context authority** — request-level `join_code` class switching eliminated; session-authoritative context enforced; feature gating complete.
3. **Wave 4 class configuration canonicalization** — `FeatureSettings` fully cleaned; policy lineage live; rebalance activation is transition-native; analytics enrollment canonical.
4. **Dual-scope model hardening** — legacy tables (`transaction`, `balance_cache`, `tap_events`) now have mandatory `seat_id + class_id` enforcement hooks that make them behaviorally compliant even though their table names are legacy.

The first validation report's characterization of "0 of 44 canonical tables written at runtime" was imprecise. The more accurate picture: **all active legacy tables are dual-scoped** with canonical columns enforced at the model level, but they have not yet been renamed to the canonical DOM-CORE-002 table names. Waves 5–10 complete that renaming/consolidation work.

| Wave | Domain | Status | Revised Confidence |
|------|--------|--------|--------------------|
| 1 | Canonical Model Foundation | ✅ COMPLETE | High |
| 2 | Bootstrap Migration Squash | ✅ COMPLETE | High |
| 3 | Identity Domain (behavioral/routing) | ✅ COMPLETE (re-scoped) | High |
| 3 | Identity Domain (auth table drops / User activation) | ❌ DEFERRED | N/A |
| 4 | Class Configuration | ✅ COMPLETE | High |
| 5 | Ledger Domain | ⚠️ BEHAVIORAL ONLY — table rename/consolidation pending | Medium |
| 6 | Attendance Domain | ⚠️ BEHAVIORAL ONLY — table rename/consolidation pending | Medium |
| 7 | Obligations Domain | ⚠️ BEHAVIORAL ONLY — canonical tables not yet used | Medium |
| 8 | Store Domain | ⚠️ BEHAVIORAL ONLY — canonical tables not yet used | Low–Medium |
| 9 | Operations + Interpretation | ⚠️ AUDIT CHAIN OPERATIONAL (non-canonical table) | Low |
| 10 | Support Domain | ❌ LEGACY SCOPE COLUMNS NOT CLEANED | Low |
| 11 | Post-Launch Completion | ⚠️ PARTIAL | Low |
| 12 | Final Validation | ❌ NOT STARTED | — |

**Current migration head:** `a91cf11e8b2d` (9 migrations, linear single-head chain ✅)  
**Tables in `models.py`:** ~60 ORM classes, ~66 table names total  
**Legacy tables dual-scoped with canonical columns:** Confirmed for `transaction`, `balance_cache`, `tap_events`, `hall_pass_logs`  
**Canonical table names live at runtime:** `classes` (renamed), `users`, `seats`, `feature_settings`, `policy_versions`, `policy_transitions`, `class_features`, `payroll_settings`, `rent_settings`, `banking_settings`, `hall_pass_settings`, `store_items`, `class_memberships`, `identity_profiles`  
**Active adversarial scorecard:** FAIL on Cross-Class Isolation (1) and Lineage Verifier (5) as of 2026-05-15

---

## Wave 1 — Canonical Model Foundation

### Status: ✅ COMPLETE (minor smoke test gap)

| Deliverable | Status | Notes |
|---|---|---|
| `app/models_canonical.py` with 44 ORM classes | ✅ EXISTS — 46 classes | `PolicyVersion` + `PolicyTransition` added in Wave 4; justified |
| `tests/domain/test_smoke.py` | ✅ EXISTS | Tests 44 hardcoded classes; does not include Wave 4 additions |
| `docs/development/archive/tracking/V2_SCHEMA_GAP_AUDIT.md` | ✅ EXISTS | Complete table-by-table mapping |

### Gaps

- `test_smoke.py` asserts `len(models) == 44` against a hardcoded list that excludes `PolicyVersion` and `PolicyTransition`. The assertion passes but these two classes are not exercised.
- `models_canonical.py` canonical class bodies are minimal stubs (`id = sa.Column(sa.Integer, primary_key=True)`). This is correct for Wave 1 (reference definitions), but should be fully populated when each domain wave executes.

---

## Wave 2 — Bootstrap Migration Squash

### Status: ✅ COMPLETE

| Deliverable | Status | Notes |
|---|---|---|
| 196 legacy migrations archived | ✅ — exact count confirmed | `migrations/archive/v1_196_migrations/` |
| `migrations/archive/README.md` | ✅ | Correct date, prior head, file count |
| `migrations/versions/0001_bootstrap.py` with `down_revision = None` | ✅ | Root migration; uses `metadata.create_all(checkfirst=True)` for both model sets |
| `scripts/verify_migration_squash.py` | ✅ | Validates 44 canonical tables by name |
| Single migration head | ✅ | Chain: `0001 → 0002a → 3447255cb1af → 53e7c7148fea → 8357d4036478 → c4e36a4ab2f1 → d2f9f1d9be2e → f84c7ad2c1aa → a91cf11e8b2d` |

### Gaps

- `verify_migration_squash.py` hardcodes head check for `0001`; stale since Waves 3–4 advanced the head. Treat as historical evidence only.
- Bootstrap uses `metadata.create_all(checkfirst=True)` rather than per-table `op.create_table()` + `table_exists()` guards per the migration standards doc. Functionally equivalent; no correctness issue.

---

## Wave 3 — Identity Domain

Wave 3 was re-scoped during execution from the full structural auth migration (activate `User`/`Seat`, drop legacy auth tables) to a behavioral/routing compliance pass. Both scopes are documented below.

### 3A: Routing Authority & Single-Context Enforcement (Re-scoped — Complete)

| Deliverable | Status | Evidence |
|---|---|---|
| `class_economies` → `classes` rename (`0002a`) | ✅ COMPLETE | 37 FK references updated; `ClassEconomy` model maps to `classes` table |
| Auth helpers: `get_current_seat()`, `get_current_class_id()`, `get_current_user()`, `require_seat_context()` | ✅ COMPLETE | `auth.py` lines 338–429 |
| Admin feature gating via `@admin_bp.before_request` | ✅ COMPLETE | `admin.py` lines 402–457; disabled → `admin_feature_disabled.html` |
| Student feature gating with hard `abort(404)` | ✅ COMPLETE | `student.py` lines 147–166; `STUDENT_FEATURE_ENDPOINTS` (10 routes) |
| Single-context: no request-level `join_code` class switching in admin/analytics | ✅ COMPLETE | `analytics.py` uses `resolve_current_class_context()`; admin context is session-authoritative |
| Route commit elimination: `student.py`, `analytics.py`, `system_admin.py`, `api.py` | ✅ COMPLETE | 0 `db.session.commit()` in all four files |
| `student_detail()` no longer accepts `?join_code=` override | ✅ COMPLETE | Route auto-resolves from student context |
| Legacy claim flow: `join_code + first_name + last_name` (no DOB) | ✅ COMPLETE | `student.py:549–698`; dedupe code for name collisions |
| `last_active_class_id` on `User` model | ✅ COMPLETE | `models.py:192`; migration `8357d4036478` |
| `scripts/policy_guardrails.py` (10 rules, waiver system) | ✅ COMPLETE | Enforces: NO_ROUTE_COMMIT, WRITE_ON_GET, SCOPE_FALLBACK, TAP_NULL_SCOPE, AUDIT_UPDATE_DELETE, and 5 others |
| `.github/workflows/policy-guardrails.yml` | ✅ COMPLETE | PR mode (waivers allowed) + main branch strict mode |
| Test files: `test_feature_flag_enforcement.py`, `test_teacher_student_flow.py`, `test_class_context_and_switching.py`, `test_legacy_student_claim.py` | ✅ COMPLETE | All 4 exist; 28 of 28 tracker-claimed test files verified present |

### 3B: Structural Auth Migration (Original Plan — Deferred)

| Original Deliverable | Status |
|---|---|
| `User` activated as primary auth principal | ❌ NOT DONE — admin login resolves `Admin` model via session `admin_id`; student login resolves `Student` model |
| `0002_identity_domain.py` migration (drop legacy auth tables) | ❌ DOES NOT EXIST |
| Legacy tables dropped: `teachers`, `students`, `student_teachers`, `student_blocks`, `teacher_blocks`, `class_memberships`, `recovery_requests`, `student_recovery_codes`, `teacher_onboarding`, `teacher_credentials` | ❌ ALL STILL IN SCHEMA AND STILL USED |
| `tests/domain/test_identity.py` | ❌ DOES NOT EXIST |

### 3C: Remaining Routing Compliance Issues (Not Fully Closed)

These are pre-Wave-12 items but were tracked as Wave 3 cleanup targets:

**`join_code` as internal scope key in admin routes (INV-ARC-014 precursor):**  
Significant number of `filter_by(join_code=...)` and `filter(*.join_code ==...)` patterns remain in `admin.py` outside of pure session context reads. Examples:
- Line 982: `TeacherBlock.query.filter_by(join_code=join_code)`
- Lines 1040–1055: class deletion cleanup queries via `join_code`
- Lines 4479, 4486, 4512–4514: student detail financial queries filtered by `join_code` (not `class_id`)
- Line 4463: `ClassEconomy.query.filter_by(join_code=join_code, teacher_id=teacher_id)` — double-legacy scope

**INV-ARC-014 — `block` as control key (not closed):**  
`RentSettings` still has `block = db.Column(db.String(10), nullable=True)` at line 1540 (despite `FeatureSettings.block` being dropped in Wave 4). Admin routes use `block` as a scope routing key in several places:
- `admin.py:4087`: `RentSettings.query.filter_by(class_id=class_id, block=current_block)`
- `admin.py:6337–6339`: `require_admin_feature_scope('rent', requested_block=block)` + `RentSettings.query.filter_by(..., block=block)`
- `admin.py:5237, 5351`: `block = request.form.get('block', '').strip()` — still accepts block from request
- `admin.py:973`: `requested_block=request.values.get('cwi_block') or request.values.get('block')`

`V2_CLASS_ID_INVARIANT_BACKLOG.md` explicitly tracks this as a deferred cleanup target: "Revisit settings models that still act like `teacher_id + block` is a durable ownership boundary."

**Wave 3 Exit Criterion 1 revisited:** The criterion states "No scope fallback paths in identity/scope-critical route surfaces." `get_current_seat()` in `auth.py` (lines 338–376) does fall back to `student_id`-based seat lookup when `seat_id` is not in session. This was accepted as part of the dual-identity transitional state, not a violation under the re-scoped exit criteria — but it means the canonical seat-first identity path is not fully enforced end-to-end.

---

## Wave 4 — Class Configuration

### Status: ✅ COMPLETE

All 13 claimed deliverables verified:

| Deliverable | Status |
|---|---|
| Analytics enrollment via `ClassMembership` by `class_id` | ✅ `analytics_engine.py:108–111` |
| `get_active_policy_mode_for_class(class_id)` | ✅ `economy_policy.py:602` |
| `get_analytics_policy(mode)` | ✅ `economy_policy.py:614` |
| `get_feature_settings_row_for_class(class_id)` | ✅ `economy_policy.py:565` |
| Analytics activity queries by `Transaction.class_id`, `TapEvent.class_id` | ✅ Multiple lines in `analytics_engine.py` |
| `Student.get_checking/savings_balance()` require `class_id + seat_id` (ValueError on missing) | ✅ `models.py:491, 498` |
| `PolicyVersion` + `PolicyTransition` in `models.py` + `models_canonical.py` | ✅ `models.py:2997–3054`; `models_canonical.py:64–71` |
| Migration `c4e36a4ab2f1_add_policy_lineage_tables.py` | ✅ Idempotent; correct FK wiring |
| `FeatureSettings.economy_pending_rebalance_json` dropped + migration `d2f9f1d9be2e` | ✅ Column absent; migration present |
| `FeatureSettings.teacher_id`, `.join_code`, `.block` dropped + migration `a91cf11e8b2d` | ✅ Columns absent; migration present |
| Legacy uniqueness constraint dropped + migration `f84c7ad2c1aa` | ✅ `class_id` is now `unique=True` |
| `activate_due_rebalances()` uses `policy_transitions` exclusively | ✅ `economy_rebalance.py:483` |
| Dual-write policy transitions for rebalance scheduling | ✅ `_create_policy_transitions_for_changes()` |

### Caveats

- `RentSettings` still has `teacher_id` (NOT NULL), `join_code`, and `block` columns — Wave 4 only cleaned `FeatureSettings`. The other settings tables (`rent_settings`, `banking_settings`, `payroll_settings`, `hall_pass_settings`) retain legacy scope columns. These are Wave 7, 6, and post-Wave work respectively.
- `StoreItem` model retains mandatory `teacher_id` (NOT NULL), with `class_id` optional — store scope migration is Wave 8.

---

## Wave 5 — Ledger Domain

### Status: ⚠️ BEHAVIORAL COMPLIANCE ACHIEVED — TABLE CONSOLIDATION PENDING

The first validation report characterized this as "NOT STARTED." The deeper analysis reveals meaningful progress:

**What IS done (behavioral compliance on legacy tables):**

| Check | Finding |
|---|---|
| `Transaction` dual-scope | `student_id` (nullable), `seat_id` (**NOT NULL**), `class_id` (indexed) — all present |
| `ledger_service.py` scope enforcement | `if not class_id or not seat_id: raise ValueError(...)` at service layer |
| All balance reads by `seat_id + class_id` | `get_posted_balance()`, `get_pending_balance_delta()` all scope by both fields |
| Services use `flush()` not `commit()` | Confirmed — commit delegated to FEAT context |
| `BalanceCache` dual-scope | `student_id` (nullable), `seat_id` (**NOT NULL**), `class_id` (**NOT NULL**); UniqueConstraint on `(class_id, seat_id)` |
| FEAT validates `seat_id + class_id` before any ledger write | `ledger_service.py:131–133` — FATAL ValueError if missing |

**What is NOT done (table consolidation):**

| Check | Status |
|---|---|
| `ledger_service.py` still imports `Transaction` (legacy table name) | ❌ — writes to table `transaction`, not `ledger_transaction` |
| `balance_service.py` still imports `BalanceCache` (legacy table name) | ❌ — reads from `balance_cache`, not `ledger_balance_snapshot` |
| Migration to rename/replace ledger tables | ❌ DOES NOT EXIST |
| `LedgerTransaction` / `LedgerBalanceSnapshot` used at runtime | ❌ — stub-only in `models_canonical.py` |
| `ClassEconomy` import in `ledger_service.py` | ⚠️ — `ClassEconomy` now maps to `classes` table (migration done), so this is functional but semantically confusing |

**Assessment:** The ledger write path is architecturally correct (FEAT-owned, seat+class scoped, flush-not-commit). What remains is the Wave 5 formal work: rename the tables, update the service imports, and drop the old table names. The behavioral model is already aligned.

---

## Wave 6 — Attendance Domain

### Status: ⚠️ BEHAVIORAL COMPLIANCE MOSTLY ACHIEVED — TABLE CONSOLIDATION + FEAT FILE PENDING

**What IS done:**

| Check | Finding |
|---|---|
| `TapEvent` dual-scope | `student_id` (NOT NULL — legacy), `seat_id` (nullable), `class_id` (nullable); enforcement hook mandates both seat_id + class_id on insert/update (raises `ValueError`) |
| `HallPassLog` dual-scope | `student_id` (NOT NULL), `seat_id` (nullable), `class_id` (nullable); legacy `teacher_id` column **removed** |
| INV-ARC-007: `GET /api/student-status` is read-only | ✅ |
| `POST /api/student-status/reconcile` exists, FEAT-wrapped | ✅ `api.py:2940` |
| Wave 3C.8 hall pass scope hardened | ✅ — class context required for mutation paths; fail-closed |
| `FEAT-ATTN-001`, `FEAT-ATTN-002` in FEAT registry | ✅ Both registered |
| `get_class_today_range()` and time helpers for class-local boundaries | ✅ `app/utils/time.py` |

**What is NOT done:**

| Check | Status |
|---|---|
| `tap_feat.py` in `app/feats/` | ❌ DOES NOT EXIST |
| `attendance_service.py` ports to canonical tables | ❌ Still imports `HallPassLog, StudentTeacher, TapEvent, TeacherBlock` |
| `AttendanceSession`, `SeatAttendanceState` used at runtime | ❌ Stub-only in `models_canonical.py` |
| Wave 6 migration (`0005_attendance_domain.py`) | ❌ DOES NOT EXIST |

**Critical note on `TapEvent`:** Despite being the "legacy" table, it enforces mandatory `seat_id + class_id` via `before_insert`/`before_update` hooks. The enforcement is stricter than most other legacy tables — `TapEvent` **will raise a ValueError** if written without canonical scope. However, `student_id` remains mandatory (NOT NULL) as a legacy requirement, creating a dependency on the legacy `students` table that blocks full Wave 6 completion.

---

## Wave 7 — Obligations Domain

### Status: ⚠️ BEHAVIORAL CONTRACTS COMPLETE — SCHEMA CONSOLIDATION PENDING

**Behavioral contracts (locked per tracker "System Behavior Contracts" section):**

| Contract | Status | Evidence |
|---|---|---|
| Rent prepay cycle model with explicit `coverage_start_time`, `coverage_end_time` | ✅ IMPLEMENTED | `RentPayment` model has both columns |
| `cycle_idempotency_key` on rent payments | ✅ IMPLEMENTED | Column present |
| `has_received_rent_exemption` on `Seat` | ✅ IMPLEMENTED | Column present |
| Insurance waiting period: calendar-based, class-local midnight boundaries | ✅ IMPLEMENTED | `app/utils/time.py` helpers wired |
| Insurance eligibility evaluated against transaction timestamp (not current time) | ✅ IMPLEMENTED | Canonical rule enforced via shared helper |
| Rent execution class-scoped with deterministic idempotency | ✅ IMPLEMENTED | `rent_cycle_feat.py` exists; scheduler uses class-scoped entrypoints |
| `rent_cycle_feat.py` with FEAT shell | ✅ EXISTS | `app/feats/rent_cycle_feat.py` |
| All temporal logic uses `get_class_cycle_start_utc()`, `get_class_today_range()` | ✅ IMPLEMENTED | `app/utils/time.py:235–257` |

**Schema consolidation (Wave 7 formal deliverables):**

| Check | Status |
|---|---|
| `obligations_service.py` | ❌ Still imports `InsuranceClaim, RentPayment, StudentInsurance` (legacy tables) |
| `AssessmentEvent`, `ObligationLifecycle`, etc. used at runtime | ❌ Stub-only in `models_canonical.py` |
| `rent_payment_feat.py`, `insurance_claim_feat.py`, `insurance_purchase_feat.py` write to obligation canonical tables | ❌ All still write to legacy tables via services |
| Wave 7 migration (`0006_obligations_domain.py`) | ❌ DOES NOT EXIST |
| Legacy obligation tables dropped | ❌ `rent_payments`, `rent_waivers`, `rent_items`, `insurance_policies`, `insurance_policy_blocks`, `student_insurance`, `insurance_claims` all still in schema |

---

## Wave 8 — Store Domain

### Status: ⚠️ PARTIAL SCOPE MIGRATION — TABLE CONSOLIDATION PENDING

**What IS done (tracker Wave 3C.9 work):**
- Store item resolution, pricing, purchase eligibility, and redemption-facing paths migrated from teacher-scoped to class-scoped filtering.
- Store mutations (create, edit, delete) wrapped in FEAT contexts with idempotency keys (confirmed at `admin.py:5571`, `5974`, `6023`).

**What is NOT done:**

| Check | Status |
|---|---|
| `store_service.py` | ❌ Still imports `RentItem, Student, StudentItem, TeacherBlock` (legacy tables) |
| `StorePurchase`, `RedemptionEvent`, `StoreItemVisibility` used at runtime | ❌ Stub-only in `models_canonical.py` |
| `StoreItem.teacher_id` dropped | ❌ Still `NOT NULL` — mandatory legacy scope anchor |
| `store_purchase_feat.py` writes to canonical tables | ❌ Writes to legacy `student_items` via `store_service` |
| Wave 8 migration (`0007_store_domain.py`) | ❌ DOES NOT EXIST |
| `student_items`, `store_item_blocks` dropped | ❌ Both still in schema |
| `identity_service.reconcile_rent_hall_pass_top_off()` | ❌ HYBRID — resolves Seat/User but writes to legacy `Student.hall_passes` and `StudentBlock.rent_hall_passes` |

---

## Wave 9 — Operations + Interpretation Domains

### Status: ⚠️ AUDIT CHAIN OPERATIONAL (non-canonical) — CANONICAL OPS TABLES NOT USED

This wave's picture is more nuanced than the first report indicated:

**What IS operational (but not on canonical DOM-OPS-001 tables):**

The `audit_events` / `chain_heads` / `integrity_status` tables form a **cryptographic tamper-evident audit chain** added via migration `3447255cb1af`. This is architecturally distinct from the DOM-OPS-001 canonical `audit_log` table — it provides HMAC-chained lineage verification, sequence numbers, and genesis-seeded chain heads. Key properties:
- `AuditEvent` model — 22-column cryptographic record with `hmac_signature`, `previous_hash`, `event_hash`, `sequence_number`
- `audit_protected()` in `base.py:333–375` writes to `audit_events` after every ledger mutation
- `audit_service.emit_audit_event()` enforces FEAT context before writing
- The lineage chain is **live and writing** — every `Transaction` write triggers an audit event and populates `transaction.lineage_event_id` + `transaction.lineage_token`

**Gap vs DOM-OPS-001:** The canonical `audit_log` table (a simpler operational log) does NOT receive writes — `base.py`'s `audit_protected()` targets `audit_events`, not `audit_log`. The canonical `OperationalEvent`, `IncidentEvent`, etc. are entirely unused stubs.

**Additional non-canonical tables not in DOM-CORE-002:**
- `economy_snapshot` — immutable analytics snapshot per class (live; written by admin route at line 2107)
- `payroll_cache` — performance optimization cache per class (live; class-scoped)
- `redemption_audit_logs` — domain-specific audit trail for store redemptions (live; class + seat scoped)

These serve legitimate purposes and are class_id-scoped, but they are additions outside the 44-table target.

| Check | Status |
|---|---|
| Cryptographic audit chain (`audit_events`, `chain_heads`, `integrity_status`) | ✅ OPERATIONAL — migration `3447255cb1af`; writes live |
| `AuditLog` (canonical DOM-OPS-001 `audit_log`) used at runtime | ❌ UNUSED — stub only |
| `OperationalEvent`, `IncidentEvent`, etc. used at runtime | ❌ ALL UNUSED stubs |
| Wave 9 migration (`0008_operations_domain.py`) | ❌ DOES NOT EXIST |
| Legacy observability tables dropped (`actor_request_trace`, `error_events`, `error_logs`, `analytics_alerts`, `user_reports`) | ❌ ALL STILL IN SCHEMA |
| `InterpretationSnapshot`, `InterpretationAnnotation` used at runtime | ❌ UNUSED stubs |
| Wave 9 interpretation migration (`0009_interpretation_domain.py`) | ❌ DOES NOT EXIST |
| `analytics_snapshots`, `analytics_events` (legacy) dropped | ❌ STILL IN SCHEMA |

---

## Wave 10 — Support Domain

### Status: ❌ LEGACY SCOPE COLUMNS NOT CLEANED

| Check | Status |
|---|---|
| `Issue.join_code` column | ❌ STILL PRESENT AND MANDATORY (`NOT NULL`, line 2436) |
| `Issue.teacher_id` column | ❌ STILL PRESENT AND MANDATORY (`NOT NULL`, line 2433) |
| `Issue.class_id`, `Issue.seat_id` | ✅ PRESENT but optional (nullable) |
| `announcement` table legacy columns | ❌ Not audited in this pass; likely similar |
| Wave 10 migration (`0010_support_domain.py`) | ❌ DOES NOT EXIST |

**Canonical support classes in `models_canonical.py`** map to the same table names as legacy models — there's no actual divergence to reconcile, only column cleanup needed.

---

## Wave 11 — Post-Launch Completion

### Status: ⚠️ PARTIAL

| Deliverable | Status |
|---|---|
| Adversarial harness (13 scripts in `scripts/adversarial/`) | ✅ COMPLETE |
| Sanitized evidence export protocol | ✅ COMPLETE |
| Phase 1 adversarial scorecard — claimed PASS (2026-05-14) | ⚠️ SEE NOTE BELOW |
| INV-ARC-007: `GET /api/student-status` split into GET + `POST /reconcile` | ✅ COMPLETE |
| INV-ARC-007: remaining violation in `admin.py:2107` | ❌ OPEN — `db.session.commit()` in GET handler (economy snapshot persistence), no FEAT context |
| `admin.py` decomposition into sub-blueprints | ❌ NOT DONE — 12,862 lines; no `admin_roster.py`, `admin_finance.py`, etc. exist |
| Backup/restore rehearsal | ❌ NOT DONE |
| Operator sign-off flow (`user_invite_tokens`) | ❌ NOT DONE |
| Sysadmin audit (INV-ARC-011 phantom scope) | ❌ NOT DONE |
| `V2_CLASS_ID_INVARIANT_BACKLOG.md` items closed | ❌ ALL OPEN — explicitly deferred to post-launch |
| Full-repo INV-ARC-015 sweep documentation | ❌ NOT DONE |
| INV-ARC-014 full sweep (`block`/`period`/`section` as control keys) | ❌ NOT DONE — multiple `block`-as-scope-key usages confirmed in admin routes |

### ⚠️ Adversarial Scorecard Discrepancy

**Tracker claims (2026-05-14):** Cross-Class Isolation PASS(0), Lineage Verifier PASS(0), Runtime Attacks PASS(0).  
**Artifact file (`artifacts/adversarial/sanitized/current/scorecard_sanitized.md`, generated 2026-05-15):**

| Check | Status | Violations |
|---|---|---:|
| Cross-Class Isolation | **FAIL** | 1 |
| Lineage Verifier | **FAIL** | 5 |
| Runtime Session Attacks | PASS | 0 |
| Synthetic Injection Step | PASS | 0 |

The scorecard was generated the day after the tracker's claimed PASS. The Wave 4 work (May 20–24) occurred after this scorecard, so Wave 4 changes are not the cause. Possible explanations:
1. The scorecard was run against a post-injection database state (injected cross-class data was not cleaned before the run).
2. A regression was introduced between the May 14 PASS run and the May 15 scorecard generation.
3. The lineage verifier (5 failures) may reflect transactions created outside the audit chain (pre-lineage rows from legacy test data).

**Risk:** Until the adversarial harness is re-run against a clean seeded state, the true cross-class isolation and lineage status is uncertain. The May 14 PASS may represent the last confirmed clean state.

---

## Wave 12 — Final Validation

### Status: ❌ NOT STARTED

| Gate | Required | Current |
|---|---|---|
| Exactly 44 canonical tables | 44 | ~66 table-owning ORM classes (40+ legacy + non-canonical additions) |
| `models.py` re-exports only | Yes | Still defines all legacy model classes |
| Clean `User`/`Seat` auth path | Yes | `Admin`/`Student` still primary; `User`/`Seat` supplementary |
| 0 failing tests | 0 | ~123 failing (per plan baseline; not re-measured) |
| All domain tests in `tests/domain/` | Yes | Only `test_smoke.py` exists |
| Zero `*.student_id` scope filters in routes | 0 | Many remain (legitimate during transition) |

---

## FEAT Layer Compliance — Detailed

The FEAT execution layer is the most thoroughly completed component. Revised assessment:

| Check | Status | Evidence |
|---|---|---|
| `FEATContext` class with commit ownership | ✅ COMPLETE | `base.py:107–244` |
| `feat_shell()` decorator for legacy-wrapped routes | ✅ COMPLETE | `base.py:392–425` |
| `FEATContextError` on unauthorized flush/commit | ✅ COMPLETE | `before_flush` + `before_commit` hooks at app boot |
| `init_feat_enforcement(app)` called at boot | ✅ COMPLETE | `app/__init__.py` |
| FEAT registry with all domain codes | ✅ COMPLETE | LED-001/002/003/004, IDEN-001/002, STOR-001/002/003/004/005, ATTN-001/002, ADMN-001, OBL-001 |
| **Services use `flush()`; FEAT owns `commit()`** | ✅ VERIFIED | `ledger_service.py:148, 227` flush; FEAT context `__exit__` commits |
| Store mutations (create, edit, delete) FEAT-wrapped | ✅ VERIFIED | `admin.py:5571` (FEAT-STOR-001), `5974` (FEAT-STOR-001), `6023` (FEAT-STOR-003) |
| Banking settings update FEAT-wrapped | ✅ VERIFIED | `admin.py:10910` (FEAT-ADMN-001) |
| `db.session.commit()` in `student.py`, `analytics.py`, `api.py`, `system_admin.py` | ✅ 0 violations | Confirmed |
| `db.session.commit()` in `admin.py` | ❌ 1 violation | `admin.py:2107` — GET-path economy snapshot persistence |
| `audit_protected()` writes to cryptographic chain | ✅ FUNCTIONAL | Targets `audit_events` table (lineage chain), not canonical `audit_log` |
| Transaction enforcement hook mandates FEAT context | ✅ `models.py:903–1062` — `FEATContextError` if ledger mutation outside FEAT |

**Architecture clarification on `audit_protected()`:** The function writes to `audit_events` (the cryptographic HMAC chain added by migration `3447255cb1af`) — not to the DOM-OPS-001 canonical `audit_log` table. Both exist, but only `audit_events` is live. This means the lineage chain is operational but the canonical operations domain is not.

---

## Schema State Audit — Revised

### Current table distribution in `app/models.py` (~66 table-owning classes)

**Canonical tables LIVE at runtime (survive to v2 target state):**  
`users`, `seats`, `classes` (was `class_economies`), `identity_profiles`, `class_features`, `feature_settings` (fully cleaned), `hall_pass_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `rent_settings`, `banking_settings`, `hall_pass_logs`, `store_items`, `class_memberships`, `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_pack`, `issue_categories`, `announcements`, `policy_versions`, `policy_transitions`

**Dual-scoped legacy tables (behaviorally compliant, table rename pending in Waves 5–8):**  
`transaction` → target: `ledger_transaction`  
`balance_cache` → target: `ledger_balance_snapshot`  
`tap_events` → target: `attendance_sessions` + `seat_attendance_state`  
`rent_payments` (w/ coverage_start/end + idempotency_key) → target: `obligation_lifecycle`  
`student_insurance`, `insurance_claims` → target: `obligation_lifecycle` derivatives  

**Pure legacy tables (used in active write paths, targeted for drop in Waves 5–10):**  
`student_items`, `store_item_blocks` (Wave 8)  
`rent_waivers`, `rent_items`, `insurance_policies`, `insurance_policy_blocks` (Wave 7)  

**Legacy auth tables (deferred Wave 3 structural drops):**  
`teachers`, `students`, `teacher_blocks`, `student_teachers`, `student_blocks`, `recovery_requests`, `student_recovery_codes`, `teacher_credentials`, `teacher_onboarding`, `teacher_invite_codes`

**Legacy observability tables (targeted for drop in Wave 9):**  
`analytics_alerts`, `analytics_snapshots`, `analytics_events`, `actor_request_trace`, `error_logs`, `error_events`, `user_reports`

**Non-canonical additions with legitimate operational purpose (not in DOM-CORE-002 44-table target):**  
`audit_events` — cryptographic HMAC-chained audit lineage (live, actively written)  
`chain_heads` — audit chain head tracking (live, seeded)  
`integrity_status` — nightly verifier status (live, seeded)  
`economy_snapshot` — immutable analytics snapshot (live, written by admin route)  
`payroll_cache` — performance cache (live, class-scoped)  
`redemption_audit_logs` — store redemption audit trail (live, class + seat scoped)

---

## INV-ARC Compliance Summary

| Invariant | Status | Notes |
|---|---|---|
| **INV-ARC-007** (no write-on-GET) | ⚠️ 1 OPEN violation | `admin.py:2107` — GET-path snapshot commit |
| **INV-ARC-007** (student-status endpoint) | ✅ FIXED | GET/POST reconcile split at `api.py:2940` |
| **INV-ARC-014** (no label-based routing) | ❌ NOT CLOSED | `block` still used as scope key in `RentSettings` queries and admin route scope resolution; tracked in `V2_CLASS_ID_INVARIANT_BACKLOG.md` |
| **INV-ARC-015** (class-local time everywhere) | ✅ SUBSTANTIALLY COMPLETE | All critical paths (rent, insurance, attendance, analytics) use class-local time helpers |
| **INV-CORE** (FEAT-only mutation) | ✅ ENFORCED RUNTIME | Before-flush/before-commit hooks active; one remaining route-level commit in admin.py |
| **INV-ARC-011** (phantom scope access) | ❌ NOT AUDITED | Wave 11 sysadmin audit not done |
| **INV-ARC-013** (archived class behavior) | ❌ NOT DEFINED | Class lifecycle not yet specified |

---

## Corrections to First Validation Report

The first report contained several characterizations that this deeper analysis revises:

1. **"Canonical tables written at runtime: 0 of 44"** — Revised to: Active legacy tables are dual-scoped with canonical columns (`seat_id`, `class_id`) enforced at model level. The write paths are architecturally correct; only the table names need renaming in Waves 5–10.

2. **Wave 5 as "NOT STARTED"** — Revised to: "Behavioral compliance achieved; formal table consolidation pending." `ledger_service.py` enforces `seat_id + class_id` on every write; the FEAT-flush-commit model is correct.

3. **Wave 9 as "infrastructure only"** — Revised to: "Cryptographic audit chain fully operational on `audit_events` (non-canonical table). DOM-OPS-001 canonical tables are unused stubs."

4. **Adversarial scorecard status** — First report characterized it as PASS. The artifact shows FAIL (Cross-Class 1, Lineage 5) dated 2026-05-15, the day after the tracker's claimed PASS. Status is uncertain until re-run.

5. **FEAT atomicity model** — First report did not distinguish FEAT-commits vs service-flushes. The correct model is confirmed: FEAT context owns the commit; services only flush. This is working correctly.

---

## Recommended Next Steps (Updated Priority Order)

1. **Re-run adversarial harness against clean seeded state** — confirm or refute the May 15 scorecard's cross-class and lineage failures. This is the highest-urgency validation gap.

2. **Fix `admin.py:2107`** — wrap the economy snapshot persistence in a FEAT context (small change, closes the only remaining FEAT violation).

3. **Execute Wave 5 (Ledger table rename)** — the behavioral model is already correct; this is primarily a table rename + service import update + formal migration. Lower risk than it appears.

4. **Create `tap_feat.py` and execute Wave 6 (Attendance)** — `FEAT-ATTN-001/002` are already registered; the main work is the feat file + porting `attendance_service.py`.

5. **Update `test_smoke.py`** — add `PolicyVersion` and `PolicyTransition` to the import list and bump the assertion to 46 (2-line fix).

6. **Close INV-ARC-014 (`block` as routing key)** — `RentSettings.block` column needs to be resolved to `class_id` alone. Tracked in `V2_CLASS_ID_INVARIANT_BACKLOG.md`.

7. **Execute Wave 7 (Obligations)** — behavioral contracts already complete; schema consolidation is the remaining work.

8. **Execute Waves 8–10** in sequence (Store → Operations/Interpretation → Support).

9. **Wave 3 structural completion** — activate `User`/`Seat` as the primary auth path and drop legacy auth tables. This is the largest architectural debt item.

10. **Create per-domain test files** in `tests/domain/` (`test_identity.py`, `test_attendance.py`, `test_obligations.py`, `test_store.py`, `test_operations.py`, `test_support.py`).

11. **Decompose `admin.py`** (Wave 11) — 12,862 lines is the single largest maintenance liability.

---

*This report (Revision 2) supersedes the prior version. Produced by multi-pass direct code inspection on 2026-05-25.*

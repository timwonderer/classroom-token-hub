# V2 Full-Compliance Migration Plan

## Context

The `codex/v2.0` branch is an active v2 rebuild that introduced the capability-based authority model (INV→DOM→FEAT), `seat_id`/`class_id` canonical scoping, and the FEAT execution layer. However, the codebase is in a transitional state: 44 of 54+ SQLAlchemy models are **dual-scoped** (carry both v1 `student_id`/`teacher_id`/`join_code` and v2 `seat_id`/`class_id` columns), 5 models are pure v1 legacy (Admin, AdminCredential, RecoveryRequest, StudentRecoveryCode, TeacherOnboarding), and the `User` auth model exists but is inactive.

**V2 is a clean break from V1. No data migration is required. Old tables are dropped as each domain is ported, not carried forward.** The goal is a fresh system that complies fully with DOM-CORE-002 (44 canonical tables only) from the ground up.

Target state:
- DOM-CORE-002: exactly 44 canonical tables, nothing else in the schema
- DOM-CORE-001: 9 domains with strict authority boundaries
- FEAT-CORE-000: all state mutation through FEAT units
- INV-CORE-000 + INV-ARC-000–015: all invariants enforced

**Each wave ends with a mandatory verification gate. A wave that produces a non-operational app must be rolled back (git + `flask db downgrade`) and retried before proceeding.**

---

## Current State Snapshot

| Dimension | Status |
|---|---|
| Models | 54+ classes; 44 dual-scoped, 5 pure v1, ~5 pure v2 |
| Migration files | 196 in `migrations/versions/`; single head `db80eb72e775` |
| Test files | 117; ~708 passing, ~123 failing (active stabilization) |
| Feats | 8 active (`transfer`, `store_purchase`, `rent_payment`, `transaction_void`, `insurance_claim`, `insurance_purchase`, `admin_adjustment`, `base`) |
| Services | 8 (`access_policy`, `attendance`, `balance`, `identity`, `ledger`, `obligations`, `store`, `tlcp`) |
| Blueprints | 8 (`admin` 514K lines, `student` 178K, `api` 120K, `system_admin` 78K, `docs` 30K, `analytics` 19K, `main` 14K, `recovery` 8.6K) |
| Target canonical tables | 44 across 9 domains (DOM-CORE-002) |
| Auth | `User` model exists but inactive; `Admin`/`Student`/`SystemAdmin` are still primary |
| `Seat` | Partially active; bridges to `Student` via `student_id` FK |
| `ClassEconomy` | Active v2 class anchor (`class_id` UUID); table name `class_economies` vs target `classes` |

---

## Canonical Target Schema (DOM-CORE-002)

| Domain | Canonical Tables |
|---|---|
| Identity | `users`, `seats`, `classes`, `identity_profiles`, `user_invite_tokens`, `user_recovery_tokens` |
| Class Config | `class_features`, `feature_settings`, `hall_pass_settings`, `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `banking_settings` |
| Attendance | `attendance_sessions`, `hall_pass_logs`, `seat_attendance_state` |
| Obligations | `assessment_events`, `obligation_lifecycle`, `obligation_satisfaction`, `obligation_reversal`, `entitlement_events` |
| Ledger | `ledger_transaction`, `ledger_balance_snapshot` |
| Store | `store_items`, `store_item_visibility`, `store_purchases`, `redemption_events` |
| Operations | `operational_events`, `audit_log`, `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`, `health_check_events` |
| Interpretation | `interpretation_snapshots`, `interpretation_annotations` |
| Support | `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_packs`, `announcements`, `issue_categories` |

---

## Wave Overview

| Wave | Name | Outcome |
|---|---|---|
| 1 | Canonical Model Foundation | All 44 ORM classes written; schema gap audit complete; app still runs on legacy |
| 2 | Bootstrap Migration Squash | 196 files archived; single idempotent bootstrap migration; both legacy + canonical tables co-resident |
| 3 | Identity Domain | Unified User/Seat auth live; legacy auth tables dropped |
| 4 | Class Configuration | Settings tables ported to canonical; legacy settings columns dropped |
| 5 | Ledger Domain | `transaction` → `ledger_transaction`; old ledger tables dropped |
| 6 | Attendance Domain | `tap_events` → `attendance_sessions`; old attendance tables dropped |
| 7 | Obligations Domain | Rent + insurance → canonical obligation hierarchy; old obligation tables dropped |
| 8 | Store Domain | `student_items` → `store_purchases` + `redemption_events`; old store tables dropped |
| 9 | Operations + Interpretation | Observability and analytics ported; old event/analytics tables dropped |
| 10 | Support Domain | Support tables finalized; old support columns dropped |
| 11 | Post-Launch Completion | Backup/restore, operator sign-off, sysadmin audit, admin route decomposition, invariant sweeps |
| 12 | Final Validation | Schema exactly matches DOM-CORE-002; clean test suite; zero v1 artifacts |

---

## Cross-Wave Protocol

### Verification Gate (required at end of every wave)

```bash
flask db upgrade                       # migration applies cleanly
flask db downgrade                     # rolls back cleanly
flask db upgrade                       # re-applies
flask db heads                         # must show exactly 1 head
pytest tests/domain/test_smoke.py      # domain smoke suite passes
# manual: start app, /health → 200, teacher login works, student login works
pytest                                 # full suite; fail count must not increase vs prior wave
```

### Rollback

1. `git revert` or reset wave branch
2. `flask db downgrade` to prior migration head
3. Confirm app launches and passes prior gate
4. Diagnose — do NOT proceed to next wave until current wave passes

### Per-Domain Wave Structure

Each domain wave (3–10) follows this exact sequence:
1. **Create canonical tables** (migration with `table_exists` guards)
2. **Port models** in `models.py` / `models_canonical.py` to canonical ORM classes
3. **Port services** for that domain to query canonical tables
4. **Port feats** that touch that domain to write canonical tables
5. **Port routes** that use that domain
6. **Drop old tables** (migration — use `table_exists` guards; after code is confirmed working)
7. **Write domain tests** in `tests/domain/test_<domain>.py`
8. **Retire old scattered tests** for that domain
9. **Verification gate** — app operational, no regression

---

## Wave 1 — Canonical Model Foundation

**Goal:** Write all 44 DOM-CORE-002 ORM model classes as the authoritative reference. Produce a gap audit document. App still runs on legacy tables — no schema changes yet.

### Deliverables

1. **`app/models_canonical.py`** (new file) — defines all 44 canonical ORM classes:
   - Identity: `User`, `Seat`, `Class_` (table=`classes`), `IdentityProfile`, `UserInviteToken`, `UserRecoveryToken`
   - Class Config: canonical settings classes (no `teacher_id`/`join_code` columns — only `class_id`)
   - Attendance: `AttendanceSession`, `HallPassLog` (clean), `SeatAttendanceState`
   - Obligations: `AssessmentEvent`, `ObligationLifecycle`, `ObligationSatisfaction`, `ObligationReversal`, `EntitlementEvent`
   - Ledger: `LedgerTransaction`, `LedgerBalanceSnapshot`
   - Store: `StoreItem` (clean), `StoreItemVisibility`, `StorePurchase`, `RedemptionEvent`
   - Operations: `OperationalEvent`, `AuditLog`, `IncidentEvent`, `IncidentSummary`, `AlertEvent`, `InvariantRunEvent`, `JobEvent`, `HealthCheckEvent`
   - Interpretation: `InterpretationSnapshot`, `InterpretationAnnotation`
   - Support: `Issue`, `IssueStatusHistory`, `IssueResolutionAction`, `TicketCorrelationPack`, `Announcement`, `IssueCategory`

2. **`docs/development/tracking/V2_SCHEMA_GAP_AUDIT.md`** — for each of the 44 canonical tables: current table name (if any), columns to add, columns to drop, FK changes needed, and which wave ports it

3. **`tests/domain/`** directory with `tests/domain/test_smoke.py` (imports all 44 classes, no DB needed)

### Critical Files

- `app/models_canonical.py` (create)
- `docs/development/tracking/V2_SCHEMA_GAP_AUDIT.md` (create)
- `tests/domain/test_smoke.py` (create)

### Verification

- `python -c "from app.models_canonical import *"` — no errors
- All 117 existing tests pass (zero regression — no code changes, only new file)

---

## Wave 2 — Bootstrap Migration Squash

**Goal:** Archive the 196 legacy migration files and produce a single idempotent bootstrap migration that co-creates both the remaining legacy tables (so the app still runs) and all 44 canonical tables. This is the clean baseline for all future migrations.

### Deliverables

1. **Archive:** move all 196 files from `migrations/versions/` → `migrations/archive/v1_196_migrations/`; add `migrations/archive/README.md` documenting the squash date and prior head (`db80eb72e775`)

2. **`migrations/versions/0001_bootstrap.py`** — `down_revision = None`:
   - Section A: creates all legacy tables with full `table_exists()` guards (so existing dev DBs are no-ops)
   - Section B: creates all 44 canonical tables with `table_exists()` guards
   - `downgrade()`: no-op (cannot destroy a production bootstrap)
   - Includes all helper functions from `migrations/migration_template.py.mako`

3. **`scripts/verify_migration_squash.py`** — asserts `flask db heads` = `0001`, checks all 44 canonical tables exist

4. CHANGELOG updated

### Critical Files

- `migrations/versions/0001_bootstrap.py` (create)
- `migrations/archive/v1_196_migrations/` (move 196 files)
- `scripts/verify_migration_squash.py` (create)

### Verification

- Fresh empty DB: `flask db upgrade` creates both legacy and canonical tables
- Existing dev DB: `flask db upgrade` is a no-op on legacy tables, creates canonical tables
- `flask db heads` → `0001` only
- Full test suite: same pass count as Wave 1

### Status Update (2026-04-30)

- ✅ Archived `196` migration files from `migrations/versions/` to `migrations/archive/v1_196_migrations/`.
- ✅ Added bootstrap migration `migrations/versions/0001_bootstrap.py` with `down_revision = None`.
- ✅ Added `scripts/verify_migration_squash.py` and validated: head is `0001`, canonical table count is `44`.
- ✅ Migration gate executed on active Postgres environment:
  - `flask db upgrade`
  - `flask db downgrade`
  - `flask db upgrade`
  - `flask db heads` → `0001 (head)`
- ✅ Targeted verification tests passed: `tests/domain/test_smoke.py`, `tests/test_migration_idempotency.py`, `tests/test_migration_1a4ee2388d62_fix.py` (`11 passed`).

Operational note:
- `flask db` in this codebase resolves DB URL via Flask app bootstrap and may force `.env` values during CLI runs depending on environment flags. When validating against alternate DB URLs, confirm the effective URL from command output (`DEBUG: Migrating database at ...`) and use explicit environment guards in CI.

---

## Wave 3 — Identity Domain (DOM-IDEN-001)

**Goal:** Activate `User`/`Seat`/`Class_` as the primary auth path. Drop all legacy auth tables at end of wave.

### Deliverables

1. **Rename `class_economies` → `classes`** (migration with full FK cascade update across all tables that reference it)

2. **Activate `User` as primary auth principal:**
   - `app/auth.py`: login → resolve `User` record → resolve/create `Seat` → session gets `seat_id` + `class_id`
   - `get_logged_in_student()` → returns `(User, Seat)` tuple
   - `get_current_admin()` → returns `User` with role=`teacher`
   - Remove all `Admin`/`Student`/`SystemAdmin` session bridges

3. **Port `RecoveryRequest`/`StudentRecoveryCode`** logic → `user_recovery_tokens` table

4. **Add `user_invite_tokens`** table and teacher invite flow for onboarding

5. **`app/services/identity_service.py`** rewritten to operate on `User`/`Seat` only

6. **Migration `0002_identity_domain.py`:**
   - Renames `class_economies` → `classes` (with FK updates)
   - Drops: `teachers`, `students`, `student_teachers`, `student_blocks`, `teacher_blocks`, `class_memberships`, `recovery_requests`, `student_recovery_codes`, `teacher_onboarding`, `teacher_credentials`, `admin_credentials`

7. **`tests/domain/test_identity.py`:**
   - Student login → Seat claim → session context (`seat_id`, `class_id` set)
   - Teacher login → User resolution → class context
   - Account recovery via `user_recovery_tokens`
   - Multi-class student: one `User`, two `Seats`, correct context switch
   - `seat_id` uniqueness per class (UQ constraint enforced)
   - Cross-tenant isolation: seat from class A cannot access class B

8. Retire: `tests/test_teacher_recovery.py`, login sections of `tests/test_admin_routes.py` and `tests/test_student_routes.py`

### Critical Files

- `app/auth.py`
- `app/models.py` (remove legacy auth model classes)
- `app/models_canonical.py` (activate identity classes)
- `app/services/identity_service.py`
- `app/routes/student.py` (login handler)
- `app/routes/admin.py` (login handler)
- `app/routes/recovery.py`
- `migrations/versions/0002_identity_domain.py`
- `tests/domain/test_identity.py`

### Verification

- Student can log in; session has `seat_id` + `class_id`
- Teacher can log in; class selection works
- Account recovery flow end-to-end functional
- System admin login functional
- `flask db heads` → `0002`; schema has `classes` table, no `class_economies`, no `teachers`/`students`

### Status Update (2026-05-03): Wave 3C.10-B Rent Lifecycle + Scheduled Execution

- Added class-scoped scheduler entrypoints in `app/scheduled_tasks.py`:
  - `run_rent_cycle_for_class(class_id, execution_time)`
  - `run_rent_cycle_scheduler(execution_time=None)`
- Enforced seat-scoped economic actor for scheduled rent (`seat_id + class_id`) with claimed-seat gating (`claimed_at IS NOT NULL`).
- Added explicit prepay coverage windows on `rent_payments`:
  - `coverage_start_time`
  - `coverage_end_time`
- Added deterministic cycle idempotency:
  - `cycle_idempotency_key`
  - normalized cycle-boundary derivation before key generation
- Added new-seat one-cycle exemption state on `seats`:
  - `has_received_rent_exemption`

Focused validation:

- `pytest -q tests/test_scheduled_tasks_rent_cycle.py tests/test_add_rent_waiver_route.py tests/test_redemption_audit_log.py tests/test_redemption_rejection.py tests/test_scheduled_tasks_store_item_cleanup.py`
- Result: `18 passed`

### Status Update (2026-05-04): Wave 3C.10-T/C Temporal Enforcement + Insurance Calendar Semantics

- Enforced temporal boundary discipline in critical execution paths:
  - attendance/day-boundary evaluation now class-scoped (`get_class_today_range`)
  - student weekly/monthly windows now class-scoped (`get_class_week_range_utc`, `get_class_month_start_utc`)
  - rent scheduler cycle boundary now class-aligned (`get_class_cycle_start_utc`)
- Added temporal helper hardening in `app/utils/time.py`:
  - `get_class_cycle_start_utc(...)`
  - class-reference-aware `get_class_now(...)` / `get_class_today_range(...)`
- Completed insurance temporal semantics alignment:
  - waiting period is calendar-based in class-local time (not purchase timestamp + N*24h)
  - waiting-start = next class-local midnight after purchase day
  - coverage-start storage is derived from class-local boundary and converted to UTC
  - eligibility checks use class-local temporal comparisons from `class_id` context
- Corrected rent cycle month/year derivation:
  - `period_month/year` and `coverage_month/year` now come from class-local cycle start, not raw UTC month/year

Focused validation:

- `pytest -q tests/test_time_money_guardrails.py tests/test_scheduled_tasks_rent_cycle.py tests/test_add_rent_waiver_route.py tests/test_redemption_audit_log.py tests/test_redemption_rejection.py tests/test_scheduled_tasks_store_item_cleanup.py`
- Result: `22 passed`
- `pytest -q tests/test_insurance_security.py tests/test_scheduled_tasks_rent_cycle.py tests/test_add_rent_waiver_route.py tests/test_redemption_audit_log.py tests/test_redemption_rejection.py tests/test_scheduled_tasks_store_item_cleanup.py`
- Result: `24 passed`

---

## Wave 4 — Class Configuration Domain (DOM-CLASS-001)

**Goal:** Remove `teacher_id` and `join_code` from all settings tables; `class_id` becomes the sole scope key.

### Deliverables

1. **Migration `0003_class_config_domain.py`:**
   - Drops `teacher_id` + `join_code` columns from: `payroll_settings`, `rent_settings`, `banking_settings`, `hall_pass_settings`, `feature_settings`, `payroll_rewards`, `payroll_fines`
   - `class_features` already clean — validate
   - Adds any missing columns per DOM-CLASS-001 spec

2. **All services** (`access_policy_service`, `obligations_service`) and **scheduled tasks** (`scheduled_tasks.py`) updated to query settings by `class_id` only

3. **`tests/domain/test_class_config.py`:**
   - Load settings by `class_id`
   - Policy change takes effect for new operations
   - Two classes have independent payroll rates
   - Feature toggle: class A has store, class B does not

### Critical Files

- `app/services/access_policy_service.py`
- `app/services/obligations_service.py`
- `app/scheduled_tasks.py`
- All settings model classes
- `migrations/versions/0003_class_config_domain.py`
- `tests/domain/test_class_config.py`

### Verification

- Payroll job runs against canonical settings
- Feature toggle respected per class
- No `join_code` or `teacher_id` references in settings-related queries

---

## Wave 5 — Ledger Domain (DOM-LED-001)

**Goal:** All money movement through `ledger_transaction` exclusively. Drop `transaction` and `balance_cache`.

### Deliverables

1. **Migration `0004_ledger_domain.py`:**
   - Creates `ledger_transaction`: `ledger_tx_id` (UUID PK), `class_id`, `seat_id`, `account_type` (enum: checking/savings), `amount` (Decimal), `direction` (debit/credit), `description`, `feat_code`, `idempotency_key`, `correlation_id`, `posted_at`
   - Creates `ledger_balance_snapshot`
   - Unique constraint: `(class_id, seat_id, feat_code, idempotency_key)`
   - Drops: `transaction`, `balance_cache`, `payroll_cache`

2. **`app/services/ledger_service.py`** rewritten: `post_entry()`, `get_balance()`, `get_ledger()`, `void_entry()` — all on `LedgerTransaction`

3. **`app/services/balance_service.py`** reads from `LedgerBalanceSnapshot`

4. **All 8 FEATs** updated to call `ledger_service.post_entry()` (not direct model writes)

5. **`app/feats/base.py`** — update FEAT registry and `_enforce_transaction_integrity` event listener to target `LedgerTransaction`

6. **`tests/domain/test_ledger.py`:**
   - Post debit → balance decreases
   - Post credit → balance increases
   - Void → counter-entry created; original immutable
   - Transfer zero-sum invariant
   - Idempotency key prevents double-post
   - `FEATContextError` raised if no FEAT context
   - Cross-class isolation

### Critical Files

- `app/services/ledger_service.py`
- `app/services/balance_service.py`
- `app/feats/base.py`
- All 8 feat files in `app/feats/`
- `migrations/versions/0004_ledger_domain.py`
- `tests/domain/test_ledger.py`

### Verification

- Teacher sees student balances
- Student sees own balance
- Admin adjustment changes balance
- Transfer succeeds and reflected correctly
- No `transaction` or `balance_cache` tables remain in schema

---

## Wave 6 — Attendance Domain (DOM-ATT-001)

**Goal:** Replace `tap_events` with `attendance_sessions` + `seat_attendance_state`. Remove all GET-triggered write violations (INV-ARC-007).

### Deliverables

1. **Migration `0005_attendance_domain.py`:**
   - Creates `attendance_sessions` (tap-in/tap-out pairs as session records)
   - Creates `seat_attendance_state` (current state per seat: in/out/done-for-day)
   - `hall_pass_logs`: drops `join_code`/`teacher_id` columns; keeps `class_id`/`seat_id`
   - Drops: `tap_events`

2. **`app/services/attendance_service.py`** updated to write/read canonical attendance tables

3. **New FEAT: `app/feats/tap_feat.py`** — tap-in and tap-out as atomic, idempotent operations (fixes INV-ARC-007: no more write-on-GET)

4. **Route audit:** all GET handlers in attendance sections made pure (no DB writes)

5. **`tests/domain/test_attendance.py`:**
   - Tap in → `attendance_sessions` record + `seat_attendance_state` updated
   - Tap out → session closed, duration recorded
   - Hall pass request → issued state
   - Hall pass return → session closed
   - Done-for-day lock respected
   - GET routes confirmed write-free

### Critical Files

- `app/services/attendance_service.py`
- `app/feats/tap_feat.py` (new)
- `app/routes/api.py` (tap endpoints)
- `app/routes/admin.py` (hall pass section)
- `migrations/versions/0005_attendance_domain.py`
- `tests/domain/test_attendance.py`

### Verification

- Full tap-in/tap-out cycle works
- Hall pass lifecycle functional
- Done-for-day lock works
- Dashboard load produces no DB writes

---

## Wave 7 — Obligations Domain (DOM-OBL-001)

**Goal:** Port rent and insurance to the canonical obligation hierarchy. Drop all old obligation tables. This is the highest-complexity domain wave.

### Deliverables

1. **Migration `0006_obligations_domain.py`:**
   - Creates: `assessment_events`, `obligation_lifecycle`, `obligation_satisfaction`, `obligation_reversal`, `entitlement_events`
   - Drops: `rent_payments`, `rent_waivers`, `rent_items`, `insurance_policies`, `student_insurance`, `insurance_claims`, `insurance_policy_blocks`

2. **`app/services/obligations_service.py`** rewritten on canonical obligation tables

3. **FEATs updated:**
   - `rent_payment_feat.py` → writes `AssessmentEvent` + `ObligationLifecycle` + `LedgerTransaction`
   - `insurance_claim_feat.py` → writes satisfaction/reversal on `ObligationLifecycle`
   - `insurance_purchase_feat.py` → writes `EntitlementEvent` + `LedgerTransaction`

4. **`tests/domain/test_obligations.py`:**
   - Rent assessment creates `assessment_events` + `obligation_lifecycle`
   - Rent payment satisfies obligation (ledger + obligation linked via `obligation_satisfaction`)
   - Rent waiver creates `obligation_reversal`
   - Insurance purchase creates `entitlement_events` + ledger entry
   - Insurance claim satisfies obligation
   - Delinquency guard blocks appropriate feats
   - Cross-class isolation

### Critical Files

- `app/services/obligations_service.py`
- `app/feats/rent_payment_feat.py`
- `app/feats/insurance_claim_feat.py`
- `app/feats/insurance_purchase_feat.py`
- `migrations/versions/0006_obligations_domain.py`
- `tests/domain/test_obligations.py`

### Verification

- Rent payment end-to-end works
- Insurance purchase + claim works
- Delinquency guard active
- No old rent/insurance tables in schema

---

## Wave 8 — Store Domain (DOM-STORE-001)

**Goal:** Replace `student_items` with `store_purchases` + `redemption_events`. Add `store_item_visibility`.

### Deliverables

1. **Migration `0007_store_domain.py`:**
   - Creates `store_purchases`: `seat_id`, `class_id`, `store_item_id`, `quantity`, `price_at_purchase`, `idempotency_key`, `ledger_tx_id` FK
   - Creates `redemption_events`: `purchase_id`, `redeemed_at`, `redeemed_by_seat_id`
   - Creates `store_item_visibility`: `store_item_id`, `class_id`, `visible`, `available_from`, `available_until`
   - Drops: `student_items`, `store_item_blocks`

2. **`app/services/store_service.py`** updated to query `store_purchases`, `redemption_events`, `store_item_visibility`

3. **`store_purchase_feat.py`** updated to write `StorePurchase` + `LedgerTransaction` atomically

4. **`tests/domain/test_store.py`:**
   - Purchase → `store_purchases` record, ledger debited
   - Redeem → `redemption_events` record
   - Visibility: item hidden for class A, visible for class B
   - Insufficient balance blocks purchase
   - Idempotency: duplicate purchase rejected

### Critical Files

- `app/services/store_service.py`
- `app/feats/store_purchase_feat.py`
- `migrations/versions/0007_store_domain.py`
- `tests/domain/test_store.py`

### Verification

- Teacher creates item, sets visibility per class
- Student purchases; balance decreases
- Teacher marks redeemed
- No `student_items` or `store_item_blocks` in schema

---

## Wave 9 — Operations + Interpretation Domains (DOM-OPS-001, DOM-ITR-001)

**Goal:** Port observability and analytics to canonical tables. Drop all legacy event/analytics tables.

### Deliverables

1. **Migration `0008_operations_domain.py`:**
   - Creates: `operational_events`, `audit_log`, `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`, `health_check_events`
   - Drops: `actor_request_trace`, `error_events`, `error_log`, `analytics_alerts`, `user_reports`

2. **Migration `0009_interpretation_domain.py`:**
   - Creates: `interpretation_snapshots`, `interpretation_annotations`
   - Drops: `analytics_snapshots`, `analytics_events`

3. **`app/utils/analytics_engine.py`** updated to write `InterpretationSnapshot` / `InterpretationAnnotation`

4. **`app/feats/base.py`** — FEAT execution emits `AuditLog` + `OperationalEvent` on every FEAT run

5. **Invariant runner** — scheduled check emits `InvariantRunEvent`; failures create `IncidentEvent`

6. **`tests/domain/test_operations.py`** and **`tests/domain/test_interpretation.py`:**
   - FEAT execution emits audit record
   - Invariant failure creates incident event
   - Analytics snapshot computed and scoped by class

### Critical Files

- `app/utils/analytics_engine.py`
- `app/feats/base.py`
- `app/scheduled_tasks.py`
- `migrations/versions/0008_operations_domain.py`
- `migrations/versions/0009_interpretation_domain.py`
- `tests/domain/test_operations.py`
- `tests/domain/test_interpretation.py`

### Verification

- Analytics dashboard loads
- FEAT produces audit record
- Invariant check run produces events
- No legacy analytics/event tables remain

---

## Wave 10 — Support Domain (DOM-SUP-001)

**Goal:** Finalize support tables to canonical schema. Remove any remaining `join_code`/`teacher_id` columns from support tables.

### Deliverables

1. **Migration `0010_support_domain.py`:**
   - Drops `join_code`/`teacher_id` columns from `issues`, `announcements`, `issue_resolution_actions` where present
   - Renames `ticket_correlation_pack` → `ticket_correlation_packs` if needed
   - Ensures all scope is via `class_id` / `seat_id`

2. **`tests/domain/test_support.py`:**
   - File issue → status `open`
   - Resolve → resolution action created
   - Announcement created, visible to class members
   - Cross-class isolation: class A issues not visible to class B

### Critical Files

- Support model classes in `app/models.py`
- `app/routes/admin.py` (support section)
- `app/routes/student.py` (issue filing)
- `migrations/versions/0010_support_domain.py`
- `tests/domain/test_support.py`

### Verification

- Teacher files and resolves issues
- Student submits report
- Announcements display correctly
- Schema has canonical support tables; no legacy columns

---

## Wave 11 — Post-Launch Completion

**Goal:** Complete all deferred post-launch items from V2_LAUNCH_READINESS_MATRIX.md plus structural cleanup.

### Deliverables

1. **Backup/restore rehearsal** (currently `blocked` in readiness matrix):
   - Test `pg_dump` + `pg_restore` against canonical 44-table schema
   - Document in `docs/operations/Deployment_Guide.md`

2. **Operator sign-off flow** — teacher onboarding gate using `user_invite_tokens` (from Wave 3)

3. **Sysadmin audit** — system admin routes reviewed for DOM-IDEN/DOM-OPS compliance; phantom scope access (INV-ARC-011) eliminated

4. **Class lifecycle** — define archived class behavior per INV-ARC-013; implement if needed

5. **`app/routes/admin.py` decomposition** (514K lines → domain-aligned sub-blueprints):
   - `app/routes/admin_roster.py`
   - `app/routes/admin_finance.py`
   - `app/routes/admin_store.py`
   - `app/routes/admin_attendance.py`
   - `app/routes/admin_settings.py`
   - `app/routes/admin_support.py`
   - `app/routes/admin_analytics.py` (merge existing `analytics.py`)
   - All existing URL paths preserved

6. **INV-ARC-007 final sweep** — confirm zero GET handlers trigger DB writes

7. **INV-ARC-014 final sweep** — confirm zero label-based routing (`block`/`period`/`section` as control keys)

8. **`V2_TEMPORAL_INVARIANT_AUDIT.md`** completed (INV-ARC-015 temporal correctness)

9. **`V2_CLASS_ID_INVARIANT_BACKLOG.md`** all items closed

10. **TLCP (`app/services/tlcp.py`)** validated against canonical `ledger_transaction` table

### Verification

- Backup/restore rehearsed on staging
- All GET routes are write-free
- Admin routes functional after decomposition; all URL paths respond correctly
- All readiness matrix items marked `done`

---

## Wave 12 — Final Validation

**Goal:** Confirm the schema is exactly DOM-CORE-002, the codebase has zero v1 artifacts, and the test suite is clean.

### Deliverables

1. **Schema audit script** (`scripts/validate_canonical_schema.py`):
   - Connects to DB, enumerates all tables
   - Asserts exactly the 44 canonical tables exist — no more, no less
   - Prints pass/fail per table

2. **Code audit** (grep-based):
   - No references to dropped table names (`transaction`, `balance_cache`, `tap_events`, `teachers`, `students`, `student_items`, `rent_payments`, `insurance_claims`, etc.)
   - No `student_id`/`teacher_id` column references in query filters (only allowed in identity resolution layer)
   - No `join_code` used as internal scope key (only as user-facing input → immediately resolved to `class_id`)

3. **`app/models.py`** becomes a one-liner re-export: `from app.models_canonical import *`; no model class definitions of its own

4. **`app/auth.py`** — all v1 fallback bridges removed; clean `User`/`Seat` path only

5. **Test cleanup:**
   - All domain tests in `tests/domain/` organized by domain
   - Remove all legacy-pattern test files that tested removed code
   - Target: 0 failing tests; any residual failures have open tracking issues

6. **Documentation:**
   - `docs/technical-reference/database_schema.md` — rewritten to canonical 44-table schema
   - `DOM-CORE-002` marked as `v1.1 implemented` with completion date
   - `CLAUDE.md` updated to remove all v1 transitional guidance
   - `CHANGELOG.md` updated

### Verification (Final Gate)

```bash
python scripts/validate_canonical_schema.py   # exactly 44 tables
flask db upgrade                               # clean on empty DB
flask db heads                                 # single head
pytest                                         # 0 failures
grep -r "\.teacher_id" app/routes/            # 0 results (outside identity_service)
grep -r "\.student_id" app/routes/            # 0 results (outside identity_service)
```

- App launches; teacher login → student login → transaction cycle completes
- System admin login works

---

## Key Technical Risks

| Risk | Mitigation |
|---|---|
| `class_economies` → `classes` rename (Wave 3) touches FKs across 20+ tables | Execute rename + FK update in single migration; test with `flask db downgrade` before merging |
| `admin.py` 514K decomposition (Wave 11) breaks URL routing | Preserve all existing URL paths using identical `url_prefix`; split file only, not routes |
| Dropping `transaction` removes FEAT context enforcement hook | Re-register event listener on `LedgerTransaction` in Wave 5 before drop |
| 123 currently failing tests may hide v1 assumptions | Triage all 123 failures before Wave 3: classify as (a) fixed by wave N, (b) needs rewrite, (c) genuine bug |
| `join_code` used as scope key deep in `app/routes/` | INV-ARC audit in Wave 11; grep pass in Wave 12 acts as enforcement |

---

## File Reference

| Category | Key Files |
|---|---|
| Canonical schema spec | `docs/development/v2_restructure_doc/DOMAIN/DOM-CORE-002_Canonical_Schema_Definition.md` |
| Domain authority | `docs/development/v2_restructure_doc/DOMAIN/DOM-CORE-001_Domain_Authority_Summary.md` |
| FEAT constitution | `docs/development/v2_restructure_doc/FEATURE-EXECUTION/FEAT-CORE-000_Feature_Execution_Constitutional_Directive.md` |
| Core invariants | `docs/development/v2_restructure_doc/INVARIANT/CORE/INV-CORE-000_Core_Invariants.md` |
| Launch readiness | `docs/development/tracking/V2_LAUNCH_READINESS_MATRIX.md` |
| Migration template | `migrations/migration_template.py.mako` |
| Migration linter | `scripts/lint_migrations.py` |
| Current models | `app/models.py` (3261+ lines) |
| Feats | `app/feats/` (8 files) |
| Services | `app/services/` (8 files) |
| Auth layer | `app/auth.py` |
| Seat scope utils | `app/utils/seat_scope.py` |

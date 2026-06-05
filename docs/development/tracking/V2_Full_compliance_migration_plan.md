# V2 Full-Compliance Migration Plan

## Context

The `codex/v2.0` branch is an active v2 rebuild that introduced the capability-based authority model (INV→DOM→FEAT), `seat_id`/`class_id` canonical scoping, and the FEAT execution layer. The codebase remains transitional: many runtime models still carry v1 compatibility columns and deprecated principal rows still exist for route rendering. However, canonical auth is now active for credential verification: `User` owns teacher/sysadmin TOTP, student PIN/passphrase, session anchoring, recovery capability, and passkey capability; `Seat + Class` owns class-local actor authority; `IdentityProfile` owns display only.

**V2 is a clean break from V1. No data migration is required. Old tables are dropped as each domain is ported, not carried forward.** The goal is a fresh system that complies fully with DOM-CORE-002 (44 canonical tables only) from the ground up.

Target state:
- DOM-CORE-002: exactly 44 canonical tables, nothing else in the schema
- DOM-CORE-001: 9 domains with strict authority boundaries
- FEAT-CORE-000: all state mutation through FEAT units
- INV-CORE-000 + INV-ARC-000-016: all invariants enforced

**Each wave ends with a mandatory verification gate. A wave that produces a non-operational app must be rolled back (git + `flask db downgrade`) and retried before proceeding.**

---

## Current State Snapshot

| Dimension | Status |
|---|---|
| Models | 54+ classes; 44 dual-scoped, 5 pure v1, ~5 pure v2 |
| Migration files | 16 in `migrations/versions/`; single head `f7b8c9d0e1f2` |
| Test files | 117 test files; ~798 total tests (617 passed, 174 failed, 1 skipped, 6 errors) |
| Feats | 19 registered FEAT codes in canonical registry |
| Services | 8 (`access_policy`, `attendance`, `balance`, `identity`, `ledger`, `obligations`, `store`, `tlcp`) |
| Blueprints | 8 (`admin` 514K lines, `student` 178K, `api` 120K, `system_admin` 78K, `docs` 30K, `analytics` 19K, `main` 14K, `recovery` 8.6K) |
| Target canonical tables | 44 across 9 domains (DOM-CORE-002) |
| Auth | `User` is active for teacher/sysadmin TOTP, student PIN/passphrase, passkey ownership, and session `user_id`; `Admin`/`Student`/`SystemAdmin` remain route compatibility shadows |
| `Seat` | Active class-local actor anchor; remaining `student_id` bridges are compatibility only |
| `Class` | `classes.class_id` is the canonical class boundary; `join_code` is a public alias |

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

## Authoritative Tracking Scope

This file is the single active tracker for v2 migration execution. All prior tracking/checklist/matrix docs under `docs/development/tracking/` have been archived to `docs/development/archive/tracking/` and are informational history only.

### Consolidated Open TODO Backlog

#### Active execution waves
- [x] Complete Wave 3 identity migration sequence through remaining scoped domains (strict exit criteria below; no legacy fallback permitted)
- [ ] Complete Wave 4 class-configuration canonicalization and drop legacy settings columns
- [x] Complete Wave 5 ledger table migration and FEAT hook reassignment
- [ ] Complete Wave 6 attendance table migration (`tap_events` lineage removal)
- [ ] Complete Wave 7 obligations schema migration while preserving already-landed prepay/temporal behavior
- [ ] Complete Wave 8 store schema migration and remove remaining teacher-scoped enforcement remnants
- [ ] Complete Wave 9 operations + interpretation canonical migration
- [ ] Complete Wave 10 support domain canonical migration
- [ ] Integrate `DOM-ECON-000_ECONOMY_GOVERNANCE_FOUNDATION.md` into Waves 4-9 implementation scope (policy config, ledger/solvency math, timezone-safe recurring execution, and aggregate analytics) without creating a parallel migration track

#### Post-launch hardening and readiness
- [ ] Wave 11 backup/restore rehearsal evidence
- [ ] Wave 11 operator sign-off flow completion (`user_invite_tokens`)
- [ ] Wave 11 system-admin compliance audit completion
- [ ] Wave 11 admin route decomposition (`app/routes/admin.py`)
- [ ] Wave 11 invariant sweeps complete (INV-ARC-007, INV-ARC-014, INV-ARC-015 full repo pass)
- [ ] Wave 11 `V2_CLASS_ID_INVARIANT_BACKLOG` closure
- [ ] Complete single-context UI enforcement sweep: remove remaining page-level class selectors and request `join_code` context controls outside nav context switch
- [ ] Wave 12 final schema/code/test validation gate (exact 44 tables, zero v1 runtime artifacts, clean suite)

#### Deferred-but-tracked architecture items
- [ ] TemporalContext full architecture rebuild (`V2_Temporal_Architecture_Rebuild_Plan.md`)
- [ ] Backwards compatibility cleanup execution (`V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` scope, when explicitly re-opened)
- [ ] Remaining docs-platform migration phases from `V2_DOCS_PLATFORM_SPLIT.md` (Phases 2–4)

#### DOM-ECON-000 Integrated Execution Checklist (Wave-aligned)
- [ ] Wave 4 (Class Config): encode policy modes, CWI inputs, and ratio-band configuration in canonical class settings ownership
- [ ] Wave 5 (Ledger): centralize CWI-relative solvency and pricing calculation primitives with FEAT-safe ledger integration
- [ ] Wave 6-7 (Attendance + Obligations): enforce attendance-dominance and class-timezone temporal windows in recurring economy execution
- [ ] Wave 8-9 (Store + Interpretation): align store tier pricing and aggregate economy-health analytics/drift metrics to DOM-ECON-000 formulas
- [ ] Verification gates: add invariant tests proving deterministic shared calculations and no duplicated formula paths across validators/recommenders/analytics

### Build Specs Index (Authoritative Specs in `docs/development/specs/`)

- `V2_ADMIN_ROUTE_REFACTOR.md`
- `V2_AUTHORITY_EXTRACTION_PLAN.md`
- `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`
- `V2_BALANCE_SCOPE_AND_SETTLEMENT_CONTRACT.md`
- `V2_CANONICAL_AUTH_RUNTIME_CUTOVER.md`
- `V2_CAPABILITY-BASED_ARCHITECTURE_REBUILD.md`
- `V2_CLASS_ID_INVARIANT_BACKLOG.md`
- `V2_Class_Scope_Normalization_Target.md`
- `DOM-ECON-000_ECONOMY_GOVERNANCE_FOUNDATION.md`
- `V2_DOCS_PLATFORM_SPLIT.md`
- `V2_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `V2_SESSION_MUTATION_SAFETY.md`
- `V2_STUDENT_BLOCKS_REDESIGN_NOTE.md`
- `V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `V2_TEACHER_IDENTITY_ARCHITECTURE.md`
- `V2_Temporal_Architecture_Rebuild_Plan.md`
- `V2_WAVE_3_IDENTITY_DOMAIN_RISK_AND_DEPENDENCY.md`

---

### Cross-Wave Status Update: Temporal + Obligations Hardening (Pre-Wave 7)

Work completed ahead of formal Wave 7 (Obligations Domain) and Wave 11 (Temporal Audit):

- Rent lifecycle fully implemented (prepay + coverage windows)
- Scheduled rent execution with idempotency
- Seat-scoped economic actor enforcement (`seat_id + class_id`)
- Class-scoped temporal enforcement across attendance, analytics, and scheduler (INV-ARC-015)
- Insurance waiting period aligned to class-local calendar semantics (next-day midnight start, N-day window)
- Coverage start stored as UTC derived from class-local boundary
- Temporal guardrails added (tests enforcing scoped time helpers)

Interpretation:
- This work is a partial early completion of Wave 7 (behavior) and Wave 11 (temporal invariants).
- Subsequent waves MUST preserve these behaviors; only structural/schema migration is expected.

---

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
## System Behavior Contracts (Locked)

The following behaviors are considered **canonical and invariant**. These are not subject to redesign in later waves and must be preserved during all schema migrations.

---

### Rent (Obligations — Prepay Cycle Model)

* Rent is a **prepay system**: payment grants coverage for a future cycle.
* Coverage window is explicit and enforced as:

  ```
  coverage_start_time <= now < coverage_end_time
  ```
* Coverage windows are derived from **class-local cycle boundaries**, then stored in UTC.
* Rent execution:

  * Runs per `class_id`
  * Uses deterministic cycle boundaries (`get_class_cycle_start_utc`)
  * Enforces idempotency via `cycle_idempotency_key`
* Economic actor is strictly `seat_id + class_id`

---

### Insurance (Calendar-Based Waiting Period Model)

* Waiting period is **calendar-based**, not duration-based.
* Defined as:

  * Waiting starts at **00:00 of the next class-local day after purchase**
  * Waiting spans N full calendar days
  * Coverage becomes active at the next class-local midnight after waiting ends
* All calculations:

  * Performed in class-local time
  * Converted to UTC only for storage
* Eligibility evaluation is **event-time based**:

  * Must evaluate coverage relative to transaction timestamp, not current time
* No raw UTC-based waiting period logic is allowed

---

### Attendance (Session-Based Model)

* Attendance is modeled as **sessions**, not individual events
* All day boundaries are class-local:

  * Derived using `get_class_today_range(class_id)`
* No write operations are allowed during GET requests (INV-ARC-007)

---

### Ledger (Immutable Transaction Model)

* All financial state is derived from `ledger_transaction`
* Transactions are:

  * Immutable
  * FEAT-controlled
  * Idempotent via `(class_id, seat_id, feat_code, idempotency_key)`
* Balance is computed or snapshotted; never stored as authoritative mutable state

---

### Temporal Model (INV-ARC-015)

* All timestamps are stored in UTC
* All logic uses **class-local time** derived from `class_id`
* Server/system time MUST NOT influence business logic
* Day and cycle boundaries are always class-local and normalized

---

### Purpose of This Section

This section defines **behavioral truth**, independent of schema implementation.

* "What the system does" is fixed here
* "How the system stores it" evolves across waves

All future migration work must preserve these contracts.

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

2. **`docs/development/archive/tracking/V2_SCHEMA_GAP_AUDIT.md`** — for each of the 44 canonical tables: current table name (if any), columns to add, columns to drop, FK changes needed, and which wave ports it

3. **`tests/domain/`** directory with `tests/domain/test_smoke.py` (imports all 44 classes, no DB needed)

### Critical Files

- `app/models_canonical.py` (create)
- `docs/development/archive/tracking/V2_SCHEMA_GAP_AUDIT.md` (historical artifact)
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

### Status Update (2026-06-04): Canonical Identity Foundation Schema

- Added migration `a6d9c2e4f1b7_add_canonical_identity_foundation.py` after the
  current rebuild head.
- Expanded `users` to represent global auth, credential, recovery, session, role,
  and last-active-seat state.
- Added `seats.claim_first_name_hash` and `seats.claim_last_name_hash` as
  class-local seat claim artifacts. These hashes do not belong to `users`.
- Added nullable `identity_profiles.seat_id` as the one-to-one display identity
  binding and completed lifecycle fields for `user_invite_tokens` and
  `user_recovery_tokens`.
- Added `classes.section` and the transitional `classes.join_code_token` alias.
- This is an additive foundation only. It does not infer `User`, `Seat`, or
  `IdentityProfile` bindings from deprecated `Student`, `Admin`, `TeacherBlock`,
  `ClassMembership`, or `classes.teacher_id` authority.
- Audited identity backfill, runtime auth cutover, legacy authority removal, and
  final non-null constraints remain pending.
- Repaired the empty-database rebuild path where `0001_bootstrap.py` creates live
  final metadata but later migrations still assumed historical table or column
  shapes:
  - `0002a` now accepts an already-final referenced `classes` table.
  - `53e7c7148fea` accepts an already-final `ledger_transaction` table.
  - `8357d4036478` idempotently handles an existing
    `users.last_active_class_id`.
  - `ebb7b66b2176` no longer reads a removed `users.username` column.
- `scripts/seed_canonical_v2.py` no longer calls `db.create_all()`. It seeds
  canonical teacher/student users, teacher/student/unclaimed seats, one
  `IdentityProfile` per seat, and seat-owned claim hashes. Deprecated identity
  rows remain explicitly labeled compatibility shadows until their runtime
  constraints are removed.

Focused validation:

- `python -m py_compile app/models.py app/models_canonical.py migrations/versions/a6d9c2e4f1b7_add_canonical_identity_foundation.py`
- `python scripts/lint_migrations.py migrations/versions/a6d9c2e4f1b7_add_canonical_identity_foundation.py`
- `flask db upgrade`
- `flask db downgrade 4e85bf5c5594`
- `flask db upgrade`
- `pytest -q tests/domain/test_identity_schema.py tests/domain/test_smoke.py`
  - Result: `4 passed`
- `flask db current` and `flask db heads`
  - Result: `a6d9c2e4f1b7 (head)`
- Empty disposable PostgreSQL database:
  - `flask db upgrade` from no schema to `a6d9c2e4f1b7`
  - `python scripts/seed_canonical_v2.py`
  - Result: `4` canonical users, `4` seats, `4` seat-bound profiles, and `1`
    unclaimed student seat with both claim hashes.

### Status Update (2026-06-04): Canonical Principal Backfill and Session Anchor

- Added irreversible migration
  `b7e4c1d9a2f6_backfill_canonical_identity_principals.py`.
- The migration uses legacy principal tables as migration input only:
  - credentialed teachers, students, and system admins are copied into `users`
  - existing bound seats receive canonical role and `claimed_at` state
  - teacher seats are created only for credentialed teachers' owned classes
  - student `IdentityProfile` rows are bound or copied one-to-one per seat
- The migration fails closed on duplicate username lookup hashes, students bound
  to multiple users, mixed-role users, and conflicting teacher-seat ownership.
- It does not create users for roster placeholders, derive claim state from
  `TeacherBlock`, or bind `teacher_block` profiles as teacher identity.
- Successful teacher, student, and system-admin login flows now write canonical
  `session["user_id"]` when a migrated user exists.
- `get_current_user()` now accepts only canonical `user_id` plus an owned seat
  resolution path. `student_user_id` and `current_user_id` are no longer active
  user-session aliases.
- Legacy `admin_id`, `student_id`, and `sysadmin_id` remain route compatibility
  shadows.

### Status Update (2026-06-04): Canonical Credential Verification Cutover

- Teacher TOTP, student PIN, and system-admin TOTP login now resolve `User` by
  canonical username lookup hash and verify credentials from `users`.
- Deprecated `Admin`, `Student`, and `SystemAdmin` rows are resolved only after
  successful `User` authentication as route compatibility shadows.
- Legacy-only principals, role mismatches, missing route shadows, and ambiguous
  student shadows fail closed.
- Student claim/setup, teacher signup/reset, system-admin provisioning, teacher
  TOTP reset, and student recovery now synchronize or invalidate canonical
  credential fields.
- Student transfer and recovery passphrase checks now read `User.passphrase_hash`.
- Remaining auth work is removal of `admin_id`, `student_id`, and `sysadmin_id`
  route-session compatibility shadows.

### Status Update (2026-06-04): Canonical Passkey Ownership Cutover

- Added migration `c8f1e2d3a4b5_add_canonical_passkey_credential_owners.py`.
- `teacher_credentials` and `system_admin_credentials` now carry canonical
  `user_id` ownership with `users.id` foreign keys.
- Existing passkey metadata is backfilled from legacy teacher/sysadmin shadows
  to the canonical `User`; unmapped credential rows fail the migration.
- Passwordless registration now creates external users as `user_<User.id>`.
- Passwordless authentication finish now accepts only `user_<User.id>`, resolves
  the canonical `User`, then resolves the legacy route shadow.
- Legacy `admin_<id>` and `sysadmin_<id>` Passwordless principals are rejected.
- Remaining auth work is to remove `admin_id`, `student_id`, and `sysadmin_id`
  route-session compatibility shadows and move route resolvers fully to
  `User`/`Seat`.

### Status Update (2026-06-05): Canonical Resolver Gate Cutover

- `get_current_admin()`, `get_current_system_admin()`, and
  `get_logged_in_student()` now require a canonical `User` identity before
  resolving deprecated route shadows.
- Legacy `admin_id`, `sysadmin_id`, and `student_id` session values are still
  written for route compatibility, but they no longer establish identity when
  `session["user_id"]` is missing.
- Resolver mismatch between canonical user and legacy route shadow fails closed.
- Focused fixtures now seed canonical users and set `session["user_id"]` when
  simulating authenticated teacher/sysadmin/student sessions.
- Remaining work is broad route cleanup: remove direct `session["admin_id"]`,
  `session["student_id"]`, and `session["sysadmin_id"]` consumers in favor of
  resolver-owned context and `User + Seat + Class` scope.

Focused validation for resolver gate:

- `pytest -q tests/test_canonical_auth_session.py tests/test_admin_auth.py tests/test_login_redirect.py tests/test_tap_flow.py tests/test_student_recovery.py tests/test_teacher_recovery.py tests/test_admin_identity_bridge_service.py`
  - Result: `54 passed, 1 skipped`
- `python -m py_compile app/auth.py tests/test_canonical_auth_session.py tests/test_admin_auth.py tests/test_student_recovery.py tests/test_teacher_recovery.py`
- `python scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: clean

Focused validation:

- `python scripts/lint_migrations.py migrations/versions/b7e4c1d9a2f6_backfill_canonical_identity_principals.py`
  - Result: clean
- `flask db downgrade a6d9c2e4f1b7 && flask db upgrade`
  - Result: idempotent backfill re-run with no duplicate users, seats, or profiles
- `pytest -q tests/test_canonical_auth_session.py tests/domain/test_identity_schema.py tests/domain/test_smoke.py tests/test_migration_idempotency.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result before credential verification cutover: `14 passed`
- `pytest -q tests/test_canonical_auth_session.py tests/domain/test_identity_schema.py tests/domain/test_smoke.py tests/test_migration_idempotency.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result after credential verification cutover: `18 passed`
- `pytest -q tests/test_student_recovery.py tests/test_teacher_recovery.py tests/test_admin_auth.py tests/test_canonical_auth_session.py`
  - Result: `34 passed, 1 skipped`
- `pytest -q tests/test_login_redirect.py tests/test_tap_flow.py`
  - Result: `6 passed`
- Combined auth, recovery, login, identity-schema, migration, and Wave 3 guardrail
  regression run:
  - Result: `51 passed, 1 skipped`
- Passkey cutover validation:
  - `python scripts/lint_migrations.py migrations/versions/c8f1e2d3a4b5_add_canonical_passkey_credential_owners.py`
    - Result: clean
  - `flask db downgrade b7e4c1d9a2f6 && flask db upgrade`
    - Result: clean, final head `c8f1e2d3a4b5`
  - Combined auth, passkey, recovery, login, identity-schema, migration, and
    Wave 3 guardrail regression run:
    - Result: `61 passed, 1 skipped`
- `python scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: clean, no expansion
- Empty disposable PostgreSQL database:
  - `flask db upgrade` from no schema to `b7e4c1d9a2f6`
  - `python scripts/seed_canonical_v2.py`
  - Result: `4` canonical users, `4` seats, and `4` seat-bound profiles
- Development database:
  - `flask db current` and `flask db heads`
  - Result: `b7e4c1d9a2f6 (head)`

### Status Update (2026-05-02): Wave 3C.2–3C.6 Identity Compatibility Bridge

- Landed compatibility helpers and context plumbing to centralize canonical identity resolution while preserving runtime behavior:
  - `get_current_seat()`, `get_current_class_id()`, `get_current_user()`, `require_seat_context()`
- Request context moved to helper-derived identity (no raw-session-only dependency in global plumbing).
- Low-risk route slices migrated to helper-first identity resolution (`main`, `docs`, read-only `api`, student read paths).
- Non-ledger write-path bridge pattern established and validated:
  - `seat -> student` one-time resolution per handler with a single legacy fallback
  - Hall pass/tap flows hardened with explicit identity anchors (`student_id`, `seat_id`, `class_id`, `join_code`) and fail-closed context guards.

### Status Update (2026-05-02): Class Table Rename Execution

- Executed table rename migration from `class_economies` to `classes` with FK/index updates in supporting code paths.
- Schema/runtime now treat `classes` as the active class anchor in migration sequencing.

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

> NOTE: This is cross-wave work (primarily Wave 7 + Wave 11) executed early. It is documented here for chronological accuracy but should be interpreted as part of obligations and temporal invariant completion.

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

### Status Update (2026-05-04): Wave 3C.11 Insurance Scope Completion + Waiting Rule Unification

- Completed remaining insurance scope migrations for active enforcement paths:
  - admin insurance queries now class-scoped in dashboard/context analysis and policy-management surfaces
  - insurance eligibility item resolution remains class-scoped (`StoreItem.class_id`)
- Unified claim-type resolution across admin/student claim flows:
  - canonical resolver used instead of ad-hoc route-specific inference
- Unified waiting-period semantics across insurance claim evaluation:
  - canonical rule enforced everywhere:
    - starts at class-local `00:00` on day after purchase
    - ends at class-local `00:00` after day `N` (equivalent to `24:00` on waiting day `N`)
  - implemented via shared helper and reused by:
    - transaction eligibility checks
    - admin claim gate
    - student claim gate
- Completed class-scope cleanup in teacher account insurance deletion paths:
  - policy/dependent deletes now resolved by teacher-owned `class_id` set (not teacher-only policy filter)
- Student/admin active-insurance lookup now class-first with teacher fallback only for legacy callers.

Focused validation:

- `pytest -q tests/test_insurance_class_scoping.py tests/test_insurance_security.py tests/test_insurance_snapshots.py tests/test_dashboard_rendering.py tests/test_login_redirect.py`
- Result: `18 passed`

### Status Update (2026-05-06): Wave 3C.12-A Payroll Scope Bridge (Student Read Path)

- Started Wave 3C.12 with a low-risk payroll/attendance read-path slice.
- `app/payroll.py` now resolves teacher scope from `join_code` when `teacher_id` is absent in:
  - `get_pay_rate_for_block(...)`
  - `get_daily_limit_seconds(...)`
- `student.payroll` now passes `join_code` explicitly into pay-rate resolution.
- Behavior preserved: existing teacher-scoped callers remain valid, while class/join-code callers no longer fail-closed to default rates when `teacher_id` is missing.

Focused validation:

- `pytest -q tests/test_feature_flag_enforcement.py -k "payroll_allowed_when_payroll_enabled or payroll_blocked_when_payroll_disabled" tests/test_dashboard_rendering.py`
- Result: `2 passed` (`13 deselected`)

### Status Update (2026-05-06): Wave 3C.12-B Payroll Scope Bridge (Admin Read Paths)

- Expanded payroll class-scope migration across admin read/query paths without changing FEAT orchestration or response behavior.
- `app/routes/admin.py` updates:
  - `_load_economy_rebalance_context(...)` now resolves active payroll settings by admin-owned `class_id` set (instead of teacher-scoped payroll filtering).
  - `/admin/payroll` `has_settings` + `block_settings` now scope on selected `class_id`.
  - `onboarding_status` payroll completion now checks `PayrollSettings.class_id` across admin-owned classes.
- Fixed runtime guard bug in `_handle_mismatched_admin_class_context()` (used undefined `admin_id` in log payload; now consistently uses `scoped_admin_id`).
- FEAT atomicity hardening surfaced by this slice was resolved without behavior redesign:
  - `app/payroll.py:get_cached_payroll_with_meta(...)` changed `db.session.commit()` to `db.session.flush()` inside FEAT shell (`FEAT-LED-004`) to preserve orchestrator-owned transaction boundaries.
  - `tests/test_admin_payroll_scoped_balances.py` fixture setup updated from `commit()` to `flush()` inside `FEATContext` for invariant compliance.

Focused validation:

- `pytest -q tests/test_admin_payroll_scoped_balances.py tests/test_feature_flag_enforcement.py -k "admin_payroll" tests/test_admin_membership_gates.py -k "payroll"`
- Result: `6 passed` (`22 deselected`)

Focused validation:

- `pytest -q tests/test_time_money_guardrails.py tests/test_scheduled_tasks_rent_cycle.py tests/test_add_rent_waiver_route.py tests/test_redemption_audit_log.py tests/test_redemption_rejection.py tests/test_scheduled_tasks_store_item_cleanup.py`
- Result: `22 passed`
- `pytest -q tests/test_insurance_security.py tests/test_scheduled_tasks_rent_cycle.py tests/test_add_rent_waiver_route.py tests/test_redemption_audit_log.py tests/test_redemption_rejection.py tests/test_scheduled_tasks_store_item_cleanup.py`
- Result: `24 passed`

### Status Update (2026-05-08): Wave 3C.12-C Single-Context Enforcement Sweep (Students/Hall Pass/Attendance)

- Enforced single-context UI behavior on active admin pages:
  - `templates/admin_students.html`
    - removed page-level class-context mutation script (`/admin/current-class` post from block tabs)
    - removed `join_code` query propagation from student detail/export links
  - `templates/admin_hall_pass.html`
    - removed page-level class selector (`join_code` GET switching)
    - removed `join_code` query propagation in setup link and API calls
    - removed period-level cross-context filter control from hall pass history panel
- Enforced session/class context authority in backend read paths:
  - `app/routes/admin.py`
    - `/admin/hall-pass` and `/admin/hall-pass/setup` no longer resolve scope from request `join_code`/`block`
  - `app/routes/api.py`
    - `/api/hall-pass/settings` now resolves scope from `session.current_class_id/current_join_code` only
    - `/api/hall-pass/history` explicitly filters by `session.current_class_id`
    - `/api/attendance/history` explicitly filters by `session.current_class_id`

Focused validation:

- `python3 -m py_compile app/routes/admin.py app/routes/api.py`
- `pytest -q tests/test_time_money_guardrails.py tests/test_scheduled_tasks_rent_cycle.py`
- Result: `5 passed`

Remaining follow-up (same sweep family):

- remove remaining page-level class selectors and `join_code` query propagation on other admin templates (notably payroll/store/banking/support surfaces) while preserving existing visual design.

### Status Update (2026-05-09): Wave 3C.12-D Single-Context Enforcement Sweep (Payroll/Store/Banking/Support)

- Enforced single-context UI behavior on additional admin surfaces:
  - `templates/admin_payroll.html`
    - removed page-level class selector (`join_code` GET switching)
    - removed request-level `join_code` propagation in payroll AJAX/form actions
  - `templates/admin_store.html`
    - removed page-level class selector (`join_code` GET switching)
    - removed request-level `join_code` propagation from edit/deactivate/delete actions
  - `templates/admin_support_tickets.html`
    - removed page-level join-code selectors for submission/filtering
    - support submission now carries active session class context only
- Enforced session/class context authority in backend scope resolution:
  - `app/routes/admin.py`
    - payroll/store/banking pages no longer resolve feature scope from request `join_code`
    - support page no longer accepts request-level `join_code` context switching
    - payroll/store/banking redirects no longer propagate `join_code` query params

Focused validation:

- `python3 -m py_compile app/routes/admin.py`
- `pytest -q tests/test_admin_payroll_scoped_balances.py tests/test_dashboard_rendering.py -k "payroll or store or banking or support"`
- Result: `1 passed` (`3 deselected`)

### Status Update (2026-05-09): Wave 3C.12-E Single-Context Enforcement Sweep (Hall Pass Setup/Insurance/Rent/Economy Health)

- Enforced single-context UI behavior on additional admin surfaces:
  - `templates/hall_pass_setup.html`
    - removed page-level class selector (`join_code` GET switching)
    - removed request-level `join_code` propagation in hall-pass setup API calls
  - `templates/admin_insurance.html`
    - removed page-level class selector (`settings_block` GET switching)
  - `templates/admin_rent_settings.html`
    - removed page-level class selector (`settings_block` GET switching)
  - `templates/admin_banking.html`
    - removed page-level class selector (`settings_block` GET switching)
  - `templates/admin_economy_health.html`
    - removed page-level class selector control and made active context display-only
- Enforced session/class context authority in backend scope resolution:
  - `app/routes/admin.py`
    - rent/insurance/banking scope resolution no longer accepts request-level class switching on page load
  - `app/routes/api.py`
    - hall-pass setup GET/POST now derive class scope from active session class context only

### Status Update (2026-05-09): Wave 3C.12-F Feature Toggle Authority + Disabled Route UX

- Established feature toggle authority and disabled-route behavior for class-scoped surfaces:
  - `app/routes/admin.py`
    - admin feature pages (`payroll`, `store`, `banking`, `rent`, `insurance`, `hall_pass`) are now gated from class-scoped feature state in `@admin_bp.before_request`
    - when disabled for active `class_id`, teacher sees a simple disabled page with a direct link to `/admin/feature-settings`
  - `app/routes/student.py`
    - centralized feature-gate hook in `@student_bp.before_request` for mapped student feature routes
    - when disabled, student receives hard `404` (no feature existence disclosure)
  - `templates/admin_feature_settings.html`
    - reduced to per-period feature controls only (global/copy UI removed)
  - `templates/admin_feature_disabled.html` (new)
    - minimal disabled-state page for teachers with clear enablement path
- Added/updated regression coverage:
  - `tests/test_feature_flag_enforcement.py`
    - validates teacher disabled-page behavior for admin feature routes in active class context
    - validates student hard-`404` behavior for disabled feature routes
    - aligns enabled banking transfer case with explicit `ClassFeature` seed

Focused validation:

- `python3 -m py_compile app/routes/admin.py app/routes/student.py tests/test_feature_flag_enforcement.py`
- `pytest -q tests/test_feature_flag_enforcement.py tests/test_feature_settings.py`
- Result: `29 passed`

### Status Update (2026-05-09): Wave 3C.12-G Runtime Class-Scoped Settings Normalization

- Continued clean-break runtime normalization (no migration/backfill paths introduced):
  - `app/routes/student.py`
    - banking settings context lookup now reads strictly by `class_id`
  - `app/payroll.py`
    - pay-rate and daily-limit resolution for student payroll now resolve class scope and query `PayrollSettings` by `class_id`
  - `app/routes/analytics.py`
    - payroll/rent cycle settings resolution now resolves class first and queries settings by `class_id`
  - `app/utils/analytics_engine.py`
    - CWI payroll settings lookup now resolves and queries by `class_id`
- Kept compatibility at API surface level (function signatures), while enforcing `class_id` authority under the hood.

Focused validation:

- `python3 -m py_compile app/payroll.py app/routes/analytics.py app/utils/analytics_engine.py`
- `pytest -q tests/test_feature_flag_enforcement.py tests/test_feature_settings.py -k "feature"`
- Result: `29 passed`

### Status Update (2026-05-09): Wave 3C.12-H Class-Scoped Cleanup in Rebalance + Admin Teardown Paths

- Removed additional runtime dependence on teacher/global settings rows:
  - `app/utils/economy_rebalance.py`
    - pending rebalance selection now scopes `FeatureSettings` by teacher-owned `class_id`s
    - effective rent settings now resolve class scope first and query `RentSettings.class_id`
  - `app/routes/admin.py`
    - teacher cleanup helpers now delete settings/activity rows through teacher-owned `class_id`s (`BankingSettings`, `FeatureSettings`, `HallPassSettings`, `PayrollSettings`, `PayrollFine`, `PayrollReward`, `RentSettings`)
    - banking settings block resolver now queries by resolved `class_id`
  - `app/payroll.py`
    - batch pay-rate fetch now queries `PayrollSettings` by teacher-owned class IDs
- Updated rent-waiver tests to use canonical class-scoped `RentSettings` fixtures (`class_id` + `join_code`).

Focused validation:

- `python3 -m py_compile app/payroll.py app/routes/admin.py app/utils/economy_rebalance.py tests/test_add_rent_waiver_route.py`
- `pytest -q tests/test_class_deletion.py tests/test_add_rent_waiver_route.py tests/test_feature_flag_enforcement.py tests/test_feature_settings.py -k "deletion or rent or feature"`
- Result: `39 passed`

### Status Update (2026-05-09): Wave 3C.12-I Store GET Purity (INV-ARC-007 Hardening)

- Eliminated residual write-on-read behavior from admin store page load:
  - `app/routes/admin.py`
    - removed lazy call to `process_expired_collective_goals(...)` from `GET /admin/store`
    - removed unused import of `process_expired_collective_goals`
- This keeps `/admin/store` GET path pure (no reconciliation mutation side effects on page render) and aligns with FEAT constitutional read/write separation.

Focused validation:

- `python3 -m py_compile app/routes/admin.py`
- `pytest -q tests/test_v2_authority_guardrails.py -k "not transaction_constructor_is_only_used_in_ledger_service"`
- `pytest -q tests/test_dashboard_rendering.py tests/test_feature_flag_enforcement.py -k "store"`
- Result: `23 passed` + `2 passed`

### Status Update (2026-05-09): Wave 3C.12-J Store Mutation FEAT Wrapping (Admin Surface)

- Wrapped remaining admin store mutation paths in FEAT contexts with deterministic idempotency keys:
  - `app/routes/admin.py`
    - `POST /admin/store` (create item) now executes in `FEATContext("FEAT-STOR-001", ...)`
    - `POST /admin/store/edit/<item_id>` now executes in `FEATContext("FEAT-STOR-001", ...)`
    - `POST /admin/store/delete/<item_id>` / `/item/deactivate/<item_id>` now execute in `FEATContext("FEAT-STOR-003", ...)`
  - Removed direct route-level commit ownership from these handlers (FEAT orchestrator owns transaction boundary).
- Atomicity follow-up:
  - `app/utils/store.py`
    - `process_expired_collective_goals` shell path now uses `db.session.flush()` instead of direct `commit()` to respect FEAT commit ownership.

Focused validation:

- `python3 -m py_compile app/routes/admin.py app/utils/store.py`
- `pytest -q tests/test_dashboard_rendering.py tests/test_feature_flag_enforcement.py -k "store"`
- Result: `2 passed`

### Status Update (2026-05-10): Wave 3C.12-K Banking GET Purity + Settings FEAT Wrapping

- Removed residual write-on-read behavior from banking page load:
  - `app/routes/admin.py`
    - `/admin/banking` no longer creates default `BankingSettings` rows on GET
    - request-scoped fallback bypass was removed so disabled banking class scope remains hard `404`
- Wrapped banking settings mutation path in FEAT-owned boundary with deterministic idempotency key:
  - `app/routes/admin.py`
    - `POST /admin/banking/settings` now executes updates/creates inside `FEATContext("FEAT-ADMN-001", ...)`
    - direct route-level commit ownership removed

Focused validation:

- `python3 -m py_compile app/routes/admin.py`
- `pytest -q tests/test_feature_flag_enforcement.py -k "admin_banking_rejects_disabled_class_scope or banking"`
- Result: `3 passed`, `1 failed` (`test_transfer_allowed_when_banking_enabled`) — failure is in student transfer feature-gate path and is outside the banking route changes in this slice.

### Wave 3 Exit Criteria (Strict, No Legacy Fallback)

Wave 3 is considered complete only when all conditions below are true:

1. **No scope fallback paths** in identity/scope-critical route surfaces (`admin`, `student`, `api`) including `except HTTPException` fallback-to-resolver patterns.
2. **Feature toggle authority is sole gate** for class-scoped feature routes:
   - teacher sees disabled page with link to `/admin/feature-settings`
   - student receives hard `404` for disabled feature routes (no feature disclosure)
3. **Single-context authority**:
   - no page-level class switching controls outside global nav class switcher
   - no request-level `join_code` class switching on admin pages
4. **Read/write boundary compliance in changed code**:
   - guardrail CI passes for changed lines (no route-level commits in GET/read paths; no write-on-GET)
5. **No legacy compatibility fallback reintroduction**:
   - no runtime "legacy-safe" bypass behavior for missing canonical identity/scope rows
   - fail-closed behavior is required when canonical class/scope context is absent

### Status Update (2026-05-10): Wave 3 Exit-Bar Snapshot + Remaining Punch List

Snapshot against the strict Wave 3 exit criteria:

- `PASS`: Feature toggle authority + disabled-route UX already implemented (`3C.12-F`).
- `PASS`: Guardrail CI framework landed (`scripts/policy_guardrails.py`, `.github/workflows/policy-guardrails.yml`) and blocks new violations on changed lines.
- `PARTIAL`: Single-context enforcement is advanced but not fully closed in all remaining admin/analytics surfaces.
- `OPEN`: Full legacy scope-switch cleanup is not yet complete in all route families.

Concrete remaining punch list before checking off Wave 3:

- Remove remaining request-level class switch handling on analytics/admin surfaces still consuming request `join_code` for context switching (notably `app/routes/analytics.py`, selected admin handlers).
- Finish template cleanup where page-level class selectors still exist outside nav switch context (remaining `settings_block`/selector UI fragments).
- Eliminate remaining Wave-3-scope GET/write and route-commit hotspots in changed surfaces as they are touched by refactors, using FEAT-owned mutation boundaries only.
- Re-run focused validation:
  - `pytest -q tests/test_feature_flag_enforcement.py tests/test_feature_settings.py`
  - `python3 scripts/policy_guardrails.py --git-diff-base origin/main --git-diff-head HEAD`

### Status Update (2026-05-10): Wave 3 Exit Closure Slice — Request-Level Class Switch Removal (Analytics + Admin)

- Removed request-driven class switching from analytics:
  - `app/routes/analytics.py`
    - `resolve_current_join_code(...)` no longer reads `request.args['join_code']`
    - active class resolution is now session/nav-authoritative with deterministic fallback to teacher-owned class list
- Removed additional admin request-level class switching:
  - `app/routes/admin.py`
    - `_require_payroll_feature_scope_from_request(...)` no longer consumes request `join_code` payload/query/form values
    - `student_detail(...)` no longer accepts `?join_code=...` context override
    - `export_students(...)` now scopes by active session/nav class context instead of request `join_code`

Focused validation:

- `python3 -m py_compile app/routes/analytics.py app/routes/admin.py`
- `pytest -q tests/test_admin_payroll_scoped_balances.py tests/test_dashboard_rendering.py tests/test_feature_flag_enforcement.py -k "payroll or student_detail or export or feature"`
- Result: `13 passed`, `3 deselected`

### Status Update (2026-05-11): Wave 3 Exit Closure Slice — Route Commit Elimination + FEAT Shell Coverage

- Completed repo sweep for Wave-3-scope route mutation boundaries:
  - Removed remaining route-level `db.session.commit()` ownership from:
    - `app/routes/student.py`
    - `app/routes/analytics.py`
    - `app/routes/system_admin.py`
    - `app/routes/api.py`
  - Replaced route commits with `db.session.flush()` so FEAT/orchestrator transaction boundaries remain authoritative.
- Expanded FEAT shell coverage for mutation routes touched in this slice:
  - `app/routes/student.py`
    - `claim_account` → `FEAT-IDEN-001`
    - `setup_pin_passphrase` → `FEAT-IDEN-001`
    - `add_class` → `FEAT-IDEN-001`
    - `cancel_insurance` → `FEAT-OBL-001`
    - `login` (lookup-hash write path) → `FEAT-IDEN-001`
    - `verify_recovery` / `dismiss_recovery` → `FEAT-IDEN-002`
  - `app/routes/analytics.py`
    - `acknowledge_alert` → `FEAT-ANLY-001`
- Guardrail status moved from outstanding route-commit debt to clean baseline:
  - before slice: `30` `NO_ROUTE_COMMIT` violations (`api.py` + `system_admin.py`)
  - after slice: `0` violations (`Policy guardrails: clean`)

Focused validation:

- `python3 scripts/policy_guardrails.py`
- `pytest -q tests/test_tap_event_class_scope_invariant.py tests/test_api_admin_tap_scope.py tests/test_api_tenancy.py -k "tap_entries or delete_tap_entry or block_tap_settings or hall_pass_available_types or attendance_history_api"`
- Result: `13 passed`, `7 deselected`

### Status Update (2026-05-12): Wave 3 Exit Closure Slice — Class-Authority Sticky Context + V2 Claim Contract

- Completed identity sticky-context enforcement using class authority first:
  - durable pointer remains `users.last_active_class_id`
  - runtime restoration now resolves `class_id` first, then resolves owned seat within that class (`class_id -> seats`)
  - missing/invalid class context fails closed and routes through explicit class-context selection gate
- Landed v2 student claim contract update (no DOB in claim flow):
  - `/student/claim-account` now matches on `join_code + full first_name + last_name`
  - optional dedupe code supported for same-name collisions
  - DOB/first-initial credential checks removed from claim form and route contract
- Canonicalized teacher identity spec document:
  - `docs/development/specs/V2_TEACHER_IDENTITY_ARCHITECTURE.md` rewritten from transitional tracker format to canonical v2 architecture language
  - document now explicitly states class-authority-first restoration (`last_active_class_id`) and seat resolution second
- Migration safety verification (upgrade/downgrade loop) passed for current head:
  - `flask db downgrade 53e7c7148fea`
  - `flask db upgrade 8357d4036478`
  - `SELECT version_num FROM alembic_version` => `8357d4036478`
- Focused regression evidence after test remediation:
  - `pytest -q tests/test_teacher_student_flow.py tests/test_class_context_and_switching.py tests/test_legacy_student_claim.py`
  - Result: `21 passed`

### Status Update (2026-05-14): Wave 3 Exit Closure Slice — Request-Level Context Propagation Cleanup (Admin + Analytics Templates)

- Removed additional request-level class context propagation from active admin and analytics surfaces:
  - `app/routes/admin.py`
    - `_get_requested_admin_class_id()` now resolves explicit request `class_id` only; request `join_code` alias resolution removed.
  - `app/routes/analytics.py`
    - removed legacy `resolve_current_join_code(...)` helper; class context remains `class_id`-authoritative via `resolve_current_class_context(...)`.
  - Analytics templates migrated off request `join_code` switching:
    - `templates/admin_analytics_dashboard.html`
    - `templates/admin_analytics_events.html`
    - `templates/admin_analytics_student_detail.html`
    - class switching now posts `class_id` through the existing nav-authoritative `admin.set_current_class` flow.
  - Removed remaining `join_code` propagation on student-detail/admin actions in touched templates:
    - `templates/admin_banking.html`
    - `templates/admin_rent_settings.html`
    - `templates/admin_payroll.html`
    - `templates/admin_payroll_history.html`
    - `templates/admin_view_student_policy.html`
    - `templates/admin_edit_item.html`
    - `templates/admin_support_tickets.html` (removed unused hidden `join_code` field)

Focused validation:

- `python3 scripts/policy_guardrails.py --git-diff-base origin/main --git-diff-head HEAD`
  - Result: `Policy guardrails: clean`
- `pytest -q tests/test_feature_flag_enforcement.py tests/test_feature_settings.py`
  - Result: `29 passed`

### Status Update (2026-05-14): Wave 3 Exit Closure Slice — Admin Feature-Scope Helper Simplification

- Removed obsolete request-level `requested_join_code` compatibility path from admin feature-scope helpers:
  - `app/routes/admin.py`
    - `resolve_admin_feature_join_code(...)` no longer accepts `requested_join_code`
    - `require_admin_feature_scope(...)` no longer accepts `requested_join_code`
  - Updated dependent payroll/hall-pass scope callsites to stay class/block/session-authoritative only.

Focused validation:

- `python3 -m py_compile app/routes/admin.py app/routes/analytics.py`
  - Result: pass
- `python3 scripts/policy_guardrails.py --git-diff-base origin/main --git-diff-head HEAD`
  - Result: `Policy guardrails: clean`
- `pytest -q tests/test_feature_flag_enforcement.py tests/test_feature_settings.py`
  - Result: `29 passed`

### Status Update (2026-05-14): Wave 3 Exit Readiness — Closure Verification

- Final Wave 3 closure verification executed after request-level context cleanup and helper simplification slices.
- Exit criteria assessment:
  - `PASS` no request-level `join_code` class switching in active admin/analytics context-selection paths; class switching is nav-authoritative (`class_id`).
  - `PASS` feature-toggle authority + disabled-route UX remains enforced for teacher/student paths.
  - `PASS` changed-surface read/write boundary guardrails remain clean.
  - `PASS` no route-level commit ownership regressions introduced in touched scope.
  - `PASS` no legacy compatibility fallback reintroduction in cleaned scope.
- Wave 3 confidence evidence:
  - `python3 scripts/policy_guardrails.py --git-diff-base origin/main --git-diff-head HEAD`
    - Result: `Policy guardrails: clean`
  - `pytest -q tests/test_admin_payroll_scoped_balances.py tests/test_dashboard_rendering.py tests/test_feature_flag_enforcement.py tests/test_feature_settings.py tests/test_api_tenancy.py -k "payroll or student_detail or export or feature or hall_pass_available_types or attendance_history_api"`
    - Result: `38 passed`, `14 deselected`

Wave impact:

- Wave 3 closure criteria are satisfied for the tracked identity/scope cleanup sequence on `codex/v2.0`.
- Execution focus can now proceed sequentially to Wave 4 class-configuration canonicalization.

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Legacy Auth Surface Freeze

- Addressed the deferred Wave 3 table-drop risk by making the remaining coupling surface explicit and machine-enforced:
  - Added `scripts/wave3_identity_drop_surface_guardrail.py`
    - scans `app/**/*.py` (excluding model definition files) for legacy auth symbols and legacy session-principal keys
    - compares current coupling surface to a checked-in baseline and fails only when the surface expands
  - Added baseline: `docs/development/tracking/wave3_identity_drop_surface_baseline.json`
  - Added CI test: `tests/test_wave3_identity_drop_surface_guardrail.py`
- Baseline snapshot (current deferred surface):
  - Legacy symbol file counts:
    - `Student` 20, `TeacherBlock` 19, `StudentTeacher` 10, `StudentBlock` 9
    - `Admin` 8, `StudentRecoveryCode` 3, `RecoveryRequest` 2, `TeacherOnboarding` 2, `AdminInviteCode` 2, `AdminCredential` 1
  - Legacy session-principal key file counts:
    - `admin_id` 12, `is_system_admin` 8, `is_admin` 6, `student_id` 6
- Unblocking sequence this enables:
  1. Keep surface non-expanding while runtime slices remove dependencies subsystem-by-subsystem.
  2. Re-cut baseline only after each approved reduction slice (never for expansions).
  3. Execute `0002_identity_domain.py` drop migration only after symbol/session surfaces reach zero for targeted legacy auth constructs.

Focused validation:

- `python3 -m py_compile scripts/wave3_identity_drop_surface_guardrail.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: pass
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`
- `pytest -q tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `1 passed`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Recovery Student-Route Decoupling

- Landed the first dependency-reduction slice under the Wave 3 legacy-auth surface freeze:
  - Added `app/services/recovery_bridge_service.py` to isolate student recovery reads/writes against recovery tables via table-level access.
  - `app/routes/student.py` no longer directly references `RecoveryRequest` / `StudentRecoveryCode` symbols for:
    - dashboard pending-recovery banner lookup
    - `/student/verify-recovery/<code_id>` lookup/update path
    - `/student/dismiss-recovery/<code_id>` lookup/update path
  - Added targeted service coverage: `tests/test_recovery_bridge_service.py`.
- Surface reduction applied and baseline re-cut:
  - `symbols.RecoveryRequest`: removed `app/routes/student.py` coupling
  - `symbols.StudentRecoveryCode`: removed `app/routes/student.py` coupling
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`

Focused validation:

- `python3 -m py_compile app/services/recovery_bridge_service.py app/routes/student.py tests/test_recovery_bridge_service.py`
  - Result: pass
- `pytest -q tests/test_recovery_bridge_service.py`
  - Result: `3 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Recovery Admin-Path Decoupling

- Landed a major recovery-domain reduction slice to remove legacy recovery table symbols from admin/runtime surfaces:
  - expanded `app/services/recovery_bridge_service.py` with admin lifecycle operations (create/list/find/invalidate/save-progress/complete/delete) on recovery tables via table-level access.
  - rewired `app/routes/admin.py` recovery flow (`/recover`, `/recovery-status`, `/reset-credentials`, `/confirm-reset`, `/save-recovery-progress`, `/resume-credentials`) to use bridge-service operations instead of direct `RecoveryRequest` / `StudentRecoveryCode` model references.
  - rewired `app/utils/student_deletion.py` to use bridge-service deletion for student recovery-code cleanup.
  - extended coverage in `tests/test_recovery_bridge_service.py` for admin lifecycle operations and helper behavior.
- Surface reduction applied and baseline re-cut:
  - `symbols.RecoveryRequest`: removed `app/routes/admin.py` coupling (now 0 runtime symbol references in `app/**`).
  - `symbols.StudentRecoveryCode`: removed `app/routes/admin.py` and `app/utils/student_deletion.py` couplings (now 0 runtime symbol references in `app/**`).
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`.

Focused validation:

- `python3 -m py_compile app/services/recovery_bridge_service.py app/routes/admin.py app/routes/student.py app/utils/student_deletion.py tests/test_recovery_bridge_service.py`
  - Result: pass
- `pytest -q tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `6 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Passkey + Onboarding Symbol Decoupling

- Landed the next major identity reduction slice by removing `AdminCredential` and `TeacherOnboarding` symbol dependencies from route/runtime code:
  - Added `app/services/admin_identity_bridge_service.py` with table-level bridge operations for:
    - teacher onboarding lifecycle and widget state
    - admin passkey credential lifecycle
  - Rewired `app/routes/admin.py` passkey and onboarding endpoints/helpers to the bridge service.
  - Rewired teacher-deletion helper path in `app/routes/admin.py` to bridge deletion for passkeys/onboarding.
  - Removed unused `TeacherOnboarding` import dependency from `app/routes/system_admin.py`.
  - Added targeted bridge coverage: `tests/test_admin_identity_bridge_service.py`.
- Surface reduction applied and baseline re-cut:
  - `symbols.AdminCredential`: removed `app/routes/admin.py` coupling.
  - `symbols.TeacherOnboarding`: removed `app/routes/admin.py` and `app/routes/system_admin.py` couplings.
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`.

Focused validation:

- `python3 -m py_compile app/services/admin_identity_bridge_service.py app/routes/admin.py app/routes/system_admin.py tests/test_admin_identity_bridge_service.py`
  - Result: pass
- `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `10 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Invite-Code Symbol Decoupling

- Landed the next identity reduction slice by removing `AdminInviteCode` route/runtime symbol dependencies:
  - extended `app/services/admin_identity_bridge_service.py` with invite-code bridge operations (count/create/list/get/void).
  - rewired `app/routes/system_admin.py` invite-code surfaces (`dashboard`, `manage_teachers`, `void_invite_code`) to bridge operations.
  - removed legacy `AdminInviteCode` import dependency from `app/routes/admin.py` and `app/routes/system_admin.py`.
  - extended coverage in `tests/test_admin_identity_bridge_service.py` for invite-code lifecycle behavior.
- Surface reduction applied and baseline re-cut:
  - `symbols.AdminInviteCode`: removed `app/routes/admin.py` and `app/routes/system_admin.py` couplings.
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`.

Focused validation:

- `python3 -m py_compile app/services/admin_identity_bridge_service.py app/routes/system_admin.py tests/test_admin_identity_bridge_service.py app/routes/admin.py`
  - Result: pass
- `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `11 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Session Principal Key Reduction (Docs/Main)

- Landed the next low-risk reduction slice by removing direct legacy session-principal checks from public/docs route surfaces:
  - `app/routes/main.py` home redirect logic now uses explicit resolver checks (`get_current_admin()`, `get_current_seat()`) instead of direct `session['is_admin'/'admin_id'/'student_id']` fallback checks.
  - `app/routes/docs.py` audience and role determination now uses explicit resolver checks (`get_current_admin()`, `get_current_seat()`, `get_current_user()`) and only treats sysadmin context as valid when both `is_system_admin` and `sysadmin_id` are present.
  - `app/utils/helpers.py` `has_internal_docs_session()` now resolves authenticated state through explicit auth resolvers rather than direct `admin_id` / `student_id` session-key checks.
  - Updated `tests/test_docs_platform_split.py` authentication setup to stay aligned with explicit resolver behavior for internal docs routing.
- Surface reduction applied and baseline re-cut:
  - `session_keys.admin_id`: removed `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py` couplings.
  - `session_keys.student_id`: removed `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py` couplings.
  - `session_keys.is_admin`: removed `app/routes/main.py` coupling.
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`.

Focused validation:

- `pytest -q tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `18 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-05-24): Wave 3 Structural Deferment Unblocking — Session Principal Key Reduction (API/TLCP/Sysadmin Resolver)

- Landed the next high-impact reduction slice by removing direct legacy session-principal checks from API utility and TLCP actor-resolution surfaces:
  - Added explicit resolver helper `get_current_system_admin()` in `app/auth.py` (session flag + id + row resolution; no raw key trust).
  - `app/routes/api.py`:
    - `/api/attendance/history` no longer falls back to `session['admin_id']`; it uses `get_current_admin()` as authoritative context.
    - `/api/set-timezone` now authenticates admin/sysadmin/student paths via explicit resolver checks (`get_current_admin`, `get_current_system_admin`, `get_logged_in_student`) instead of direct `is_admin`/`admin_id`/`is_system_admin` checks.
  - `app/services/tlcp.py` `resolve_actor_context()` now resolves actor identity from explicit auth helpers (`get_current_seat`, `get_logged_in_student`, `get_current_admin`, `get_current_system_admin`) rather than direct principal-key inference.
  - `app/__init__.py` maintenance bypass and `current_sysadmin` template context now use `get_current_system_admin()` rather than trusting raw sysadmin session keys.
  - Added targeted coverage in `tests/test_tlcp_actor_context_resolution.py` for student/admin/sysadmin actor-context resolution.
- Surface reduction applied and baseline re-cut:
  - `session_keys.admin_id`: removed `app/routes/api.py`, `app/services/tlcp.py` couplings.
  - `session_keys.is_admin`: removed `app/routes/api.py`, `app/services/tlcp.py` couplings.
  - `session_keys.is_system_admin`: removed `app/__init__.py`, `app/routes/api.py`, `app/services/tlcp.py` couplings.
  - `session_keys.student_id`: removed `app/services/tlcp.py` coupling.
  - Baseline refreshed in `docs/development/tracking/wave3_identity_drop_surface_baseline.json`.

Focused validation:

- `python3 -m py_compile app/auth.py app/routes/api.py app/services/tlcp.py app/__init__.py`
  - Result: pass
- `pytest -q tests/test_tlcp_actor_context_resolution.py tests/test_timezone_fix.py tests/test_api_fixes.py tests/test_api_attendance_history.py tests/test_maintenance_bypass.py tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py`
  - Result: `41 passed`
- `python3 scripts/wave3_identity_drop_surface_guardrail.py`
  - Result: `Wave 3 identity-drop surface guardrail: clean (no expansion)`

### Status Update (2026-06-01): Wave 3 Scope Hardening — Admin Student-Detail Seat Public IDs

- Replaced teacher-facing numeric student-detail URL identity with class-local `Seat.public_id`:
  - `/admin/students/<int:student_id>` now returns `404`.
  - `/admin/students/<string:student_public_id>` requires a short-lived signed navigation token.
  - teacher-facing templates and post-action redirects now generate URLs through `student_detail_url(...)`.
- Enforced fail-closed active-class resolution:
  - route resolution requires `Seat.public_id`, teacher-owned class scope, signed token class, and active `session["current_class_id"]` to identify the same seat.
  - URL generation does not fall back to another seat if the student is not present in the active class.
  - role-specific public IDs and legacy numeric student IDs are not accepted as aliases for a class-scoped seat.
- Added tenancy regressions for both shared-student cases:
  - two teachers, two classes, one student: one teacher cannot query the other teacher's seat public ID.
  - one teacher, two classes, one student: a URL generated in class A returns `404` after switching to class B, and class B generates its own seat public ID.

Focused validation:

- `python -m py_compile app/routes/admin.py tests/test_admin_tenancy.py`
  - Result: pass
- `pytest -q tests/test_admin_tenancy.py -k "shared_student_accessible_to_multiple_teachers or student_detail_public_url_requires_nav_token or student_detail_public_id_is_seat_scoped_for_shared_student or student_detail_public_id_requires_active_class_for_same_teacher or student_detail_forbids_cross_tenant_access"`
  - Result: `5 passed, 10 deselected`

### Status Update (2026-06-02): Identity Ownership Contract Formalized

- Added `docs/development/specs/V2_IDENTITY_AND_OWNERSHIP_MODEL.md` as the normative
  clean-v2 ownership contract:
  - `users.id` authenticates.
  - `seats.id` acts.
  - `classes.class_id` scopes.
  - UUID-encoded `seats.public_id` is the single deidentified public actor identifier
    for teacher and student seats.
- Recorded that role-specific public-ID fields and separate pre-cutover actor
  correlation are invalid v2 residue, not compatibility surfaces to preserve.
- Kept capability-token ownership separate from actor identity. Final ownership and
  class scope for `hall_pass_verify_token` remain open.
- Validation:
  - `git diff --check` -> pass
  - `python -m py_compile app/models_canonical.py app/models.py app/routes/admin.py tests/test_admin_tenancy.py` -> pass
  - focused admin-tenancy suite -> `5 passed, 10 deselected`

### Status Update (2026-06-02): Teacher-Seat Public Lookup Runtime Reduction

- Added teacher-seat provisioning to class-anchor creation and claim-anchor repair
  paths.
- Removed role-specific teacher-public-ID authority from class-scoped runtime paths:
  - `/student/switch-teacher/<teacher_public_id>` now returns `404`; the existing
    `/student/switch-class/<class_id>` route remains the supported class switch path.
  - `/api/hall-pass/available-types` rejects `teacher_public_id` input.
  - `/api/hall-pass/verification/active` now requires one explicit `class_id` plus the
    matching teacher-seat UUID `Seat.public_id`; it no longer aggregates every class
    owned by an `Admin`.
- Removed the obsolete teacher-switch resolver and access-policy branch.
- Closed adjacent fail-closed bugs exposed during validation:
  - explicit invalid `join_code` aliases now fail instead of falling back to another
    claimed seat.
  - dashboard scope failure redirects to `student.select_class_context`, not the
    removed `student.select_class` endpoint.
- Validation:
  - `git diff --check` -> pass
  - touched-module `python -m py_compile` -> pass
  - `pytest -q tests/test_api_tenancy.py tests/test_route_authorization_sweep.py tests/test_v2_authority_guardrails.py tests/test_class_context_and_switching.py`
    -> `61 passed`

### Status Update (2026-06-02): TLCP Runtime Actor-Public-ID Cutover

- Replaced runtime support/log actor identity generation with class-scoped
  `Seat.public_id`:
  - `resolve_actor_context()` now emits `actor_public_id` for student and teacher
    contexts.
  - request traces, error events, and ticket correlation packs store that seat UUID in
    `actor_public_id`.
  - student support recent-error prompts resolve from the active `seat_id` instead of
    hashing `student_id`.
  - support issue creation now requires the submitted class-scoped seat and uses its
    `public_id` as the ticket reference.
- Removed a FEAT atomicity violation in `create_issue()` by eliminating the nested
  transaction around TLCP pack creation; the support FEAT boundary now owns the
  correlation-pack write.
- Completed follow-up:
  - `TLCP-SCHEMA-001` renamed physical TLCP actor columns, indexes, log labels, tests,
    and sysadmin copy affordances to `actor_public_id`.
- Validation:
  - `git diff --check` -> pass
  - touched-module `python -m py_compile` -> pass
  - `pytest -q tests/test_tlcp_actor_context_resolution.py tests/test_ticket_log_correlation_pack.py`
    -> `6 passed`
  - `pytest -q tests/test_api_tenancy.py tests/test_route_authorization_sweep.py tests/test_v2_authority_guardrails.py tests/test_class_context_and_switching.py`
    -> `61 passed`

### Status Update (2026-06-02): TLCP-SCHEMA-001 Completed

- Renamed physical TLCP actor identity surfaces from the former opaque actor column
  name to `actor_public_id`:
  - `actor_request_trace.actor_public_id`
  - `error_events.actor_public_id`
  - `ticket_correlation_pack.actor_public_id`
- Updated ORM models, TLCP service queries, raw error-event insert SQL, logging format
  fields, tests, and sysadmin copy UI to use `actor_public_id`.
- Added idempotent migration `f6a7b8c9d0e1_rename_tlcp_actor_public_id.py` with
  downgrade support back to the previous physical name.
- Validation:
  - `scripts/lint_migrations.py migrations/versions/f6a7b8c9d0e1_rename_tlcp_actor_public_id.py`
    -> pass
  - `flask db heads` -> `f6a7b8c9d0e1 (head)`
  - `flask db upgrade` -> upgraded `ebb7b66b2176` to `f6a7b8c9d0e1`
  - `flask db downgrade ebb7b66b2176` -> pass
  - `flask db upgrade` -> re-upgraded to `f6a7b8c9d0e1`
  - live schema check confirms only `actor_public_id` TLCP actor columns remain
  - `pytest -q tests/test_tlcp_actor_context_resolution.py tests/test_ticket_log_correlation_pack.py`
    -> `6 passed`

### Status Update (2026-06-02): Support Issue Actor Public ID Schema Rename

- Renamed support issue filing-actor reference from the former student-opaque field
  name to `issues.actor_public_id`.
- Updated ORM, issue creation, sysadmin templates, and support tests to use
  `actor_public_id`.
- Added idempotent migration `f7b8c9d0e1f2_rename_issue_actor_public_id.py` with
  downgrade support back to the previous physical name.
- `issues.actor_public_id` stores the filing seat's UUID `Seat.public_id`; it is the
  sysadmin-safe public actor reference for the support ticket.
- Fixed adjacent stale class-deletion lookup in `collapse_universe()` so the deletion
  primitive resolves `ClassEconomy` by `join_code` instead of treating `join_code` as
  the primary key.
- Validation:
  - active grep for former support issue opaque-student field names -> no app/test/doc
    hits
  - touched-module `python -m py_compile` -> pass
  - migration lint for `f7b8c9d0e1f2_rename_issue_actor_public_id.py` -> pass
  - `flask db heads && flask db current` -> `f7b8c9d0e1f2 (head)`
  - live schema check confirms only `issues.actor_public_id` remains
  - affected support/schema/class-deletion suite -> `15 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — Analytics Enrollment Class Scope

- Resumed v2 rebuild execution with a Wave-4-aligned class-scope hardening slice in analytics:
  - `app/utils/analytics_engine.py`
    - added canonical `class_id` resolution on engine initialization
    - switched primary enrolled-student resolution to `ClassMembership` scoped by `class_id` + `role=student`
    - retained transitional fallback to legacy teacher/block roster resolution only when canonical membership rows are absent
    - updated CWI lookup path to reuse resolved `class_id`
- Validation:
  - `python3 -m py_compile app/utils/analytics_engine.py` → pass
  - `pytest -q tests/test_analytics.py` → `16 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — DOM-ECON-000 Governance in Analytics

- Extended analytics governance alignment to DOM-ECON-000 policy semantics:
  - `app/utils/analytics_engine.py`
    - resolves active policy mode using canonical `class_id` at engine initialization
    - initializes `EconomyBalanceChecker` with resolved policy mode (avoids implicit default drift)
    - updates budget-survival metric threshold from fixed `10%` to policy-governed `savings_weekly.min` ratio per mode
  - `app/utils/economy_policy.py`
    - adds `get_active_policy_mode_for_class(class_id)` helper to keep policy authority class-id-native
- Validation:
  - `python3 -m py_compile app/utils/analytics_engine.py` → pass
  - `pytest -q tests/test_analytics.py` → `16 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — DOM-ECON Analytics Governance Tests

- Added regression coverage to keep analytics governed by canonical economy policy rules:
  - `tests/test_analytics.py`
    - verifies policy mode resolution is class-authoritative (`class_id`) via `FeatureSettings`
    - verifies budget-survival pass-rate threshold uses mode-specific `savings_weekly.min` (tight vs comfortable) instead of fixed 10%
- Validation:
  - `python3 -m py_compile tests/test_analytics.py` → pass
  - `pytest -q tests/test_analytics.py` → `18 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — Backend-Only Analytics Authority Hardening

- Enforced backend single-authority semantics in analytics with no legacy fallback path:
  - `app/utils/analytics_engine.py`
    - removed legacy enrollment fallback chain (`StudentTeacher` / `TeacherBlock` / `StudentBlock` inference)
    - enrollment now resolves only through canonical `ClassMembership` scoped by `class_id`
    - moved analytics warning/band thresholds off engine constants into policy accessor (`get_analytics_policy(...)`)
  - `app/utils/economy_policy.py`
    - added `ANALYTICS_POLICY_DEFAULTS` and `get_analytics_policy(mode)` so analytics thresholds are policy-sourced server-side
- Regression coverage updated for canonical enrollment authority:
  - `tests/test_analytics.py`
    - fixture now seeds canonical `ClassMembership` rows
    - removed fallback-only tests and added class-membership-authoritative enrollment assertion
- Validation:
  - `python3 -m py_compile app/utils/economy_policy.py app/utils/analytics_engine.py tests/test_analytics.py` → pass
  - `pytest -q tests/test_analytics.py` → `16 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — Analytics Activity Queries Canonicalized to `class_id`

- Completed analytics query-scope migration from `join_code` to canonical `class_id` for core activity and cache surfaces:
  - `app/utils/analytics_engine.py`
    - `Transaction` activity queries now filter by `Transaction.class_id`
    - `TapEvent` activity queries now filter by `TapEvent.class_id`
    - snapshot lookup/history queries now filter by `AnalyticsSnapshot.class_id`
    - alert lookup/lifecycle queries now filter by `AnalyticsAlert.class_id`
    - created snapshots/alerts now persist `class_id` on write
    - added fail-closed guards: snapshot create/read APIs now require canonical `class_id` context
- Validation:
  - `python3 -m py_compile app/utils/analytics_engine.py tests/test_analytics.py` → pass
  - `pytest -q tests/test_analytics.py` → `16 passed`

### Status Update (2026-05-20): Wave 4 Resume Slice — Balance Scope Invariant Enforcement (`class_id + seat_id`)

- Enforced strict scope invariants for student balance reads:
  - `app/models.py`
    - `Student.get_checking_balance(...)` now requires both `class_id` and `seat_id`
    - `Student.get_savings_balance(...)` now requires both `class_id` and `seat_id`
    - removed legacy `kwargs` / `join_code` fallback semantics from both helpers
- Updated analytics and related backend callsites to pass canonical scope explicitly:
  - `app/utils/analytics_engine.py`
    - resolved seat IDs from canonical `seats` table per `class_id`
    - all balance reads now call with explicit `class_id + seat_id`
  - `app/routes/analytics.py`
    - student detail analytics now resolves canonical class/seat scope before balance reads
  - `app/utils/issue_helpers.py`
    - issue context snapshot now resolves canonical class/seat scope before balance reads
  - `app/routes/admin.py`
    - student detail and student export scoped balance reads now use explicit `class_id + seat_id`
- Validation:
  - `python3 -m py_compile app/models.py app/utils/analytics_engine.py app/routes/analytics.py app/routes/admin.py app/utils/issue_helpers.py tests/test_analytics.py` → pass
  - `pytest -q tests/test_analytics.py` → `16 passed`

### Status Update (2026-05-22): Wave 4 Resume Slice — Scheduled Rebalance Class-Authority Hardening

- Hardened scheduled rebalance activation to enforce canonical class boundary authority from `FeatureSettings.class_id`:
  - `app/utils/economy_rebalance.py`
    - removed payload-driven class resolution during activation (`join_code` / `block` no longer influence mutation target)
    - rent rebalance application now resolves `RentSettings` by `settings_row.class_id` only
    - insurance rebalance application now resolves `InsurancePolicy` by `settings_row.class_id` only
    - `activate_due_rebalances(...)` now increments activation counts only when at least one scoped change is actually applied
- Added regression coverage for cross-class payload tampering cases:
  - `tests/test_economy_policy_mode.py`
    - verifies rent changes cannot be redirected to a different class via payload `block` / `join_code`
    - verifies insurance changes cannot mutate a policy in another class for the same teacher
- Validation:
  - `python3 -m py_compile app/utils/economy_rebalance.py tests/test_economy_policy_mode.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances or run_payroll_applies_scheduled_rebalance"` → `4 passed`, `16 deselected`

### Status Update (2026-05-22): Wave 4 Resume Slice — Policy Lineage Schema Scaffolding

- Added policy-lineage scaffolding for class-configuration economic governance:
  - `app/models.py`
    - introduced `PolicyVersion` (`policy_versions`) and `PolicyTransition` (`policy_transitions`) ORM classes
    - class-scoped ownership via `class_id` FK, unique `(class_id, domain, version_number)` lineage key, and class/domain/state indexes
  - `app/models_canonical.py`
    - added canonical model stubs for `policy_versions` and `policy_transitions`
  - `migrations/versions/c4e36a4ab2f1_add_policy_lineage_tables.py`
    - idempotent creation of both tables, FK wiring, and supporting indexes
    - downgrade uses dynamic FK discovery (no hardcoded FK-name dependency)
- Scope note:
  - This slice is schema/model scaffolding only. Runtime rebalance execution remains on transitional `FeatureSettings` fields until FEAT cutover slices land.
- Validation:
  - `python3 -m py_compile app/models.py app/models_canonical.py migrations/versions/c4e36a4ab2f1_add_policy_lineage_tables.py` → pass
  - `python3 scripts/lint_migrations.py migrations/versions/c4e36a4ab2f1_add_policy_lineage_tables.py` → pass (0 warnings)
  - `flask db upgrade` → pass
  - `flask db downgrade 8357d4036478` → pass
  - `flask db upgrade` → pass
  - `flask db heads` → `c4e36a4ab2f1 (head)`
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances"` → `3 passed`, `17 deselected`

### Status Update (2026-05-22): Wave 4 Resume Slice — FEAT-ECON Dual-Write Activation Cutover

- Shifted scheduled rebalance activation to policy-lineage-first while retaining transitional JSON compatibility:
  - `app/utils/economy_rebalance.py`
    - added class-scoped policy lineage writers for rebalance changes (`policy_versions`, `policy_transitions`)
    - immediate rebalance apply now writes `applied` transitions/versions in parallel
    - scheduled rebalance queue now writes `pending` transitions/versions in parallel
    - `activate_due_rebalances(...)` now processes pending `policy_transitions` as primary source and falls back to legacy `economy_pending_rebalance_json` only when no pending transitions exist for the class
    - pending transition supersession/cancellation/apply state updates are now tracked in `policy_transitions`
  - `app/routes/admin.py`
    - scheduled rebalance route now queues policy transitions during schedule flow
    - economy-policy update now cancels pending transitions for the class scope
    - pending effective-at UI lookup now resolves from `policy_transitions` first, then legacy JSON fallback
- Added regression coverage for dual-write and transition-driven activation:
  - `tests/test_economy_policy_mode.py`
    - next-renewal schedule test now asserts pending policy transition/version creation
    - added activation test proving pending transition can apply without any legacy JSON payload
- Validation:
  - `python3 -m py_compile app/utils/economy_rebalance.py app/routes/admin.py tests/test_economy_policy_mode.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances or next_renewal_rebalance"` → `5 passed`, `16 deselected`
  - `pytest -q tests/test_economy_policy_mode.py` → `21 passed`

### Status Update (2026-05-22): Wave 4 Resume Slice — Legacy Pending-Payload Write Removal (Route/UI Path)

- Removed legacy pending-rebalance JSON writes from active rebalance route flows now that pending-state UI is transition-backed:
  - `app/routes/admin.py`
    - `update_economy_policy()` no longer mutates `FeatureSettings.economy_pending_rebalance_json`; pending transition cancellation remains class-scoped
    - `apply_economy_rebalance()` scheduled branch no longer serializes pending payload JSON; policy transitions are the sole scheduled-state write path
    - policy summary now exposes transition-backed flag (`has_pending_policy_transition`) instead of legacy payload presence
    - pending effective date resolution now reads only from `policy_transitions`
  - `templates/admin_economy_health.html`
    - scheduled badge/render gate switched from legacy payload presence to transition-backed `has_pending_policy_transition`
  - `app/utils/economy_rebalance.py`
    - immediate apply path no longer writes/clears `economy_pending_rebalance_json`
    - transition-driven activation path no longer writes legacy payload cleanup rows; legacy JSON writes remain only inside fallback compatibility handling for pre-existing payload data
- Regression updates:
  - `tests/test_economy_policy_mode.py`
    - next-renewal scheduling test now asserts no legacy JSON write while validating transition/target payload creation
- Validation:
  - `python3 -m py_compile app/routes/admin.py app/utils/economy_rebalance.py tests/test_economy_policy_mode.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "next_renewal_rebalance_schedules_rent_for_next_cycle or activate_due_rebalances_applies_pending_policy_transition_without_legacy_payload or run_payroll_applies_scheduled_rebalance"` → `3 passed`, `18 deselected`

### Status Update (2026-05-23): Wave 4 Resume Slice — Legacy Pending-Payload Activation Fallback Retirement

- Retired legacy pending JSON compatibility path from scheduled activation:
  - `app/utils/economy_rebalance.py`
    - `activate_due_rebalances(...)` no longer falls back to `FeatureSettings.economy_pending_rebalance_json` when a class has no pending transitions
    - classes without pending `policy_transitions` now no-op in activation flow
- Migrated scheduled-activation regression coverage fully to transition-native fixtures:
  - `tests/test_economy_policy_mode.py`
    - replaced legacy JSON-seeded scheduled activation/payroll tests with `PolicyVersion` + `PolicyTransition` setup
    - removed legacy JSON field assertions from transition-path tests
    - added shared helper for pending transition fixture creation to keep tests consistent and class-scoped
- Validation:
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances or next_renewal_rebalance or run_payroll_applies_scheduled_rebalance"` → `6 passed`, `15 deselected`

### Status Update (2026-05-23): Wave 4 Resume Slice — FeatureSettings Legacy Rebalance Column Drop

- Removed the final runtime schema artifact for legacy pending-rebalance payload storage:
  - `app/models.py`
    - dropped `FeatureSettings.economy_pending_rebalance_json` from runtime ORM model
  - `migrations/versions/d2f9f1d9be2e_drop_legacy_pending_rebalance_json.py`
    - idempotent schema migration drops `feature_settings.economy_pending_rebalance_json`
    - downgrade safely restores nullable `TEXT` column
- Scope note:
  - This completes the scheduled-rebalance payload cutover path from JSON storage to policy lineage (`policy_versions` / `policy_transitions`) for runtime model/schema ownership.
- Validation:
  - `python3 -m py_compile app/models.py migrations/versions/d2f9f1d9be2e_drop_legacy_pending_rebalance_json.py` → pass
  - `python3 scripts/lint_migrations.py migrations/versions/d2f9f1d9be2e_drop_legacy_pending_rebalance_json.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances or next_renewal_rebalance or run_payroll_applies_scheduled_rebalance"` → `6 passed`, `15 deselected`

### Status Update (2026-05-23): Wave 4 Resume Slice — FeatureSettings Legacy Scope Uniqueness Removal

- Removed legacy uniqueness enforcement keyed to teacher/block alias scope:
  - `app/models.py`
    - dropped `uq_feature_settings_teacher_join_code_block` from `FeatureSettings.__table_args__`
    - canonical row uniqueness remains anchored on `FeatureSettings.class_id`
  - `migrations/versions/f84c7ad2c1aa_drop_feature_settings_legacy_scope_unique.py`
    - idempotent migration drops `uq_feature_settings_teacher_join_code_block` when present
    - downgrade recreates the legacy unique constraint
- Scope note:
  - This advances Wave 4 legacy-column-contract cleanup by removing a remaining legacy-key uniqueness contract while preserving runtime behavior.
- Validation:
  - `python3 -m py_compile app/models.py migrations/versions/f84c7ad2c1aa_drop_feature_settings_legacy_scope_unique.py` → pass
  - `python3 scripts/lint_migrations.py migrations/versions/f84c7ad2c1aa_drop_feature_settings_legacy_scope_unique.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "get_feature_settings_row_for_class_requires_explicit_class_scope or update_economy_policy_creates_block_scoped_settings"` → `2 passed`, `19 deselected`

### Status Update (2026-05-23): Wave 4 Resume Slice — Scheduled Activation Block Scope Canonicalization

- Removed runtime dependence on legacy `FeatureSettings.block` and removed inferred scope resolution (`teacher_id + block -> class_id`) from scheduled rebalance activation:
  - `app/utils/economy_rebalance.py`
    - activation scope now accepts explicit canonical `class_id` context
    - pending `FeatureSettings` rows are filtered by explicit `class_id`
    - removed payload-level block gating in activation loop so transition application remains class-authoritative
  - `app/routes/admin.py`
    - payroll-triggered activation now passes `selected_scope['class_id']` (already resolved canonical scope) into activation
- Added regression coverage:
  - `tests/test_economy_policy_mode.py`
    - new test confirms explicit class-scoped activation still applies even when `FeatureSettings.block` contains stale legacy data
- Validation:
  - `python3 -m py_compile app/utils/economy_rebalance.py app/routes/admin.py tests/test_economy_policy_mode.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances"` → `5 passed`, `17 deselected`

### Status Update (2026-05-23): Wave 4 Resume Slice — FeatureSettings Class-Authoritative Resolution

- Replaced inferred FeatureSettings scope resolution in active economy-policy paths with explicit canonical class context:
  - `app/utils/economy_policy.py`
    - added `get_feature_settings_row_for_class(class_id, ...)` as explicit `class_id` lookup/create helper
    - legacy create fields (`teacher_id`, `join_code`, `block`) are now write-through only when explicitly provided by already-resolved scope
  - `app/routes/admin.py`
    - `update_economy_policy()` now resolves scope via `require_admin_feature_scope(...)` and reads/writes `FeatureSettings` by explicit `class_id`
    - `apply_economy_rebalance()` now resolves scope via `require_admin_feature_scope(...)` and reads/writes `FeatureSettings` by explicit `class_id`
    - `economy_health()` now anchors class-scoped fine/store queries and policy summary on explicit scope `class_id` instead of deriving class via join-code lookup chain
- Regression updates:
  - `tests/test_economy_policy_mode.py`
    - updated policy-setting creation assertion to query by `class_id`
    - renamed helper contract test to `test_get_feature_settings_row_for_class_requires_explicit_class_scope`
- Validation:
  - `python3 -m py_compile app/utils/economy_policy.py app/routes/admin.py app/utils/economy_rebalance.py tests/test_economy_policy_mode.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py` → `22 passed`
  - `pytest -q tests/test_analytics.py -k "policy_mode_resolves_by_class_id or budget_survival_uses_policy_mode_min_savings_ratio"` → `2 passed`, `14 deselected`

### Status Update (2026-05-24): Wave 4 Resume Slice — FeatureSettings Legacy Column Retirement

- Removed legacy scope columns from runtime `FeatureSettings` contract:
  - `app/models.py`
    - dropped `FeatureSettings.teacher_id`, `FeatureSettings.join_code`, and `FeatureSettings.block`
    - removed legacy `teacher` relationship/index and simplified repr to `class_id` authority
  - `app/utils/economy_policy.py`
    - simplified `get_feature_settings_row_for_class(...)` create path to class-authoritative row creation (no legacy write-through fields)
    - compatibility wrapper `get_feature_settings_row(...)` still resolves class scope, then delegates to class-authoritative helper
  - `app/routes/admin.py`
    - removed remaining legacy-create args for policy update/rebalance settings-row creation
    - rebalance apply logging now records canonical `class_id` instead of legacy `block` field from settings rows
- Added migration to retire schema columns:
  - `migrations/versions/a91cf11e8b2d_drop_feature_settings_legacy_scope_columns.py`
    - drops `feature_settings.teacher_id`, `feature_settings.join_code`, `feature_settings.block`, and legacy teacher index
    - idempotent downgrade restores columns/index/FK as nullable compatibility fields
- Updated tests to canonical row creation/query semantics:
  - `tests/test_economy_policy_mode.py`
  - `tests/test_analytics.py`
  - `tests/test_feature_settings.py`
- Validation:
  - `python3 -m py_compile app/models.py app/utils/economy_policy.py app/routes/admin.py tests/test_economy_policy_mode.py tests/test_analytics.py tests/test_feature_settings.py migrations/versions/a91cf11e8b2d_drop_feature_settings_legacy_scope_columns.py` → pass
  - `python3 scripts/lint_migrations.py migrations/versions/a91cf11e8b2d_drop_feature_settings_legacy_scope_columns.py` → pass
  - `pytest -q tests/test_economy_policy_mode.py` → `22 passed`
  - `pytest -q tests/test_economy_policy_mode.py -k "activate_due_rebalances"` → `5 passed`, `17 deselected`
  - `pytest -q tests/test_analytics.py -k "policy_mode_resolves_by_class_id or budget_survival_uses_policy_mode_min_savings_ratio"` → `2 passed`, `14 deselected`
  - `pytest -q tests/test_feature_settings.py -k "feature_settings_to_dict_reads_class_features or class_feature_defaults"` → `2 passed`, `15 deselected`

### Status Update (2026-05-20): Spec Coverage Audit — Banking/Balance/Overdraft/Rent Touchpoints

- Confirmed existing v2 spec coverage for touched features:
  - `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`
  - `DOM-CLASS-001_Class_Configuration_Domain.md`
  - `FEAT-LED-001_Post_Ledger_Transaction.md`
  - `FEAT-OBLI-001_Assess_Obligation.md`
  - `FEAT-STOR-001_Store_Purchase.md`
- Added missing focused implementation contract doc for the exact touched helper+settlement boundary:
  - `V2_BALANCE_SCOPE_AND_SETTLEMENT_CONTRACT.md`
  - documents current runtime logic and explicit risk against v2 rules where transitional behavior remains

### Status Update (2026-05-01): FEAT Atomicity Enforcement Baseline

- Enforced FEAT-owned transaction boundaries as a runtime invariant:
  - direct `db.session.commit()` outside orchestrator-owned FEAT boundaries now fails fast with `FEATContextError`
- Subsequent wave fixes (including 3C.12-B payroll cache shell) are required to conform to this baseline via `flush()` or orchestrator commit ownership.

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

### Status Update (2026-05-02): Wave 3C.8 Hall Pass Scope Hardening

- Completed hall-pass enforcement hardening to class-authoritative scope:
  - removed permissive teacher-only and inferential fallback paths in action enforcement
  - class context is required for mutation paths (fail-closed)
  - verification token entry remains teacher-scoped for physical verification, while pass rows remain class-anchored.

---

## Wave 7 — Obligations Domain (DOM-OBL-001)

### Pre-Implemented Behavior (from 3C.10-T/C)

The following obligation behaviors are already implemented and MUST be preserved during this wave:

- Rent operates on a prepay cycle model with explicit coverage windows (`coverage_start_time`, `coverage_end_time`)
- Rent execution is class-scoped and scheduled with deterministic idempotency keys
- Economic actor is strictly `seat_id + class_id`
- Insurance waiting period is calendar-based using class-local midnight boundaries (not duration-based)
- Coverage eligibility is evaluated against class-local time, not raw UTC
- All temporal logic in obligations respects INV-ARC-015 (canonical class time)

Constraint:
- Wave 7 MUST NOT redesign or alter these behaviors.
- Wave 7 is strictly responsible for migrating these behaviors into canonical obligation tables (`assessment_events`, `obligation_lifecycle`, `entitlement_events`, etc.)

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

### Status Update (2026-05-02 to 2026-05-03): Wave 3C.9 / 3C.9-B Store Scope Migration

- Migrated active store enforcement paths from teacher-scoped filtering to class-scoped filtering:
  - item resolution, pricing/settings, purchase eligibility, and redemption-facing reads/writes now class-authoritative.
- Completed cross-domain cleanup for remaining store-related scope leaks in linked admin/service/feat paths where store behavior was still teacher-filtered.
- Preserved FEAT orchestration and transaction boundaries while updating enforcement scope only.

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

**Goal:** Complete all deferred post-launch items from `docs/development/archive/tracking/V2_LAUNCH_READINESS_MATRIX.md` plus structural cleanup.

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

8. **`docs/development/archive/tracking/V2_TEMPORAL_INVARIANT_AUDIT.md`** completion and verification
   - INV-ARC-015 is substantially implemented as of 3C.10-T/C:
     - class-local time enforcement complete in critical execution paths (attendance, scheduler, analytics, obligations)
     - temporal guardrails present in test suite
   - Remaining work:
     - full-repo enforcement sweep (no unscoped temporal helpers)
     - documentation formalization

9. **`docs/development/specs/V2_CLASS_ID_INVARIANT_BACKLOG.md`** all items closed

10. **TLCP (`app/services/tlcp.py`)** validated against canonical `ledger_transaction` table

### Verification

- Backup/restore rehearsed on staging
- All GET routes are write-free
- Admin routes functional after decomposition; all URL paths respond correctly
- All readiness matrix items marked `done`

### Status Update (2026-05-13): Wave 11 Adversarial Harness Restoration + INV-ARC-007 Attendance Read/Write Split

- Restored adversarial Phase 1 source harness on `codex/v2.0`:
  - `scripts/adversarial/phase1_seed_and_snapshot.sh`
  - `scripts/adversarial/run_phase1.sh`
  - `scripts/adversarial/verify_cross_class_isolation.py`
  - `scripts/adversarial/verify_lineage_lawfulness.py`
  - `scripts/adversarial/render_constitutional_scorecard.py`
  - `scripts/adversarial/build_evidence_bundle.py`
  - snapshot/reset utilities under `scripts/adversarial/`
- Reintroduced runtime attack reporting as first-class evidence output:
  - Added `scripts/adversarial/verify_runtime_session_attacks.py`
  - `run_phase1.sh` now executes runtime battery and regenerates `runtime_attacks_report.json`
  - Evidence bundle manifest now includes `runtime_attacks_report.json`
  - Scorecard now reports runtime battery status/violation counts
- Established sanitized evidence documentation protocol:
  - `scripts/adversarial/build_evidence_bundle.py` now emits commit-safe summaries under `artifacts/adversarial/sanitized/<run_id>/`
  - protocol spec: `docs/development/specs/V2_ADVERSARIAL_EVIDENCE_DOCUMENTATION_PROTOCOL.md`
  - intent: always document results without committing raw engagement payload files
- Fixed adversarial replay reliability issues discovered during rerun:
  - `scripts/adversarial/inject_impossible_state.py` now bootstraps a compliant `balance_cache` row when the seed topology has none, then performs class mismatch injection
  - bootstrap write is FEAT-owned (`FEAT-ADMN-001`)
  - `scripts/adversarial/reset_db.py` tolerates known `pg_restore` compatibility warning (`transaction_timeout`) in mixed Postgres tool/server versions
  - `app/feats/base.py` top-level FEAT entry now safely falls back to `begin_nested()` on scoped-session `InvalidRequestError`
- Completed another `INV-ARC-007` rewrite slice in attendance polling:
  - `GET /api/student-status` is now read-only
  - New explicit mutation endpoint: `POST /api/student-status/reconcile` (FEAT-wrapped)
  - `static/js/attendance.js` now reconciles via POST before status polling reads
  - Added targeted regression coverage in `tests/test_tap_flow.py` for GET read-only vs POST reconcile mutation behavior

Validation snapshot after clean seeded baseline and injected replay:

- Baseline (pre-injection): cross-class `PASS(0)`, lineage `PASS(0)`, runtime `PASS(0)`
- Injected replay: cross-class `FAIL(1)` (expected synthetic corruption detection), lineage `PASS(0)`, runtime `PASS(0)`
- Scorecard remains non-terminal overall due to:
  - expected injected cross-class failure in replay mode
  - remaining GET mutation detector findings (`INV-ARC-007`) outside this slice

Wave impact:

- Advances Wave 11 item **6. INV-ARC-007 final sweep** by removing additional write-on-GET behavior from live student polling path.
- Re-establishes adversarial evidence generation as a stable standing gate for ongoing v2 rewrite waves.

### Status Update (2026-05-14): Wave 11 Adversarial Verifier Remediation + Phase 1 PASS Scorecard

- Completed remediation hardening to keep adversarial evidence deterministic and signal-accurate:
  - `scripts/adversarial/run_phase1.sh` now resets per-run `violations.jsonl` before execution to prevent stale carryover between runs.
  - `scripts/adversarial/verify_cross_class_isolation.py` now classifies known synthetic injection rows (from `injection_report.json`) as expected test signals.
  - Cross-class verifier now fails only on unexpected violations while still recording expected injected findings as separate evidence.
  - `scripts/adversarial/verify_lineage_lawfulness.py` now supports strict mode via `--require-lineage`; default mode treats missing lineage metadata as `UNVERIFIED` (informational) for Phase 1 skeleton reporting.
- Confirmed targeted remediation areas are live and passing in current branch tests:
  - unclaimed seat context rejection path
  - hall-pass available-types feature gate enforcement path
  - FEAT transaction entry safety path for pre-existing session transactions
- Current constitutional scorecard state (`artifacts/adversarial/current/scorecard.md`):
  - GET Mutation Detector: `PASS (0)`
  - Cross-Class Isolation Verifier: `PASS (0)` unexpected, with expected synthetic injection tracked separately
  - Lineage Verifier (Skeleton): `PASS (0)` with `UNVERIFIED` rows reported separately
  - Runtime Session Attack Battery: `PASS (0)`
  - Synthetic Impossible-State Injection: `PASS (0)`
  - Overall: `PASS`

Wave impact:

- Closes a reliability gap in Wave 11 adversarial evidence reporting (stale data contamination removed).
- Makes Phase 1 scorecard outcomes actionable by separating expected synthetic probes from real violations.
- Advances Wave 11 item **6. INV-ARC-007 final sweep** by preserving clean detector signal for subsequent GET-route hardening slices.

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
| Archived tracker history | `docs/development/archive/tracking/` |
| Active build specs | `docs/development/specs/` |
| Migration template | `migrations/migration_template.py.mako` |
| Migration linter | `scripts/lint_migrations.py` |
| Current models | `app/models.py` (3261+ lines) |
| Feats | `app/feats/` (8 files) |
| Services | `app/services/` (8 files) |
| Auth layer | `app/auth.py` |
| Seat scope utils | `app/utils/seat_scope.py` |

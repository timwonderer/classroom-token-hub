# Multi-Tenancy Hardening Progress Log (v2.0)

Date: 2026-02-17  
Branch: `join-code-centric-architecture-rebuild`

## Scope and Rule of Truth
- `join_code` is the primary class boundary.
- No action is valid without scoped `join_code` + identity validation (`ClassMembership` role/status).
- "Apply to all sections" means fan-out across all `join_code` values owned by the teacher; no global unscoped action exists.
- Deleting a `join_code` removes all data in that boundary by design.

## Completed
- Added core class-boundary models and wiring:
  - `ClassEconomy`, `ClassMembership`, `ClassJoinCodeAlias`
  - FK scoping across class-bound entities to `class_economies.join_code`
- Added non-enumerable teacher public identity:
  - `Admin.public_id` random identifier introduced for public-facing teacher references (internal numeric PK remains internal-only)
  - `Admin.public_id` now generates as a readable 3-word slug from `app/data/random-words.txt` for easier QR/url handling and manual entry
- Added membership/access primitives in auth:
  - `resolve_join_code`, `get_membership`, `check_membership_access`, `membership_required`, `get_actor_membership_id`
- Hardened high-risk student/API financial paths:
  - `/api/purchase-item` now authorizes spending with class-scoped balances
  - Removed purchase authorization fallback to `teacher_id + join_code=None`
  - Overdraft checks in purchase flow now use class-scoped balances
- Hardened student context and subject scoping:
  - `get_current_class_context()` resolves by active `ClassMembership`
  - Student dashboard/shop/insurance flows use `join_code` scoping
  - `Student.get_active_insurance()` moved to `join_code` scoping
- Hardened hall-pass class scoping:
  - Queue/settings/setup/available-types enforce `join_code` and membership checks where applicable
  - Verification display is intentionally unauthenticated and teacher-wide via stable random `Admin.public_id` URL, returning only join-codes owned by that teacher
  - Added join-code settings bootstrap helper that clones teacher template rows into join-code-scoped settings
- Fixed audit-anchor implementation bug:
  - `HallPassLog.actor_membership_id` is now a real persisted column definition
  - Completed `actor_membership_id` sweep: Added audit trail anchors to all state-changing `Transaction` endpoints (`admin.py`, `api.py`, `student.py`, `system_admin.py`). Sysadmins pass `None`.
- Hardened issue-resolution reverse flow (`/admin/issues/<id>/resolve`):
  - Enforces issue/transaction scope match (`student_id`, `teacher_id`, `join_code`) before reversal.
  - For both pending and posted transactions, creates compensating pending reversal ledger row (`type='refund'`) and links via `reversal_transaction_id`.
  - Pending transactions are transitioned to `VOID` with `voided_at`.
- Replaced remaining admin financial aggregates that used global student properties:
  - Admin dashboard totals and banking summary totals now aggregate only across teacher-owned active `join_code` memberships.
  - Shared helper added for scoped per-student totals (`checking`, `savings`, `earnings`) to reduce future regressions.
- Added route-level admin membership gates for class-bound actions:
  - `/admin/current-class` now requires active admin `ClassMembership` for the requested `join_code`.
  - `/admin/students/delete-block` and `/admin/join-code/delete` now enforce admin membership authorization for targeted join codes.
  - `/admin/issues` now uses `current_join_code` and filters through owned active join-code memberships.
  - `ensure_admin_join_code` now prefers `ClassMembership` as source-of-truth (with legacy `TeacherBlock` fallback only during migration).
  - Added guarded legacy bootstrap helper to create missing admin memberships from owned `TeacherBlock` only when no ownership conflict exists.
- Removed remaining live global-balance display leak in admin payroll UI:
  - `/admin/payroll` now renders per-student checking/savings from scoped join-code aggregates.
  - `templates/admin_payroll.html` no longer reads `student.checking_balance` / `student.savings_balance` directly.
- Removed remaining live student earnings display leaks:
  - `templates/student_payroll.html` and `templates/student_transfer.html` now render `scoped_total_earnings` provided by route context.
  - Student payroll/transfer routes now pass join-code scoped earnings instead of template reads from `student.total_earnings`.
- Hardened API admin tap/block settings endpoints to current class membership context:
  - `/api/admin/tap-entries/<student_id>` and `/api/admin/tap-entries/<event_id>` now require admin session + `current_join_code` membership and enforce join-code/student membership scope.
  - `/api/admin/student-block-settings` and `/api/admin/block-tap-settings` now require admin `current_join_code` membership and avoid cross-class StudentBlock writes.
  - Added compatibility handling for legacy payload key `enabled` in block tap settings POST.
- Extended route-level hardening sweep across admin/api/student/system-admin surfaces:
  - `/api/attendance/history` now scopes to either authorized requested `join_code` or explicit fan-out over admin-owned active join-codes.
  - `/api/hall-pass/verification/active` now requires a stable random teacher public identifier and is constrained to that teacher's active join-code membership set.
  - Deprecated hall-pass terminal APIs/routes were removed (`/api/hall-pass/lookup/*`, `/api/hall-pass/terminal/use`, `/api/hall-pass/terminal/return`, `/hall-pass/terminal`).
  - Student dashboard queue status now consumes `/api/hall-pass/queue` via explicit `join_code` context and displays same-class queue entries.
  - Queue API now supports student-role access in-class and resolves teacher-scoped hall-pass settings via the class admin membership anchor.
  - `/api/approve-redemption` and `/api/reject-redemption` now enforce admin membership on redemption class scope before mutation.
  - Student insurance claim eligibility now prioritizes policy `join_code` (fallback to `teacher_id` only when policy has no join_code).
  - `/admin/join-code/delete` now requires explicit `confirm_join_code` confirmation before destructive hard delete.
- Removed legacy `join_code=NULL` settings fallback blending:
  - `get_banking_settings_for_context()`, `get_rent_settings_for_context()`, `get_feature_settings_for_student()` in `student.py` no longer fall back to `join_code IS NULL` rows.
  - `purchase_item()` banking settings lookup in `api.py` no longer falls back to `join_code IS NULL`.
  - Settings now return `None` or system defaults when no class-scoped row exists.
- Completed comprehensive admin mutation route audit and gating:
  - Audited all 50+ POST routes in `admin.py` against the v2 join-code scoping rule.
  - Added `_verify_membership_for_blocks` shared helper that resolves blocks → join_codes via `TeacherBlock` and verifies admin `ClassMembership` for each.
  - Config mutation routes gated: `store_management` POST (create), `edit_store_item` POST, `delete_store_item` POST (soft), `payroll_settings` POST, `update_expected_weekly_hours` POST, `edit_insurance_policy` POST, `deactivate_insurance_policy` POST, `delete_insurance_policy` POST.
  - Financial state routes gated: `rent_settings` POST, `insurance_management` POST (create), `add_rent_waiver` POST (per-student TeacherBlock join_code), `remove_rent_waiver` POST.
  - Payroll reward/fine CRUD scoped to `current_join_code`: `payroll_add_reward`, `payroll_add_fine` now set `join_code` on records; `delete`/`edit` routes verify membership on the record's `join_code`.
  - Pending/legacy student cleanup gated: `delete_pending_student`, `bulk_delete_pending_students`, `bulk_delete_legacy_unclaimed` now verify join_code membership.
  - Identity-level routes documented as exempt: auth flows, display name settings, student creation.
  - **Strict FK Constraint Hardening**: Verified and fixed all test fixtures to respect Postgres-level foreign key constraints (essential for production stability).
  - **Legacy API Cleanup**: Replaced all deprecated `ClassEconomy.query.get` usages with modern `db.session.get` across the test suite.
  - **Query Inversion Phase 2 (Diagnostics)**: Swept read paths for RentSettings, InsurancePolicy, PayrollFine, and StoreItem in `api_economy_analyze`, `api_economy_validate`, and `economy_health` to use explicitly scoped `join_code` lookups. Included `teacher_id` fallbacks to preserve backward compatibility until full rotation backfill is complete.
  - **Query Inversion Phase 2 (Admin UI)**: Swept admin UI read paths for `InsurancePolicy` (`insurance_management`, `edit_insurance_policy`) to use explicitly scoped `join_code` lookups based on active class memberships, retaining `teacher_id` fallbacks for legacy compatibility.
  - **Model Migration Safeguards**: Fixed testing models and modernized legacy queries (like `Query.get()`) to pass cleanly ahead of PostgreSQL foreign key constraints hardening.
  - **DB CHECK Constraints**: Implemented `ck_membership_xor` and `ck_membership_role_consistency` on `ClassMembership` via Alembic to guarantee isolation logic at the database layer.

## Commit Review Snapshot (Recent Branch Work)
| Commit | Scope Review | Hardening Impact |
|---|---|---|
| `1e4953e` | `student/admin/api` read paths | Phase 1 query inversion: Scoped settings reads and student shop by `join_code`. Removed `teacher_id` leaks in these reads. |
| `cca4cf9` - `534255d` | `admin` deletion flows | Comprehensive class and account deletion: Implemented 2-step modals (`a6d972b`) and `collapse_universe` DB integrity rules (`534255d`). |
| `fc51967` | `tests/models` | Test suite strict foreign key fixes and legacy `Query.get()` modernization to ensure DB integrity during deployment. |
| `37dc4e7` | `admin/api/student/system_admin` + new route sweep tests | Broad membership/join-code enforcement expansion, attendance/redemption/hall-pass/claim scoping tightening, and destructive delete confirmation gate |
| `177e296` | `api` tap + block settings | Enforced current-class admin membership and cross-join-code rejection for tap/block settings endpoints |

## Verified
- Targeted and multitenancy-related suites passed after hardening updates:
  - `98 passed` across the selected multi-tenancy regression suites
- Endpoint-level runtime checks (not static-only) additionally verified:
  - `18 passed` across export scoping, issue reversal, void rules, and admin tenancy tests.
  - `19 passed` across admin membership gates + legacy delete flows.
  - `20 passed` across payroll + shared-student + admin multitenancy regression slice including scoped payroll display checks.
  - `10 passed` across student scoped earnings display + adjacent feature/transfer regression slice.
  - `12 passed` across new API admin tap-scope tests + API fix smoke tests + admin membership/tenancy checks.
  - `13 passed` across route authorization sweep + API tenancy + admin membership + API tap scope tests:
    - `tests/test_route_authorization_sweep.py`
    - `tests/test_api_tenancy.py`
    - `tests/test_api_admin_tap_scope.py`
    - `tests/test_admin_membership_gates.py`
  - `24 passed` across route authorization + hall-pass queue/history + API tenancy/fixes suites after terminal removal and stable teacher-public-id verification scope update:
    - `tests/test_route_authorization_sweep.py`
    - `tests/test_hall_pass_queue_scoping.py`
    - `tests/test_hall_pass_history_scoping.py`
    - `tests/test_api_tenancy.py`
    - `tests/test_api_fixes.py`
  - `7 passed` across new settings fallback removal tests:
    - `tests/test_settings_fallback_removal.py`
  - `7 passed` across new FK compatibility and legacy-query-cleanup validation:
     - `tests/test_student_payroll_rate.py` (FK fix)
     - `tests/test_sysadmin_issue_rewards.py` (FK fix)
  - Full suite: `497 passed, 1 skipped, 0 failures` (with 0 warnings) after all hardening changes.

## Risk Report Reconciliation (`docs/audits/2026-02-16_stage-2_economic-invariant-risk.md`)
- 1) Cross-tenant purchase authorization leakage: `Patched`
  - `/api/purchase-item` uses class-scoped balances (`join_code`) and no global balance fallback.
- 2) Global balance properties violate isolation: `Partially patched`
  - High-risk call paths now use `get_checking_balance/get_savings_balance/get_total_earnings` with `join_code`.
  - Legacy global properties (`Student.checking_balance`, `Student.savings_balance`, `Student.total_earnings`) still exist for compatibility, but known admin export/dashboard/banking/payroll display and student payroll/transfer display usages were migrated to scoped helpers.
- 3) CSV export cross-tenant leakage: `Patched`
  - `/admin/export-students` now computes balances/earnings from teacher-owned `join_code` memberships only.
- 4) Ledger mutability via direct voiding: `Partially patched`
  - Reversal transactions are created in key void flows, including issue-resolution reverse actions.
  - Original-row mutability flags remain in use (`is_void`) and full immutable-ledger semantics are not complete.
- 5) Float precision risk: `Partially patched`
  - Core money storage is `Numeric`, and ledger cache uses integer cents.
  - Remaining float conversions still exist in presentation/compatibility paths and should be minimized for strict financial invariants.
- 6) Join-code hard deletion audit concern: `Intended behavior (accepted)`
  - Confirmed as required by design: join_code destruction removes all data in that tenant boundary.
  - UX guardrail work for destructive confirmation is still pending.

## Intentional-by-Design Decisions
- Join-code deletion performs hard deletion of all class-scoped data in that boundary.
- Legacy unscoped aggregate earnings/balance paths are being retired; scoped (`join_code`) calls are the expected v2 behavior.

## Remaining TODO (Must Complete for Full v2.0 Hardening)

### 1) Route-Level Authorization Completion
- ~~Apply `membership_required(...)` or equivalent explicit `check_membership_access(...)` gates to all class-scoped API/admin/student routes.~~ **Complete for admin mutation routes.** All admin POST routes now validate `join_code` membership or are documented as identity-level.
- Remaining: student-side and API routes still need audit for class-scoped reads.

### 2) Query Inversion Completion (`teacher_id/block` -> `join_code`)
- Remove remaining class-scope filters using:
  - `teacher_id` comparisons for class data access
  - `join_code IS NULL` legacy blending in class-level reads/writes
  - `block=None` as access boundary (keep only as per-class settings field where `join_code` is present)
- Highest concentration remains in:
  - `app/routes/admin.py`
  - `app/routes/system_admin.py`
  - `app/routes/api.py` (residual areas outside already hardened flows)
  - `app/routes/student.py` (residual legacy blend points)

### 3) Admin "All Sections" Semantics
- Replace implicit teacher-global reads with explicit fan-out across teacher-owned `join_code` set.
- Ensure every batch update/read is implemented as union/iteration over concrete `join_code` values.

### 4) Audit Anchor Completion
- Ensure every state-changing write sets `actor_membership_id` where applicable.
- Backfill/guard rails for paths that can still write without a resolved actor membership (fail loudly or log warnings instead of silently dropping audits).

### 5) Legacy Path Removal
- Remove deprecated routes/branches that bypass join-code membership validation.
- Remove compatibility code that enables unscoped class actions once migration cutoff is reached.
- Gate TeacherBlock legacy fallbacks with a `USE_LEGACY_TB_FALLBACK` feature flag and schedule complete removal.

### 6) Class Deletion Architecture
- ~~Implement the `collapse_universe` primitive for all destructive paths inside a single DB transaction.~~
- ~~Enforce `ON DELETE CASCADE` foreign keys for high-risk tables (BalanceCache, Transaction, StudentBlock, TapEvent, RentPayment).~~
- ~~Add destructive confirmation UI guardrails for all class and student deletion paths.~~
- ~~Ensure student accounts with zero remaining active memberships are fully deleted.~~

### 7) Test Coverage Expansion (Required)
- Add explicit regression tests asserting:
  - cross-join-code purchase/transfer/insurance/rent access is denied
  - all class-scoped endpoints reject missing or unauthorized `join_code`
  - teacher "all sections" operations only affect that teacher's join-code set
  - actor membership audit fields are persisted on all state-changing endpoints

## Exit Criteria for "Fully Hardened"
- No class-scoped action executes without validated `join_code` + membership.
- No access control decisions depend on `TeacherBlock`, `teacher_id`, or `block`.
- No class-scoped reads/writes rely on `join_code IS NULL` fallback logic.
- All multitenancy hardening tests pass and block regressions in CI.

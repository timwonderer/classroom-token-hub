# Multi-Tenancy Hardening Progress Log (v2.0)

Date: 2026-02-16  
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
  - Verification/queue/settings/setup/available-types now require `join_code` and membership checks where applicable
  - Added join-code settings bootstrap helper that clones teacher template rows into join-code-scoped settings
- Fixed audit-anchor implementation bug:
  - `HallPassLog.actor_membership_id` is now a real persisted column definition

## Verified
- Targeted and multitenancy-related suites passed after hardening updates:
  - `98 passed` across the selected multi-tenancy regression suites

## Intentional-by-Design Decisions
- Join-code deletion performs hard deletion of all class-scoped data in that boundary.
- Legacy unscoped aggregate earnings/balance paths are being retired; scoped (`join_code`) calls are the expected v2 behavior.

## Remaining TODO (Must Complete for Full v2.0 Hardening)

### 1) Route-Level Authorization Completion
- Apply `membership_required(...)` or equivalent explicit `check_membership_access(...)` gates to all class-scoped API/admin/student routes.
- Eliminate endpoints that still allow teacher-only or implicit scope without `join_code`.

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
- Backfill/guard rails for paths that can still write without a resolved actor membership.

### 5) Legacy Path Removal
- Remove deprecated routes/branches that bypass join-code membership validation.
- Remove compatibility code that enables unscoped class actions once migration cutoff is reached.

### 6) Test Coverage Expansion (Required)
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

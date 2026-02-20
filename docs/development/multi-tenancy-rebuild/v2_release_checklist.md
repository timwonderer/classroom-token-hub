# v2 Multitenancy Go/No-Go Checklist

Date: 2026-02-17  
Branch: `join-code-centric-architecture-rebuild`

## Release Gate

| # | Checklist Item | Status | Pass Criteria | Primary Validation |
|---|---|---|---|---|
| 1 | Membership gate on all class-scoped routes | Complete | Every admin mutation route validates `join_code` membership via `_check_admin_join_code_access` or `_verify_membership_for_blocks`; identity-level routes documented | Route audit matrix + endpoint tests |
| 2 | Query inversion complete (`teacher_id/block` removed as access control) | In Progress | Access decisions no longer depend on `TeacherBlock`, `teacher_id`, `block` | Code sweep + targeted deny tests |
| 3 | No class-scoped `join_code IS NULL` fallback paths | Complete | Settings helpers (`banking`, `rent`, `feature`) no longer fall back to `join_code=NULL` rows; return `None` or system defaults | `tests/test_settings_fallback_removal.py` (7 tests) |
| 4 | “All sections” implemented as explicit fan-out over owned join-codes | In Progress | Batch operations iterate concrete owned join-codes only | Integration tests for multi-class teacher |
| 4a | No global-balance property reads in live class-scoped displays | In Progress | Student/admin financial display surfaces render route-provided scoped totals only | Template + endpoint tests |
| 5 | Actor audit anchor complete (`actor_membership_id`) | In Progress | All state-changing writes persist actor membership or fail safely | Endpoint mutation tests |
| 6 | Ledger immutability semantics complete | In Progress | Reversal-first behavior for voids; no destructive retroactive mutation as source-of-truth | Void flow tests + ledger reconciliation |
| 7 | Monetary precision hardened | In Progress | Core financial calculations avoid float drift | Precision tests |
| 8 | Legacy bypass routes removed/deprecated paths blocked | In Progress | No deprecated route can mutate/read class data without membership scope | Route tests + routing audit |
| 9 | Join-code deletion UX guardrails implemented | In Progress | Multi-step confirmation flow before hard delete | UI + endpoint tests |
| 10 | CI multitenancy regression suite required for merge | Complete | Full 497-test suite passing with strict FK constraints and no warnings | CI validation |

## Execution Order (Recommended)

1. Complete route-level authorization sweep (`admin`, `api`, `student`, `system_admin`).
2. Finish query inversion and remove class-level legacy null-join-code blending.
3. Enforce all-sections fan-out semantics everywhere (no implicit globals).
4. Complete audit-anchor coverage for every state-changing endpoint.
5. Finalize immutable-ledger and precision hardening remaining paths.
6. Remove legacy bypass routes and compatibility branches.
7. Add destructive delete UX guardrails.
8. Lock CI gate for multitenancy regression suite.

## Recent Completions

- **Comprehensive admin mutation route audit**: Audited all 50+ POST routes and added join_code membership gates to every class-scoped mutation route.
- **Settings fallback hardening**: Removed legacy `join_code=NULL` fallback queries from `get_banking_settings_for_context()`, `get_rent_settings_for_context()`, `get_feature_settings_for_student()`, and `purchase_item()` banking lookup.
- **Config mutation gates**: Added `_verify_membership_for_blocks` to `store_management` POST (create), `edit_store_item` POST, `delete_store_item` POST (soft), `payroll_settings` POST, `update_expected_weekly_hours` POST, `edit_insurance_policy` POST, `deactivate_insurance_policy` POST, `delete_insurance_policy` POST.
- **Financial state gates**: Added `_check_admin_join_code_access` to `rent_settings` POST, `insurance_management` POST (create), `add_rent_waiver` POST, `remove_rent_waiver` POST.
- **Payroll reward/fine class scoping**: `payroll_add_reward` and `payroll_add_fine` now set `join_code` from session context; `delete`/`edit` routes verify membership on the record's `join_code`.
- **Pending student cleanup gates**: `delete_pending_student`, `bulk_delete_pending_students`, `bulk_delete_legacy_unclaimed` now verify join_code membership before deletion.
- **Shared helper**: Introduced `_verify_membership_for_blocks` (resolves blocks → join_codes via TeacherBlock, verifies admin ClassMembership for each).
- **Test coverage**: Created `tests/test_settings_fallback_removal.py` (7 tests) verifying settings helpers refuse legacy `join_code=NULL` rows.
- Scoped admin payroll display balances to owned join-codes.
- Scoped student payroll/transfer lifetime earnings display to current join-code context.
- Hardened admin tap/block settings APIs to require `current_join_code` admin membership and block cross-join-code student/event access.
- Expanded authorization sweep coverage for attendance/redemption/hall-pass/insurance claim class scoping and added explicit join-code delete confirmation guardrail.
- Removed deprecated hall-pass terminal routes/APIs and switched student dashboard queue polling to explicit `current_join_code` scope.
- Updated verification display API to intentional unauthenticated teacher-wide scope via stable random teacher public-id URL across that teacher's join-codes.
- Added random `Admin.public_id` and moved verification identity resolution off numeric teacher IDs.
- Switched new `Admin.public_id` generation to readable 3-word slugs from local word list for stable QR/manual use.

## Immediate Next Step

1. Complete query inversion sweep: remove remaining class-scope filters using `teacher_id` comparisons and `block=None` as access boundary.
2. Ensure all state-changing writes set `actor_membership_id` universally.
3. Lock CI gate for multitenancy regression suite.

## Definition of Done for v2

- No class-scoped action executes without validated `join_code` + membership.
- No access decision depends on `TeacherBlock`, `teacher_id`, or `block`.
- No class-scoped reads/writes rely on `join_code IS NULL` fallback logic.
- All hardening regression tests pass in CI and block merge on failure.

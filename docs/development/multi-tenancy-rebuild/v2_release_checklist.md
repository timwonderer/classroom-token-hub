# v2 Multitenancy Go/No-Go Checklist

Date: 2026-02-17  
Branch: `join-code-centric-architecture-rebuild`

## Release Gate

| # | Checklist Item | Status | Pass Criteria | Primary Validation |
|---|---|---|---|---|
| 1 | Membership gate on all class-scoped routes | In Progress | Every class-scoped admin/student/api route denies unauthorized or missing `join_code` membership | Route inventory + endpoint tests |
| 2 | Query inversion complete (`teacher_id/block` removed as access control) | In Progress | Access decisions no longer depend on `TeacherBlock`, `teacher_id`, `block` | Code sweep + targeted deny tests |
| 3 | No class-scoped `join_code IS NULL` fallback paths | In Progress | Class reads/writes never blend legacy null join_code rows | Regression tests + grep guard |
| 4 | “All sections” implemented as explicit fan-out over owned join-codes | In Progress | Batch operations iterate concrete owned join-codes only | Integration tests for multi-class teacher |
| 4a | No global-balance property reads in live class-scoped displays | In Progress | Student/admin financial display surfaces render route-provided scoped totals only | Template + endpoint tests |
| 5 | Actor audit anchor complete (`actor_membership_id`) | In Progress | All state-changing writes persist actor membership or fail safely | Endpoint mutation tests |
| 6 | Ledger immutability semantics complete | In Progress | Reversal-first behavior for voids; no destructive retroactive mutation as source-of-truth | Void flow tests + ledger reconciliation |
| 7 | Monetary precision hardened | In Progress | Core financial calculations avoid float drift | Precision tests |
| 8 | Legacy bypass routes removed/deprecated paths blocked | In Progress | No deprecated route can mutate/read class data without membership scope | Route tests + routing audit |
| 9 | Join-code deletion UX guardrails implemented | In Progress | Multi-step confirmation flow before hard delete | UI + endpoint tests |
| 10 | CI multitenancy regression suite required for merge | Pending | PR fails if multitenancy suite fails | CI workflow enforcement |

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

- Scoped admin payroll display balances to owned join-codes.
- Scoped student payroll/transfer lifetime earnings display to current join-code context.
- Hardened admin tap/block settings APIs to require `current_join_code` admin membership and block cross-join-code student/event access.
- Expanded authorization sweep coverage for attendance/redemption/hall-pass/insurance claim class scoping and added explicit join-code delete confirmation guardrail.
- Removed deprecated hall-pass terminal routes/APIs and switched student dashboard queue polling to explicit `current_join_code` scope.
- Updated verification display API to intentional unauthenticated teacher-wide scope via stable random teacher public-id URL across that teacher's join-codes.
- Added random `Admin.public_id` and moved verification identity resolution off numeric teacher IDs.
- Switched new `Admin.public_id` generation to readable 3-word slugs from local word list for stable QR/manual use.

## Immediate Next Step

1. Complete the route-level authorization inventory and convert remaining class-scoped endpoints to strict join-code membership gates (`membership_required` or explicit `check_membership_access`), starting with unresolved `admin` and `api` endpoints that still depend on legacy `teacher_id/block` access patterns.

## Definition of Done for v2

- No class-scoped action executes without validated `join_code` + membership.
- No access decision depends on `TeacherBlock`, `teacher_id`, or `block`.
- No class-scoped reads/writes rely on `join_code IS NULL` fallback logic.
- All hardening regression tests pass in CI and block merge on failure.

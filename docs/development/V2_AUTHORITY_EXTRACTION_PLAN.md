# V2 Authority Extraction Plan

**Status:** Planned  
**Sequence Position:** Immediately after Project 3 low-conflict production fixes  
**Branch Context:** `codex/v2.0`

## Summary

This wave lands immediately after Project 3 and is not a compatibility refactor. It is the point where V2 defines and enforces its system laws.

The objective is to remove policy authority from routes and helpers, and concentrate it into a small set of services that become the only legal path for scope resolution, access decisions, money behavior, CWI policy, and collective-goal lifecycle state.

A service may depend on lower-level primitives and repositories, but no route may bypass a service to reach policy-bearing logic directly.

## Why This Exists

V2 is not preserving V1 authority patterns. This extraction is the constitutional layer for the new system.

This work establishes:

- how scope is resolved
- how permission is decided
- how money can move
- how CWI policy is interpreted
- how collective-goal state evolves

Everything built after this wave must inherit these laws rather than re-implement them.

## V2 Authority Guarantees

After this wave:

- All class-scoped operations originate from a resolved class scope produced by `class_scope_service`.
- All authorization and ownership decisions flow through `access_policy_service`.
- All money-affecting writes originate in `economy_service`.
- All CWI analysis and policy interpretation flow through `cwi_service`.
- All collective-goal lifecycle transitions and progress evaluation flow through `collective_goal_service`.
- Route handlers are orchestration and presentation only. They do not resolve scope, decide permission, compute balances, or evaluate collective-goal state.

These are hard rules, not conventions.

## Implementation Changes

### 1. Create the authority layer under `app/services`

Add these modules:

- `class_scope_service.py`
  Owns student/admin class resolution, active class selection, feature-scope resolution, and canonical `ResolvedClassScope`.
- `access_policy_service.py`
  Owns permission and ownership decisions using actor identity plus resolved scope.
- `economy_service.py`
  Owns scoped balance reads, transfer execution, overdraft behavior, and all ledger-affecting orchestration.
- `cwi_service.py`
  Owns all route/API-facing CWI entrypoints, using `EconomyBalanceChecker` only as an internal engine.
- `collective_goal_service.py`
  Owns collective-goal instance issuance, purchase attachment, progress counting, threshold unlocks, expiration/refunds, and reactivation rotation.

No new business-rule helper should be added to `routes` or generic `utils`.

### 2. Scope and access boundary

Make this boundary explicit and non-negotiable:

- `class_scope_service` resolves scope
- `access_policy_service` decides permission

`class_scope_service` rules:

- Resolve one authoritative class context for student and admin flows.
- Normalize stale session-selected scope only when exactly one unambiguous owned scope exists.
- Return a rejection state when the selection is invalid and no unambiguous owned scope exists.
- Resolve feature scope from the same canonical scope path, not feature-specific route logic.

`access_policy_service` rules:

- Take actor facts, resolved scope, and target resource facts, and return a structured decision.
- Own shared-student, multi-teacher, class-boundary, and mutation-permission checks.
- Return decisions, not Flask responses.

Routes may not inspect ownership tables and decide access on their own.

### 3. Delete route-owned policy logic

Remove scope/economy/policy behavior from routes instead of preserving it.

- Student routes must stop owning current-class resolution, feature gating, scoped balance logic, and collective-goal progress logic.
- Admin routes must stop owning feature-scope resolution, scoped student-query policy, direct CWI policy branching, and collective-goal progress logic.
- Routes may still:
  - parse request data
  - call services
  - map service results to HTML or JSON responses

Direct route-local policy code is invalid after this wave.

### 4. Economy model

`economy_service` becomes the single path for money behavior.

- All class-scoped balance reads are service-owned.
- All money-affecting writes originate in `economy_service`, not in routes or feature-specific helpers.
- Transfer execution must:
  - require resolved scope
  - validate account pair and amount
  - enforce Project 3 submission-token rules
  - perform ledger writes consistently
  - apply overdraft behavior consistently
  - return structured outcomes for HTML and JSON callers
- Routes may not create transfer ledger rows directly.
- Routes may not compute available balances directly.

Keep lower-level ledger primitives such as settlement and transaction-idempotency utilities as dependencies of `economy_service`, not parallel business-rule entrypoints.

### 5. CWI model

`cwi_service` becomes the single route/API entrypoint for CWI policy.

- Admin pages and APIs must call `cwi_service`, not instantiate `EconomyBalanceChecker` directly.
- Warning filtering, bypass semantics, long-term-goal exemptions, and recommendation shaping are owned by `cwi_service`.
- `EconomyBalanceChecker` remains an internal calculation engine for this wave only.

No controller-facing code may depend directly on `EconomyBalanceChecker` after cutover.

### 6. Collective-goal model

`collective_goal_service` becomes the single path for collective-goal state.

Collective-goal invariants:

- Progress is always instance-scoped.
- Duplicate-purchase checks are current-instance only.
- Reactivation always rotates the instance code.
- Historical rows are never repurposed into a new instance.
- Refunds are instance-matched only.

Operational rules:

- On initial collective-item creation, assign an instance code immediately.
- On inactive -> active reactivation, assign a fresh instance code immediately.
- On purchase, attach the current instance code to the `StudentItem`.
- All progress counts, duplicate checks, threshold evaluation, unlock transitions, and expiration/refund matching must include the current instance code.

Routes and generic store helpers may not count collective progress or decide collective lifecycle state themselves.

### 7. Cut old abstractions aggressively

This wave reduces legal entrypoints.

- Delete helpers that exist only because routes used to own policy.
- Do not leave duplicate "service path" and "route path" logic alive after cutover.
- Do not add long-lived compatibility wrappers unless a same-PR cutover is unsafe due to breadth.
- If names encode the old model, rename them cleanly.

The end state is fewer authority surfaces, not more layers.

### 8. Sequence

Apply in this order:

1. Finish Project 3.
2. Extract and cut over scope resolution.
3. Extract and cut over access policy.
4. Extract and cut over economy and money-affecting writes.
5. Extract and cut over CWI entrypoints.
6. Extract and cut over collective-goal lifecycle logic.
7. Remove leftover duplicated helpers in routes and utils before starting the next major V2 workstream.

This front-loads the laws that later subsystems depend on.

## Internal Interfaces

Define these internal types as plain dataclasses or typed dicts:

- `ResolvedClassScope`
  Fields: `actor_type`, `actor_id`, `teacher_id`, `join_code`, `class_id`, `block`, `seat_id`
- `ScopeResolutionResult`
  Fields: `status`, `scope`, `reason_code`
- `AccessDecision`
  Fields: `allowed`, `reason_code`, `scope`
- `TransferRequest`
  Fields: `student_id`, `scope`, `from_account`, `to_account`, `amount`, `submission_token`
- `TransferResult`
  Fields: `status`, `message`, `checking_balance`, `savings_balance`, `fee_charged`, `fee_amount`
- `CWIAnalysisResult`
  Fields: `cwi`, `breakdown`, `warnings`, `recommendations`, `policy_mode`
- `CollectiveGoalProgress`
  Fields: `store_item_id`, `join_code`, `instance_code`, `count`, `target`, `remaining`, `percent`, `is_complete`

No Flask request/session/response objects cross the service boundary.

## Test Plan

### Authority enforcement tests

Add explicit enforcement mechanisms:

- In route tests, patch service entrypoints and assert the targeted routes call them.
- In targeted route modules, remove direct imports of policy-bearing helpers and engines.
- Add focused grep/static checks in review or test scripts for forbidden direct dependencies in routes:
  - direct `EconomyBalanceChecker` usage
  - direct collective-goal counting logic
  - direct scoped-balance calculation logic
  - direct permission/ownership table decisions
- Verify route behavior through service-returned result shapes, not duplicated inline policy.

### Behavioral tests

Verify:

- a student with multiple classes resolves exactly one authoritative scope
- an admin with stale selected class is normalized only when unambiguous; otherwise the service rejects
- transfer uses only class-scoped balances
- transfer rejection does not create extra monetary side effects
- Project 3 submission token prevents stale or duplicate transfer submission
- CWI output is identical across admin page and API paths for the same scope
- collective-goal create assigns an instance code
- collective-goal reactivation rotates the instance code
- whole-class duplicate purchase checks only the current instance
- expired goals only refund pending purchases from the matching instance
- reactivated goals start with zero progress without deleting history

### Regression suites to keep green

Run and adapt:

- transfer and scoped-balance tests
- feature-flag enforcement tests
- collective-goal expiration/reactivation tests
- multi-teacher scoping tests
- economy/CWI API tests

## Completion Gate

This wave is not complete until:

- targeted routes no longer perform inline authority decisions
- duplicated helper paths are removed or reduced to non-policy plumbing only
- direct controller use of `EconomyBalanceChecker` is eliminated
- all money-affecting writes for targeted flows originate in `economy_service`
- collective-goal state is computed only through `collective_goal_service`
- targeted route and service tests pass through service-first paths only

## Assumptions

- This wave is V2-only and does not preserve behavior solely for historical compatibility.
- Session/auth decorators remain in `app/auth.py` for now, but authority decisions move out of routes.
- `EconomyBalanceChecker` is retained as an internal engine only until a later deeper simplification.
- No generic `store_service` is introduced in this wave; collective-goal policy is extracted first because it already has its own lifecycle laws.
- After this wave, any new V2 feature work must build on these services rather than adding route-local policy.

# V2 Launch Project Checklist

**Last Updated:** 2026-04-08
**Purpose:** Consolidate the active `docs/development` v2 materials into one implementation-facing checklist organized by project, build order, invariants, and test expectations for v2 launch.  
**Use this doc for:** sequencing work, assigning sections, and deciding what must be complete before live test, before production, or after launch.

## Source Documents

This checklist is derived from the active and supporting development docs below. The project sections intentionally preserve the source intent instead of replacing it with a new plan.

- `docs/development/V2_MAIN_RECONCILIATION_TRACKER.md`
- `docs/development/V2_LAUNCH_READINESS_MATRIX.md`
- `docs/development/V2_PARALLEL_WORKSTREAMS.md`
- `docs/development/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`
- `docs/development/V2_ADMIN_ROUTE_REFACTOR.md`
- `docs/development/V2_Class_Scope_Normalization_Target.md`
- `docs/development/V2_CLASS_ID_INVARIANT_BACKLOG.md`
- `docs/development/V2_BACKWARDS_COMPATIBILITY_CLEANUP.md`
- `docs/development/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/development/TABLE_CONSOLIDATION_ANALYSIS.md`
- `docs/development/LEGACY_SCHEMA_ANALYSIS.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-001_REFACTOR_BEST_PRACTICES.md`

## Build Order Summary

### Phase 0: Already-Landed Foundation

- [x] Transaction idempotency and frozen analytics payloads landed on `codex/v2.0`
- [x] Rent waivers, perk suppression, settlement, and related banking fixes landed on `codex/v2.0`
- [x] PostgreSQL validation baseline is green per `V2_LAUNCH_READINESS_MATRIX`

### Phase 1: Pre-Live-Test Blockers

- [x] Project 1: Launch evidence and active-doc alignment
- [x] Project 2: Economy policy and rent-cycle corrections

### Phase 2: Pre-Production Required Ports

- [ ] Project 3: Low-conflict production fixes
- [ ] Project 4: Insurance reconciliation wave
- [ ] Project 5: Production transition evidence

### Phase 3: Post-Launch Structural Hardening

- [ ] Project 6: Admin route structural refactor
- [ ] Project 7: Class scope normalization and class-identity cleanup
- [x] Project 8: Backwards compatibility and schema cleanup
- [ ] Project 9: Long-term identity-model convergence

## Global Launch Invariants

These rules appear repeatedly across the source docs and should be treated as non-negotiable when evaluating any project below.

- [ ] `codex/v2.0` remains the active v2 branch until launch strategy changes.
- [ ] Admin and teacher writes must originate from explicit canonical session class context.
- [ ] `current_join_code` is the current enforced runtime boundary for admin writes.
- [ ] Request-level scope can assist reads, but does not replace canonical session scope for writes.
- [ ] `ClassEconomy` and `ClassMembership` remain the active authority model during launch work.
- [ ] New launch-critical changes must not deepen `teacher_id`-only scoping where class scope already exists.
- [ ] Live-test work must not silently turn deferred architecture targets into in-scope rewrites.
- [ ] Any schema work must use v2-native migrations rather than replaying divergent `main` migration history verbatim.
- [ ] Historical docs stay historical unless they are explicitly promoted back into active guidance.

## Project 1: Launch Evidence And Active-Doc Alignment

**Status:** Pre-live-test blocker  
**Primary source docs:** `V2_LAUNCH_READINESS_MATRIX`, `V2_DOCUMENTATION_COMPLIANCE_SWEEP`, `V2_PARALLEL_WORKSTREAMS`  
**Why this comes first:** It has low code conflict, unblocks launch decision-making, and keeps operators and developers aligned while feature ports are landing.

### Scope

- [x] Refresh the live-test rehearsal artifact with named operator confirmation.
- [x] Record either independent verifier confirmation or a documented solo-operator exception.
- [x] Record smoke-route execution outcome with named ownership.
- [x] Add the active v2 tracker/readiness/compliance docs to the documentation index.
- [x] Re-run the focused active-doc link check after live-test blocker code lands.
- [x] Refresh the readiness matrix so only intentional open items remain.

### Invariants To Preserve

- [x] Runbooks must reflect the actual branch, database, and migration truth on `codex/v2.0`.
- [x] Active docs must point to current trackers and SOPs, not retired checklist paths.
- [x] Historical artifacts may be superseded, but should not be rewritten as if they are active truth.

### Tests / Verification To Write Or Run

- [x] Doc review against current branch and runbook commands
- [x] Active-doc link validation for the index, README, development docs, and v2 SOPs
- [x] Operator-owned smoke execution record review

### Exit Criteria

- [x] `V2_LAUNCH_READINESS_MATRIX` no longer lists open pre-live-test documentation/evidence gaps except intentional deferrals.
- [x] The documentation index includes the active v2 launch tracker docs.
- [x] The rehearsal artifact names who ran it and how sign-off was handled.

## Project 2: Economy Policy And Rent-Cycle Corrections

**Status:** Pre-live-test blocker  
**Primary source docs:** `V2_MAIN_RECONCILIATION_TRACKER`, `V2_PARALLEL_WORKSTREAMS`, `V2_LAUNCH_READINESS_MATRIX`  
**Why this comes second:** It is the remaining launch-critical application delta called out before live testing.

### Scope

- [x] Port the remaining `main` economy-policy and rent-cycle correctness deltas into v2 manually.
- [x] Preserve existing v2 membership-based authority and `current_join_code` behavior.
- [x] Reconcile improved rent-cycle locking and next-cycle rebalance timing.
- [x] Reconcile penalty-reversal behavior.
- [x] Port the CWI warning bypass controls through a v2-native migration if fields are still missing.
- [x] Keep economy-health calculations scoped to selected class context only.

### Target Files

- [x] `app/routes/admin.py`
- [x] `app/routes/student.py`
- [x] `app/utils/economy_balance.py`
- [x] `app/utils/economy_policy.py`
- [x] `app/utils/economy_rebalance.py`
- [x] `templates/admin_economy_health.html`
- [x] `templates/admin_rent_settings.html`
- [x] `static/js/economy-balance.js`

### Invariants To Preserve

- [x] Class A rebalance changes must not mutate class B rent cycles.
- [x] Rent penalties must not reverse incorrectly after rebalance changes.
- [x] CWI bypass controls must appear only where intended.
- [x] No port step may reintroduce teacher-global assumptions in place of class-scoped behavior.
- [x] If schema differs from `main`, implement a new v2 migration instead of replaying the old chain.

### Tests To Write Or Port

- [x] Port or adapt `tests/test_economy_policy_mode.py`
- [x] Port `tests/test_rent_penalty_reversal.py`
- [x] Re-run related economy API coverage
- [x] Re-run rent-display coverage

### Exit Criteria

- [x] Reconciliation tracker classifies the remaining economy/rent delta as landed or intentionally deferred.
- [x] The live-test readiness matrix no longer carries ambiguous status on launch-critical economy/rent deltas.
- [x] Required economy/rent regressions pass on the v2 branch.

## Project 3: Low-Conflict Production Fixes

**Status:** Pre-production required  
**Primary source docs:** `V2_MAIN_RECONCILIATION_TRACKER`, `V2_PARALLEL_WORKSTREAMS`, `V2_LAUNCH_READINESS_MATRIX`  
**Why this comes before insurance:** These ports are narrower, lower conflict, and reduce production risk without forcing the shared insurance/admin rewrite wave first.

### Scope A: Maintenance Workflow Security Fix

- [ ] Port the workflow templating/security fix from `main`
- [ ] Verify maintenance toggling still works after the workflow change

**Files**

- [ ] `.github/workflows/deploy.yml`
- [ ] `.github/workflows/toggle-maintenance.yml`

**Verification**

- [ ] Workflow review
- [ ] Dry-run style inspection in CI if available

### Scope B: Teacher Announcement Visibility And Sunset Messaging

- [ ] Port the teacher-facing system announcement visibility fix
- [ ] Keep README and docs-site sunset messaging consistent

**Files**

- [ ] `app/routes/admin.py`
- [ ] `templates/admin_dashboard.html`
- [ ] `docs/index.html`
- [ ] `README.md`

**Verification**

- [ ] Add or reuse announcement visibility coverage
- [ ] Manually confirm dashboard rendering for teacher users

### Scope C: Transfer Submission Hardening

- [ ] Port malformed/stale transfer submission protections
- [ ] Preserve v2 student seat/user-context behavior while porting
- [ ] Confirm intended feature-flag constraints remain enforced

**Files**

- [ ] `app/routes/student.py`
- [ ] `templates/layout_student.html`
- [ ] `templates/student_transfer.html`

**Verification**

- [ ] Port relevant `tests/test_transfer_legacy_transactions.py` coverage
- [ ] Update `tests/test_feature_flag_enforcement.py`
- [ ] Exercise active-session and stale-session transfer paths

### Scope D: Collective Goal Reactivation Instance Codes

- [ ] Add instance-code handling so reactivated collective goals start a new logical run
- [ ] Implement a v2-native migration for instance-code fields
- [ ] Avoid replaying `main` merge-head migrations verbatim

**Files**

- [ ] `app/models.py`
- [ ] `app/routes/admin.py`
- [ ] `app/routes/api.py`
- [ ] `app/routes/student.py`
- [ ] `app/utils/store.py`

**Verification**

- [ ] Port `tests/test_collective_goal_expiration.py`
- [ ] Manually verify that prior contributions do not reappear after reactivation

### Cross-Cutting Invariants

- [ ] Workflow hardening can land independently.
- [ ] Shared-file application changes should wait until Project 2 route churn settles.
- [ ] Manual ports must preserve v2 tenancy/session behavior already present on `codex/v2.0`.

### Exit Criteria

- [ ] All production-required non-insurance `main` deltas in the tracker are landed or explicitly deferred by decision.
- [ ] Workflow, announcement, transfer, and collective-goal checks pass.

## Project 4: Insurance Reconciliation Wave

**Status:** Pre-production required  
**Primary source docs:** `V2_MAIN_RECONCILIATION_TRACKER`, `V2_PARALLEL_WORKSTREAMS`, `V2_LAUNCH_READINESS_MATRIX`  
**Why this is a dedicated project:** The source docs treat insurance as a coordinated schema-and-behavior wave, not a set of safe independent cherry-picks.

### Scope A: Modularization And Tiered Setup Flow

- [ ] Port teacher-facing modular tiered insurance setup
- [ ] Finalize tiered guidance flow from `main`
- [ ] Keep simple/advanced mode transitions stable

### Scope B: Pricing Snapshots, Approval Caps, And Claim Time-Limit Gate

- [ ] Use filing timestamp rather than the wrong event timestamp for claim limits
- [ ] Add explicit teacher override path
- [ ] Reconcile variable approval caps
- [ ] Keep pricing snapshots consistent with the modularized model

### Target Files

- [ ] `app/forms.py`
- [ ] `app/models.py`
- [ ] `app/routes/admin.py`
- [ ] `app/routes/student.py`
- [ ] `app/utils/economy_balance.py`
- [ ] `app/utils/economy_policy.py`
- [ ] `templates/admin_insurance.html`
- [ ] `templates/admin_edit_insurance_policy.html`
- [ ] `templates/admin_process_claim.html`
- [ ] `templates/student_file_claim.html`
- [ ] `templates/student_insurance_marketplace.html`

### Migration Checklist

- [ ] Diff `g9h0i1j2k3l4_modularize_insurance_products.py` against current v2 schema
- [ ] Diff `h0i1j2k3l4m_add_economy_snapshot_table.py` against the already-landed v2 snapshot path
- [ ] Diff `k1l2m3n4o5p6_add_time_limit_override_to_claims.py` against current v2 claims schema
- [ ] Consolidate all required schema changes into a coherent v2-native migration path
- [ ] Do not cherry-pick the `main` insurance commits independently

### Invariants To Preserve

- [ ] Insurance work must land after or alongside a stable shared-file baseline from Projects 2 and 3.
- [ ] Switching between simple and advanced setup must not drop saved state.
- [ ] Claim time-limit enforcement must use filing-time semantics.
- [ ] Teacher override must be explicit and auditable, not the default path.
- [ ] Insurance pricing surfaces that feed economy logic must stay consistent with the active economy model on v2.

### Tests To Write Or Port

- [ ] Port `tests/test_insurance_modularization.py`
- [ ] Update `tests/test_insurance_snapshots.py`
- [ ] Port claim-gate coverage from `tests/test_insurance_security.py`
- [ ] Update any affected assertions in `tests/test_economy_policy_mode.py`

### Operational Verification

- [ ] Switch simple/advanced policy setup modes without losing saved values
- [ ] Confirm marketplace and claim views show expected modular products and coverage values
- [ ] File claims around the boundary window and confirm filing-time behavior
- [ ] Exercise teacher override and confirm explicit override behavior

### Exit Criteria

- [ ] Both insurance clusters in the reconciliation tracker are landed on v2.
- [ ] Insurance schema path is clean and v2-native.
- [ ] Insurance regressions pass on the v2 branch.

## Project 5: Production Transition Evidence

**Status:** Pre-production required  
**Primary source docs:** `V2_LAUNCH_READINESS_MATRIX`, `V2_PARALLEL_WORKSTREAMS`  
**Why this follows the production-required code waves:** The final production evidence should be recorded against the launch candidate that actually contains the required production ports.

### Scope

- [ ] Execute backup/restore rehearsal on intended production topology
- [ ] Record successful rehearsal in the production-facing artifact set
- [ ] Confirm production transition record includes operator sign-off flow and reopen criteria
- [ ] Resolve any live-test findings touching authorization, migration safety, or financial correctness

### Invariants To Preserve

- [ ] Production evidence must reflect the real launch topology, not only local development assumptions.
- [ ] Findings that affect authorization, migration safety, or money correctness are blocking until resolved.

### Tests / Verification To Run

- [ ] Backup/restore rehearsal evidence review
- [ ] Production runbook dry run against current workflow references
- [ ] Final launch-candidate smoke execution

### Exit Criteria

- [ ] All `V2_LAUNCH_READINESS_MATRIX` pre-production requirements are closed.
- [ ] Backup/restore evidence exists in the repo-facing readiness record or linked operator artifact.

## Project 6: Admin Route Structural Refactor

**Status:** Post-launch structural hardening  
**Primary source docs:** `V2_ADMIN_ROUTE_REFACTOR`, `V2_PARALLEL_WORKSTREAMS`  
**Why deferred:** The source doc marks this as structural, behavior-preserving work that should not be mixed into launch-critical blocker reduction.

### Scope

- [ ] Extract deletion workflows into `services/deletion_service.py`
- [ ] Extract economy logic into `services/economy_service.py`
- [ ] Extract payroll logic into `services/payroll_service.py`
- [ ] Extract scope logic into `services/scope_service.py`
- [ ] Extract roster helpers into `services/roster_service.py`
- [ ] Keep `app/routes/admin.py` as a thin HTTP orchestration layer

### Invariants To Preserve

- [ ] This refactor must not change system behavior.
- [ ] No new business logic should be added to `admin.py`.
- [ ] Refactor steps must preserve behavior, pass tests, and avoid schema changes.

### Tests / Verification To Write Or Run

- [ ] Existing admin route regression suite
- [ ] New service-level unit tests for extracted destructive, economy, payroll, and scope logic
- [ ] Behavioral parity checks for representative admin workflows

### Exit Criteria

- [ ] `admin.py` is materially thinner and mostly HTTP orchestration.
- [ ] High-risk deletion and economy logic lives in services.

## Project 7: Class Scope Normalization And Class-Identity Cleanup

**Status:** Post-launch architecture hardening  
**Primary source docs:** `V2_Class_Scope_Normalization_Target`, `V2_CLASS_ID_INVARIANT_BACKLOG`  
**Why deferred:** The source docs explicitly state this is target-state architecture and should not be folded into live-test port work.

### Scope

- [ ] Normalize internal class-scoped tables toward `class_id`
- [ ] Restrict `join_code` to public entry/display and `join_code -> class_id` resolution
- [ ] Remove `teacher_id` fan-out shortcuts for class-scoped data access
- [ ] Migrate session/runtime context from `current_join_code` to `current_class_id` when ready
- [ ] Remove lifecycle semantics that imply `active` / `inactive` / `archived` class worlds
- [ ] Rework cleanup logic that still keys off labels or teacher-wide groupings instead of surviving class associations

### Invariants To Preserve

- [ ] `class_id` either exists or never existed.
- [ ] `join_code` is the public entry point, not the long-term internal scoping key.
- [ ] Labels such as block/period/section/display name are metadata, not identity.
- [ ] A student exists in a class only if that student has a valid association with that class universe.
- [ ] Student-in-class state is limited to unclaimed or claimed.
- [ ] Deletion from a `class_id` erases the participant from that universe as if they never existed there.
- [ ] If a student loses the last remaining class association, the student is erased from the system.

### Tests To Write

- [ ] Single-class query tests driven by `class_id`
- [ ] Teacher-wide multi-class lookup tests that first resolve active `class_id` set
- [ ] Session-context tests for `current_class_id` enforcement
- [ ] Deletion/cleanup tests for last-association erasure semantics
- [ ] Fixtures cleanup to remove impossible lifecycle worlds

### Exit Criteria

- [ ] `class_id` is the canonical internal scoping key across normalized paths.
- [ ] `join_code` has been reduced to user-facing/public resolution roles.
- [ ] Lifecycle-state compatibility shims no longer define runtime behavior.

## Project 8: Backwards Compatibility And Schema Cleanup

**Status:** Post-launch cleanup  
**Primary source docs:** `V2_BACKWARDS_COMPATIBILITY_CLEANUP`, `LEGACY_SCHEMA_ANALYSIS`  
**Why deferred:** Most of this cleanup is safe only once launch work is stable and any still-needed transitional paths have been revalidated.

### Scope

- [x] Remove `Admin.username` legacy plaintext username column once modern identifier audit supports it
- [ ] Remove legacy username validator and lookup fallback
- [ ] Remove `TeacherBlock.dob_sum` compatibility shim
- [ ] Remove `StudentTeacher.admin_id` synonym
- [ ] Remove `Student.has_completed_profile_migration` if still unused
- [ ] Drop `deletion_requests` table and model if still truly unused
- [ ] Update misleading comments that call active hashes or logic “legacy” when they are still runtime-critical

### Invariants To Preserve

- [ ] Do not remove active claim or recovery mechanisms just because comments label them legacy.
- [ ] `students.first_half_hash` and `students.second_half_hash` stay until the active identity model replaces them.
- [ ] Nullable schema fields that encode intended defaults are not cleanup targets by default.

### Tests To Write Or Refresh

- [ ] Authentication lookup coverage for modern teacher identifiers
- [ ] Student claim/account reuse coverage that still depends on hash fields
- [ ] Deletion workflow coverage if `deletion_requests` is removed
- [ ] Model and fixture cleanup tests after synonym/shim removal

### Exit Criteria

- [ ] Compatibility code removed is truly unused on the active runtime path.
- [ ] Remaining “legacy” labels in code/docs distinguish between deprecated and still-active transitional behavior.

## Project 9: Long-Term Identity-Model Convergence

**Status:** Post-launch / future architecture  
**Primary source docs:** `V2_STUDENT_IDENTITY_ARCHITECTURE`, `TABLE_CONSOLIDATION_ANALYSIS`  
**Why included here:** These docs define the intended end-state so launch work does not accidentally move away from it.

### Target Model

- [ ] User = credential identity
- [ ] Class = economic universe container
- [ ] Seat = actor in class universe
- [ ] Economic activity attaches to `seat_id`
- [ ] Recovery targets users, not seats
- [ ] Role is seat-scoped, not user-scoped

### Planning Checklist

- [ ] Keep roster-created pending participants modeled as seats, not a separate staging object
- [ ] Preserve duplicate-on-paper-only handling via seat-local dedupe code
- [ ] Plan for one-profile-per-seat display identity
- [ ] Plan for seat-local claim data and class-local uniqueness constraints
- [ ] Treat current student/teacher-block/student-block/student-teacher separation as intentional until the actual replacement wave is designed

### Invariants To Preserve

- [ ] If the seat exists, the participant exists in that class universe.
- [ ] A seat belongs to exactly one class.
- [ ] A user may own multiple seats.
- [ ] Delete last seat for a user and the user becomes eligible for garbage collection.
- [ ] Existence of rows defines reality.

### Tests To Write When This Work Starts

- [ ] Seat claim resolution tests keyed by `class_id` plus roster fingerprint
- [ ] Duplicate-with-dedupe-code tests
- [ ] Multi-seat-per-user recovery tests
- [ ] Seat-scoped role/permission tests
- [ ] Seat-linked economy ledger tests

## Launch Gate Checklist

### Must Be Complete Before Live Test

- [x] Project 1 complete
- [x] Project 2 complete
- [x] Readiness matrix reflects only intentional open items

### Must Be Complete Before Production

- [ ] Project 3 complete
- [ ] Project 4 complete
- [ ] Project 5 complete

### Explicitly Deferred Until After Launch

- [ ] Project 6
- [ ] Project 7
- [x] Project 8
- [ ] Project 9

## Notes For Execution

- [ ] Treat Projects 1 and 2 as the only true pre-live-test gates unless scope is explicitly re-opened.
- [ ] Treat Project 4 as one coordinated insurance wave, not independent cherry-picks.
- [ ] Keep shared-file ownership clear when multiple threads are active, especially for `app/routes/admin.py`, `app/routes/student.py`, `app/models.py`, and economy helpers.
- [ ] If a historical or deferred doc becomes active scope again, update this checklist and the readiness matrix in the same change.
- [ ] Use `SOP-DEV-001` as the sequencing rule: launch stabilization first, post-launch architecture second.

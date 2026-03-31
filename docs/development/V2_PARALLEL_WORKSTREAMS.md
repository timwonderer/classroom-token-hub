# V2 Parallel Workstreams

**Last Updated:** 2026-03-29
**Purpose:** Break the v2.0 reconciliation and launch-readiness program into parallelizable workstreams with clear file ownership, dependencies, and outputs.

This document is the execution map for running multiple v2 threads at the same time. It complements:

- `docs/development/V2_MAIN_RECONCILIATION_TRACKER.md`
- `docs/development/V2_LAUNCH_READINESS_MATRIX.md`
- `docs/development/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`

## Coordination Rules

1. One thread owns one write set.
2. Shared files must have a single named owner at a time.
3. Threads should land into separate branches and merge only after branch-specific verification.
4. When a workstream depends on another, it can prepare analysis and tests in parallel but should not finalize code before the dependency lands.
5. `DEVELOPMENT.md`, `README.md`, and top-level launch docs should be edited only by the documentation/operations thread unless explicitly reassigned.

## Recommended Thread Set

### Thread 1: Economy Policy and Rent-Cycle Corrections

**Goal**

Port the `main`-only economy-policy, rebalance-timing, rent-locking, and penalty-reversal deltas required before live testing.

**Primary source cluster**

- Economy policy scheduling and rent-cycle locking

**Owned files**

- `app/routes/admin.py`
- `app/routes/student.py`
- `app/utils/economy_balance.py`
- `app/utils/economy_policy.py`
- `app/utils/economy_rebalance.py`
- `templates/admin_economy_health.html`
- `templates/admin_rent_settings.html`
- `static/js/economy-balance.js`

**Deliverables**

- v2-native code port for economy/rent correctness
- any required v2 migration for CWI warning bypass fields
- updated economy/rent tests

**Required verification**

- `tests/test_economy_policy_mode.py`
- `tests/test_rent_penalty_reversal.py`
- related economy API and rent-display coverage

**Dependencies**

- None for implementation start
- Coordinate migration naming with Thread 2 if both add new revisions

### Thread 2: Idempotency, Waivers, Settlement, and Banking Safety

**Status**

Completed and merged into `codex/v2.0` on 2026-03-30.

**Goal**

Port the live-test-critical transaction-idempotency, frozen analytics payloads, waiver-scope, perk-suppression, settlement, and related banking fixes from `main`.

**Primary source clusters**

- Transaction idempotency and frozen analytics payloads
- Rent waivers, perk suppression, pending-transaction settlement, and sysadmin logging fixes

**Owned files**

- `app/routes/api.py`
- `app/utils/transaction_idempotency.py`
- `app/utils/banking.py`
- `app/utils/store.py`
- `app/routes/system_admin.py`
- `scripts/settle_pending_transactions.py`
- `templates/student_rent.html`
- `templates/student_shop.html`

**Shared-file rule**

- `app/routes/admin.py` and `app/routes/student.py` remain owned by Thread 1 while both threads are active.
- Thread 2 can prepare patch notes for route changes, but final integration into those files should happen through Thread 1 or after Thread 1 lands.

**Deliverables**

- idempotency helper and route integration plan
- v2-native schema updates for idempotency key and analysis payload if needed
- settlement script port
- updated waiver and banking tests

**Required verification**

- `tests/test_transaction_idempotency.py`
- `tests/test_add_rent_waiver_route.py`
- `tests/test_banking_core.py`
- `tests/test_decimal_precision.py`
- `tests/test_void_transaction_rules.py`
- `tests/test_sysadmin_grafana_auth.py`

**Dependencies**

- Coordinate with Thread 1 before touching shared admin/student routes
- May land helper modules and migrations ahead of final route wiring if that reduces conflicts

### Thread 3: Live-Test and Production Operations

**Goal**

Close the non-code launch blockers: migration rehearsal, smoke-route ownership, runbook completeness, and evidence capture.

**Primary source areas**

- `SOP-DEP-022`
- `SOP-DEP-023`
- `SOP-DB-009`
- `V2_LAUNCH_READINESS_MATRIX`

**Owned files**

- `DEVELOPMENT.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-009_Migration_Compliance_Review.md`
- `docs/development/V2_LAUNCH_READINESS_MATRIX.md`

**Deliverables**

- named smoke-route ownership model
- runbook completion fixes
- documented rehearsal record template
- updated blocker status in the readiness matrix

**Required verification**

- doc review against current branch and runbook commands
- operator confirmation once rehearsal is executed

**Dependencies**

- Can start immediately
- Final blocker closure depends on Threads 1 and 2 landing and being validated

### Thread 4: Insurance Reconciliation Wave

**Goal**

Handle the production-required insurance backlog as a dedicated wave, separate from live-test blocker work.

**Primary source clusters**

- Insurance modularization and tiered setup flow
- Insurance pricing snapshots, approval caps, and claim time-limit gate

**Owned files**

- `app/forms.py`
- `templates/admin_insurance.html`
- `templates/admin_edit_insurance_policy.html`
- `templates/admin_process_claim.html`
- `templates/student_file_claim.html`
- `templates/student_insurance_marketplace.html`
- `tests/test_insurance_modularization.py`
- `tests/test_insurance_snapshots.py`
- `tests/test_insurance_security.py`

**Shared-file rule**

- `app/models.py`, `app/routes/admin.py`, `app/routes/student.py`, `app/utils/economy_balance.py`, and `app/utils/economy_policy.py` overlap other threads.
- Treat this thread as analysis-first until Threads 1 and 2 land, then rebase and integrate the shared-file changes in one pass.

**Deliverables**

- final insurance port spec against current v2 schema
- v2-native insurance migrations
- coordinated code port for policy setup, pricing snapshots, and claim gating

**Required verification**

- full insurance test wave
- regression coverage for claim filing-time behavior and teacher override path

**Dependencies**

- Strong dependency on Threads 1 and 2 for shared economy/admin surfaces

### Thread 5: Secondary Product and Security Fixes

**Goal**

Port the lower-conflict, production-required items that are outside the live-test blocker wave.

**Primary source clusters**

- Transfer submission hardening
- Maintenance workflow security fix
- Teacher announcement visibility and v1 sunset messaging
- Collective goal reactivation instance codes

**Owned files**

- `.github/workflows/deploy.yml`
- `.github/workflows/toggle-maintenance.yml`
- `templates/admin_dashboard.html`
- `docs/index.html`
- `templates/layout_student.html`
- `templates/student_transfer.html`
- `tests/test_transfer_legacy_transactions.py`
- `tests/test_feature_flag_enforcement.py`
- `tests/test_collective_goal_expiration.py`

**Shared-file rule**

- `app/routes/admin.py`, `app/routes/student.py`, `app/routes/api.py`, `app/models.py`, and `app/utils/store.py` overlap other workstreams.
- Workflow and docs-site changes can land immediately.
- Collective-goal and transfer code should wait until Thread 1 route churn settles.

**Deliverables**

- cherry-picked workflow hardening
- transfer and announcement fixes integrated into v2
- collective-goal reactivation fix once shared files are clear

**Required verification**

- workflow review
- transfer tests
- announcement smoke check
- collective-goal regression test

**Dependencies**

- Workflow work: none
- Application-code portions: depends on Thread 1 stabilizing shared route files

### Thread 6: Documentation Compliance and Historical Cleanup

**Goal**

Keep active docs aligned with v2 while other threads are shipping code.

**Primary source areas**

- `V2_DOCUMENTATION_COMPLIANCE_SWEEP`
- `LOG-ARC-049`
- documentation index and active top-level docs

**Owned files**

- `README.md`
- `docs/LOGS/AUDITS/LOG-ARC-049_V2_Multitenancy_Go_No_Go_Checklist.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-002_Documentation_Index.md`
- `docs/development/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`
- `docs/development/V2_PARALLEL_WORKSTREAMS.md`

**Deliverables**

- active-doc index updates
- supersession notes for historical docs where needed
- ongoing documentation status updates as code threads land

**Required verification**

- active-doc link review
- terminology check against current v2 authority model

**Dependencies**

- Can start immediately
- Final cleanup pass depends on code threads finishing

## Merge Order

Recommended merge order to minimize conflicts:

1. Thread 6 documentation index and supersession updates
2. Thread 3 operations/runbook updates
3. Thread 1 economy policy and rent-cycle corrections
4. Thread 2 idempotency, waivers, settlement, and banking safety
5. Thread 5 workflow hardening and low-conflict production fixes
6. Thread 4 insurance reconciliation wave
7. Thread 5 shared-file application changes that were deferred until after Threads 1 and 2

## Fast-Start Assignment

If only three threads are available, use this split:

1. Thread A: Threads 1 and 2 combined, with a single owner for `app/routes/admin.py` and `app/routes/student.py`
2. Thread B: Thread 3 plus Thread 6
3. Thread C: Thread 5 immediate work, then Thread 4 insurance analysis while waiting on shared files

If five or more threads are available, use the full thread set above.

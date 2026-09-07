# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-08-06
**Current Released Version:** 1.9.0
**Engineering State:** v2.0 with 3 domains Phase 10 certified (Identity, Obligations, Store)
**Active Integration Branch:** `main`

## Quick Links

- **[Production Readiness 2026-09](docs/TRACKING/PRODUCTION_READINESS_2026-09.md)** - The tracker of record: launch blockers, open defects, and readiness status
- **[Core Invariants](docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** - Non-negotiable system laws
- **[Capability-Based Architecture and Authority Model](docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** - System design, the `INV → DOM → FEAT` hierarchy, and where authority lives
- **[Documentation Index](docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-002_DOCUMENTATION_INDEX.md)** - Full map of every live document by namespace
- **[Class Scope Normalization Target](docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md)** - Deferred post-port target for `class_id`-first internal scoping
- **[v2 Live-Test Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md)** - Internal validation workflow before live testing
- **[Design Principles & Project History](docs/PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md)** - Why the system is shaped the way it is

> [!NOTE]
> The former quick links to the v2 reconciliation tracker, launch readiness matrix, documentation
> compliance sweep, parallel workstreams map, banking ledger settlement plan, `class_id` invariant
> backlog, and the `ARC-*` architecture/schema/API guides all resolved into `docs/archive/` or to
> paths that no longer exist. Superseded material is not a quick link. Launch status now lives in
> the readiness tracker above; architecture lives in `docs/INVARIANT/`; schema truth lives in
> `app/models.py` and `migrations/`.

## Branch and Database Truth

- `main` is the active protected branch and carries v2. It is the same branch that older
  documents and CHANGELOG entries call `codex/v2.0` and then `CTH_v2.0`; both names were
  retired and no ref by either exists locally or on the remote. Read historical references
  accordingly rather than looking for a second branch.
- The v1 `main` that preceded this was renamed on 2026-09-07 and now lives at
  `main_legacy_v1.10.0`. It was 1053 commits behind. The separate `legacy_v1.10.0` ref no
  longer exists; its tip (`1f7bfeb40`) is contained in `main_legacy_v1.10.0`, which is the
  superset of the two, so **`main_legacy_v1.10.0` is the single ref carrying the v1 line**.
  All `v1.*` tags remain. CHANGELOG entries that say "never merge to `main`" describe the
  former v1 branch, not this one.
- Dev and migration work must use the team-configured v2 dev database.
- Test runs must use the team-configured PostgreSQL test database.
- The validated v2 branch state passed:
  - `DATABASE_URL=<team-test-db-url> pytest -q`
  - Result: `708 passed, 1 skipped`

## Git Hooks

Run once after clone:

```bash
./scripts/setup-hooks.sh
```


## Current v2.0 State

### Ready Now

- **Identity Domain Phase 10 Certified** (2026-08-06): DOM-IDEN-001/002/003/006 complete with full Phase 5-7 view model wiring. IdentityProfileView wired to student_detail surface. Phase 9 legacy sweep confirmed no dead code. Audit: `docs/TRACKING/SOP-DEV-002a_IDENTITY_20260806_AUDIT.md`.
- **Obligations Domain Phase 10 Certified** (2026-08-04): DOM-OBL-001 complete with immutable view models (StudentObligationView, ClassObligationSummary) and full Phase 6-7 surface integration. Audit: `docs/TRACKING/OBLIGATION_DOMAIN_QA_AUDIT_AUG_2026.md`.
- **Store Domain Phase 10 Certified** (2026-08-04): DOM-STORE-001, FEAT-STOR-001 (purchase), FEAT-STOR-002 (lifecycle transition), FEAT-STOR-003 (insurance claims), and FEAT-STOR-004 (direct grant) fully implemented, tested end-to-end, and audited for production readiness.
- **Entitlement Read Service**: Canonical read operations for entitlements, purchase counts, and active grants implemented in `app/services/entitlement_read_service.py`.
- **Product Policy Resolver**: `app/services/store_policy_resolver.py` provides policy resolution and payload schema validation per SPEC-STORE-001.
- **View Model Builders**: Obligation view models and class obligation summaries implemented in `app/services/obligation_view_model.py`.
- `classes.class_id` is the canonical class boundary; `join_code` is a public alias.
- `Seat + Class` is the runtime class-scoped authority for student/admin/API flows.
- Legacy `ClassMembership`, `student_teachers`, and principal columns may still support compatibility paths, but they are not the identity or class-boundary authority.
- Branch consolidation is complete: prior merge-prep branches were folded into `codex/v2.0` and pruned.
- Migration heads are resolved in repo with `e8f1a2b3c4d5_merge_remaining_v2_heads.py`.
- Full-suite validation succeeded on the PostgreSQL test database.
- Economy policy scheduling, rebalance timing, rent-cycle locking, penalty-reversal corrections, transaction idempotency, frozen economy snapshots, waiver scope, settlement safety, and related sysadmin auth/logging fixes have landed on `codex/v2.0`.
- Wave 7 rent-waiver actor attribution is now seat-scoped, and rent-waiver add/remove flows no longer emit legacy analytics rows; the analytics schema still needs its own seat-scoped cutover before those annotations return.
- Pricing recommendation logic is now centralized in `app/utils/economy_policy.py`, with the checker, rebalance preview, economy APIs, and insurance setup/edit pages consuming that shared source instead of duplicating pricing math.

### Required Before Live Testing

- Publish and review the v2 live-test runbook with operator ownership.
- Refresh migration-compliance status so current exceptions are explicit and not buried in historical audit language.
- Rehearse migration upgrade flow on the v2 dev database with operator-facing verification steps.
- Complete smoke-route checklist and confirm it can be executed by someone who did not author the branch.
- Remove or supersede stale docs that still imply deleted branches or legacy TeacherBlock fallback plans.
- Confirm whether the remaining adjacent economy-health delta from the v1 line (CWI warning bypass controls) is needed before live testing or can move to the post-live-test/production lane.
- Port launch-critical v1-line deltas. These are measured against `main_legacy_v1.10.0`, not against
  `main` — `main` now carries v2 itself, so a "port from `main`" instruction reads as porting a
  branch into itself. The v2 reconciliation tracker that enumerated them is
  archived (`docs/archive/v1-development/tracking/V2_MAIN_RECONCILIATION_TRACKER.md`, superseded);
  the surviving open items are carried in `docs/TRACKING/PRODUCTION_READINESS_2026-09.md`.
- Close the open documentation-compliance items now tracked in
  `docs/TRACKING/PRODUCTION_READINESS_2026-09.md`. The v1 sweep that originated them is archived
  (`docs/archive/v1-development/tracking/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`, superseded).

### Required Before Production

- Complete the v2 production transition runbook and sign-off workflow.
- Re-audit rollback expectations for migrations that are forward-safe but not business-safe to downgrade after live data changes.
- Finish operator backup/restore rehearsal on the intended production topology.
- Confirm monitoring, maintenance-mode usage, and post-deploy verification steps are current.
- Port production-required v1-line deltas (against `main_legacy_v1.10.0`) still marked open in the reconciliation tracker.

## Operations Doc Boundaries

- This branch now carries only launch-critical v2 runbook fixes needed for live testing and production transition.
- Deeper operations-document restructuring, route-taxonomy cleanup, and architecture-driven SOP rewrites are intentionally deferred until after `docs/SPECS/V2_ADMIN_ROUTE_REFACTOR.md` and `docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md` are ready to land.
- Until those refactors land, prefer targeted supersession notes, explicit operator record templates, and current-command verification over broad documentation reorganization.

### Post-Live-Test Cleanup

- Broader historical audit cleanup and supersession notes.
- Lower-priority guide refreshes where wording is stale but not dangerous.
- Compatibility shim reduction for legacy aliases that still exist only to ease migration or testing.
- Class-scope normalization project to move internal scoping from `join_code` to `class_id`.
- Banking ledger rebuild project to move financial authority to `class_id + seat_id + account_type` with explicit available/current balance semantics.
- Class-identity invariant cleanup that removes pseudo-lifecycle semantics from class and membership layers.

## v2.0 Technical Direction

- `users.id` is the authentication principal; legacy role-specific session keys are route compatibility shadows only.
- `seats.id` plus `classes.class_id` is the class-scoped runtime authority.
- `join_code` is a public class alias and must resolve to `class_id` before authority-sensitive work.
- Class-scoped reads and writes are seat/class-gated, not `teacher_id`-, `student_id`-, block-, or `TeacherBlock`-gated.
- Public actor identity uses UUID-encoded `Seat.public_id`, not role-specific public-ID families.
- Roster upload provisions an inactive `User`, class-local `Seat`, seat-bound `IdentityProfile`, and seat-owned claim artifacts; it does not create an authenticated student.
- v2 documentation should not describe TeacherBlock fallback as intended runtime behavior.
- Use `db.session.get(Model, id)`, not `Model.query.get(id)`. Treat `Query.get()` as banned in new development.

## Focus Areas

### High Priority

#### 1. Live-Test Operational Readiness

- Finalize runbooks for v2 live testing and production transition.
- Document migration rehearsal, verification queries, and rollback decision points.
- Confirm maintenance-mode and operator sign-off procedures.

#### 2. Migration and Schema Safety

- Keep migration-head hygiene explicit in docs and deployment instructions.
- Track remaining migration-policy exceptions separately from current v2 merge readiness.
- Publish current migration validation expectations for local, test, and production-like databases.

#### 3. Residual v2 Hardening

- Continue removing compatibility-only assumptions that are no longer part of the v2 runtime contract.
- Audit lower-priority read paths and sysadmin paths for contract clarity and documentation parity.
- Keep “all sections” semantics explicit anywhere teacher-wide fan-out still exists.

### Medium Priority

#### 1. Documentation Consistency

- Keep architecture, SOP, and user guides aligned with `main`.
- Prefer superseding notes on historical audits over rewriting release-history records.

#### 2. Live-Test Feedback Loop

- Capture findings from live testing in the v2 checklist and runbooks.
- Convert any repeated operator questions into permanent SOP updates.

## Release Framing

- Public docs site remains on the current released product line: **1.9.0**.
- Internal engineering docs describe the repo as a **v2.0 live-test candidate**.
- Do not label v2.0 as released until live-test and production transition gates are complete.

# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-03-30
**Current Released Version:** 1.9.0
**Engineering State:** v2.0 live-test candidate
**Active Integration Branch:** `codex/v2.0`

## Quick Links

- **[Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** - System design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** - Current data models and transitional compatibility notes
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** - Runtime contract for public, student, and admin APIs
- **[v2 Checklist](docs/development/multi-tenancy-rebuild/v2_release_checklist.md)** - Live-test and production-readiness checklist
- **[v2 Live-Test Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md)** - Internal validation workflow before live testing

## Branch and Database Truth

- Only `codex/v2.0` is an active protected v2 branch.
- Dev and migration work must use the team-configured v2 dev database.
- Test runs must use the team-configured PostgreSQL test database.
- The validated v2 branch state passed:
  - `DATABASE_URL=<team-test-db-url> pytest -q`
  - Result: `664 passed, 1 skipped`

## Git Hooks

Run once after clone:

```bash
./scripts/setup-hooks.sh
```

This sets `core.hooksPath=hooks` and enables shared repo hooks, including branch-aware DB switching:

- Protected v2 branch: `codex/v2.0` -> `classroom_economy`
- All other branches -> `production_dev`

## Current v2.0 State

### Ready Now

- `ClassEconomy` and `ClassMembership` are live ORM models and DB-backed authority for class scope.
- `join_code` is the runtime class boundary for student/admin/API flows.
- `student_teachers` remains the teacher-student ownership model, but it is not the class-boundary authority.
- Branch consolidation is complete: prior merge-prep branches were folded into `codex/v2.0` and pruned.
- Migration heads are resolved in repo with `e8f1a2b3c4d5_merge_remaining_v2_heads.py`.
- Full-suite validation succeeded on the PostgreSQL test database.
- Economy policy scheduling, rebalance timing, rent-cycle locking, and penalty-reversal corrections have landed on `codex/v2.0`.
- Pricing recommendation logic is now centralized in `app/utils/economy_policy.py`, with the checker, rebalance preview, economy APIs, and insurance setup/edit pages consuming that shared source instead of duplicating pricing math.

### Required Before Live Testing

- Publish and review the v2 live-test runbook with operator ownership.
- Refresh migration-compliance status so current exceptions are explicit and not buried in historical audit language.
- Rehearse migration upgrade flow on the v2 dev database with operator-facing verification steps.
- Complete smoke-route checklist and confirm it can be executed by someone who did not author the branch.
- Remove or supersede stale docs that still imply deleted branches or legacy TeacherBlock fallback plans.
- Finish the remaining live-test economy deltas: transaction idempotency, waiver/perk suppression, settlement handling, and related sysadmin logging fixes.

### Required Before Production

- Complete the v2 production transition runbook and sign-off workflow.
- Re-audit rollback expectations for migrations that are forward-safe but not business-safe to downgrade after live data changes.
- Finish operator backup/restore rehearsal on the intended production topology.
- Confirm monitoring, maintenance-mode usage, and post-deploy verification steps are current.

### Post-Live-Test Cleanup

- Broader historical audit cleanup and supersession notes.
- Lower-priority guide refreshes where wording is stale but not dangerous.
- Compatibility shim reduction for legacy aliases that still exist only to ease migration or testing.

## v2.0 Technical Direction

- `ClassMembership` and `ClassEconomy` are the source of truth for class access.
- `current_join_code` is the selected class context for both teacher and student sessions.
- Class-scoped reads and writes are membership-gated, not `teacher_id`-gated.
- Public teacher identity uses `Admin.public_id` / `teacher_public_id`, not numeric teacher IDs.
- v2 documentation should not describe TeacherBlock fallback as intended runtime behavior.

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

- Keep architecture, SOP, and user guides aligned with `codex/v2.0`.
- Prefer superseding notes on historical audits over rewriting release-history records.

#### 2. Live-Test Feedback Loop

- Capture findings from live testing in the v2 checklist and runbooks.
- Convert any repeated operator questions into permanent SOP updates.

## Release Framing

- Public docs site remains on the current released product line: **1.9.0**.
- Internal engineering docs describe the repo as a **v2.0 live-test candidate**.
- Do not label v2.0 as released until live-test and production transition gates are complete.

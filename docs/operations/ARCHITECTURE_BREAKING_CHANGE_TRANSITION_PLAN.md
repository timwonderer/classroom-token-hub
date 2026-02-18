# Architecture Breaking Change Transition Plan

## Purpose

This runbook defines a low-risk rollout path for a **major architecture-breaking release** when:

1. Existing production data must remain usable after the new architecture ships.
2. Production is not guaranteed to be on the same migration state as this feature branch.
3. Downtime must be minimized and reversible.

The plan follows the repository migration policy and the Expand/Contract model in `docs/development/migration-specifications.md`.

---

## Guiding Principles

1. **Do not assume migration parity.** Treat `production`, `main`, and `feature` as potentially different heads until proven otherwise.
2. **Separate schema change from behavior change.** Deploy additive schema first, then data backfill, then code-path cutover, then cleanup.
3. **Design every step to be idempotent.** Re-runs must be safe.
4. **Protect user experience during risky windows.** Use maintenance mode only for short, irreversible cutovers.
5. **Prefer rollback by feature flag/code path over destructive DB rollback.**

---

## Release Architecture (Recommended)

Use a 4-phase release instead of a single “big bang”.

### Phase A - Baseline Alignment and Diff

Goal: produce a single, shared understanding of current schema states.

- Capture current revisions:
  - `production`: `flask db current` (run in prod env)
  - `main`: `flask db current` against main branch
  - `feature`: `flask db current` against this branch
- Capture heads:
  - `flask db heads` for each environment/branch
- Build a migration matrix:
  - Which revisions are missing from prod vs main vs feature.
  - Which migrations are structural-only vs data-transforming.
- If multiple heads are discovered in the branch, create a merge migration before any new migration work.

**Deliverable:** migration diff table checked into release notes or PR.

### Phase B - Expand (Backward-Compatible Schema)

Goal: introduce the new architecture’s required schema without breaking old code.

- Add new tables/columns/indexes as nullable or optional.
- Keep legacy columns/tables intact.
- Add dual-write support in app logic where needed (legacy + new structures).
- Add integrity check queries and migration guards.

**Must hold true:** current production code still works after this phase.

### Phase C - Data Backfill and Verification

Goal: migrate existing data to the new structure with observability and retry safety.

- Perform backfill in chunks (batch by primary key or time window).
- Store checkpoints (last processed id/timestamp) for resumability.
- Record metrics each batch:
  - rows scanned
  - rows transformed
  - rows skipped
  - validation failures
- Run post-backfill parity checks (legacy vs new aggregates/counts).
- Repeat until parity checks pass at threshold (ideally exact; else documented tolerance).

### Phase D - Controlled Cutover + Contract

Goal: switch read paths to the new architecture with minimal downtime.

- Enable maintenance mode briefly only during hard cutover if needed.
- Switch reads to new schema behind a feature flag.
- Keep dual-write enabled for one full release cycle.
- Monitor errors and domain-specific correctness metrics.
- After stability window, remove legacy read/write paths in code.
- Only then schedule destructive DB contract migrations (drop/rename legacy artifacts).

---

## Detailed Execution Checklist

## 1) Pre-Flight (T-7 to T-2 days)

- [ ] Backup production database and verify restore in staging.
- [ ] Confirm one migration head in feature branch.
- [ ] Confirm feature branch is rebased/merged with latest `main` before creating final migrations.
- [ ] Run a full staging rehearsal with prod-like snapshot.
- [ ] Define SLOs and rollback triggers.

## 2) Migration Drift Reconciliation (T-2 to T-1 days)

When production is behind/different from branch:

- [ ] Create a linear migration path from `production current` to `feature head`.
- [ ] If needed, ship an intermediate “bridge” release from `main` first.
- [ ] Never delete old migration files; create merge/bridge migrations instead.
- [ ] Validate upgrade graph in staging from all expected starting revisions.

## 3) Backfill Dry Run (T-1 day)

- [ ] Run backfill in staging with realistic volume.
- [ ] Measure runtime and lock behavior.
- [ ] Tune batch sizes to avoid long transactions.
- [ ] Validate idempotent re-run behavior.

## 4) Production Rollout (T day)

1. Deploy Expand release (no behavior break).
2. Run backfill job with monitoring.
3. Verify parity checks.
4. Enable maintenance mode (only if required for final atomic switch).
5. Flip read-path feature flag to new architecture.
6. Disable maintenance mode.
7. Keep dual-write on during soak period.

## 5) Post-Deploy (T+1 to T+14 days)

- [ ] Monitor correctness dashboards and error logs.
- [ ] Compare business KPIs before/after cutover.
- [ ] Keep rapid rollback instructions ready.
- [ ] Schedule contract cleanup in a separate release after stability confidence.

---

## Legacy Data Compatibility Strategy

To gracefully handle all existing data:

1. **Canonical mapping table/spec**
   - Define one mapping from legacy entities to new entities (field-by-field).
2. **Null and orphan policy**
   - For every required new field, define fallback source and defaulting rule.
3. **Inconsistent historical data policy**
   - Define deterministic conflict handling (latest-write-wins, priority source, or quarantine).
4. **Auditability**
   - Write migration metadata (source id, transformed at, transform version).
5. **Replay safety**
   - Use UPSERT/merge semantics so reruns do not duplicate records.

---

## Downtime Minimization Tactics

- Prefer online, additive DDL first.
- Avoid table rewrites during peak traffic windows.
- Use chunked backfills with short transactions.
- Gate new reads behind a feature flag.
- Reserve maintenance mode for final irreversible/atomic steps only.
- Announce a maintenance window even if expected downtime is near-zero.

---

## Rollback Strategy

If cutover causes issues:

1. Re-enable legacy read path by feature flag (fast rollback).
2. Keep dual-write active to preserve forward compatibility.
3. Investigate with parity/audit logs.
4. Roll back app release if needed.
5. Perform DB restore only for unrecoverable corruption cases.

---

## Required Artifacts for This Breaking Release

Before approving production rollout, prepare:

1. **Migration state matrix** (`production` vs `main` vs `feature`).
2. **Backfill spec** (algorithm, chunk size, checkpointing, retry behavior).
3. **Parity verification checklist** (counts, sums, critical joins).
4. **Cutover runbook** (minute-by-minute with owners).
5. **Rollback runbook** (flag rollback + app rollback + DB restore criteria).
6. **Communication plan** (internal + user-facing maintenance notice).

---

## Ownership and Sign-Off

Minimum sign-off gates:

- Engineering owner (architecture + migration safety)
- Operations owner (rollout/monitoring readiness)
- Product owner (downtime and user communication)

No production cutover should proceed without all three approvals.

---
title: V2 Multitenancy Go/No-Go Checklist
category: logs
roles: [developer]
description: Historical go/no-go checklist for the v2 multi-tenancy rollout.
---

# LOG-ARC-049: V2 Multitenancy Go/No-Go Checklist

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| LOG-ARC-049 | 1.0 | 2026-03-08 | N/A | Informative |

## I. Purpose

Preserve the historical release-readiness checklist for the v2 multi-tenancy rollout.

## II. Scope

This document is a historical release artifact and does not supersede active SOP runbooks.

## III. Historical Checklist

Date: 2026-03-08
Branch: `codex/v2.0`

## Release Gate

| # | Checklist Item | Status | Pass Criteria | Primary Validation |
|---|---|---|---|---|
| 1 | `ClassEconomy` / `ClassMembership` model parity | Complete | ORM matches active class-economy schema and runtime imports succeed | `app/models.py`, migration review, full suite |
| 2 | Membership gate on class-scoped routes | Complete | Class-scoped admin/student/API routes validate membership or owned join-code scope | Route audit + tenancy suites |
| 3 | Query inversion complete for recent hardening scope | Complete | Active class decisions no longer depend on `TeacherBlock`, `teacher_id`, or `block` as access-control authority | Code sweep + regression tests |
| 4 | No class-scoped `join_code IS NULL` fallback paths in live v2 flows | Complete | Student settings/purchase flows return scoped values or defaults, not null-join-code blends | `tests/test_settings_fallback_removal.py` |
| 5 | Public teacher identity is non-numeric | Complete | Public teacher-facing verification uses `Admin.public_id` / `teacher_public_id` instead of numeric IDs | API tests + route inspection |
| 6 | Join-code deletion guardrails and cleanup | Complete | Destructive class deletion requires confirmation and cleans the tenant boundary | deletion tests + route tests |
| 7 | DB check constraints on `ClassMembership` | Complete | XOR and role/status consistency enforced at DB layer | migration review + tests |
| 8 | Remaining v2 migration heads resolved | Complete | Repo contains a single coherent merge path for current heads | migration graph review |
| 9 | Full PostgreSQL suite green on v2 branch | Complete | `pytest -q` passes on `classroom_economy_test` | `664 passed, 1 skipped` |
| 10 | Live-test runbook published | Complete | Internal operator workflow exists for migration rehearsal, smoke checks, and rollback decisions | `SOP-DEP-022` |
| 11 | Production transition runbook published | Complete | Production transition workflow exists with maintenance mode, backup, and sign-off steps | `SOP-DEP-023` |
| 12 | Branch/database switching docs current | Complete | Docs describe `codex/v2.0` as the only active protected branch and distinguish dev vs test DBs | SOP update |
| 13 | Migration compliance status current | In Progress | Historical audit is superseded by current status and remaining exceptions | `SOP-DB-009` |
| 14 | Archived economy read-only policy | Not Started | Archived economies have explicit documented and tested runtime policy | contract doc + tests |
| 15 | Full sysadmin tenancy audit | Not Started | `system_admin.py` routes are reviewed against v2 join-code contract | route audit matrix |
| 16 | Global-balance property deprecation cleanup | Not Started | Legacy aggregate convenience properties are either retired or fully documented as transitional only | code/doc review |
| 17 | Economy/rent correction wave from main | In Progress | Rebalance timing, rent-cycle locking, penalty reversal, and shared insurance recommendation sourcing are implemented on `codex/v2.0`; remaining live-test economy deltas stay visible | `app/utils/economy_policy.py`, `app/utils/economy_rebalance.py`, `tests/test_economy_policy_mode.py`, `tests/test_rent_penalty_reversal.py` |

## Readiness Artifact

### Ready Now

- Validated branch consolidation is complete and only `codex/v2.0` remains active.
- Full suite result on PostgreSQL test DB is `664 passed, 1 skipped`.
- Current class authority is `ClassMembership` + `ClassEconomy`, with `current_join_code` as active session context.
- Migration heads are resolved in repo with the current merge migration.
- The first `origin/main` economy/rent reconciliation wave is landed on `codex/v2.0`, including rent-cycle locking, penalty reversal, and shared insurance recommendation sourcing.

### Must Finish Before Live Testing

- Finish the migration compliance refresh so current exceptions are explicit and actionable.
- Execute the v2 live-test runbook end-to-end on the dev/migration database and record the result.
- Confirm smoke-route checklist ownership and sign-off path.
- Complete a final stale-reference sweep to ensure no living docs still imply deleted branches or fallback design.

### Can Wait Until After Live Testing

- Broad historical audit cleanup and supersession notes.
- Lower-priority user guide polish beyond the currently corrected flows.
- Further compatibility-shim reduction where behavior is already correct but documentation still carries transitional notes.

## Remaining Work by Phase

### Required Before Live Testing

1. Rehearse migration upgrade and verification on the team-configured v2 dev/migration database.
2. Close the migration-compliance status gap with a current exception list and owner.
3. Run the live-test smoke checklist from the new runbook and capture results.

### Required Before Production

1. Finalize production backup, maintenance-mode, and rollback rehearsal.
2. Complete operator sign-off flow in the production transition runbook.
3. Resolve any issues discovered during live testing that affect migration, authorization, or data integrity.

### Post-Live-Test Cleanup

1. Continue sysadmin route audit and lower-priority query inversion cleanup.
2. Clarify archived-economy behavior and complete remaining compatibility cleanup.
3. Consolidate or supersede stale historical audit notes with cross-links to current SOPs.

## Deferred Main-Branch Feature Reconciliation

Track features present on `origin/main` but not yet intentionally reconciled into `codex/v2.0`. This is separate from v2 stabilization so feature divergence stays visible without obscuring readiness gates.

| Source | Feature / Commit | Classification | Status | Notes |
|---|---|---|---|---|
| `origin/main` | `589d6ba7` - economy policy mode and rebalance hardening (`#1077`) | Must evaluate before production | Partially Completed | Core economy/rent corrections and shared insurance recommendation sourcing are now on `codex/v2.0`. Remaining live-test economy deltas still include idempotency and waiver/settlement follow-up from later `main` commits. |

### Reconciliation Workflow

1. Diff `origin/main...codex/v2.0` before each major v2 milestone.
2. Group unique `origin/main` commits by feature, not by file count.
3. Classify each as:
   - must-port before live testing
   - must-port before production
   - safe to defer
4. Record owner, source commit/PR, and merge strategy before implementation starts.

# V2 Launch Readiness Matrix

**Last Updated:** 2026-03-31
**Scope:** `codex/v2.0` live-test candidate readiness, informed by the active v2 runbooks, migration review, historical checklist, and the main-reconciliation tracker.

## Status Vocabulary

- `done`
- `needs refresh`
- `blocked`
- `defer until post-live-test`

## Readiness Matrix

| Area | Status | Evidence source | Current state | Completion criterion |
|---|---|---|---|---|
| Branch and database truth | `done` | `DEVELOPMENT.md`, `README.md`, git branch state | Active v2 branch is `codex/v2.0`; docs distinguish v2 dev DB vs test DB | Keep current unless branch strategy changes |
| Main-branch feature reconciliation tracker | `done` | `docs/development/V2_MAIN_RECONCILIATION_TRACKER.md` | All sampled `origin/main` feature clusters are now tracked and classified | Revisit before each major v2 milestone |
| Migration compliance summary | `needs refresh` | `SOP-DB-009_Migration_Compliance_Review.md` | Summary now includes the 2026-03-30 local rehearsal evidence and the restored PostgreSQL baseline on 2026-03-31, but still needs the named operator record and either an independent verifier record or a documented solo-operator exception | Attach named operator confirmation, independent verifier confirmation or solo-operator exception record, and final rehearsal artifact |
| Live-test migration rehearsal | `needs refresh` | `SOP-DEP-022_V2_Live_Test_Runbook.md` | 2026-03-30 rehearsal reached `q9r0s1t2u3v4 (head)` before and after upgrade on the configured dev DB; PostgreSQL validation is now green again, so the remaining step is operator-owned smoke execution and sign-off | Record smoke execution outcome and named sign-off in the rehearsal artifact |
| Smoke-route checklist ownership | `needs refresh` | `SOP-DEP-022`, `DEVELOPMENT.md` | Smoke-route ownership model is now documented, but the specific named operator and either an independent verifier or a solo-operator exception record are still pending execution | Record named owners and execution outcome in the rehearsal artifact |
| PostgreSQL validation baseline | `done` | `DEVELOPMENT.md`, `README.md`, `SOP-DB-009` | Latest local PostgreSQL validation on 2026-03-31 passed with `708 passed, 1 skipped` on the configured test DB | Re-run only if launch-critical changes land before live testing |
| Economy/rent launch-critical main deltas | `needs refresh` | `docs/development/V2_MAIN_RECONCILIATION_TRACKER.md` | The major live-test economy/rent wave has landed on `codex/v2.0`; confirm whether the remaining adjacent CWI warning-bypass delta stays pre-live-test or moves later | Refresh the tracker/readiness docs and leave only intentional open items |
| Production transition runbook completeness | `done` | `SOP-DEP-023_V2_Production_Transition_Runbook.md` | Runbook now has named operator roles, current workflow references, launch-critical smoke coverage, and a production transition record template | Revisit only if deployment workflow or maintenance controls change materially |
| Backup and restore rehearsal | `blocked` | `SOP-DEP-023`, `SOP-DEP-016`, operator process | Required by docs but not evidenced in repo-facing readiness artifacts | Record successful rehearsal on intended topology |
| Maintenance-mode and deploy workflow safety | `needs refresh` | `SOP-DEP-023`, `.github/workflows/*`, reconciliation tracker | Workflow fix exists on `main` and is still pending on v2 | Port workflow fix and verify maintenance toggling path |
| Announcement visibility fix | `needs refresh` | reconciliation tracker | Teacher-facing announcement fix exists on `main`, not yet reconciled | Port and verify dashboard rendering |
| Sysadmin tenancy audit | `defer until post-live-test` | `LOG-ARC-049` | Still tracked as unfinished historical follow-up | Convert to active audit if live testing exposes a concrete gap |
| Archived-economy read-only policy | `defer until post-live-test` | `LOG-ARC-049` | Still undocumented as a final runtime contract | Publish policy before production only if the feature remains active scope |
| Active-doc v2 compliance sweep | `needs refresh` | `docs/development/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md` | Initial sweep and top-level fixes are in place; broader active-doc verification remains open | Close all `needs update` items in the sweep doc |
| Operations doc restructuring | `defer until post-live-test` | `DEVELOPMENT.md`, `SOP-DEP-022`, `SOP-DEP-023`, `SOP-DB-009` | Launch-critical runbook fixes are in scope now; broader SOP taxonomy and architecture-driven rewrite work is intentionally deferred until the admin-route and class-scope refactors land | Re-open after `V2_ADMIN_ROUTE_REFACTOR` and `V2_Class_Scope_Normalization_Target` are validated |

## Pre-Live-Test Blockers

These items must be closed before treating `codex/v2.0` as ready for live testing:

1. Complete the v2 dev/migration database rehearsal artifact from `SOP-DEP-022` with named operator confirmation and either independent verifier confirmation or a documented solo-operator exception.
2. Refresh the reconciliation tracker so only intentional pre-live-test deltas remain open.
3. Record smoke-route execution outcome with named operator ownership now that automated validation is green.
4. Close active-doc issues still marked `needs update` in the documentation sweep.

## Pre-Production Requirements

These can follow live testing, but must be complete before a v2 production launch:

1. Port the production-required `origin/main` deltas:
   - insurance modularization and tiered setup flow
   - insurance pricing snapshots, approval caps, and claim time-limit gate
   - collective goal reactivation instance codes
   - transfer submission hardening
   - maintenance workflow security fix
   - teacher announcement visibility fix
2. Execute backup/restore rehearsal on the intended production topology.
3. Record operator sign-off flow and reopen criteria in the production transition record.
4. Resolve any live-test findings that touch authorization, migration safety, or financial correctness.

## Nice-to-Have Cleanup

These are explicitly non-blocking under the current standard unless re-scoped:

- support/store UX polish from `main`
- observer-account and decision-history follow-up work
- safe dependency-upgrade wave
- broader historical audit cleanup beyond active-doc supersession notes

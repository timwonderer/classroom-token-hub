# V2 Launch Readiness Matrix

**Last Updated:** 2026-03-30
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
| Migration compliance summary | `needs refresh` | `SOP-DB-009_Migration_Compliance_Review.md` | Current-state summary exists, but it still points to execution work not yet recorded | Attach actual rehearsal evidence and remaining-exception owner |
| Live-test migration rehearsal | `blocked` | `SOP-DEP-022_V2_Live_Test_Runbook.md` | Runbook exists, but repo docs do not record a completed rehearsal on the team dev/migration DB | Capture before/after head state, upgrade result, and smoke status |
| Smoke-route checklist ownership | `needs refresh` | `SOP-DEP-022`, `DEVELOPMENT.md` | Smoke routes are listed, but owner and sign-off path are not captured in a single status artifact | Assign operator owner and record execution outcome |
| PostgreSQL validation baseline | `needs refresh` | `DEVELOPMENT.md`, `README.md`, `LOG-ARC-049` | Baseline remains `664 passed, 1 skipped`, but it predates this reconciliation wave | Re-run after each must-port implementation wave |
| Economy/rent launch-critical main deltas | `needs refresh` | `docs/development/V2_MAIN_RECONCILIATION_TRACKER.md` | The major live-test economy/rent wave has landed on `codex/v2.0`; confirm whether the remaining adjacent CWI warning-bypass delta stays pre-live-test or moves later | Refresh the tracker/readiness docs and leave only intentional open items |
| Production transition runbook completeness | `needs refresh` | `SOP-DEP-023_V2_Production_Transition_Runbook.md` | Runbook exists, but owner/sign-off detail and scope needed cleanup | Keep scope/dependencies explicit and attach operator sign-off record |
| Backup and restore rehearsal | `blocked` | `SOP-DEP-023`, `SOP-DEP-016`, operator process | Required by docs but not evidenced in repo-facing readiness artifacts | Record successful rehearsal on intended topology |
| Maintenance-mode and deploy workflow safety | `needs refresh` | `SOP-DEP-023`, `.github/workflows/*`, reconciliation tracker | Workflow fix exists on `main` and is still pending on v2 | Port workflow fix and verify maintenance toggling path |
| Announcement visibility fix | `needs refresh` | reconciliation tracker | Teacher-facing announcement fix exists on `main`, not yet reconciled | Port and verify dashboard rendering |
| Sysadmin tenancy audit | `defer until post-live-test` | `LOG-ARC-049` | Still tracked as unfinished historical follow-up | Convert to active audit if live testing exposes a concrete gap |
| Archived-economy read-only policy | `defer until post-live-test` | `LOG-ARC-049` | Still undocumented as a final runtime contract | Publish policy before production only if the feature remains active scope |
| Active-doc v2 compliance sweep | `needs refresh` | `docs/development/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md` | Initial sweep and top-level fixes are in place; broader active-doc verification remains open | Close all `needs update` items in the sweep doc |

## Pre-Live-Test Blockers

These items must be closed before treating `codex/v2.0` as ready for live testing:

1. Complete the v2 dev/migration database rehearsal from `SOP-DEP-022` and attach evidence.
2. Refresh the reconciliation tracker so only intentional pre-live-test deltas remain open.
3. Re-run PostgreSQL validation after the live-test port wave.
4. Record smoke-route execution outcome with named operator ownership.
5. Close active-doc issues still marked `needs update` in the documentation sweep.

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

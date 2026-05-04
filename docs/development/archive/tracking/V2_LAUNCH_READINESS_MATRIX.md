# V2 Launch Readiness Matrix

**Last Updated:** 2026-04-25
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
| Main-branch feature reconciliation tracker | `done` | `docs/development/tracking/V2_MAIN_RECONCILIATION_TRACKER.md` | All sampled `origin/main` feature clusters are now tracked and classified | Revisit before each major v2 milestone |
| Migration compliance summary | `done` | `SOP-DB-009_Migration_Compliance_Review.md`, `LOG-ARC-050` | Completed live-test rehearsal record exists with named operator, documented solo-operator exception, migration output, smoke-route results, and final `GO` after remediation | Re-run only if new launch-critical app, migration, or test-code changes land before live testing |
| Live-test migration rehearsal | `needs refresh` | `SOP-DEP-022_V2_Live_Test_Runbook.md`, `LOG-ARC-050_V2_Live_Test_Rehearsal_Report_04032026.md` | Historical rehearsal remains valid, but branch has materially changed since 2026-04-03 and requires a fresh run before live-test decision | Re-run rehearsal on current `codex/v2.0` head |
| Smoke-route checklist ownership | `done` | `SOP-DEP-022`, `LOG-ARC-050_V2_Live_Test_Rehearsal_Report_04032026.md` | Timothy Chang is recorded as primary solo operator; the solo-operator exception and smoke-route outcomes are documented in `LOG-ARC-050` | Re-run only if the solo-operator exception is rejected or new launch-critical route behavior lands before live testing |
| PostgreSQL validation baseline | `blocked` | Current full-suite run on `codex/v2.0` (2026-04-25) | Current runtime baseline is `619 passed, 123 failed, 1 skipped` after ongoing v2 hardening | Reduce failing set to launch-acceptable threshold and rerun full PostgreSQL validation |
| Economy/rent launch-critical main deltas | `needs refresh` | `docs/development/tracking/V2_MAIN_RECONCILIATION_TRACKER.md`, focused regression run | Port wave is landed; key slice tests are green, but broader rent/store/void regressions remain in current full-suite baseline | Continue stabilization until full-suite rent/store/void failures are closed |
| Insurance modularization and tiered policies | `done` | `app/utils/economy_policy.py`, `templates/admin_insurance.html` | Tiered coverage multipliers, UI accordion, and setup flow landed | Verify setup flow in simple/advanced modes |
| Insurance pricing snapshots and claim gates | `needs refresh` | `app/models.py`, `app/routes/admin.py`, focused insurance suite | Core insurance security/snapshot slices are currently green, but branch-wide regressions remain outside the focused slice | Keep insurance slices green while stabilizing cross-domain regressions |
| Production transition runbook completeness | `done` | `SOP-DEP-023_V2_Production_Transition_Runbook.md` | Runbook now has named operator roles, current workflow references, launch-critical smoke coverage, and a production transition record template | Revisit only if deployment workflow or maintenance controls change materially |
| Backup and restore rehearsal | `blocked` | `SOP-DEP-023`, `SOP-DEP-016`, operator process | Required by docs but not evidenced in repo-facing readiness artifacts | Record successful rehearsal on intended topology |
| Maintenance-mode and deploy workflow safety | `done` | `SOP-DEP-023`, `.github/workflows/*`, reconciliation tracker | Workflow security hardening and host key verification landed | Port workflow fix and verify maintenance toggling path |
| Announcement visibility fix | `done` | reconciliation tracker | Teacher-facing system announcement visibility query landed in admin.py | Port and verify dashboard rendering |
| Sysadmin tenancy audit | `defer until post-live-test` | `LOG-ARC-049` | Still tracked as unfinished historical follow-up | Convert to active audit if live testing exposes a concrete gap |
| Archived-economy read-only policy | `defer until post-live-test` | `LOG-ARC-049` | Still undocumented as a final runtime contract | Publish policy before production only if the feature remains active scope |
| Active-doc v2 compliance sweep | `done` | `docs/development/tracking/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`, `SOP-DOC-002` | Constitutional documentation overhaul completed 2026-04-12; gaps in multi-tenancy, alerting, and ledger integrity resolved. Focused link pass verified. | Re-run only if later production-required doc or workflow ports change active documentation links |
| Operations doc restructuring | `defer until post-live-test` | `DEVELOPMENT.md`, `SOP-DEP-022`, `SOP-DEP-023`, `SOP-DB-009` | Launch-critical runbook fixes are in scope now; broader SOP taxonomy and architecture-driven rewrite work is intentionally deferred until the admin-route and class-scope refactors land | Re-open after `V2_ADMIN_ROUTE_REFACTOR` and `V2_Class_Scope_Normalization_Target` are validated |

## Pre-Live-Test Blockers

These items must be closed before treating `codex/v2.0` as ready for live testing:

1. Complete the v2 dev/migration database rehearsal artifact from `SOP-DEP-022` with named operator confirmation and either independent verifier confirmation or a documented solo-operator exception. Completed in `LOG-ARC-050`.
2. Refresh the reconciliation tracker so only intentional pre-live-test deltas remain open. Completed 2026-04-08 for the economy/rent delta; no ambiguous economy/rent pre-live-test item remains.
3. Record smoke-route execution outcome with named operator ownership now that automated validation is green. Completed in `LOG-ARC-050`.
4. Close active-doc issues still marked `needs update` in the documentation sweep. Completed 2026-04-08; future link checks should be rerun after later doc or workflow ports.
5. Recover full-suite stability from current baseline (`619 passed, 123 failed, 1 skipped`) to launch-safe threshold, then rerun live-test rehearsal and PostgreSQL validation.

## Pre-Production Requirements

These can follow live testing, but must be complete before a v2 production launch:

1. Port the production-required `origin/main` deltas:
   - [x] insurance modularization and tiered setup flow
   - [x] insurance pricing snapshots, approval caps, and claim time-limit gate
   - [x] collective goal reactivation instance codes
   - [x] transfer submission hardening
   - [x] maintenance workflow security fix
   - [x] teacher announcement visibility fix
2. Execute backup/restore rehearsal on the intended production topology.
3. Record operator sign-off flow and reopen criteria in the production transition record.
4. Resolve any live-test findings that touch authorization, migration safety, or financial correctness.

## Nice-to-Have Cleanup

These are explicitly non-blocking under the current standard unless re-scoped:

- support/store UX polish from `main`
- observer-account and decision-history follow-up work
- safe dependency-upgrade wave
- broader historical audit cleanup beyond active-doc supersession notes

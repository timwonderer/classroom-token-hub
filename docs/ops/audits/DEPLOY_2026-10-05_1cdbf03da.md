# Deployment record: 2026-10-05 production release, `1cdbf03da`

**Type:** Routine release under `SOP-DEP-002`. No migrations. `CHANGELOG.md` (§ `[2.2.0]`) lists
this release as one of the "last two [with] no release record" from this window; this record fills
that gap.

## Release identity

| | |
|---|---|
| Release SHA | `1cdbf03dae6ae3d5eda7832920206db6b3bc39c4` (untagged) |
| Branch / lineage | `main` (`lineage_ref=main`) |
| Previous deployed SHA | `35bad089ab06a1f5a10f91596dc8559f7af3f7f6`, record [DEPLOY_2026-10-04_35bad089a.md](DEPLOY_2026-10-04_35bad089a.md) |
| Release run | [37407704785](https://github.com/timwonderer/classroom-token-hub/actions/runs/37407704785), created 2026-10-06T03:10:13Z, job 03:10:19Z → 03:10:42Z, event `workflow_dispatch`, success |
| Triggered by | GitHub actor `timwonderer` (`workflow_dispatch`); who physically executed the dispatch is not recorded in the run or in any adjacent document |
| Verifier | Not independently confirmed for this run. No adjacent record states a verifier for this specific SHA. |

### Contents since `35bad089a`

Every commit in this window belongs to a single PR (`git log --oneline 35bad089a..1cdbf03da`, matched to its
PR with `gh api .../commits/{sha}/pulls`):

| PR | Change |
|---|---|
| #1491 | Keep teacher-authored support tickets out of the Student Issues queue. Before this fix, a ticket a teacher filed directly through Help & Support (a report to system support) could be marked Dev Resolved by sysadmin and would then appear in the Student Issues queue as if a student had raised it. A non-model change per the PR's own Schema Change Gate Classification. |

Application paths changed (`git diff --stat 35bad089a..1cdbf03da -- app templates static`):

```
app/routes/admin.py                      | 12 ++++++++----
app/services/support_operator_access.py  | 11 +++++++++++
2 files changed, 19 insertions(+), 4 deletions(-)
```

No templates or static files changed in this window; GitHub's PR metadata reports 4 changed files for #1491 in
total, the other 2 being tests.

## §VI pre-release checks

| Check | Result |
|---|---|
| Release SHA on `main`, descendant of the running release | PASS. `35bad089a` is an ancestor of `1cdbf03da`, and the workflow's own lineage check printed "Approved revision: 1cdbf03da…" / "Approved lineage tip: 1cdbf03da…" (and `HEAD is now at 1cdbf03d Merge pull request #1491 from timwonderer/claude/fix-teacher-ticket-routing-xw5acn` on the host). |
| Migrations changed since the running release | None. `git diff --name-only 35bad089a..1cdbf03da -- migrations` is empty, matching PR #1491's own "NON-MODEL CHANGE" classification. |
| `requirements.txt` changed | No. |
| `app/models.py` changed | No. |
| CI on the release commit | From `gh api .../commits/1cdbf03d.../check-runs`: `Release exact v2 revision`, `production-docs-smoke`, `markdown-web-links`, `local-doc-links`, `guardrails-main`, both `Mirror postgres` jobs, and the three `Analyze` (CodeQL) jobs passed. The scheduled nightly `Full Test Suite` run [37348995248](https://github.com/timwonderer/classroom-token-hub/actions/runs/37348995248)'s `head_sha` is this exact release SHA (`1cdbf03dae6ae3d5eda7832920206db6b3bc39c4`); it started 2026-10-05T17:30:56Z and concluded `cancelled` at 20:01:20Z, roughly seven hours **before** this release (2026-10-06T03:10Z). It did not gate this deployment, and a cancelled run (as opposed to a completed run with failures) carries no information about whether the code itself passes — but it is a run against this exact SHA, not an unrelated one, and the attempt did not complete. |
| Backup | Not recorded. No backup artifact tied to this release was found in `docs/ops/audits/evidence/` or in the workflow logs. |
| Full suite dedicated to this exact SHA | A dedicated run exists and is recorded above (run 37348995248, same SHA) — it did not complete (`cancelled`), so this release shipped without a completed full-suite result for this exact revision. |

## Release run

From the workflow log (`gh run view 37407704785 --log`): the job checked out `1cdbf03dae6ae3d5eda7832920206db6b3bc39c4`
on `main`, validated it against the approved lineage, connected over Tailscale, then on the production host checked
out the exact revision, ran `pip install` (all satisfied) and `flask db upgrade` (no migrations applied), restarted
`classroom-economy`, and printed `Released exact revision 1cdbf03dae6ae3d5eda7832920206db6b3bc39c4` at
03:10:38Z. The health-check step printed `Production health passed` at 03:10:39Z. The job completed at 03:10:42Z
with conclusion `success`.

## §VIII post-release verification

| Check | Result |
|---|---|
| Deploy workflow's own health check | PASS — `Production health passed` at 03:10:39Z. This is the only post-release verification evidence found for this SHA. |
| Host-level checks (service active, scheduler, error logs) | Not recorded. No separate post-release verification note tied to this SHA was found in the workflow logs or in `docs/ops/audits/evidence/`. |
| Functional verification (ticket routing fix) | Not recorded as a dedicated post-release check against this exact SHA in any document found. |

## Outcome

Released and the deploy workflow's health check passed. No rollback was recorded as necessary. Per `CHANGELOG.md`
§ `[2.2.0]`, this SHA is the revision production ran into that release, and the four behavior-affecting PRs listed
there against `1cdbf03da` (#1522, #1526, #1527, #1528) are part of a later, already-documented release
(`5ebae62db`, 2026-10-09), not this one.

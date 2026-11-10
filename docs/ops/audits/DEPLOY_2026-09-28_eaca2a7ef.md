# Deployment record: 2026-09-29 production release, `eaca2a7ef`

**Type:** Incident correction release under `SOP-DEP-002`. No migrations. Ships the teacher-reviewed
one-time payroll correction for `PROD-PAY-001`; see
[`INCIDENT_2026-09-28_PROD-PAY-001.md`](INCIDENT_2026-09-28_PROD-PAY-001.md) §4 for the correction's
calculation, attribution and verification-before-approval detail.

## Release identity

| | |
|---|---|
| Release SHA | `eaca2a7ef016b97a131b70848f0bd857af9145af` (untagged) |
| Branch / lineage | `main` (`lineage_ref=main`) |
| Previous deployed SHA | `bc5c07a2ee71138fdad492358951c331b8c85eb4`, released the same night; record [DEPLOY_2026-09-28_bc5c07a2e.md](DEPLOY_2026-09-28_bc5c07a2e.md) |
| Release run | [36520218616](https://github.com/timwonderer/classroom-token-hub/actions/runs/36520218616), created 2026-09-29T04:07:45Z, job 04:07:50Z → 04:08:08Z, event `workflow_dispatch`, success |
| Triggered by | GitHub actor `timwonderer` (`workflow_dispatch`); who physically executed the dispatch is not recorded in the run or in any adjacent document |
| Verifier | Not independently confirmed for this run. See the note in [DEPLOY_2026-09-28_bc5c07a2e.md](DEPLOY_2026-09-28_bc5c07a2e.md) — this release falls in the same operational window between the `ad64a473f` and `314158d53` records, both of which name Claude Opus 5.5 under the solo-operator arrangement, but that is not direct evidence for this specific run. |

### Contents since `bc5c07a2e`

Only one PR is in this window (`git log --oneline bc5c07a2e..eaca2a7ef`, one commit, matched to its PR with
`gh api .../commits/{sha}/pulls`):

| PR | Change |
|---|---|
| #1440 | `feat(payroll)`: teacher-reviewed one-time correction for `PROD-PAY-001`. Adds the correction calculator (replays what each earlier-rule payroll run paid against the time actually worked in that run's window; a student whose replay does not match the ledger is marked "Needs review" and cannot be approved), the `/admin/payroll/correction` review page, and a dashboard/payroll-page banner pointing to it. Per the incident record's attribution table, each approved correction posts as a `manual_credit` event whose actor is the approving teacher's seat and whose mechanism is `SYSTEM`, keyed by a deterministic per-student idempotency key so no student can be corrected twice. |

Application paths changed (`git diff --stat bc5c07a2e..eaca2a7ef -- app templates static`):

```
app/routes/admin.py                                 | 130 +++++++
app/services/payroll/corrections.py                 | 376 +++++++++++++++++++++
templates/admin_dashboard.html                      |   1 +
templates/admin_payroll.html                        |   1 +
templates/admin_payroll_correction.html              |  69 ++++
templates/components/payroll_correction_banner.html  |   8 +
6 files changed, 585 insertions(+)
```

`app/services/payroll/corrections.py` is new in this PR.

## §VI pre-release checks

| Check | Result |
|---|---|
| Release SHA on `main`, descendant of the running release | PASS. `bc5c07a2e` is an ancestor of `eaca2a7ef`, and the workflow's own lineage check printed "Approved revision: eaca2a7ef…" / "Approved lineage tip: eaca2a7ef…". |
| Migrations changed since the running release | None. `git diff --name-only bc5c07a2e..eaca2a7ef -- migrations` is empty, and the workflow log shows no `Running upgrade` line. |
| `requirements.txt` changed | No; `pip install` reported every requirement already satisfied. |
| `app/models.py` changed | No. |
| CI on the release commit | `Release exact v2 revision`, `local-doc-links`, `guardrails-main`, and the three `Analyze` (CodeQL) jobs passed. `markdown-web-links` and `production-docs-smoke` failed (known: placeholder link and the Cloudflare Access window, as in the prior release). A `Full test suite` check-run is recorded against this SHA with conclusion `failure`, but its own timestamps (started 15:10:43Z, completed 16:49:09Z on 2026-09-29) are roughly eleven hours **after** this release (04:08Z) — it did not gate this deployment and is not evidence about the state of the code at release time. |
| Backup | Not recorded. No backup artifact tied to this release was found in `docs/ops/audits/evidence/` or in the workflow logs. |
| Verification against the ledger before approval | Not part of the release workflow itself, but recorded separately: `INCIDENT_2026-09-28_PROD-PAY-001.md` §4 states each class's correction review page was checked against an independent per-student SQL calculation before the teacher approved it (all four classes matched), and the 79 posted `manual_credit` events totalling $1,947.40 were confirmed in production after approval. |

## Release run

From the workflow log (`gh run view 36520218616 --log`): the job checked out `eaca2a7ef016b97a131b70848f0bd857af9145af`
on `main`, validated it against the approved lineage, connected over Tailscale, then on the production host checked
out the exact revision (`HEAD is now at eaca2a7e feat(payroll): teacher-reviewed one-time correction for PROD-PAY-001
(#1440)`), ran `pip install` (all satisfied) and `flask db upgrade` (no migrations applied), restarted
`classroom-economy`, and printed `Released exact revision eaca2a7ef016b97a131b70848f0bd857af9145af` at 04:08:06Z.
The health-check step printed `Production health passed` at 04:08:07Z. The job completed at 04:08:08Z with
conclusion `success`.

## §VIII post-release verification

| Check | Result |
|---|---|
| Deploy workflow's own health check | PASS — `Production health passed` at 04:08:07Z. This is the only automated post-release check evidence found for this SHA. |
| Host-level checks (service active, scheduler, error logs) | Not recorded. No separate post-release host/database verification note tied to this SHA was found. |
| Functional verification (the correction itself) | Recorded outside the deploy workflow: per `INCIDENT_2026-09-28_PROD-PAY-001.md` §1, the teacher reviewed each class and approved the corrections at 04:21–04:25 UTC, roughly 15–17 minutes after this release, implying the `/admin/payroll/correction` page the release shipped was reachable and working. §4 records the posted result (79 students, $1,947.40) as verified in production after approval. |

## Outcome

Released and the deploy workflow's health check passed. The correction it shipped was used by the teacher
within the hour, and its result was independently checked against SQL per the incident record. No rollback was
recorded as necessary.

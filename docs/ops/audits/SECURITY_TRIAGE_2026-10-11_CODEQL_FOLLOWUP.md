# CodeQL follow-up: remaining alerts and internal adversarial tools

Reviewed source: `886b0a060394713197e49aa7c38d5dcdf52aa6bb`.

## Scope and scan evidence

Reviewed all 14 open alerts from the latest main scan, the earlier 98-alert extended-suite triage, and all 34 historical alerts under `scripts/adversarial/`. The API inventory contains 225 alerts (171 fixed, 40 dismissed, 14 open); older, already-closed application alerts outside the 98-alert baseline were inventoried, not independently re-audited. Temporary probe #324 was reverted and is fixed.

Default setup reports `query_suite: extended`, `threat_model: remote`, updated at `2026-10-11T18:22:38Z`. Python analysis 1932332655 scanned this source at `2026-10-11T18:30:57Z`; Actions analysis 1932330891 scanned it at `18:30:03Z`. Several unchanged CLI/environment findings disappeared after the threat-model change. GitHub marks them fixed, but this is reduced source coverage, not evidence of remediation. Keep CLI/CI trust-boundary review in addition to remote-input scanning.

## Remaining alerts

| Alert | Classification | Evidence / action |
|---|---|---|
| [#171](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/171) `app/routes/admin.py` | False positive | TransactionNotReversible uses a literal public refusal; PurchaseNotReversible uses eligibility.reason, whose every producer is a literal public refusal. No traceback or database exception reaches this catch. |
| [#205](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/205) `.github/workflows/actionlint.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#206](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/206) `.github/workflows/deploy-status.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#207](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/207) `.github/workflows/deploy-status.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#208](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/208) `.github/workflows/docs-links.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#209](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/209) `.github/workflows/login-notice.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#210](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/210) `.github/workflows/login-notice.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#211](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/211) `.github/workflows/release-v2.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#212](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/212) `.github/workflows/release-v2.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#213](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/213) `.github/workflows/tailscale-ssh-smoke-test.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#214](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/214) `.github/workflows/tailscale-ssh-smoke-test.yml` | Real supply-chain risk; local fix | Pinned existing tag to its upstream commit; version and workflow inputs unchanged. |
| [#291](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/291) `app/routes/system_admin.py` | False positive for arbitrary-origin SSRF | system_admin_required proves BoundaryContext/sysadmin. Origin is operator GRAFANA_URL; path is appended, not joined as an absolute URL; redirects disabled. The empty prefix defeats the claimed path allowlist; it is not mitigation evidence. |
| [#292](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/292) `scripts/check_axe_template_coverage.py` | False positive; local noise reduction | Environment is used only for parse/meta dependency discovery, never rendering. Explicit autoescape=True preserves behavior. |
| [#293](https://github.com/timwonderer/classroom-token-hub/security/code-scanning/293) `tests/test_axe_template_coverage_guard.py` | False positive; local noise reduction | Environment is used only for parse/meta dependency discovery, never rendering. Explicit autoescape=True preserves behavior. |

## Additional catalog-query repair

Historical SQL-injection alert #280 no longer appears under the remote-input model. `table_counts()` still interpolated catalog table names inside double quotes; an embedded quote could break counting or introduce SQL for an actor already able to create tables. Replaced interpolation with `psycopg2.sql.Identifier`, used by both backup and restore verification. This is a real identifier-handling defect with a privileged DDL precondition, not a demonstrated public exploit. A regression covers ordinary, quoted and SQL-shaped table names.

## Internal adversarial proof tools

These scripts are manual internal harnesses, absent from workflow invocation and application request handlers. Their artifact roots/run IDs/snapshot inputs come from operator CLI arguments, environment or local evidence. Choosing filesystem paths and deliberately creating impossible database state are intentional proof functions. No folder-wide scanner exclusion or proof-payload rewrite was added.

`pg_dump` and `pg_restore` calls use argv lists without shell interpretation. This does not alone prove absence of option injection: the exact flagged inputs are operator-controlled database URLs/restore paths. `reset_db` intentionally uses `--clean` against the selected database; that destructive behavior is a replay function, not a finding to remove. These tools must be run only against the intended isolated environment.

| Alert | Rule | Source | Review |
|---|---|---|---|
| #223 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:28` | Operator-selected filesystem input/output; no remote source. |
| #224 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:38` | Operator-selected filesystem input/output; no remote source. |
| #225 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:40` | Operator-selected filesystem input/output; no remote source. |
| #226 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:52` | Operator-selected filesystem input/output; no remote source. |
| #227 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:66` | Operator-selected filesystem input/output; no remote source. |
| #228 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:68` | Operator-selected filesystem input/output; no remote source. |
| #229 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:68` | Operator-selected filesystem input/output; no remote source. |
| #230 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:71` | Operator-selected filesystem input/output; no remote source. |
| #231 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:75` | Operator-selected filesystem input/output; no remote source. |
| #232 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:104` | Operator-selected filesystem input/output; no remote source. |
| #233 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:121` | Operator-selected filesystem input/output; no remote source. |
| #234 | `py/path-injection` | `scripts/adversarial/build_evidence_bundle.py:134` | Operator-selected filesystem input/output; no remote source. |
| #242 | `py/path-injection` | `scripts/adversarial/inject_impossible_state.py:30` | Operator-selected filesystem input/output; no remote source. |
| #243 | `py/path-injection` | `scripts/adversarial/inject_impossible_state.py:120` | Operator-selected filesystem input/output; no remote source. |
| #251 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:10` | Operator-selected filesystem input/output; no remote source. |
| #252 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:12` | Operator-selected filesystem input/output; no remote source. |
| #253 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:16` | Operator-selected filesystem input/output; no remote source. |
| #254 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:19` | Operator-selected filesystem input/output; no remote source. |
| #255 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:28` | Operator-selected filesystem input/output; no remote source. |
| #256 | `py/path-injection` | `scripts/adversarial/render_constitutional_scorecard.py:78` | Operator-selected filesystem input/output; no remote source. |
| #257 | `py/path-injection` | `scripts/adversarial/reset_db.py:18` | Operator-selected filesystem input/output; no remote source. |
| #258 | `py/path-injection` | `scripts/adversarial/snapshot_db.py:27` | Operator-selected filesystem input/output; no remote source. |
| #259 | `py/path-injection` | `scripts/adversarial/snapshot_db.py:42` | Operator-selected filesystem input/output; no remote source. |
| #261 | `py/path-injection` | `scripts/adversarial/verify_cross_class_isolation.py:20` | Operator-selected filesystem input/output; no remote source. |
| #262 | `py/path-injection` | `scripts/adversarial/verify_cross_class_isolation.py:25` | Operator-selected filesystem input/output; no remote source. |
| #263 | `py/path-injection` | `scripts/adversarial/verify_cross_class_isolation.py:27` | Operator-selected filesystem input/output; no remote source. |
| #264 | `py/path-injection` | `scripts/adversarial/verify_cross_class_isolation.py:86` | Operator-selected filesystem input/output; no remote source. |
| #265 | `py/path-injection` | `scripts/adversarial/verify_lineage_lawfulness.py:30` | Operator-selected filesystem input/output; no remote source. |
| #266 | `py/path-injection` | `scripts/adversarial/verify_lineage_lawfulness.py:99` | Operator-selected filesystem input/output; no remote source. |
| #267 | `py/path-injection` | `scripts/adversarial/verify_runtime_session_attacks.py:23` | Operator-selected filesystem input/output; no remote source. |
| #268 | `py/path-injection` | `scripts/adversarial/verify_runtime_session_attacks.py:29` | Operator-selected filesystem input/output; no remote source. |
| #269 | `py/path-injection` | `scripts/adversarial/verify_runtime_session_attacks.py:218` | Operator-selected filesystem input/output; no remote source. |
| #289 | `py/command-line-injection` | `scripts/adversarial/reset_db.py:32` | Operator-selected DB/snapshot input passed as argv; no shell. Trusted invocation required. |
| #290 | `py/command-line-injection` | `scripts/adversarial/snapshot_db.py:33` | Operator-selected DB/snapshot input passed as argv; no shell. Trusted invocation required. |

At the initial scanning review, the tools contained stale proof assumptions: `verify_runtime_session_attacks.py` imports removed `Student` and uses v1 session/seat fields; `phase1_seed_and_snapshot.sh` names an absent `seed_phase1_minimal.py`; the injector bootstrap uses removed seat fields. This review classifies scanning alerts; it does not certify these historical tools as executable current-v2 proofs. Repairing their scenario authority is separate from suppressing scanning noise. No adversarial DB mutation, reset or live exploit was executed.

## Authority and validation

Authority reviewed: INV-CORE-000/001; INV-ARC-005/017; DOM-OPS-001; SPEC-INV-001; SPEC-OPS-004 §6.5; SOP-DEP-002. FEAT-OPS-001 was checked for applicability: these edits perform no protected domain mutation or audit emission. Internal deliberate-corruption harness behavior must not be represented as lawful application production behavior.

Exact focused command:

```sh
/tmp/cth-scan-review-venv/bin/python -m pytest --noconftest tests/test_axe_template_coverage_guard.py tests/test_db_backup_client_versions.py tests/test_status_deploy_workflow.py -q
```

Result: **45 passed**. Temporary Python 3.14.6 environment because repository `.venv` lacks pytest; no repository dependency changes. The backup test mocks the cursor/identifier quoting seam, not PostgreSQL execution.

Requests prepared eight URL-shaped/path-traversal inputs against the actual proxy URL expression: all retained `localhost:3000`. AST checks confirmed the sysadmin decorator, disabled redirects, and literal-only refusal reasons. These checks do not prove Grafana authorization or live ingress behavior.

All six changed workflows pass `actionlint -shellcheck=`. Full actionlint reports the same pre-existing SC2029 informational diagnostic on `release-v2.yml:86` before and after; no new diagnostic. Every pin was resolved through the upstream tag API (peeling annotated tags), with `action.yml` verified at the commit.

| Upstream action | Existing version | Verified commit |
|---|---|---|
| `reviewdog/action-actionlint` | `v1.71.0` | `0d952c597ef8459f634d7145b0b044a9699e5e43` |
| `google-github-actions/auth` | `v2` | `c200f3691d83b41bf9bbd8638997a462592937ed` |
| `google-github-actions/setup-gcloud` | `v2` | `e427ad8a34f8676edf47cf7d7925499adf3eb74f` |
| `lycheeverse/lychee-action` | `v2` | `e7477775783ea5526144ba13e8db5eec57747ce8` |
| `tailscale/github-action` | `v4` | `d1b6cd204f8dceda5b3eaad7f1f767be390056cd` |
| `webfactory/ssh-agent` | `v0.10.0` | `e83874834305fe9a4a2997156cb26c5de65a8555` |

No full suite, production workflow, PostgreSQL restore, merge or deployment was run. The follow-up implements fixes for 12 open alerts; default-branch scanner resolution requires merge and rescan. Application false-positive dismissal results are recorded after API verification.

GitHub API confirmed #171 and #291 dismissed as false positive with evidence comments. Final open inventory: **12**, exactly #205–#214 plus #292–#293. They have fixes in this follow-up and await default-branch merge/rescan.

## Owner-authorized current-v2 harness repair

The follow-up request authorized repairing the missing seed and stale proof inputs.
`seed_phase1_minimal.py` now provisions three canonical classrooms through
SPEC-TEST-001's initializer, imports an unclaimed seat through FEAT-IDEN-006,
and posts/settles a synthetic $1 manual payment through Ledger commands.
It requires an explicitly supplied isolated environment file and an empty
identity/class database. `topology.json` records canonical class UUIDs; the
ADVA1/ADVA2/ADVB1 names are scenario labels, not join-code authority.

The runtime battery now checks the v2 User class/seat pointers, unclaimed/foreign/
missing seats, authenticated route controls, foreign-class switch/API refusal,
disabled hall-pass feature refusal, and class-selection rendering. Resolver input
corruption is transient and restored; only the deliberate Ledger snapshot
injection persists, restricted to the seeded topology. There is no Student model
or v1 session bridge. Script wrappers invoke Python modules from the repository
root and the runner honors PYTHON_BIN.

Missing topology/snapshots, missing injection evidence, unexpected statuses, empty
lineage windows and server errors cannot produce a green proof. The runner clears
stale reports, preserves evidence collection after verifier failures and exits
nonzero. Removed the unexecuted GET-mutation scorecard claim. The lineage check
remains a presence-only skeleton, not cryptographic lawfulness verification.

Validation command: `/tmp/cth-scan-review-venv/bin/python -m pytest
 tests/test_adversarial_harness.py -q --tb=short --show-capture=no` against the
configured dedicated PostgreSQL test database. The tests cover the seed,
canonical context battery, deliberate injection, verification, scorecard,
sanitized bundle and runner failure propagation. No production mutation,
pg_dump/pg_restore rehearsal, full suite or deployment was performed during validation.

Final validation: **4 passed in 19.42s**; evidence in `pytest_result/20261011_pytest_test_adversarial_harness_summary_4.md`. Shell syntax and Python 3.10 syntax checks passed.

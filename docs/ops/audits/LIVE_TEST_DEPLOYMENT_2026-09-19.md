# Live Test Deployment Record — 2026-09-19

Runbook: `SOP-DEP-001_Live_Test_Runbook.md`
Status: **§VI release gate CLOSED — PASS.** §VII–§XVI pending execution.

This record is appended to as the deployment proceeds and is finalized, and
thereafter immutable, at §XVI.

---

## Release Identity (§VI.1, §VI.5)

| Field | Value |
|---|---|
| **Deployed SHA** | `8c5cff7c894eb38e2f4908fbf49b08e41f8f3e9a` |
| Branch | `main` |
| Commit | Merge commit, PR #1401 (`codex/claim-identity-remediation`) |
| Merged | 2026-09-19T02:56:19Z by `timwonderer` |
| Migration head (before deploy) | `d9e1f3a5b7c9` — single head |
| Migration head (after deploy) | *pending §IX* |
| Operator | timwonderer |
| Verifier | timwonderer (solo-operator exception, §XIII) |
| Test window | 2026-09-19T05:05Z – 05:17Z (suite), gate closed 2026-09-19 |

### Tree equivalence to the CI-verified commit

The release is a merge commit, which normally carries content no CI run has
examined. It does not here:

| Commit | Tree |
|---|---|
| `8c5cff7c8` (release, on `main`) | `2f053318634b50140deb532e3018a620b33999a5` |
| `37f9245d8` (branch tip, CI green) | `2f053318634b50140deb532e3018a620b33999a5` |

`main` was a strict ancestor of the branch at merge time
(`git merge-base --is-ancestor origin/main HEAD` succeeded), so the merge
introduced no content. The trees are identical, and PR #1401's green CI result
therefore applies to the deployed SHA directly.

---

## §VI.2 — Working Tree

Clean at `8c5cff7c894eb38e2f4908fbf49b08e41f8f3e9a` on `main`.
No unapproved local changes.

## §VI.3 — Migration Safety

| Check | Command | Result |
|---|---|---|
| Single head | `bash scripts/check-migrations.sh` | PASS — "All Migration Checks Passed", "Safe to deploy" |
| Linter | `python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt` | PASS — **0 errors** across 165 files |

Warnings: 4, with 28 accepted by `migrations/lint_baseline.txt`. These are
pre-gate debt under `SOP-DB-009` §VI and do not block. The baseline was not
enlarged by this release.

## §VI.4 — Test Suite

| Field | Value |
|---|---|
| Command | `pytest -q` |
| Artifact | [`evidence/2026-09-19_live-test_8c5cff7c8/pytest_full_summary.md`](evidence/2026-09-19_live-test_8c5cff7c8/pytest_full_summary.md) |
| CSV | [`evidence/…/pytest_full_results.csv`](evidence/2026-09-19_live-test_8c5cff7c8/pytest_full_results.csv) — 2997 rows |
| Failures log | [`evidence/…/pytest_full_failures.txt`](evidence/2026-09-19_live-test_8c5cff7c8/pytest_full_failures.txt) — "No failed tests in this run." |
| Recorded commit | `8c5cff7c8` — matches the release SHA |
| Exit status | `0` |
| Tests recorded | 2997 |
| Passed | 2983 |
| Failed / errored / xpassed | **0** |
| Skipped | 14 — dispositioned below |
| Runtime | 704,004 ms (11m 44s) |

Per §VI.4 the gate is "no failures attributable to the release, and any skip or
failure explicitly dispositioned" — not a comparison against a historical pass
count. No failure groups are present in the artifact.

### Evidence

`pytest_result/` at the repository root is gitignored by design: every targeted
run writes its own CSV, summary and failures log, and tracking them would add
thousands of files a week. Only the **deployed full suite** — the gate run
backing this record — is preserved, copied verbatim into
[`evidence/2026-09-19_live-test_8c5cff7c8/`](evidence/2026-09-19_live-test_8c5cff7c8/)
where it is immutable and readable without the operator's machine. The per-test
CSV is the source for the skip disposition below.

The summary is also reproduced inline so this record stands on its own:

```markdown
# Pytest Run Summary (full)

## Run Metadata

- generated_utc: 2026-09-19T05:17:03.763933+00:00
- git_commit: 8c5cff7c8
- pytest_label: full
- exitstatus: 0
- tests_recorded: 2997
- csv: 20260919_pytest_full_results.csv
- failures_log: 20260919_pytest_full_failures.log

## Outcome Counts

- pass: 2983
- skip: 14

## Runtime Stats

- success_percentage: 99.53%
- total_runtime_ms: 704004
- average_duration_ms: 234.90
- median_duration_ms: 1.00

## Slowest 10 Tests

| duration_ms | outcome | nodeid |
|---:|---|---|
| 5214 | pass | tests/test_axe_compliance.py::test_published_pages_have_no_axe_violations |
| 2265 | pass | tests/test_docs_site_image_advisory_guard.py::test_docs_site_has_no_image_assets |
| 1884 | pass | tests/test_admin_store_edit_route.py::test_admin_store_edit_get_rejects_foreign_class_item |
| 1701 | pass | tests/dom/identity/test_unassigned_visibility.py::test_DOM_IDEN_001__cross_teacher_isolation |
| 1482 | pass | tests/dom/ledger/test_seat_balance_serialization.py::test_INV_LED_015__settlement_waits_for_a_debit_holding_the_seat_lock |
| 1436 | pass | tests/dom/identity/test_unclaimed_seat_economic_exclusion.py::test_DOM_IDEN_002__the_roster_modification_feat_also_refuses_an_unclaimed_seat |
| 1399 | pass | tests/dom/identity/test_teacher_lifecycle.py::test_stale_account_destruction_reuses_all_class_teardown |
| 1379 | pass | tests/dom/class/test_feature_scope_single_active_class.py::test_DOM_CLASS_001__feature_options_never_include_sibling_class |
| 1379 | pass | tests/dom/identity/test_teacher_lifecycle.py::test_last_students_delete_only_target_class_when_sibling_exists |
| 1351 | pass | tests/dom/identity/test_teacher_last_class_deletion.py::test_deleting_one_of_several_classes_preserves_the_teacher_principal |

## Failure Groups

No failed/error/xpass outcomes in this run.
```

### Skip disposition (all 14)

**1 — `tests/test_credential_primitive.py::test_the_profile_is_passed_explicitly_and_not_inherited_from_werkzeug`**

Conditional skip, self-declaring: Werkzeug's default hash profile still matches
`SPEC-SEC-001` §V.1.2, so the explicit pin cannot be distinguished from
inheriting the library default. The test is written to become load-bearing the
moment Werkzeug changes that default — which is the upgrade the pin exists to
survive. A dormant guard, not a disabled test, and not release-related.

**13 — `tests/test_layout_accessibility_contract.py::test_disclosure_triggers_describe_their_controlled_state[…]`**

Templates: `admin_banking`, `admin_dashboard`, `admin_hall_pass`,
`admin_issues_queue`, `admin_payroll`, `admin_store`, `student_detail`,
`student_payroll`, `student_shop`, `student_transfer`,
`sysadmin_combined_logs`, `sysadmin_escalated_issues`,
`sysadmin_support_tickets`.

One parametrized case per template, each skipping via
`pytest.skip(f"{template} has no non-tab aria-controls triggers")` when that
template contains no non-tab `aria-controls` trigger — i.e. there is nothing on
the page for the contract to assert. The templates that do carry disclosure
triggers were asserted, not skipped. Not release-related.

**Conclusion:** 14 of 14 skips are conditional "nothing to assert" outcomes
arising from the codebase's own shape. None is a suppressed assertion, none was
introduced or affected by this release, and none masks untested behavior.

---

## §VI Decision

**GO.** Release gate PASS at `8c5cff7c894eb38e2f4908fbf49b08e41f8f3e9a`.

---

## Release Contents

Merged from PR #1401. Significant items for operational awareness:

- **Destruction now attributes to the FEAT that owns it.** Roster deletion
  dispatches to `FEAT-IDEN-006` (seats), `FEAT-CLASS-006` (class universe) or
  `FEAT-IDEN-007` (teacher principal), selected before the FEAT opens and
  re-evaluated under lock, failing closed if the terminal scope moved.
  `FEAT-CLASS-006` is new — class destruction previously executed under
  `FEAT-CLASS-001`, whose contract is class *creation*. Audit rows for a
  destroyed class or account will now carry the correct `feat_code`.
- **Unclaim renames the seat it unclaims.** The entered names become both the
  claim material and the `IdentityProfile` display name. `DOM-IDEN-005` v2.2.
- **Two merged migrations carry Bootstrap-Replay Corrections** under the new
  `SOP-DB-001` v1.3 §V.B (`3a69db4907b4`, `8f1a2c3d4b5e`). Both are guards that
  skip an operation whose target column no longer exists. **They are
  load-bearing for a fresh database:** without them `flask db upgrade` fails at
  `3a69db4907b4` and the application will not boot.
- **The chain no longer creates cross-domain foreign keys on
  `actor_public_id`.** Seat-scoped support rows are swept explicitly, per
  `DOM-SUP-001` §X.

---

## §VII — Runtime Preparation

> **Worker count: ONE.**
> The APScheduler background scheduler starts inside `create_app`, so every
> gunicorn worker starts its own. With N workers each hourly job — ledger
> settlement, savings interest, automatic payroll, rent reconciliation,
> insurance expiry — runs N times per hour concurrently. No leader election or
> advisory lock guards this today.

*Pending execution.*

## §VIII — Environment and Secrets

*Pending execution.*

## §IX — Fresh Database and Migration

*Pending execution. Record migration head after upgrade.*

## §X — Application Start and Health Checks

*Pending execution. Attach health output.*

## §XI — Full-App First Test

*Pending execution. Every path requires recorded evidence.*

## §XIV — Decision and Rollback

Irreversible revisions, per `SOP-DEP-001` §XIV item 5: `c7a7b8c9d0e1`
(seat-owned records) raises on downgrade, and `c1a1b2d3e4f5` (claim-artifact
cleanup) downgrades to a no-op. Rolling back past either means restoring the
database snapshot taken in step 6, not walking the chain back.

*Decision pending.*

## §XVI — Completion Condition

*Pending. Complete only when the exact SHA runs from a fresh database, the
required integrations work, every §XI path has recorded evidence, and the
operator/verifier decision is stored.*

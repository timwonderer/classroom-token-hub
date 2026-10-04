# Release record (draft): v2.1.1

> **Draft, prepared before deployment.** Sections marked *To record at release* are empty on purpose: they hold
> evidence that only exists once the operator deploys. The release SHA is the tip of `main` after the sysadmin
> logout change merges. At release, fill in the open sections and rename this file to
> `DEPLOY_<YYYY-MM-DD>_<sha9>.md`, matching the other records in this directory.

**Type:** Tagged release under `SOP-DEP-002`, **with four migrations, three of them forward-only.** It tags as
v2.1.1 everything merged to `main` since v2.1.0 and ships to production everything merged after the untagged
2026-10-03 release (`ad9574334`): #1471-#1477 and the sysadmin logout change. Because one migration drops a column
the running code reads, the application must be stopped before the release workflow runs, as for v2.1.0, and the
only rollback is a database restore.

## Release identity

| | |
|---|---|
| Release SHA | *To record at release:* tip of `main` after the sysadmin logout change merges; to be tagged `v2.1.1` |
| GitHub release | *To record at release* |
| Branch / lineage | `main` (`lineage_ref=main`) |
| Previous deployed SHA | `ad9574334d72fd92cc93402e851ab0ebc22aaad9` (untagged), Alembic revision `a4b50fee84c3`; record [DEPLOY_2026-10-03_ad9574334.md](DEPLOY_2026-10-03_ad9574334.md) |
| Release run | *To record at release* |
| Triggered by | *To record at release* |
| Verifier | *To record at release* |

### Why this release

- **Student names in the application log (#1472, Security).** Bulk hall-pass adjustments write each adjusted
  student's full name to the journal at INFO. Every day the release waits, new adjustments add names.
- **Store redemptions cannot be decided (#1473).** Approving a delayed-use redemption, and every immediate-use
  redemption through `/api/use-item`, answers 500 and the request stays waiting.
- **Attendance correction (#1477).** Teachers can invalidate eligible completed attendance intervals, with paid
  contributions recovered atomically.
- **Sysadmin logout by POST** (PR not yet merged): a stray link or prefetch can no longer sign an operator out.

### Contents since `ad9574334`

Every PR below is merged unless marked, and its merge commit is an ancestor of `main` and not of `ad9574334`.

| PR | Change |
|---|---|
| #1471 | Documentation: the 2026-10-03 deployment record. |
| #1472 | No student names in application logs (bulk hall-pass adjustment logs `seat_id` and `class_id` only, plus a structural guard); each log line is written once instead of twice. |
| #1473 | Economy > Store gets one Redemptions tab; a request can be decided Accept, Deny or Return, each final (DOM-STORE-001 5.4 §VIII.E.4); immediate-use purchases queue a *Mark as complete* reminder. |
| #1474 | Store bundles are removed; a pack is a purchase quantity at a bulk price. Code only: the two `store_products` columns stay. |
| #1475 | The payroll page renders one Run Payroll button, so its id is unique (INV-ARC-020). |
| #1476 | Login page notice posted or cleared from the manual **Login page notice** workflow. |
| #1477 | Attendance interval invalidation with atomic payroll recovery; immutable ledger and payroll creation lineage; ledger posting derived from scoped reconciliation cursors; historical attendance proof assessment. Four migrations (below). |
| *pending* | Sysadmin logout requires POST with CSRF. *To record at release:* PR number. |

Commits outside a PR: `69bc370` adds `.codex/environments/environment.toml` and a `.gitignore` line (developer
tooling, not deployed behavior), `7658d12` merges it, and `7e1189d` is a documentation edit committed directly to
`main` before #1477 merged.

Application paths changed: through #1476, 30 files under `app/`, `templates/` and `static/` (store, redemptions,
logging, login notice); #1477 adds 64 more, across `app/feats/`, `app/services/ledger_*`, `app/services/payroll/`,
attendance services, `app/models.py`, `app/routes/{admin,api,student,system_admin}.py`, `app/scheduled_tasks.py`
and nine templates. `git diff --stat ad9574334 <release sha> -- app templates static` gives the full list at release.
Workflow added: `.github/workflows/login-notice.yml`.

### Migrations

Chain from production's `a4b50fee84c3`, in order:

| Revision | What it does | Downgrade |
|---|---|---|
| `d6b1e0c4a825` | Payroll creation lineage: nullable lineage columns on `payroll_event` and deferred INSERT triggers. No backfill. | Reversible (drops triggers, functions and columns) |
| `e7c2a9d4f610` | Ledger posting derived from scoped reconciliation. Takes `ACCESS EXCLUSIVE` locks on `ledger_transaction` and `ledger_balance_snapshot`, runs its own preflight, then **drops `ledger_transaction.status`**. | **Raises.** Forward-only |
| `f8b2d6e0a410` | Immutable recovery provenance on the ledger. No backfill. | **Raises.** Forward-only |
| `f9a3c7d1e620` | Terminal attendance eligibility receipts with immutable creation lineage. No backfill. | **Raises.** Forward-only |

`e7c2a9d4f610` aborts (`Ledger posting migration blocked`) if any ledger row has a missing or nonpositive
`posting_sequence`, is `VOID`, or disagrees with its snapshot's `reconciled_through_posting_sequence` (a `POSTED`
row beyond the cursor, or a `PENDING` row at or before it). Read-only preflights on 2026-10-03 found none of these
among 854 rows, and no `REVERSAL` rows or duplicate original locators
([implementation record](../../TRACKING/HISTORICAL_ATTENDANCE_RECONSTRUCTION_IMPLEMENTATION_20261003.md)). That is
a dated observation; the record itself requires a fresh preflight before deployment.

### Not part of this release

- Carried from earlier records: the status service and host sampler from #1467, and the nginx snippet from #1446.
- Historical attendance remediation: #1477 ships the assessment and proof code; running any historical
  reconstruction is a separate, separately authorized operation.

## §VI pre-release checks

| Check | Result |
|---|---|
| Release SHA on `main`, descendant of the running release | *To record at release.* `ad9574334` is an ancestor of `main` as of `66343d1` (checked 2026-10-04). |
| Running release before dispatch | *To record at release* (expected host `HEAD` `ad9574334`, Alembic `a4b50fee84c3`) |
| Migrations changed since the running release | Four, listed above. Single head `f9a3c7d1e620` as of `66343d1`. |
| **Fresh read-only migration preflight** | *To record at release.* Run in `BEGIN READ ONLY` immediately before dispatch: the `e7c2a9d4f610` predicate above returns 0, and zero `REVERSAL` rows or duplicate original locators. A nonzero count stops the release. |
| `requirements.txt` changed | No (as of `66343d1`) |
| New configuration | `LOGIN_NOTICE_PATH` (optional; unset means `instance/login_notice.json`). Nothing to set. |
| Student-setup memory store (§VI item 6) | *To record at release* |
| Full suite on the release SHA | *To record at release.* #1477's own record lists large targeted runs and says no full suite ran. With forward-only ledger migrations, a full suite on the release SHA is expected before dispatch. |
| CI on the release commit | *To record at release.* Push CI on `66343d1` (merge of #1477): Policy Guardrails, Lint Workflows, Check Database Migrations, Deploy GitHub Pages Site and Documentation Link Checks passed. |
| **Backup** | *To record at release.* **Required:** a fresh encrypted dump taken after the application is stopped and before dispatch, verified restorable, as for v2.1.0. It is the only rollback. |
| Application stopped before dispatch | *To record at release.* Required: the running code maps `ledger_transaction.status`, which `e7c2a9d4f610` drops, and the scheduler must not post during the migration. |
| Timing | Outside the school day, and not on the 2026-10-10 payday. |

## Release run

*To record at release.*

## §VIII post-release verification

*To record at release.* Beyond the standard host checks (revision, service, health, scheduler, errors since start),
this release has these specific checks:

- **Database revision** is `f9a3c7d1e620`; `ledger_transaction` has no `status` column.
- **Balances unchanged:** checking and savings totals per class match the pre-release read.
- **#1472:** service journal lines appear once each, with no `INFO:app:` duplicates after the first passkey sign-in.
- **#1473:** Economy > Store shows the Redemptions tab; a waiting redemption in a real class can be decided without
  a 500.
- **#1476:** the student and teacher login pages render with no notice file present.
- **#1477:** the payroll page opens, and the attendance correction modal opens for a completed interval (no
  invalidation needs to be made to verify it).
- **Logout:** `GET /sysadmin/logout` no longer signs the operator out; the console's sign-out button does.
- **Carried over:** the first automatic payday, 2026-10-10, now runs under #1477's payroll lineage triggers;
  hall-pass reject and cancel in production; #1469's `TLCP-SURFACE-PRINCIPAL-MISMATCH` line not yet observed.

## Rollback

**There is no redeploy rollback.** `e7c2a9d4f610`, `f8b2d6e0a410` and `f9a3c7d1e620` raise on downgrade by design
(DOM-LED-001, INV-ARC-016), and `ad9574334` cannot run against the migrated schema because it reads
`ledger_transaction.status`. Under SOP-DEP-001 §XIV the operator chooses, on verified evidence, between:

- **Fix forward:** a reviewed forward migration or code fix on `main`, released the same way.
- **Restore:** stop the application, restore the pre-release dump taken under §VI, and release `ad9574334`.
  Anything written after the release (payroll, purchases, attendance) is lost and must be re-entered.

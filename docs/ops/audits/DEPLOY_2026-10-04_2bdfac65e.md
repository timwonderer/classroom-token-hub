# Release record: v2.1.1, `2bdfac65e`

Released 2026-10-04 at 20:38 UTC (Sunday), inside a Cloudflare Access maintenance window that also carried a host
kernel update and reboot (see [Host maintenance in the same window](#host-maintenance-in-the-same-window)).

**Type:** Tagged release under `SOP-DEP-002`, **with four migrations, three of them forward-only.** It tags as
v2.1.1 everything merged to `main` since v2.1.0 and ships to production everything merged after the untagged
2026-10-03 release (`ad9574334`): #1471-#1484. Because one migration drops a column
the running code reads, the application must be stopped before the release workflow runs, as for v2.1.0, and the
only rollback is a database restore.

## Release identity

| | |
|---|---|
| Release SHA | `2bdfac65e9251e1451f29454c18de1aaac947f57` (tip of `main`); tag `v2.1.1` *not yet created* |
| GitHub release | *Not yet published* |
| Branch / lineage | `main` (`lineage_ref=main`) |
| Previous deployed SHA | `4c2fc4bc40bf411243c1eafd2f6e377b41d7fa5d`, an untagged hotfix released at 18:21 UTC the same day: #1476 cherry-picked onto `ad9574334` from branch `claude/project-thread-nhpx6y`, released with `V2_RELEASE_LINEAGE_REF` set to that branch, then restored to `main`. Alembic revision `a4b50fee84c3`. Before it: `ad9574334`, record [DEPLOY_2026-10-03_ad9574334.md](DEPLOY_2026-10-03_ad9574334.md) |
| Release run | [37232860617](https://github.com/timwonderer/classroom-token-hub/actions/runs/37232860617), 20:38:16Z → 20:38:43Z, success |
| Triggered by | `workflow_dispatch` under `timwonderer`, dispatched by Claude Code at the operator's instruction |
| Verifier | Claude Code (host and database checks, read-only); browser checks by the operator, recorded under §VIII |

### Why this release

- **Student names in the application log (#1472, Security).** Bulk hall-pass adjustments write each adjusted
  student's full name to the journal at INFO. Every day the release waits, new adjustments add names.
- **Store redemptions cannot be decided (#1473).** Approving a delayed-use redemption, and every immediate-use
  redemption through `/api/use-item`, answers 500 and the request stays waiting.
- **Attendance correction (#1477).** Teachers can invalidate eligible completed attendance intervals, with paid
  contributions recovered atomically.
- **Sysadmin logout by POST (#1482):** a stray link or prefetch can no longer sign an operator out.

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
| #1478, #1479 (via #1483) | Performance: transaction posting state is projected once per list, and batch creation proofs walk each class audit chain once. |
| #1481 | Proposed encrypted off-host database backups (`infra/db-backup/`), **not installed**; removes the never-scheduled v1 `scripts/backup-database.sh` and `scripts/restore-database.sh`. |
| #1484 | Full-suite remediation after #1477: test fixtures and historical migration inputs, `.github/workflows/full-suite.yml`, SOP-DEP-001 notes on forward-only revisions, and hidden-state CSS for the store redemption controls (`templates/admin_store.html`, `templates/student_detail.html`, `static/css/style.css`). No migrations. |
| #1482 | Signing out of the operator console takes a POST with a CSRF token; `GET /sysadmin/logout` answers 405 and changes nothing. |

Commits outside a PR: `69bc370` adds `.codex/environments/environment.toml` and a `.gitignore` line (developer
tooling, not deployed behavior), `7658d12` merges it, and `7e1189d` is a documentation edit committed directly to
`main` before #1477 merged.

Application paths changed: through #1476, 30 files under `app/`, `templates/` and `static/` (store, redemptions,
logging, login notice); #1477 adds 64 more, across `app/feats/`, `app/services/ledger_*`, `app/services/payroll/`,
attendance services, `app/models.py`, `app/routes/{admin,api,student,system_admin}.py`, `app/scheduled_tasks.py`
and nine templates; #1478-#1483 touch 14 files, including `app/routes/system_admin.py`, `app/services/tlcp.py`,
`app/utils/audit_verifier.py` and `templates/layout_system_admin.html`. `git diff --stat ad9574334 <release sha> -- app templates static` gives the full list at release.
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
| Release SHA on `main`, descendant of the running release | `2bdfac6` is the tip of `main`. It descends from `ad9574334` but not from the hotfix `4c2fc4bc4`, which is off `main`; `main` carries #1476 as `c57dadfc3`. The workflow resets the host to the exact SHA, so this needs no action. Between `0d8a346` and `2bdfac6` only `CHANGELOG.md`, `docs-site/src/pages/index.js` and this record changed. |
| Running release before dispatch | Host `HEAD` `4c2fc4bc4`, working tree clean apart from an untracked `venv.old/`; Alembic `a4b50fee84c3`. |
| Migrations changed since the running release | Four, listed above. Single head `f9a3c7d1e620` as of `0d8a346`; #1478-#1484 add none. |
| **Fresh read-only migration preflight** | PASS, 20:35:03Z, one `REPEATABLE READ READ ONLY` transaction (rolled back) with the application stopped: the `e7c2a9d4f610` predicate returned 0; `REVERSAL` rows 0; duplicate original locators 0. All 854 ledger rows had status exactly `POSTED`, and no type matched `revers` in any case. |
| `requirements.txt` changed | No. The release's `pip install` reported every requirement already satisfied. |
| New configuration | `LOGIN_NOTICE_PATH` (optional; unset means `instance/login_notice.json`). Nothing to set. |
| Student-setup memory store (§VI item 6) | `cth-student-setup.service` active (again after the reboot). Host checks from `infra/student-setup/README.md` step 5, recorded for the first time (closes the tracker item open since 2026-09-29): `save` empty, `appendonly no`, `slowlog-log-slower-than -1`, `role:master` with 0 replicas; `CONFIG SET`, `SAVE`, `BGSAVE`, `REPLICAOF` and `MONITOR` each refused with `NOPERM` for the app's `default` user; `LimitCORE=0` and `MemorySwapMax=0` on both `cth-student-setup` and `classroom-economy`; cgroup v2. The host runs Redis 6.0.16, not the 7+ the README states; see Follow-ups. |
| Full suite on the release SHA | PASS on `0d8a346`, [run 37221752367](https://github.com/timwonderer/classroom-token-hub/actions/runs/37221752367) (dispatched, 17:45 → 20:10 UTC). `2bdfac6` adds documentation only (row above). |
| CI on the release commit | Push CI on `2bdfac6`: Policy Guardrails and Deploy GitHub Pages Site passed. On `0d8a346`: Policy Guardrails, Lint Workflows and Documentation Link Checks passed. |
| **Backup** | PASS. Two points, both taken from the operator's Mac with `infra/db-backup/cth_db_backup.py backup --reason manual` (local only), each verified by restoring into an in-memory PostgreSQL 14 and comparing every table count, then restored a second time with the owner's `age` identity (`restore --live-url`): manifest match and no-resurrection check both PASS. **This is the first pre-release dump proven to restore.** Point A (before the host work): `cth-db-20261004T201652Z-manual`, `taken_at` 2026-10-04T20:16:52.731835Z, revision `a4b50fee84c3`, 44 tables, 10,856 rows, `artifact_sha256` `478bffa0481c68b1af5d1570e8f7a2031ca0cfd76a0bd9148f152e2e79db4e19`. **Point B (the rollback point):** `cth-db-20261004T203352Z-manual`, `taken_at` 2026-10-04T20:33:52.964227Z, revision `a4b50fee84c3`, 44 tables, 10,856 rows, `artifact_sha256` `8296be8782381941319120873cc0b0b5ccfd0610d7675cf65344d133840bc8ca`; its restored copy's per-class balances equal the baseline below. Both are stored on the operator's Mac, mode 600. The identity file existed only for each restore and was deleted after. |
| Application stopped before dispatch | Yes: `inactive` from 20:33:35Z until the release restarted it at 20:38:38Z. |
| **Pre-release balance baseline** | Read at 20:35:03Z with the preflight. 854 ledger rows; 7 of the 10 classes have ledger activity. The ledger sum and the posted snapshot sum agree in every row. Table below. |
| Timing | Outside the school day, and not on the 2026-10-10 payday. |

### Pre-release balance baseline

Class ids only. `ledger_cents` is `sum(amount_cents)` over `ledger_transaction`; `posted_cents` is
`sum(posted_balance_cents)` over `ledger_balance_snapshot`.

| class_id | Account | Txns | ledger_cents | Snapshots | posted_cents |
|---|---|---:|---:|---:|---:|
| `1da9085a-8760-496b-ae96-97208a2bc3f2` | checking | 130 | 268777 | 28 | 268777 |
| `1da9085a-8760-496b-ae96-97208a2bc3f2` | savings | 56 | 184080 | 16 | 184080 |
| `41e5092b-796c-4229-a634-1e8cab0eb6c9` | checking | 101 | 306574 | 30 | 306574 |
| `41e5092b-796c-4229-a634-1e8cab0eb6c9` | savings | 39 | 160387 | 11 | 160387 |
| `6eda1262-aad8-4307-bfb2-64d685daa344` | checking | 20 | 176250 | 17 | 176250 |
| `6eda1262-aad8-4307-bfb2-64d685daa344` | savings | 3 | 15000 | 3 | 15000 |
| `bfe8cfc4-626a-420c-87a7-da007c48818b` | checking | 115 | 410091 | 29 | 410091 |
| `bfe8cfc4-626a-420c-87a7-da007c48818b` | savings | 31 | 131122 | 12 | 131122 |
| `c393fd39-f9b5-41d6-8c74-569d4ac05214` | checking | 119 | 447686 | 31 | 447686 |
| `c393fd39-f9b5-41d6-8c74-569d4ac05214` | savings | 32 | 77713 | 11 | 77713 |
| `d478db0f-0ce3-42e1-b7c4-905b57f092ec` | checking | 92 | 681135 | 28 | 681135 |
| `d478db0f-0ce3-42e1-b7c4-905b57f092ec` | savings | 13 | 77587 | 8 | 77587 |
| `da5ef035-13d7-49b0-9235-7b7e3597c984` | checking | 80 | 315570 | 30 | 315570 |
| `da5ef035-13d7-49b0-9235-7b7e3597c984` | savings | 23 | 188868 | 15 | 188868 |

## Release run

Deploy step 20:38:33Z → 20:38:38Z: fetched and reset to `2bdfac6`, cleaned `docs/`, `pip install` (all requirements
already satisfied), then `flask db upgrade`:

```text
Running upgrade a4b50fee84c3 -> d6b1e0c4a825, Protect payroll creation lineage without rewriting historical evidence.
Running upgrade d6b1e0c4a825 -> e7c2a9d4f610, Derive posting from scoped reconciliation, freeze creation sequence and origin.
Running upgrade e7c2a9d4f610 -> f8b2d6e0a410, Immutable attributable recovery and exact version-three creation evidence.
Running upgrade f8b2d6e0a410 -> f9a3c7d1e620, Terminal PROD eligibility receipts with immutable creation lineage.
```

The four migrations together took about 0.3 s. The service restarted, and the health probe on `127.0.0.1:8000/health`
passed at 20:38:40Z.

## §VIII post-release verification

Host and database checks, read-only, after the release:

| Check | Result |
|---|---|
| Host `HEAD` | `2bdfac65e9251e1451f29454c18de1aaac947f57`; untracked `venv.old/` only |
| Service | `classroom-economy` active since 20:38:38Z, `--workers 1` (one master, one worker) |
| Health | `/health` returns `ok` |
| Scheduler | Started 20:38:40Z in the single worker, which holds the scheduler lock |
| Errors since start | 0 `ERROR`, `CRITICAL`, `Traceback` or `WORKER TIMEOUT` lines in the service journal since 20:38:30Z |
| Database revision | `f9a3c7d1e620`; `ledger_transaction.status` no longer exists |
| **Balances** | **Identical to the pre-release baseline** in all 14 class/account rows, for both ledger and snapshot sums; 854 ledger rows |
| #1482 | `GET /sysadmin/logout` answers 405 (host to gunicorn, nginx not involved) |
| #1476 | `/student/login` and `/admin/login` answer 200 |

Operator browser checks: *to record* (Redemptions tab, payroll page, attendance correction modal, console Sign Out).

The release's specific checks, as planned:

- **Database revision** is `f9a3c7d1e620`; `ledger_transaction` has no `status` column.
- **Balances unchanged:** checking and savings totals per class match the §VI pre-release balance baseline.
- **#1472:** service journal lines appear once each, with no `INFO:app:` duplicates after the first passkey sign-in.
- **#1473:** Economy > Store shows the Redemptions tab; a waiting redemption in a real class can be decided without
  a 500.
- **#1476:** the student and teacher login pages render with no notice file present.
- **#1477:** the payroll page opens, and the attendance correction modal opens for a completed interval (no
  invalidation needs to be made to verify it).
- **#1482:** `GET /sysadmin/logout` answers 405 and the operator stays signed in; the console's **Sign Out** button signs out.
- **Carried over:** the first automatic payday, 2026-10-10, now runs under #1477's payroll lineage triggers;
  hall-pass reject and cancel in production; #1469's `TLCP-SURFACE-PRINCIPAL-MISMATCH` line not yet observed.

## Rollback

**There is no redeploy rollback.** `e7c2a9d4f610`, `f8b2d6e0a410` and `f9a3c7d1e620` raise on downgrade by design
(DOM-LED-001, INV-ARC-016), and `ad9574334` cannot run against the migrated schema because it reads
`ledger_transaction.status`. Under SOP-DEP-001 §XIV the operator chooses, on verified evidence, between:

- **Fix forward:** a reviewed forward migration or code fix on `main`, released the same way.
- **Restore:** stop the application, restore backup point B (`cth-db-20261004T203352Z-manual`, §VI), and release `4c2fc4bc4` or `ad9574334`.
  Anything written after the release (payroll, purchases, attendance) is lost and must be re-entered.

## Host maintenance in the same window

Done after backup point A and before backup point B, on the then-running hotfix code, so a host problem could not be
mistaken for a release problem. A read-only host snapshot at 18:57 UTC came first. The working checklist is outside
the repository.

| Item | Result |
|---|---|
| Droplet snapshot | `app-server-1791144850804`, 12.77 GB, taken in the DigitalOcean panel after point A with the app stopped. A break-glass for the reboot; to be deleted once the release is confirmed, since it holds the database and `.env` |
| Package holds | `grafana`, `tempo`, `alloy` held (`apt-mark hold`); upgrades available but deferred to an observability review |
| Upgrade | `apt-get full-upgrade`: kernel `5.15.0-194` → `5.15.0-198` (`linux-virtual` meta and new `linux-image`/`modules`/`headers-5.15.0-198`), `libaudit1`, `libaudit-common`. `sosreport` held back by Ubuntu's phased rollout. Nothing for PostgreSQL, OpenSSH, Tailscale, Redis or nginx |
| Why it waited | Unattended upgrades cover `jammy` and `jammy-security` only, not `jammy-updates`, which carries the kernel meta package |
| Reboot | Booted 20:30:01Z; back over Tailscale 81 s after the reboot command. No `reboot-required`, `dpkg --audit` clean, no failed units |
| Services after boot | `postgresql@14-main`, `redis-server`, `cth-student-setup`, `nginx`, `tailscaled`, `fail2ban`, `prometheus`, `grafana-server`, `loki`, `promtail`, `classroom-economy` active; `tempo` and `alloy` inactive, as before |
| Listeners off loopback | Only nginx `:80`/`:443`, sshd `:22` and Tailscale, matching `docs/ops/PRODUCTION_HOST_NETWORK.md` drift check 1 |
| Other host facts | Ubuntu 22.04.5; PostgreSQL 14.24; nginx 1.18.0; Tailscale 1.102.4; Python 3.10.12; `/` 50% of 25 G; Let's Encrypt certificate valid to 2026-12-07, `nginx` authenticator. `pip-audit` on the production venv's full freeze (85 packages): no known vulnerabilities |
| DigitalOcean web console | Not working. The droplet agent is healthy, but the web console connects over public port 22, which the `Cloudflare` cloud firewall closes. DigitalOcean publishes no console source ranges, so no rule was added; root has no password, so the Recovery Console is not usable either. The tailnet is the only way in |

## Follow-ups

- Create tag `v2.1.1` on `2bdfac6` and its GitHub release; date the `[2.1.1]` CHANGELOG section.
- Lift the Cloudflare Access window once the operator browser checks pass, and post the resolved status update.
- Delete droplet snapshot `app-server-1791144850804`.
- First automatic payday, 2026-10-10, now runs under #1477's payroll lineage triggers.
- `infra/student-setup/README.md` says Redis 7 or newer; production runs 6.0.16 and every step-5 check passes. Find
  whether anything 7-only is relied on, then correct the README or upgrade.
- The application service runs as `root`, so the `cth-student-setup` socket group does not restrict access; the Redis
  ACL does. The README asks for the app's own service account.
- `POST_LAUNCH_TRACKER_2026.md` §VI is stale: Tempo is stopped (not crash-looping), `/tmp/loki` no longer exists, and
  `/var/lib/loki/chunks` holds 54 MB (not 333 MB). Confirm Loki's configured storage path before closing those items.
- A break-glass that does not depend on the tailnet: none exists today (see the web console row above).
- Delete `venv.old/` (162 MB) from the production checkout.

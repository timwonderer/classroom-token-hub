# Release record: v2.2.0, `5ebae62db`

Released 2026-10-09 at 07:10 UTC (Friday, 00:10 PDT), outside the school day.

**Type:** Tagged release under `SOP-DEP-002`, **with no migration.** It tags as v2.2.0 everything merged to
`main` since v2.1.1 and ships to production everything merged after the untagged release `1cdbf03da`
(2026-10-06). Production's database was already at the head revision, so the release changed code only, and
rollback is re-releasing `1cdbf03da`; no restore is needed. The application was stopped anyway, so the backup
is a consistent point.

## Release identity

| | |
|---|---|
| Release SHA | `5ebae62db0c6e6469fe4948cce36ea525b995707` (tip of `main`, the merge of #1528); tag `v2.2.0` |
| GitHub release | [v2.2.0](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.2.0), published 2026-10-09 |
| Branch / lineage | `main` (`lineage_ref=main`; Production environment `V2_RELEASE_LINEAGE_REF=main`) |
| Previous deployed SHA | `1cdbf03dae6ae3d5eda7832920206db6b3bc39c4`, untagged, released 2026-10-06 03:10Z by [run 37407704785](https://github.com/timwonderer/classroom-token-hub/actions/runs/37407704785); no release record. Alembic `f9a3c7d1e620`. The P0B record (`RECON_2026-10-06_P0B_PRODUCTION_STATE.md`) established it from the host checkout |
| Release run | [37897523165](https://github.com/timwonderer/classroom-token-hub/actions/runs/37897523165), 07:10:32Z → 07:11:01Z, success |
| Triggered by | `workflow_dispatch` under `timwonderer`, dispatched by Claude Code on the owner's go-ahead |
| Verifier | Claude Code (host and database checks, read-only); browser checks by the operator, recorded under §VIII |

### Why this release

- **A store purchase needs the money (#1526).** On 2026-10-07 a student bought 32 units of a $750 whole-class
  collective goal with $0.01 in checking. The purchase posted $24,000 into a negative balance with a $25 NSF fee.
  A purchase now proceeds only when checking, alone or with a full overdraft-protection transfer from savings,
  covers it; otherwise it is refused before anything posts, with no fee. A collective goal is one buy-in per
  student. The shop shows the spendable amount and will not confirm a total above it.
- **Reversals that work (#1526).** A collective-goal purchase can be reversed, refunding it and revoking every
  unit. The NSF fee is a Ledger fee, not an obligation (`DOM-OBL-001` 3.3 §II.C), so it can be reversed too.
  The Reverse control appears only where the action would accept it.
- **Hall passes require teacher settings (#1522).** A class with no hall-pass settings no longer offers the
  built-in destinations or records `policy_uuid = 'default'`.
- **No cross-class query on every page (#1527).** `wsgi.py`'s `inject_payroll_status` read every class's payroll
  settings on each render, and nothing used the result. It also made four accessibility tests order-dependent.
- **Sysadmin log viewers removed (#1528).** Logs are read in Grafana.
- **Every-PR deprecated-symbol guard (#1524)** and the P0A/P0B records (#1518, #1519, #1521, #1523), which change
  no application behavior.

### Contents since `1cdbf03da`

`git log 1cdbf03da..5ebae62db`: #1518, #1519, #1521, #1522, #1523, #1524, #1525, #1526, #1527, #1528, plus two
documentation commits made directly on `main` (a code-review `SKILL.md` and the IFTTT notification setup
procedure). Full
detail is in the `[2.2.0]` section of the CHANGELOG, which also covers the untagged releases `381a12d49`,
`35bad089a` and `1cdbf03da`.

### Migrations

None. `git diff 1cdbf03da 5ebae62db -- migrations/` changes only `migrations/forward_only_register.txt` (the P0A
register), which is not a migration. Single head `f9a3c7d1e620`, and production was already there.

### Not part of this release

- **Purchased hall passes cannot yet be reversed.** v2.2.0 excludes `HALL_PASS` from the reversible types. That
  was a misreading: the owner ruled on 2026-10-08 that reversing a purchase invalidates every entitlement it paid
  for, hall passes included (`SPEC-OPS-001` §3.3). DOM-STORE-001's direct-grant rule governs revoking a pass on
  its own. The fix is v2.2.1.
- **Retiring the NSF fee machinery.** No path charges the fee after this release. Removing the fee settings,
  the `fee_authority` parameter and Interpretation's NSF reading follows in a later release (owner ruling
  2026-10-07). Until then Interpretation (`SPEC-ITR-001` §8.6) still counts historical NSF records as paid
  obligations.

## §VI pre-release checks

| Check | Result |
|---|---|
| Release SHA on `main`, descendant of the running release | `5ebae62db` is the tip of `main` and descends from `1cdbf03da`. `main` did not move between the full suite and the dispatch. |
| Running release before dispatch | Host `HEAD` `1cdbf03dae6ae3d5eda7832920206db6b3bc39c4`, working tree clean apart from the untracked `venv.old/`; Alembic `f9a3c7d1e620`. |
| Migration head and safety check | `flask db heads`: `f9a3c7d1e620`, single head. `bash scripts/check-migrations.sh`: all checks passed, "Safe to deploy". |
| `requirements.txt` changed | No. The release's `pip install` reported every requirement already satisfied. |
| New configuration | None. |
| Student-setup memory store (§VI item 6) | `cth-student-setup.service` and `redis-server.service` active. |
| **Full suite on the release SHA** | Run locally by the owner on `5ebae62db` (`pytest_result/20261008_pytest_full_summary.md`, `git_commit: 5ebae62db`), 4 h 06 min: **5032 passed, 4 failed, 16 skipped.** Three failures are `tests/simulated`, whose persistent database the owner chose to leave at `f4b8d2a6c1e9` (missing `unpaid_work_notice_acknowledged_at`); environmental. The fourth, `test_attendance_invalidation_routes.py::test_paid_mobile_confirmation_recovers_once_after_response_loss`, is a test timing race: after an accepted correction the page reloads (`attendance-correction.js:61`) and the test reads the modal mid-reload. It passed 8 of 8 reruns on the release tree; the test fix is a follow-up. The 16 skips are unchanged from the 2026-10-07 run apart from the deleted `sysadmin_combined_logs.html`. |
| CI on the release commit | CodeQL, Policy Guardrails, Documentation Link Checks and Deploy GitHub Pages Site passed. CI's Full Test Suite was cancelled at its 150-minute limit; the suite needs about four hours, hence the local run. Each merged PR passed its own CI, including the WCAG 2.1 AA audit. |
| **Backup** | PASS. One point, taken from the operator's Mac with `infra/db-backup/cth_db_backup.py backup --reason manual` (local only; health `DEGRADED` solely because a local point has no off-host copy) through a Tailscale SSH tunnel to `cth`, with PostgreSQL 14.24 client tools to match the server. `cth-db-20261009T065946Z-manual`, `taken_at` 2026-10-09T06:59:46.369167Z, revision `f9a3c7d1e620`, 45 tables, 14,688 rows, `artifact_sha256` `22f77278579c8cf316997cbceb87b97c6699c48b65765f366557b49d0c5ec734`. Its manifest's 45 table counts equal production's, read at 07:00:42Z with the application stopped. Restored with the owner's `age` identity into an in-memory PostgreSQL 14 (`restore --live-url`): manifest match and no-resurrection check both PASS. The identity was saved to a mode-600 file, checked against `recipients.txt`, and deleted with `rm -P` after the restore. An earlier attempt to pass the identity through a shell process substitution failed before decrypting anything (the subprocess cannot inherit that descriptor); its partial restore target was dropped and recreated. |
| Application stopped before dispatch | Yes: `inactive` from 06:57:36Z until the release restarted it at 07:10:56Z, about 13 minutes. The only database session during the window was the verifier's read-only TablePlus connection. |
| **Pre-release balance baseline** | Read at 07:09:56Z with the application stopped. Table below. |
| Timing | Outside the school day. |

### Pre-release balance baseline

Class ids only. `ledger_cents` is `sum(amount_cents)` over `ledger_transaction`; `posted_cents` is
`sum(posted_balance_cents)` over `ledger_balance_snapshot`. 1,304 ledger rows, net −4,870,454 cents. 8 of the 10
classes have ledger activity.

| class_id | Account | Txns | ledger_cents | Snapshots | posted_cents |
|---|---|---:|---:|---:|---:|
| `1da9085a-8760-496b-ae96-97208a2bc3f2` | checking | 191 | -8571334 | 29 | -8571334 |
| `1da9085a-8760-496b-ae96-97208a2bc3f2` | savings | 73 | 535946 | 19 | 535946 |
| `41e5092b-796c-4229-a634-1e8cab0eb6c9` | checking | 166 | -1771189 | 31 | -1771189 |
| `41e5092b-796c-4229-a634-1e8cab0eb6c9` | savings | 59 | 329390 | 12 | 329390 |
| `6eda1262-aad8-4307-bfb2-64d685daa344` | checking | 42 | 401533 | 23 | 401533 |
| `6eda1262-aad8-4307-bfb2-64d685daa344` | savings | 12 | 79721 | 6 | 79721 |
| `8af5d987-5262-4b95-971c-470d15249bac` | checking | 23 | 534383 | 21 | 534383 |
| `8af5d987-5262-4b95-971c-470d15249bac` | savings | 2 | 53998 | 2 | 53998 |
| `bfe8cfc4-626a-420c-87a7-da007c48818b` | checking | 154 | 538055 | 29 | 538055 |
| `bfe8cfc4-626a-420c-87a7-da007c48818b` | savings | 50 | 243679 | 16 | 243679 |
| `c393fd39-f9b5-41d6-8c74-569d4ac05214` | checking | 136 | 496825 | 31 | 496825 |
| `c393fd39-f9b5-41d6-8c74-569d4ac05214` | savings | 46 | 118606 | 12 | 118606 |
| `d478db0f-0ce3-42e1-b7c4-905b57f092ec` | checking | 131 | 866920 | 28 | 866920 |
| `d478db0f-0ce3-42e1-b7c4-905b57f092ec` | savings | 32 | 164056 | 8 | 164056 |
| `da5ef035-13d7-49b0-9235-7b7e3597c984` | checking | 132 | 674549 | 32 | 674549 |
| `da5ef035-13d7-49b0-9235-7b7e3597c984` | savings | 55 | 434408 | 17 | 434408 |

### Pre-release finding: the purchase defect was in active use

The baseline queries, run first at 06:51Z, found that the defect this release fixes had been used again in class
`1da9085a` on 2026-10-08, 16:30-16:49Z (09:30-09:49 PDT): eight purchases by two seats that the store accepted
without the money, $92,350 in all, granting 2,068 items, each with a $25 NSF fee ($200). Seat ids and amounts
only:

| Ledger row | Seat | Amount | Entitlement type | Units | Reversible in v2.2.0 |
|---|---|---:|---|---:|---|
| 1266 | 9 | -2,400,000 | COLLECTIVE_GOAL | 32 | Yes |
| 1268 | 9 | -128,000 | DELAYED_USE | 32 | Yes |
| 1270 | 28 | -75,000 | COLLECTIVE_GOAL | 1 | Yes |
| 1273 | 9 | -4,000 | DELAYED_USE | 1 | Yes |
| 1275 | 28 | -3,000 | HALL_PASS | 1 | No; v2.2.1 |
| 1277 | 28 | -2,550,000 | HALL_PASS | 1,000 | No; v2.2.1 |
| 1279 | 28 | -4,000,000 | DELAYED_USE | 1,000 | Yes |
| 1281 | 28 | -75,000 | COLLECTIVE_GOAL | 1 | Yes |

None of the 2,068 units was used, requested or ended at 06:5xZ; none of the 1,001 hall passes appears in
`hall_pass_logs.hall_pass_id` or a pending request. This release stops new cases. The corrections are the
teacher's and owner's to make through the Reverse control, as for the 2026-10-07 rows 1207 and 1208 in class
`41e5092b`. Because of this finding the owner chose to deploy that night instead of folding the hall-pass fix in,
which would have needed another four-hour suite run.

## Release run

Deploy step 07:10:50Z → 07:10:56Z: fetched and reset to `5ebae62d` ("HEAD is now at 5ebae62d Merge pull request
#1528"), `pip install` (every requirement already satisfied), `flask db upgrade` (nothing to apply), restart. The
health step passed.

## §VIII post-release verification

Host and database checks, read-only, after the release:

| Check | Result |
|---|---|
| Host `HEAD` | `5ebae62db0c6e6469fe4948cce36ea525b995707`; untracked `venv.old/` only |
| Service | `classroom-economy` active since 07:10:56Z |
| Health | `127.0.0.1:8000/health` answers 200 `ok` |
| Scheduler | Started 07:10:57Z, holding the scheduler lock |
| Errors since start | 0 `ERROR`, `CRITICAL`, `Traceback` or `WORKER TIMEOUT` lines in the service journal since 07:10:50Z |
| Database revision | `f9a3c7d1e620`, unchanged |
| **Balances** | **Identical to the pre-release baseline** in all 16 class/account rows, ledger equal to snapshot everywhere; 1,304 ledger rows, net −4,870,454 cents (07:11:31Z) |
| Pages | `/admin/login` and `/student/login` 200; `/docs` 308, its usual redirect |
| #1528 | `/sysadmin/logs` and `/sysadmin/combined-logs` 404 |
| P0B Q13 (#1495) | 14 hall-pass logs carry `policy_uuid = 'default'`, of 17; unchanged, as #1522 requires (it gates new writes and leaves history alone) |

Operator browser checks, reported by the operator on 2026-10-09: **all passed.** They covered the shop's spendable
amount and its refusal of an unaffordable total, **Joined** on a joined collective goal, Reverse shown only on
reversible rows, and teacher and student class switching.

#### `SOP-DEP-002` §VIII coverage

| §VIII item | Result |
|---|---|
| App boots normally | PASS: service active, `/health` `ok`, scheduler started, 0 error lines (verifier) |
| `/admin/login` and `/student/login` load | PASS: 200 each (verifier, host-local) |
| `/docs` loads | PASS: 308, its usual redirect (verifier, host-local) |
| Teacher current-class switching (`POST /admin/current-class`) | PASS (operator, browser) |
| Student add-class and switch-class | Switch-class PASS (operator, browser). **Add-class not run.** |
| Class-scoped admin actions respect membership | **Not run** |
| Selected-class export (`/admin/export-students?join_code=…`) | **Not run** |
| Hall-pass verification path (`/verify/hallpass/<teacher_public_token>`) | **Not run** |
| No migration head drift | PASS: production at `f9a3c7d1e620`, the single head (verifier) |

The four unrun items need an authenticated teacher or a class's verification token, so they are browser checks,
and the operator's checks for this release did not include them. The earlier records
(`DEPLOY_2026-10-02_5ac05ea6f.md`, `DEPLOY_2026-10-04_2bdfac65e.md`) do not record them either. No line of v2.2.0
changes the code of these flows (`git diff 1cdbf03da 5ebae62db` matches none of add-class, export-students,
the hall-pass verify route, current-class or switch-class). It does change what every page render runs (#1527)
and the hall-pass rules (#1522). That is reasoning, not a check. They are recorded here as not performed, and
they stay owed for this release and the next.

## Rollback

- **Code:** release `1cdbf03dae6ae3d5eda7832920206db6b3bc39c4` through the same workflow. No migration ran, so no
  database change is needed.
- **Fix forward:** a reviewed code fix on `main`, released the same way.
- **Restore:** only if data were damaged. Stop the application and restore `cth-db-20261009T065946Z-manual`.

## Follow-ups

- **v2.2.1: purchased hall passes reversible** (owner ruling 2026-10-08). Eligibility must read
  `hall_pass_logs.hall_pass_id`, since hall-pass use writes no Store `CONSUMED` event, and refuse while a pending
  request names a pass. Targets rows 1275 and 1277 above.
- **Retire the NSF fee machinery** in a later release; the economic-engine fee columns stay (code-only contract).
- **Attendance test race** in `test_attendance_invalidation_routes.py`: wait for the reload.
- **Backup tool:** quote the table identifier in `table_counts()` (Aikido finding, not exploitable).
- **Test-suite speed:** each test replays the 182-migration chain in setup (about 2.8 of the 4 hours); migrate
  once into a template database instead.
- **Two release records are missing:** `35bad089a` and `1cdbf03da`.
- **Off-host backups:** the droplet's backup timers are not installed, so every point so far is a manual one.

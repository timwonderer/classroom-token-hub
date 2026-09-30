# CTH v2 Post-Launch Tracker

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical tracker** |
| Opened | 2026-09-28, after the v2.0.1 release |
| Baseline commit | `c42f882` (`main`) |
| Production | `00166e56`, released 2026-09-29 (untagged). Latest tag `v2.0.1` = `ad64a473f`, 2026-09-28 |
| Supersedes | `PRODUCTION_READINESS_2026-09.md`, the pre-launch ship tracker, archived at `docs/archive/v2-tracking-2026/` once launch closed its purpose |

This file carries the open work that survived launch. Every item was checked against the code on
the date shown. Where an item is marked *verified*, the cited file and line held the described state
on that date; re-check before acting, because this file is descriptive and can drift. Normative
authority stays with `INV-*`, `DOM-*`, `FEAT-*`, `SPEC-*` and `SOP-*`.

---

## I. Release state

| Release | Commit | Date | Record |
|---|---|---|---|
| v2.0.0 | `26d1792b5` | 2026-09-26 | [TRANSITION_2026-09-26_26d1792b5.md](../ops/audits/TRANSITION_2026-09-26_26d1792b5.md) |
| (untagged) | `4f9854fca` | 2026-09-27 | [DEPLOY_2026-09-27_4f9854fca.md](../ops/audits/DEPLOY_2026-09-27_4f9854fca.md) |
| (untagged) | `efdf09eda` | 2026-09-27 | Covered by the v2.0.1 record |
| v2.0.1 (security) | `ad64a473f` | 2026-09-28 | [DEPLOY_2026-09-28_ad64a473f.md](../ops/audits/DEPLOY_2026-09-28_ad64a473f.md) |
| (untagged) | `bc5c07a2` (#1439) | 2026-09-29 | None yet |
| (untagged) | `eaca2a7e` (#1440) | 2026-09-29 | None yet |
| (untagged) | `29b99b14` (#1442) | 2026-09-29 | None yet |
| (untagged) | `00166e56` (#1443) | 2026-09-29 | None yet; production runs this commit |

---

## II. Operator follow-ups from the v2.0.1 release

- [ ] **Lift the Cloudflare Access window** and post the resolved status update. The update should
  say that everyone was signed out once and that passkeys must be registered again. Passkey
  registration and sign-in are verified, so nothing blocks this.
- [ ] **Publish the security advisory** (drafted on GitHub; CVSS v4.0 9.2; CWE-304 with CWE-386 and
  CWE-459), then link it from the `[2.0.1]` section of `CHANGELOG.md`.
- [ ] **Check public routes** once the window lifts. They were not verified at release because the
  gate was in place.
- [ ] **Finish verifying the student-setup memory store.** Production has run the username-retention check
  (#1442; FEAT-IDEN-002 1.5, SPEC-IDEN-001, INV-ARC-018 §IX) since release `29b99b14` on 2026-09-29, so the
  dedicated Redis is in place: the app refuses student setup unless `STUDENT_SETUP_REDIS_URL` answers with no
  RDB/AOF, no slow log, and a primary with no replicas. The app does not check the rest of
  `infra/student-setup/README.md` step 5: swap and core dumps disabled, the store excluded from backups, and the
  ACL denying `CONFIG SET`, `SAVE`, `BGSAVE`, `REPLICAOF` and `MONITOR`. Confirm those on the host and record the
  result. SOP-DEP-002 §VI item 6 keeps the store a release precondition.
- [ ] **Record and tag the 2026-09-29 releases.** `bc5c07a2` (#1439), `eaca2a7e` (#1440), `29b99b14` (#1442) and
  `00166e56` (#1443) went to production through `release-v2.yml` with no `DEPLOY_*` record in `docs/ops/audits/`
  and no tag; `CHANGELOG.md` still lists them as Unreleased.
- [ ] **FEAT-IDEN-003 `ACT-IDEN-003` audit event** is not implemented. It needs an identity
  audit-event design first; see #1427.
- [x] **`production-docs-smoke` and `markdown-web-links`** are fixed on branch
  `claude/repo-maintenance-ci-fixes-uq01eh` (2026-09-28). Optional: create a Cloudflare Access
  service token and store it as the `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` repository
  secrets, so the production docs crawl can run during a maintenance window instead of failing.

---

## III. Not yet exercised in production

Evidence that was run is not coverage that was inferred (INV-ARC-017).

- **Signed-in flows other than teacher passkeys** have not been repeated on production since the
  launch wipe. They run for the first time when teachers start using the app.
- **Rent payment.** Rent reconciliation, genesis, advance and policy binding were exercised during
  live test, but payment was not. The live-test class's preview window opens 2026-09-29.
- **Daylight-saving and midnight transitions.** Class-timezone handling is tested, but no live
  daylight-saving change has happened since launch.
- **Load.** Concurrent settlement, payroll batches and scheduled jobs have not been tested under load.
- **Browser accessibility beyond axe.** Keyboard, focus and contrast behaviour across the whole app
  still need a person using a real browser. The signed-in insurance buy and cancel dialogs have not
  had an axe audit.

---

## IV. Code hygiene (carried from the pre-launch non-blocking findings)

Each item was verified on 2026-09-28 unless it says otherwise.

| Area | Item | Where |
|---|---|---|
| Class Configuration | `replace_enabled_class_features` is imported and never used | `app/routes/admin.py:96` |
| Identity | The `Seat.block` read-through property onto `ClassEconomy.section` remains for legacy admin rendering. `block` is display metadata only (INV-ARC-014) | `app/models.py:293-300` |
| Identity | `app/utils/deletion.py` has no importer in `app/` or `scripts/`. Only a test docstring and a migration comment mention it; `app/utils/student_deletion.py` is the live module | `app/utils/deletion.py` |
| Obligations | `get_active_rent_waivers_for_class` is marked DEPRECATED ("'active waiver' is not a lawful concept", DOM-OBL-001 §V.6) and has no caller. Neither does its `RentWaiverView` projection | `app/services/obligations_service.py:1266` |
| Obligations | `_count_rent_waiver_periods` has no caller | `app/routes/admin.py:859` |
| Obligations | Waiver-history expansion still steps periods from policy settings (display only) | follow-up from insurance slice 3 |
| Ledger | `Transaction.join_code` remains as a nullable, indexed column documented as ingress/display metadata. No domain query may filter on it | `app/models.py:478` |
| Productivity | `AttendanceReasonCode` has no `daily_limit` member (`hall_pass`, `done_for_day`, `start_work`). Confirm whether the daily-limit auto tap-out needs one before adding it | `app/models.py:72-76` |
| Productivity | Payroll reversal correlation is heuristic | not re-verified |
| Access policy | `assert_can_void_transaction` has no caller and reads `transaction.teacher_id`, a column `Transaction` does not have. Delete it, or rewrite it on `class_id` before any use | `app/services/access_policy_service.py:91-104` |
| Scripts | `verify_runtime_session_attacks.py` imports the retired `Student` model and cannot run | `scripts/adversarial/verify_runtime_session_attacks.py:13` |

**Closed since the pre-launch list:** the teardown helpers left `app/routes/admin.py` for
`app/services/teacher_destruction.py`, `context_resolver.py` has no `print()` calls left,
`StoreItem` is gone (single `StoreProduct` catalog), and `update_user_report` is gone.

---

## IV-A. Contract gaps and decisions (found 2026-09-28, amending FEAT-IDEN-001/002)

- [ ] **`ACT-IDEN-001` / `ACT-IDEN-002` audit events are not emitted.** FEAT-CORE-000 §III.4 requires an
  audit record for every FEAT execution. FEAT-IDEN-001 v3.0 §VI and FEAT-IDEN-002 §VII specify them;
  `app/feats/identity_feat.py` emits neither. This is the same gap as `ACT-IDEN-003` (#1427); design them
  together.
- [x] **Decision: student login credential — passphrase (operator ruling, 2026-09-28).** DOM-IDEN-002 2.9
  (§VII login flow, §X summary) and FEAT-IDEN-002 2.1 now say username and passphrase, matching the
  code and the credential matrix. The student guides are corrected too. `diagnostics/student/login.md`
  had told students to sign in with their PIN.
- [x] **Decision: tier of `docs/REFERENCE/` (operator ruling, 2026-09-28).** `REF-TERM-001` (developer
  vocabulary) is Normative, Tier 2. `REF-TERM-002` (user-facing) is Informative but highly recommended for
  standardization; accessibility takes precedence (INV-CORE-000 §III.7, INV-ARC-020). `REF-API-001` and
  `REF-DES-001` are Informative. Recorded in SOP-DOC-000 3.4 and REF-TERM-002 1.1.

---

## IV-B. Production walkthrough findings (2026-09-29)

Observed on production (`00166e56`) after two school days of real use. The database was queried in read-only
transactions. The nginx and app logs and Loki were only read. Nothing on the host was changed. Each item was checked
against this tracker, the archived launch trackers and the live-test RESUME records before it was listed as new.

### Observed defects and debt

- [ ] **Two settlement sweeps run concurrently every hour and deadlock.** `savings_interest_payout`
  (`app/scheduled_tasks.py:1138`) calls `run_ledger_settlement_job()` itself (`:958`) before computing interest.
  The standalone `ledger_settlement` job (`:1131`) has the same one-hour interval and starts in the same process
  at the same moment. Both sweeps take `FEAT-LED-003` with the same idempotency key
  (`settlement-sweep:<class_id>:<seat_id>`, `app/services/ledger_settlement_service.py:67`) within milliseconds
  of each other.
  - Loki records seven `psycopg2.errors.DeadlockDetected` failures ("Settlement sweep failed for seat …", `:74`)
    on 2026-09-28 at 16:42, 17:42 and 22:42 UTC.
  - Checked on 2026-09-29: every `ledger_balance_snapshot` reconciles with its posted transactions, and there are
    no duplicate idempotency keys and no duplicate same-day interest postings.
  - **Harm has not been established either way.** Still open: whether interest can be computed on a posted base
    that the losing sweep failed to settle, and whether any historical posting was affected. Fix through a single
    ownership model for settlement, not by offsetting the timers.
- [ ] **Canonical context is resolved three times per authenticated request.** For example, `GET /api/student-status`
  resolves it in `capture_correlation_context` (`app/__init__.py`), again in `login_required`
  (`app/auth.py:119`), and a third time in the route itself (`app/routes/api.py`). DOM-IDEN-006 §IX requires
  `canonicalContext` to be constructed exactly once per authenticated request, and §X requires helpers to consume it
  rather than call the resolver. `validate_canonical_session_nonce` can clear the session without resetting
  `g.canonical_context`. Still to determine: how many routes re-resolve, and whether the resolutions can disagree
  within one request. Track this separately; do not normalise it while touching individual routes.
- [ ] **`/api/student-status` is rate-limited per endpoint per IP** (default 200/hour and 500/day, `app/extensions.py`).
  - The dashboard polls every 10 s (`static/js/attendance.js:118`), so a single student's tab exhausts the hourly
    limit in about 33 minutes. Shared school IPs make it sooner.
  - Production recorded 699 `429`s; support ticket #1 matches.
  - The client parses the HTML 429 page as JSON, so the timer stops updating.
  - Fix in progress on its own branch, together with an endpoint blast-radius review of the other IP-keyed limits.
- [ ] **Student tickets are visible to sysadmin before teacher escalation.** This is a regression from `384176834`,
  and it is contrary to DOM-SUP-001 §VIII and FEAT-SUP-001.
  - Before escalation, sysadmin can see the IP, user agent, page URL, category and actor public id.
  - `update_issue` lets sysadmin close an un-escalated student ticket.
  - SPEC-OPS-004 §6.2 and §6.3 describe the regressed behaviour.
  - Fix in progress on its own branch.
- [ ] **Advanced-mode payroll rounding is not applied by payroll runs.** The rounding added on 2026-09-08
  (`2d2ace33f`) lives in `app/payroll.py` `calculate_payroll_breakdown`, which has had no production caller since
  `db7079c7d` (2026-07-21). FEAT-PROD-003 (`app/feats/prod.py`) prices exact seconds × rate.
  - No test has ever referenced `_round_billable_seconds`.
  - The archived coverage claim (#35, "✅ Calculation fixed 2026-09-08") is unsupported.
  - `templates/admin_payroll.html` tells teachers that worked time rounds.
  - No normative document defines rounding, increments or overtime. This needs a decision before implementation.
    Remediation is not decided.
- [ ] **Payroll policy authority is under investigation.** FEAT-PROD-003 is reported to price from the live
  `PayrollSettings` row (`app/payroll.py` `get_pay_rate_for_class`) while the payroll event records a
  `PolicyVersion` id. A new rate becomes `IN_USE` immediately (`upsert_payroll_settings`), which may conflict with
  DOM-CLASS-003's pending-next-cycle rule.
- [ ] **Unratified citation.** The closed-session payroll rule (#1439) is cited in code as "DOM-PROD-001 §VI.3" /
  "§VI.1" (`app/services/attendance_service.py`, `app/services/payroll/settlement.py`, `app/feats/prod.py`).
  DOM-PROD-001 §VI is the Schema Authority Declaration and has no subsections, so the rule needs ratification.
- [ ] **The student's projected pay is always empty.** `get_class_attendance_status` returns `projected_pay: None`
  (`app/services/attendance_service.py:452`), so the student view and `/api/student-status` show no projection.
- [ ] **Operational.** A few items outside the repo.
  - **Grafana.** An expired Grafana tab (refreshing every 5 s) follows nginx's `@grafana_login_redirect` into
    `GET /sysadmin/login` on every background request, about 60% of app log volume.
  - **Sysadmin login GET.** `GET /sysadmin/login` clears `user_id` from the session (`app/routes/system_admin.py`),
    which is a GET-time authentication-state mutation that needs review.
  - **Loki.** Loki stores chunks under `/tmp/loki/chunks`, which is emptied at boot, and has no retention period
    set. Local app logs rotate at 1 MB × 6.
  - **Tempo.** Tempo is still crash-looping (live-test finding 18, `RESUME_2026-09-22.md`): about 117,000 restarts,
    roughly 390,000 journal lines a day into Loki, and the app's OTLP trace export (`OTEL_TRACES_ENABLED=true`)
    targets it.
- [ ] **No scheduled database backup exists.** WAL archiving is off, and no pre-release dump was taken for the
  four 2026-09-29 releases. Older dumps sit on the production host, including v1 dumps from 2025-07 and 2025-11
  that hold student rows whose live records no longer exist. A backup and retention model is being designed
  against INV-ARC-018 §VII.4 and INV-CORE-000 §III.5 before any automation.
- [ ] **No incident record for PROD-PAY-001.** The only account is in `CHANGELOG.md`. The corrections were approved
  in production on 2026-09-29 between 04:21 and 04:26 UTC (79 students, $1,947.40). Release records for the
  2026-09-29 releases are tracked in §II.

---

## V. Tests to confirm

The rent-disablement list ratified on 2026-09-24 is mostly covered by
`tests/dom/obligations/test_rent_disablement_surviving_state.py`. There are eight tests: untouched
advance withdrawal, perks for a period paid in advance, reconciliation creating nothing while rent
is disabled, late fees continuing, paying off surviving rent not re-enabling rent, the rent page
reachable or absent, and late fees following the frozen policy. No test was found by name for
these two cases:

- [ ] disabling rent during a **partly paid** preview period (the committed part stays, the
  remainder is payable, late fees continue);
- [ ] a **policy-B preview change does not move a cycle created under policy A** (mutation-tested).

---

## VI. Architecture

- [ ] **Frozen migration baseline, reconstruction.** On 2026-09-28 the freeze landed:
  `0001_bootstrap` executes `migrations/baseline/0001_baseline_schema.sql`, and model changes no
  longer reach step 0. What remains is a baseline that reconstructs the schema each historical
  migration was written against. Until then, the two `SOP-DB-001` §V.B Bootstrap-Replay Corrections
  (`3a69db4907b4`, `8f1a2c3d4b5e`) are load-bearing. Evidence:
  [BASELINE_FREEZE_2026-09-28.md](../ops/audits/BASELINE_FREEZE_2026-09-28.md).

---

## VII. Dependencies

- [ ] **Dependabot has no `npm` entry for `/docs-site`.** `.github/dependabot.yml` declares only
  `pip` and `github-actions` at `/`, so the alerts raised against `docs-site/package-lock.json` can
  never become update PRs. That lock file is build tooling for the developer docs site; it is not
  shipped with the application.
- [ ] **Open Dependabot PRs.** They were reviewed on 2026-09-28 and all kept. The suggested merge order
  is:
  1. low-risk: #1416 packaging, #1415 SQLAlchemy/greenlet patch, #1417 playwright, #1414 actionlint
     action, #1413 setup-node;
  2. #1381 redis;
  3. #1419 alembic with #1374 Mako. Rehearse `flask db upgrade` and `flask db downgrade <rev>` first;
  4. #1380 gunicorn. Since 26.1 it rejects duplicate Host/Content-Type headers with a 400, so watch the
     400 rate;
  5. #1378 google-auth with #1418 firestore (status service; merging deploys it);
  6. #1371 with #1372, the GCP actions v3 pair (the first deploy after merge is the real test).

  CI on pip bumps does not run the application test suite, so a green PR is not evidence that the
  app works with the new pin. Closed as superseded or obsolete: #1382, #1384, #1391 and #1411.

---

## VIII. Deferred features

- **Bug-hunter badge system.** Design only (`DOM-OPS-003`, two badge SPECs, nine SVGs), preserved at
  tag `archive/bug-hunter-badges-20260914`. Before it can land, the badge SPECs must be renumbered,
  because `SPEC-OPS-001` is already `SPEC-OPS-001_REVERSAL_AND_VOID.md`.
- **Support-content registry.** Would move user-facing help text out of templates into versioned
  content files (INV-CORE-000 §III.7). It touches every template, so it belongs with the
  accessibility work.

---

## IX. Maintenance

Amend this file when an item changes state, and record each closure with its commit SHA. Dated
snapshots of finished work belong in `docs/archive/v2-tracking-2026/` (archived material). Release
and audit records belong in `docs/ops/audits/`.

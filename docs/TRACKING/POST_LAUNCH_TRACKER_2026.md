# CTH v2 Post-Launch Tracker

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical tracker** |
| Opened | 2026-09-28, after the v2.0.1 release |
| Baseline commit | `c42f882` (`main`) |
| Production | v2.1.0 = `5ac05ea6f`, deployed 2026-10-02 ([record](../ops/audits/DEPLOY_2026-10-02_5ac05ea6f.md)). Latest tag `v2.1.0` |
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
| (untagged) | `00166e56` (#1443) | 2026-09-29 | None yet |
| (untagged) | `314158d53` (#1438, #1449, #1451) | 2026-09-30 | [DEPLOY_2026-09-30_314158d53.md](../ops/audits/DEPLOY_2026-09-30_314158d53.md) |
| v2.1.0 | `5ac05ea6f` (#1464) | 2026-10-02 | [DEPLOY_2026-10-02_5ac05ea6f.md](../ops/audits/DEPLOY_2026-10-02_5ac05ea6f.md); production runs this commit |

---

## II. Operator follow-ups from the v2.0.1 release

- [ ] **Lift the Cloudflare Access window** and post the resolved status update. The update should
  say that everyone was signed out once and that passkeys must be registered again. Passkey
  registration and sign-in are verified, so nothing blocks this.
- [x] **Publish the security advisory.** Published 2026-09-28 as
  [GHSA-5v6c-mw3v-fmf2](https://github.com/timwonderer/classroom-token-hub/security/advisories/GHSA-5v6c-mw3v-fmf2)
  (critical; CVSS v4.0 9.2; CWE-304 with CWE-386 and CWE-459). Linked from the `[2.0.1]` section of
  `CHANGELOG.md` in `05951375d` (#1464).
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
  and no tag. `CHANGELOG.md` lists them under `[2.1.0]`, and tag `v2.1.0` (2026-10-02) contains them; the records are still missing.
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

## IV-B. Production walkthrough findings (2026-09-30)

Observed on production (`00166e56`) after two school days of real use. The database was queried in read-only
transactions. The nginx and app logs and Loki were only read. Nothing on the host was changed. Each item was checked
against this tracker, the archived launch trackers and the live-test RESUME records before it was listed as new.

### Observed defects and debt

- [ ] **Settlement sweeps deadlock against class-wide FEAT transactions.**
  - **Lock order.** `settle_balances` (`app/services/ledger_settlement_service.py:126`) locks the seat row, then
    the `classes` row `FOR UPDATE` (`:142`). That order is the one INV-LED-015 requires, and the lock is taken even
    when the seat has nothing pending.
  - **The conflict.** Rent reconciliation (FEAT-OBL-002, one transaction per class) inserts rows with foreign keys
    to both `classes` and `seats`. Each FK check takes `FOR KEY SHARE` on the class row first, then on each seat.
    `FOR KEY SHARE` conflicts with `FOR UPDATE`, so the two transactions lock in opposite orders and deadlock.
  - **Evidence.** Loki records seven `DeadlockDetected` sweep failures on 2026-09-28, at 16:42, 17:42 and 22:42 UTC
    (`while locking tuple … in relation "classes"`). In each case the blocker was a FEAT-OBL-002 transaction.
  - **Other contenders.** Automatic payroll, interest, collective-goal refunds and insurance renewal take the same
    inverted order. The claim flow locks the class row before the seat (`app/feats/identity_feat.py:339-340`),
    the opposite of INV-LED-015.
  - **Two sweeps per hour.** `savings_interest_payout` (`app/scheduled_tasks.py:1138`) calls
    `run_ledger_settlement_job()` itself (`:958`). The standalone `ledger_settlement` job (`:1131`) fires in the same
    second, so two sweeps run concurrently. A probe showed that two sweeps alone serialize without deadlocking.
  - **Harm.**
    - No historical posting was affected. All 23 production `Interest` rows recompute exactly from the ledger. In
      every case the other sweep committed the failed seat before the interest read.
    - Underpayment is reachable, though. A probe using the real job functions and a real Postgres deadlock paid
      interest on the stale posted base ($0.33 where $0.67 was due), and the monthly idempotency key makes the result
      final for the period.
    - The interest job ignores the sweep's `failed_contexts`.
  - **Proposed direction, not yet decided.** Serialize settlement per class, and take the class row
    `FOR NO KEY UPDATE`, which no longer conflicts with FK `KEY SHARE`. Run settlement then interest as one hourly
    pipeline, and skip interest for a seat whose settlement failed. Do not offset the timers.
  - **Documentation gap.** There is no FEAT-LED-003 contract document.
  - **Minor.** The sweep selects POSTED rows that have a NULL `posted_at` but never repairs them.
  - **Status (2026-09-30).** Open, and it stays tracked. There is no PR yet; the fix waits on a FEAT-LED-003 contract.
- [x] **Savings interest is configured weekly but paid once per calendar month.** Released: #1449 in `314158d53`
  (2026-09-30); the 365-day-year and label follow-ups in #1454, released in v2.1.0 (`5ac05ea6f`, 2026-10-02).
  - **Configuration.** Every class with interest configured (6 `economic_engine` rows) is weekly payout with daily
    compounding.
  - **Code.** The payout idempotency key is monthly: `savings-interest:<class>:<seat>:<YYYY-MM>`
    (`app/services/ledger_interest_service.py:84-86`). The amount is one payout window
    (`app/services/economic_engine.py:744-773`).
  - **Effect in production.** Each seat has received exactly one week's interest for September (23 rows, $1.82). The
    next payment will fall on the first class-local day of October, and nothing more until November. Meanwhile the
    student savings projection shows four or five payouts a month.
  - **Timing.** Interest is also paid at the first hourly tick of the period with a positive posted balance, not
    after the window closes (SPEC-ECON-001 §14.1, §8.2, §12).
  - **Status (2026-09-30).** Fixed by #1449, which is merged to `main` as `96ea2901f` and awaits release before
    2026-10-01 07:00 UTC. Payout now follows the configured window and pays only closed windows, using the daily
    balance method (SPEC-ECON-001 1.1 §9.2).
  - **Owner decisions.**
    - The daily balance method is ratified.
    - Option A: the September payments count as the week of 2026-09-28, with no top-up.
    - A 365-day year is kept and must be documented (follow-up PR).
    - The "Estimated interest next payout" label is to be fixed (follow-up PR).
- [ ] **Canonical context is resolved three times per authenticated request.** For example, `GET /api/student-status`
  resolves it in `capture_correlation_context` (`app/__init__.py`), again in `login_required`
  (`app/auth.py:119`), and a third time in the route itself (`app/routes/api.py`). DOM-IDEN-006 §IX requires
  `canonicalContext` to be constructed exactly once per authenticated request, and §X requires helpers to consume it
  rather than call the resolver.
  - **Scope.** 22 of 136 decorated routes call the resolver after their auth decorator, 18 of them in `student.py`.
    Nine more re-resolve through helpers or context processors.
  - **Stale context after a revoked session.** `validate_canonical_session_nonce` runs after
    `capture_correlation_context` and can `session.clear()` without resetting `g.canonical_context` or
    `g.correlation_context`. The stale context is then still trusted in three places:
    - `admin_bp.before_request` (`app/routes/admin.py`, before `@admin_required`), which can answer a superseded
      teacher cookie with class feature state instead of a sign-in redirect;
    - TLCP request traces and error events, which attribute the request to the revoked actor;
    - `login_required`, which sets `g.canonical_context` before its expiry check.
  - **Status (2026-10-02).** #1469 registers `validate_canonical_session_nonce` before
    `capture_correlation_context`, so a revoked cookie no longer reaches `g.canonical_context`, the TLCP trace, or
    `admin_bp.before_request`. The `login_required` expiry ordering and the repeated resolution remain open.
  - **Impact.** No cross-class leak was found.
  - **Target design.** One resolution in a `before_request` that runs after nonce validation. Auth decorators only
    check its result, and a structural guard with a mutation proof flags any other call. Do not normalise the
    pattern while touching individual routes.
  - **Status (2026-09-30).** Open, and it stays tracked as separate work. #1447 does not normalise it. Its key
    function reads the context `login_required` validated, and the route's own re-resolution is marked as tracked debt.
- [ ] **Every authenticated request writes a TLCP trace row.** `persist_request_trace` in `after_request`
  (`app/__init__.py`) inserts one row and prunes on every request, including the 10-second
  `/api/student-status` poll: about 16,000 rows in 3.5 days. Decide whether high-frequency polls should be traced.
- [x] **`/api/student-status` is rate-limited per endpoint per IP** (fixed by #1447, released in v2.1.0, `5ac05ea6f`, 2026-10-02) (default 200/hour and 500/day, `app/extensions.py`).
  - The dashboard polls every 10 s (`static/js/attendance.js:118`), so a single student's tab exhausts the hourly
    limit in about 33 minutes. Shared school IPs make it sooner.
  - Production recorded 699 `429`s; support ticket #1 matches.
  - The client parses the HTML 429 page as JSON, so the timer stops updating. Production traffic comes from a pool of about 134 school addresses, not one; most 429s are a single long-lived poller exhausting 200/hour on its own.
  - **Status (2026-09-30).** #1447 fixes `/api/student-status` only: the limit is keyed per `(class_id, seat_id)`,
    429s on `/api/` return JSON, and the client backs off.
- [ ] **Rate-limit blast radius beyond `/api/student-status`, still open.** The endpoint review behind #1447 found:
  - **Wrongly keyed by IP.** Other signed-in, class-scoped student routes use the per-IP defaults of 200/hour and
    500/day per endpoint. `/student/dashboard`, transfer, payroll and the hall-pass endpoints would break first at a
    school behind a single address.
  - **Right key, wrong size for shared school networks.** `/student/login` (60/min per IP, with GET and POST sharing
    the budget), claim and setup, and `/recovery/lookup` (10/min; FEAT-IDEN-004 §6 also calls for a per-code lockout).
  - **Docs.** `/docs/*` has one endpoint-wide budget. The production 429s there all came from the project's own
    docs-smoke crawler.
  - **Next step.** Decide endpoint by endpoint. Do not replace IP limiting wholesale, because unauthenticated
    credential endpoints need network limits.
- [x] **Student tickets are visible to sysadmin before teacher escalation.** Fixed by #1448, released in v2.1.0
  (`5ac05ea6f`, 2026-10-02). This is a regression from `384176834`,
  and it is contrary to DOM-SUP-001 §VIII and FEAT-SUP-001.
  - Before escalation, sysadmin can see the IP, user agent, page URL, category and actor public id.
  - `update_issue` lets sysadmin close an un-escalated student ticket.
  - SPEC-OPS-004 §6.2 and §6.3 describe the regressed behaviour.
  - **Status (2026-09-30).** Fixed in #1448 and awaiting merge. One server-side visibility rule applies to every
    sysadmin list, count, detail page and action, and SPEC-OPS-004 is corrected to v1.3.
  - **Before merging:** check whether `tests/simulated/test_group_d_pages.py`, which uses a fixed `ISSUE_ID = 1`,
    still passes.
- [x] **Advanced-mode payroll rounding is not applied by payroll runs.** Rounding removed by #1450, released in
  v2.1.0 (`5ac05ea6f`, 2026-10-02). The rounding added on 2026-09-08
  (`2d2ace33f`) lives in `app/payroll.py` `calculate_payroll_breakdown`, which has had no production caller since
  `db7079c7d` (2026-07-21). FEAT-PROD-003 (`app/feats/prod.py`) prices exact seconds × rate.
  - No test has ever referenced `_round_billable_seconds`.
  - The archived coverage claim (#35, "✅ Calculation fixed 2026-09-08") is unsupported.
  - `templates/admin_payroll.html` tells teachers that worked time rounds.
  - No normative document defines rounding, increments or overtime.
  - **Operator ruling (2026-09-30).** Remove rounding as a supported payroll setting.
    - The user-facing configuration and every claim about rounding are removed in #1450. The column stays, retired,
      so the schema change is no more destructive than needed.
    - **No remediation.** Rounding was never normatively defined and never applied, so the hypothetical rounded
      amount is not an amount students were owed. The gap computed during the walkthrough was ~$138.50 across 164
      payroll payments, ~$65.73 on the PROD-PAY-001 corrections, and at most $4.08 per student. It is recorded here,
      and no correction was made for the reason above.
- [x] **A saved pay rate governs the open payroll cycle immediately, contrary to DOM-CLASS-003 §VII.** Fixed by
  #1450, released in v2.1.0 (`5ac05ea6f`, 2026-10-02).
  - **The rule.** DOM-CLASS-003 §VII requires a pending `next_boundary` transition, activated at payroll cycle
    completion (FEAT-PROD-004). DOM-PROD-001 §XV.3 and INV-ARC-015 §VI.7 say the same.
  - **The code.** `upsert_payroll_settings` (`app/services/payroll_settings_service.py:99-158`) makes the new
    `PayrollSettings` row `IN_USE` immediately. It also activates a new `PolicyVersion` with no `PolicyTransition`.
  - **Effect.** Work already finished under the old rate is paid at the new one. A probe through the real routes
    and jobs paid 15 minutes worked at $1/min as $150.00 after a save of $10/min.
  - **Production.** Not yet exercised: each class has exactly one payroll settings row and one payroll version, and
    `policy_transitions` is empty. It is reachable by any teacher's next rate save.
  - **Status (2026-09-30).** Fixed in #1450, which is not yet deployed. `payroll_settings` becomes append-only and
    effective-dated. The owner's rulings are implemented: a monthly schedule is the anchored calendar month
    (SPEC-TIME-001 §IX.12), pay frequency is derived rather than stored, and the only schedules are weekly, biweekly
    and monthly. `first_pay_date` is required.
- [x] **Payroll amounts are priced from a source other than the policy version the event records.** Fixed by #1450
  and #1452, released in v2.1.0 (`5ac05ea6f`, 2026-10-02); the release added the `payroll_settings` and `payroll_event`
  immutability triggers.
  - **Two sources.** FEAT-PROD-003 prices from the live `PayrollSettings` row (`app/feats/prod.py:535` →
    `app/payroll.py:56-70`). The event records `PolicyVersion.is_active`, read once in `settlement.py:164`. They
    agree today only because `upsert_payroll_settings` writes both in one transaction.
  - **Three ways they diverge, all shown by probes.**
    - A pending payroll transition, which becomes reachable once DOM-CLASS-003 is implemented without moving the
      pricing source.
    - A hidden settings row, where pricing falls back to the default rate. Latent.
    - A teacher save that commits while a run is in progress. Settlement takes no lock shared with the upsert, so
      this is reachable today as a race.
  - **Contracts affected.** DOM-PROD-001 §XI, FEAT-PROD-003 §II.1 and INV-CORE-000 §III.3 (reproducibility).
  - **No immutability triggers.** Production has none on `payroll_event`, `policy_versions` or `payroll_settings`.
    Only `attendance_sessions` and `ledger_transaction` have them.
  - **Operator ruling (2026-09-30).** `policy_versions` and `policy_transitions` were never authorized as canonical.
    The owner removed them in `184910af8` (2026-08-03); `abb49d75e` (2026-08-08) reintroduced them and `e6f10734e`
    carved out an exception for them.
    - Payroll reads only `payroll_settings` (#1450).
    - #1452 retires both tables everywhere.
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
  - **Status (2026-10-02).** #1446 is released in v2.1.0: `GET /sysadmin/login` no longer signs anyone out. Its
    nginx snippet (`infra/grafana-auth/README.md`) is an operator step and has not been applied, so the Grafana
    loop is still open. Loki and Tempo are unchanged by the release.
  - **Loki.** Loki stores chunks under `/tmp/loki/chunks`, which is emptied at boot, and has no retention period
    set. Local app logs rotate at 1 MB × 6.
  - **Tempo.** Tempo is still crash-looping (live-test finding 18, `RESUME_2026-09-22.md`): about 117,000 restarts,
    roughly 390,000 journal lines a day into Loki, and the app's OTLP trace export (`OTEL_TRACES_ENABLED=true`)
    targets it.
- [ ] **Leftover v1 data on the host.**
  - The owner deleted the 2025-07 and 2025-11 v1 database dumps on 2026-09-30.
  - Still on disk: 333 MB of orphaned v1-era Loki log chunks under `/var/lib/loki/chunks`, dated 2025-12-22 to
    2026-04-12. Loki has read from `/tmp/loki/chunks` since April, so nothing reaches these chunks.
  - Still on disk: the live-test database dumps and env-file copies. They are waiting on the owner confirming the
    keys are stored off the droplet.
- [x] **PROD-PAY-001 incident record merged (#1441, 2026-10-01).**
  `docs/ops/audits/INCIDENT_2026-09-28_PROD-PAY-001.md`. Checked against production (read-only, 2026-10-01): 79
  `manual_credit` payroll events recorded between 04:21:32 and 04:25:47 UTC on 2026-09-29, matching the record's
  04:21–04:25 window and 79 students. Release records for the 2026-09-29 releases are tracked in §II.
- [ ] **No database backup of any kind exists.** The owner confirmed on 2026-09-30 that DigitalOcean droplet backups
  are off. There is also no scheduled dump and no WAL archiving.
  - **Direction (owner, 2026-09-30).** Scheduled encrypted off-host backups, with a replacement baseline after each
    protected destruction:
    - seat, class or teacher-account deletion is a protected destruction;
    - once one completes, recovery points that predate it become unacceptable;
    - they are superseded only after a new verified baseline exists;
    - baseline health is reported as CURRENT, or STALE/DEGRADED.
  - **Before any normative text or implementation:** a failure-mode review of this model is under way.
  - The pre-release dump for #1449 is an interim measure. It is not the settled architecture.
- [ ] **Security and ops decisions taken 2026-09-30.**
  - Disable Grafana anonymous Admin, then validate authenticated access.
  - Disable Tempo and set `OTEL_TRACES_ENABLED=false`.
  - Move Loki's storage out of `/tmp`. The retention period waits on the owner's review of what Loki retains.
  - `GET /sysadmin/login` must not destroy another browser context. The fix is added to #1446.
  - **Follow-up:** `admin.login` has the same GET-time session pop (`app/routes/admin.py:2573`).
- [x] **TLCP misclassified a student at the operator sign-in page as an invariant violation (fixed in #1469).**
  On 2026-10-02 (17:20–17:21 UTC) a student's Chromebook followed the landing page's operator sign-in button to
  `/sysadmin/login`. It loaded the page and submitted it twice, with no sysadmin session created, and the app logged
  8 `TLCP-INVARIANT-VIOLATION` lines at ERROR. TLCP named the request "sysadmin" from its URL. Owner ruling 2026-10-02:
  keep both dimensions, the surface (URL) and the principal (who authenticated) (INV-ARC-019 §V, §XIII).
  - The ERROR now fires when the principal is a sysadmin and the request carries class context, on any URL. The old
    rule never caught that case.
  - A student or teacher on a sysadmin surface logs `TLCP-SURFACE-PRINCIPAL-MISMATCH` at INFO, with surface,
    principal, class context and outcome.
  - **Follow-up:** `GET /sysadmin/logout` signs out any principal, not just a sysadmin. It is the same GET-time session
    pop as `admin.login` above.
- [ ] **Simple interest does not conform to SPEC-ECON-001 §4.1.** Credited interest joins the earning balance for
  every calculation type. `simple` prevents compounding within one payout window, but each window's credit then
  earns interest in later windows, so simple interest compounds across payout windows. Tracked and deferred by the
  owner; no production class uses simple interest. Until it is resolved, simple interest must not be described as
  fully supported or correct.
- [ ] **Session-epoch binding for identity-establishment pages (follow-up to #1457, owner design 2026-10-01).**
  #1457 refuses claim, setup and recovery requests from a signed-in browser. It cannot yet tell that a page was
  opened under one sign-in and submitted under another (sign-in changed in another tab). Owner design:
  - each authentication transition mints an opaque, random, non-secret `page_auth_epoch`, derived from nothing
    reusable (not from the session nonce); its only valid operation is equality comparison, and it carries no
    identity meaning and no authority;
  - pages carry the epoch they were rendered under; at the server boundary, a submitted epoch that differs from the
    current session epoch is rejected before capability evaluation or mutation;
  - it marks authentication generation only; class context is a separate marker.
  Refusal copy: the #1457 page ("We are having trouble determining who you are right now…"). Related items found
  with #1457: `/student/logout` requires an active class (a student with none is sent to class selection, not signed
  out); `/admin/logout` keeps `current_session_nonce`; all three logouts are GET-only.

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

- [ ] **Simple interest: credited interest still earns (SPEC-ECON-001 Appendix A, KD-1).** §4.1 says
  paid interest SHALL NOT participate in simple-interest accrual. The runtime keeps accrued interest
  out of the base within a payout window, but once credited it is posted savings balance and earns
  in every later window, for simple as for compound (`accrue_daily_interest` in
  `app/services/economic_engine.py`, fed by `apply_savings_interest` / `forecast_savings` in
  `app/services/ledger_interest_service.py`). Deferred by operator ruling 2026-09-30; the simple
  option stays. Until fixed, the teacher banking settings and the teacher and student interest guides
  carry a known-issue note, and nothing describes simple interest as fully supported. A fix needs a
  per-seat record of credited interest to subtract from the earning base, for runtime and forecast
  alike.
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


## Attendance Provenance Foundation — Ledger Proof Gate (2026-10-03)

**Bounded reconciliation-status repair in local implementation/review; production readiness is not certified.** DOM-LED-001 v2.7, FEAT-LED-001 v1.4 and DOM-OPS-002 v1.5 authorize creation-time immutable posting sequence and command metadata, signature version 2 over sixteen implemented fields, and cursor-derived PENDING/POSTED. Settlement changes account reconciliation projections and may initialize informational `posted_at`; it never rewrites signed effect fields or creation hashes. The three future compensation fields and atomic interval recovery remain a later implementation.

This supersedes the former broad Ledger-block description for the approved bounded cutover. The original conflict was persisted lifecycle `status` mutated after its creation signature; the repair removes stored status rather than preserving a parallel authority or synthesizing an original payload. Historical version 1 signatures remain unchanged and strict proof remains unavailable where retired inputs or original membership cannot be proven. Prospective verified contributions require successful independent runtime evidence before this item is closed.

Migration preflight must fail closed on unsupported historical state, missing canonical sequence, VOID state, or mismatched reconciliation evidence. No automatic production drain, backfill, sequence inference from IDs, historical signature replacement, or monetary-history rewrite is authorized. The old status-mutating drain is the pre-existing authority conflict and is not labeled a lawful remedy. A blocked preflight requires a separately reviewed historical disposition. No production drain or deployment was performed in this foundation.

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
| **Deployable ref (§VI.A)** | tag `live-test/2026-09-19` — annotated, pinned to the SHA above |
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

Checkout ref: `live-test/2026-09-19` (detached). Not `main` — at gate close
`main` was already `cc9639b11`, carrying this record, and its tree
(`8418c38e6c3d`) differs from the deployed tree (`2f053318634b`). The delta is
documentation only, verified with `git diff --name-only`, but the deployed ref
is the tag regardless.


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

*In progress.* Paths exercised and evidence below; findings are deferred to a
post-test batch by operator decision — none blocks the live test.

### Verified working

| Path | Evidence |
|---|---|
| Cloudflare Access → nginx → gunicorn → Flask → Postgres | teacher login page rendered through the full chain |
| Teacher signup + TOTP enrolment | completed on a fresh database |
| Turnstile | widget returned "Success!" — site/secret keys valid for this domain |
| Class creation (FEAT-CLASS-001) | `users` 1 (teacher), `classes` 1, `seats` 1 (teacher, claimed), `identity_profiles` 1 — exactly FEAT-CLASS-001 §X: one boundary, one teacher seat, no student seats or users. `class_timezone` populated at creation (immutable thereafter). |
| Vendored Bootstrap | `static/vendor/bootstrap/*` served 200 from the app, no CDN request — today's fix confirmed in production |
| Design tokens + fonts | `tokens.css`, `style.css` and all three font faces 200 |
| nginx `real_ip` | access log records `206.72.73.208`, in none of Cloudflare's 15 published IPv4 ranges — a resolved client, not an edge |
| Cloudflare origin monitor | correctly warned "Request not from Cloudflare IP: 127.0.0.1" for a direct origin curl — working as designed |
| Worker count | systemd cgroup shows master + exactly 1 worker |
| Ledger settlement (scheduled) | the $19.65 payroll transaction flipped `PENDING` → `POSTED` unattended and a `LedgerBalanceSnapshot` was written (`posted_balance_cents` 1965) at 19:44:53Z, 44 min after the 19:00:42Z transaction — the single worker's APScheduler doing real work, confirming `-w 1` was correctly applied |
| Store catalog creation (FEAT-SETTINGS-001) | 4 products published, all `IN_USE`, `direct_purchase_allowed` true, no date gates — all four visible to the student |
| Store purchase, sufficient funds (FEAT-STOR-001) | $19.65 → $14.65 exactly. One `purchase` row (−5.00, checking, `PENDING`) and one `GRANTED` entitlement event sharing `correlation_id` `corr_9d5785ea…`, written 12 ms apart — the debit and the grant are one transaction, not two hopeful writes. `acquisition_type` `PURCHASE`, `target_seat_id` = `actor_seat_id` = 6, `class_id` on both rows. No `pending_actions` row (the defect fixed on the store branch stayed fixed). |
| Store purchase, insufficient funds | $30.00 attempted against $9.65: refused with `INSUFFICIENT_FUNDS`. Verified the refusal is total — no transaction row, no entitlement event, no NSF/fee row, balance unchanged. Wording defect recorded as finding 11; the behaviour is correct. |
| Store inventory exhaustion | "Limited item" (`inventory_total` 1) purchased once, then rendered `Available: 0 left` with a disabled **Out of Stock** control — blocked at the surface rather than driven negative |
| Account transfer, checking → savings (FEAT-LED-000) | $7.00 moved: checking $9.65 → $2.65, savings $0.00 → $7.00. Two rows — `Withdrawal` −7.00 checking and `Deposit` +7.00 savings — sharing one `correlation_id` (`corr_ed0cb551…`) and summing to exactly zero, so the legs are one atomic unit and no value was created or destroyed. **No NSF or fee row was written**, which is the required outcome: a lateral move between a student's own accounts is not a failed agreement and must never attract a fine. |

### Findings — deferred to post-test batch

**1. Icon font is unsubsetted: 3.8 MB (performance, user-visible)** — DEFERRED

`static/fonts/material-symbols-outlined.woff2` is 3,963,852 bytes — the full
Material Symbols set, roughly 3,000 glyphs. The application uses **180**. Every
other font in the tree is 14–84 KB, so this one file is ~45× the rest combined.
Text paints immediately and icons appear only once it arrives, which is the
reported symptom. Subsetting to the 180 used glyphs should land in the 10–30 KB
range. Needs a build step and verification that no icon silently disappears.

**2. Static assets send `Cache-Control: no-cache` (performance)** — DEFERRED

Every static asset revalidates on every page load — the access log is full of
`304` responses at 40–100 ms each, roughly a dozen per page. Flask defaults to
this when `SEND_FILE_MAX_AGE_DEFAULT` is unset.

The fix is already half-built: `static_url()` appends `?v=<file mtime>`, so the
URL changes whenever content does. Far-future caching is therefore already safe
— the cache-busting was implemented and the caching it exists to enable never
was.

**3. Roster panel reports "all seats claimed" for an empty roster (correctness, display)** — FIXED

`ClassRosterView.all_seats_claimed` returned `not self.unclaimed_seats`, which
is vacuously true when the class has no seats at all. A brand-new class
displayed "Join code — all seats claimed" — the one state it certainly was not
in. Introduced by the 2026-09-17 roster view-model migration.

Fixed: `has_any_seats` added, `all_seats_claimed` now requires seats to exist,
and `unclaimed_panel_label` decides between the three states in the view model
rather than the template. Covered by
`tests/test_live_test_surface_regressions.py::TestEmptyRosterIsNotAllClaimed`,
which asserts each of the three states separately and that they produce three
distinct labels — collapsing any two reintroduces the defect.

Not yet on the live host: the running deployment is still `live-test/2026-09-19`
(`8c5cff7c8`), which predates this fix.

**4. "Next Payroll" states a date for an unconfigured class (correctness, display)** — FIXED

The dashboard showed "Next Payroll: Sep 25" for a class with **no
`payroll_settings` row at all** (table empty). Two stacked hardcodings in
`admin.py` `dashboard()`:

- `timedelta(days=14)` — a fortnightly cadence assumed rather than read from
  `PayrollSettings.pay_frequency_days`;
- when no anchor exists, an invented "next Friday": `(4 - weekday() + 7) % 7`,
  which on Sat 19 Sep yields 6 days → Fri 25 Sep.

The second is the real defect: an **unconfigured state rendered as a configured
one**. A teacher reading a specific date would expect students to be paid then;
nothing would happen. Display only — no scheduled job reads this value, so it
misinforms without mispaying.

**Confirmed worse than first recorded (corrected 2026-09-19).** Payroll was then
configured through the UI and stored correctly — `payroll_settings.pay_rate`
1.50, `payroll_frequency_days` 14, `next_payroll_date` **2026-10-02**,
`availability_state` IN_USE, carrying a `policy_uuid`. The dashboard still
displayed **Sep 25**.

The cause is that the dashboard never reads `payroll_settings` at all. Its
anchor is `max(event.recorded_at ...)` over `PayrollEvent` rows — the last
payroll that actually *ran* — so:

- the invented "next Friday" persists until the first payroll has ever run,
  which is exactly the setup window where a teacher has no other reference and
  is most likely to trust the figure;
- it does not self-correct when payroll is configured;
- once payroll has run, `timedelta(days=14)` is still hardcoded rather than
  read from `payroll_frequency_days`, so any class on a non-fortnightly
  schedule shows a wrong date indefinitely.

The fix must read the configured schedule — `next_payroll_date` when set,
`payroll_frequency_days` for the interval — and show "Not scheduled" when
neither a schedule nor a payroll history exists.

*Method note:* this entry was first narrowed to "affects unconfigured classes
only" on the strength of the stored value existing. That was wrong — the value
being correct in the database says nothing about whether any code reads it. The
read path must be checked, not inferred.

**5. "Global Default" is v1 vocabulary on the payroll settings surface (wording)** — FIXED

`templates/admin_payroll.html:343` renders:

    Global Default: $1.50/minutes, biweekly , starting 10/02/2026

Three problems in one line. "Global Default" is v1 language from when payroll
settings were global across a teacher's blocks; v2 settings are class-scoped, so
nothing is global — and a teacher running several classes would reasonably read
it as applying to all of them, which is the opposite of the truth. Also
"$1.50/**minutes**" (unit not singularised from the stored `time_unit`) and a
stray space in "biweekly **,**". The first is a correctness-of-meaning problem on
a financial surface; the other two erode confidence in it.

Note this is the same failure mode `/health/status` explicitly refuses
(§X.5): an unmonitored surface must not read as a healthy one. The principle is
already held elsewhere in the codebase; the dashboard does not hold it.

### Deferred, with reasons

**Finding 2 (static asset caching) needs asset versioning first.** The obvious
fix — raising `SEND_FILE_MAX_AGE_DEFAULT` so static files stop revalidating — is
unsafe as the templates stand: every asset is referenced by a bare
`url_for('static', filename=...)` with no fingerprint or version query, so a long
`max-age` would serve stale CSS and JavaScript after each deployment with no way
to invalidate it. That trades roughly a dozen cheap 304s per page for a class of
bug that looks like "the fix didn't deploy". Doing it properly means adding a
version to static URLs, which also changes the service worker's cache keys
(`static/sw.js` caches by URL), so it deserves its own change and its own
verification rather than riding along with a wording pass.

**Finding 1 (3.8 MB icon font) is a build-pipeline change.** Subsetting to the
~180 glyphs actually used requires a font tool in the build and a check that
keeps the subset in step with the templates that reference new icons; shipping a
subset without that check produces missing glyphs later, which is worse than a
slow font now.

Both remain open. Neither is a correctness defect.

### Intended behaviour — do not re-raise

**Manual payroll does not move the automatic payroll window.** Verified by
timestamps: the `IN_USE` `payroll_settings` row has `created_at == updated_at ==
2026-09-19 18:41:59`, and the manual payroll ran at `19:00:41` without touching
it. `next_payroll_date` was unchanged. The dashboard *displays* a moved window
(finding 6B) but the underlying schedule is intact — do not "fix" the payroll
writer on the strength of that display.

**Payroll policy is frozen per payment.** The `payroll_event` row carries
`policy_version_id` and `policy_uuid`, and `payroll_settings` holds two rows —
one `RETIRED`, one `IN_USE`, created 74 seconds apart when settings were saved
twice. Superseded policy is retired and kept, never mutated, so a later settings
change cannot retroactively alter what a past payment was computed under
(readiness item B2 holding in production).

**Actor/target attribution is correct on both attendance and payroll.** A
student self-tap wrote `target_seat_id 6 / actor_seat_id 6 / mechanism self`; the
teacher tap-out wrote `target_seat_id 6 / actor_seat_id 1 / mechanism teacher`;
the payroll event wrote `target 6 / actor 1 / mechanism TEACHER`. A single
`seat_id` column could not express who acted versus who the record is about,
which is the question that matters in any dispute over hours or pay.

**Student session expires 10 minutes after login, absolutely.**

`student.py:3155` sets `user.current_session_expires_at = now +
timedelta(minutes=SESSION_TIMEOUT_MINUTES)` (10) at login. It is an **absolute**
deadline, never extended by activity: `app/auth.py` checks it *before*
refreshing `last_activity`, so polling does not move it. Observed live — stored
expiry `18:45:49`, `GET /api/student-status` returned 401 at `18:45:52`, three
seconds later, while the student was polling every few seconds.

**This is deliberate, not a defect.** It is a safety posture for shared
classroom machines, where students routinely walk away from an unattended
computer. Teachers share the 10-minute window; sysadmins get 60
(`SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES`).

The apparent friction dissolves once the interaction model is right: **the
dashboard is a time clock, not a workstation.** A student clocks in, leaves to do
class activities, and clocks back out — as at a real job, where you badge at the
door rather than standing at it. No live session is needed in between, so
expiring it costs nothing.

Consequently the attendance clock continuing to run while the student is signed
out is correct, not a leak: attendance measures being in class, not being at the
keyboard. Session expiry deliberately does **not** tap the student out.
`enforce_daily_limits_job()` auto-taps-out at the class's configured daily limit
(1.5 hours here) as the backstop for a forgotten clock-out.

Recorded because this was initially — and wrongly — raised as the most serious
finding of the day and a launch blocker. It is neither. The error was inferring
intent from a constant's name (`SESSION_TIMEOUT_MINUTES` reads like an idle
timeout) and assuming a usage pattern that does not match how the product is
actually used.

**6. Payroll schedule: three distinct defects behind one confusing date**

Observed after configuring payroll (next payroll 10/02, biweekly) and running a
**manual** payroll on 2026-09-19. Three surfaces disagreed — dashboard "Oct 3",
payroll overview "Oct 1, 5:00 PM PDT", settings tab "10/02/2026". They are three
separate defects, not one.

**6A — The stored schedule is wrong, not just displayed wrong.**
*Severity: the automatic run fires on the wrong day.*

`payroll_settings.next_payroll_date` holds `2026-10-02 00:00:00+00`. The class
carries `class_timezone = America/Los_Angeles`, and
`next_payroll_date AT TIME ZONE 'America/Los_Angeles'` = **2026-10-01 17:00**.

A teacher setting 10/2 means "payday is 2 October in my classroom". They pick a
**calendar date**, not an instant; nobody running a class period thinks in UTC.
`class_timezone` is captured at class creation and made immutable precisely so
scheduling resolves in class time — and this value bypasses it. The automatic
run therefore fires at 5 PM on **1 October**, a day early and during school
hours. The error also varies with DST: at UTC-7 vs UTC-8 the same calendar date
resolves an hour apart, so a date set in November behaves differently from one
set in June.

Fix: interpret a teacher-picked date in `class_timezone` (10/02 00:00
America/Los_Angeles = `2026-10-02 07:00 UTC`), and audit every other
teacher-picked date for the same treatment.

**6B — The dashboard misreports a working invariant as broken.**

`admin.py` `dashboard()` derives "Next Payroll" from
`max(PayrollEvent.recorded_at) + timedelta(days=14)` and **never reads
`payroll_settings`**. After the manual run it showed **Oct 3** — arithmetically
correct (Sep 19 + 14 = Oct 3) but answering the wrong question: "14 days after
the last payroll event" instead of "when is the next scheduled payroll".

The operator rule is that **running a manual payroll must not change the
automatic payroll window**. That rule is *upheld in the data* — verified: the
`IN_USE` settings row has `created_at == updated_at == 18:41:59`, while payroll
ran at **19:00:41** and never touched it. But the dashboard makes it look as
though the manual run pushed the window out two weeks.

This is the entry most likely to cost someone an afternoon: the visible symptom
points at the payroll writer, where there is no bug. The dashboard must read the
configured schedule, and the hardcoded 14 days must come from
`payroll_frequency_days`.

**6C — Two surfaces render the same instant a day apart.**

Payroll Overview shows "Oct 1, 2026, 5:00 PM PDT" (the stored instant correctly
converted to class time). The Settings tab shows "starting 10/02/2026" (the same
instant printed as its UTC date, unconverted). Both read the same row. Once 6A is
fixed the two will agree, but the settings tab should convert explicitly rather
than coincidentally matching.

**7. Stated rounding does not match actual payment behaviour (wording)** — FIXED

The Pay Simulator states "Time tracking **rounds down** to the nearest time
increment." With `time_unit = minutes` a teacher reads that as "partial minutes
are not paid". Actual: 13m 6s of attendance paid **$19.65** — full per-second
pro-rata (786s x $0.025). Rounded down to whole minutes it would be $19.50.

The ledger is correct; the description of it is not. Either the copy is wrong or
it means "rounds to the nearest second", which is vacuous. On a financial
surface this is worth stating accurately.

**8. The app cannot link to its own status page (deferred, small)** — FIXED

`wsgi.py` validates `STATUS_PAGE_URL` against an allowlist of exactly one
provider:

    if url and url.startswith('https://stats.uptimerobot.com/'):

`status.classroomtokenhub.com` fails that test, so setting the variable makes the
validator return `None` and the link silently never renders. The allowlist is
v1-era and was never updated when the self-hosted status service replaced
UptimeRobot. Its own docstring anticipates this: "To support other status page
providers, add their specific domain patterns to the validation."

The allowlist itself is sound and should be widened, not removed — it exists so
that someone with environment access cannot redirect users to a phishing page.
Fix: add the `status.classroomtokenhub.com` pattern, then set `STATUS_PAGE_URL`.

**9. Cloudflare-origin check warns on every request (log noise, not a gap)** — FIXED (app side)

Every non-static request logs:

    WARNING: Request not from Cloudflare IP: 127.0.0.1 (real_ip: <client ip>, ...)

`validate_cloudflare_request()` (`app/utils/ip_handler.py:173`) handles the
local-proxy case by reading `X-Real-IP`, documented as "the immediate upstream
proxy IP", and testing it against Cloudflare's published ranges. But
`/etc/nginx/conf.d/cloudflare-realip.conf` sets `real_ip_header CF-Connecting-IP`,
which rewrites `$remote_addr` to the *end client* before
`proxy_set_header X-Real-IP $remote_addr` runs. The header therefore carries the
visitor's own IP, never Cloudflare's edge, so the check cannot succeed while
real-ip rewriting is enabled — which is also what makes `CF-Connecting-IP`-based
rate limiting work correctly. The two features want the same header for
different purposes.

**Not a security finding.** Origin restriction is enforced by the DigitalOcean
firewall (Cloudflare ranges + Tailscale only); this function only logs. But it
emits a WARNING per request, which will bury real warnings once classes are
using the app.

Fix options: pass the edge IP separately (`proxy_set_header X-CF-Edge-IP
$realip_remote_addr`) and read that, or drop the check in favour of the firewall
that actually enforces it. Do not "fix" it by removing `real_ip_header` — that
would break rate limiting, which is the load-bearing consumer.

**10. Immediate-use items are never consumed at sale (correctness, spec violation)** — FIXED

`SPEC-STORE-001` §III defines the type in one line — "IMMEDIATE_USE — Granted
and consumed in the same action (no expiry)" — and §V.A repeats it:
"IMMEDIATE_USE is exercised at the moment of sale." An unexercised
`IMMEDIATE_USE` entitlement is therefore a state the specification does not
permit to exist.

It exists. Purchasing an immediate item leaves it sitting in the student's **My
Items** tab, badged "Ready to Use" with a *Use Now* button, requiring a second
deliberate action to consume.

`execute_store_purchase` implements the contract correctly: Phase 4
(`app/feats/store_purchase_feat.py:486`) writes a `CONSUMED` event for every
granted entitlement inside the same transaction as the `GRANTED` event, when
`instant_use` is true. The sole purchase route never turns it on:

    result = execute_store_purchase(
        canonical_context=context,
        policy_uuid=policy_uuid,
        quantity=quantity,
        instant_use=False,  # TODO: Read from product policy
    )

`app/routes/api.py:323` — an unfinished TODO. The flag is hardcoded off for
every purchase of every type, so no product ever reaches Phase 4. Live evidence:
the `GRANTED` event for the "Cheap item" purchase carries payload
`{'instant_use': False, ...}` on an `entitlement_type` of `IMMEDIATE_USE` — the
contradiction, recorded in the database.

**Severity is bounded but it is not cosmetic.** Pressing *Use Now* does work:
`item_type == 'immediate'` routes to `execute_use_item_immediate`
(`app/routes/api.py:380`), which consumes the entitlement directly with no
teacher approval and writes no `pending_actions` row. Nothing is stuck, no money
is wrong, and no approval is spuriously demanded. The lifecycle simply takes two
steps where the contract says one. Consequences:

1. Immediate items **accumulate indefinitely**. §V.A requires `auto_expiry_days`
   to be null for this type, so an unconsumed immediate entitlement never
   expires; the student's item list fills with things that should have been
   consumed at the till.
2. Any consumed-versus-outstanding entitlement count reads immediate items as
   permanently outstanding.
3. Student-visible incoherence: you buy the thing, then later go "use" it.

**The fix does not belong in the route.** The route holds only a `policy_uuid`
and would have to re-resolve the product to compute the flag — and every future
caller would have to remember to do the same. The FEAT already holds
`policy_config.entitlement_type` before Phase 4 runs, so deriving `instant_use`
there enforces the rule once for all callers. That also states the rule
correctly: per the specification `instant_use` is a *derived property of the
product type*, not a caller-supplied option, and the current signature — a
caller-passed boolean defaulting to `False` — is what made this defect
expressible at all.

**The UI explicitly promises the behaviour that does not occur.** The purchase
confirmation modal renders, for `item_type == 'immediate'`
(`templates/student_shop.html:483`):

> **Immediate use** — This item is used instantly upon purchase. You won't need
> to redeem it later - it's applied to your account right away.

The student confirms the purchase having just been told they will not need to
redeem it later, and is then required to redeem it later. This raises the
finding above a specification-conformance issue: the product states something
false to the user at the moment of sale. Note the copy is correct *as written* —
it describes the contract in `SPEC-STORE-001`. The template is right and the
call site is wrong, so the copy must not be "corrected" to describe the defect.

Found by the operator during §XI store testing, from the UI alone: an immediate
item should not have a *Use Now* button.

**11. Internal domain names leak into student-facing error copy (wording)** — FIXED

Attempting to buy the $30 item against a $9.65 balance produced, in the purchase
modal:

> **Purchase not completed**
> Purchase denied by Ledger

"Ledger" is an internal domain boundary. To a student it names nothing; it reads
as a component that has taken a decision about them, and it does not say what
went wrong or what to do. The correct message is that they do not have enough
money.

**The classification is already right; only the prose is wrong.**
`execute_store_purchase` returns `error_code="INSUFFICIENT_FUNDS"` on both denial
branches (`app/feats/store_purchase_feat.py:394` and `:407`) — accurate and
machine-readable. The defect is that the route renders the *other* field
verbatim:

    error_msg = result.error_message or f"Purchase failed: {result.error_code}"
    return jsonify({"status": "error", "message": error_msg}), 400

`app/routes/api.py:327`. A FEAT's `error_message` is a diagnostic written for
developers and logs; here it becomes the sentence a child reads. The second
branch is worse still — it interpolates a raw reason string
(`f"Purchase denied by Ledger: {ledger_result.get('reason', 'unknown')}"`), so an
internal reason code, or the literal word `unknown`, can surface in the modal.

**Rewording the FEAT string is the wrong fix.** It would leave the same pipe open
for every other error the FEAT can return, and would push user-facing copy down
into a domain that should not own it. The durable fix is to map `error_code` to
student copy at the presentation boundary and stop rendering `error_message` to
users at all — keeping it for logs, where it is useful. `INSUFFICIENT_FUNDS` then
renders as something like "Not enough funds — this costs $30.00 and you have
$9.65 in checking", which answers the two questions the student actually has.

Raised by the operator: "the wording could be better. maybe 'Insufficient funds'
or something else".

**12. Redemption asks for a PIN and verifies the passphrase (correctness, blocks the student)** — FIXED

The *Use Item* modal labels its credential field **"Enter your PIN to confirm:"**
and the input is built for a PIN — `name="pin"`, `inputmode="numeric"`,
`pattern="[0-9]*"` (`templates/student_shop.html:372`). The handler reads it as
`pin`, posts it as `passphrase` (`:722`), and the server verifies it against
`user.passphrase_hash` (`app/routes/api.py:359`), returning **"Incorrect
passphrase."** A student who does exactly what the label says is refused, and the
error names a credential the form never asked for.

Observed live: PIN entered, "Item not used — Incorrect passphrase."

**Not a hard block, and worth being exact about why.** The submit handler is bound
to the button's `click` (`#confirmUseBtn`) and reads `.value` directly, so HTML
constraint validation never runs and `pattern="[0-9]*"` does not actually reject
letters. A student who guesses to type their passphrase will succeed. But
`inputmode="numeric"` still raises a numeric keypad on a phone or tablet, so on
the devices most classes use, entering a passphrase like
`Dairy9_Faster_Shrunk` means fighting the keyboard the form chose.

**Which credential is correct is a genuine open question, not an obvious typo.**
`DOM-IDEN-002` §167 states: "Student financial actions (transfers, purchases,
insurance claims) require passphrase re-verification. The passphrase gate is
separate from the PIN used at login." Redeeming an already-purchased entitlement
moves no money and is not in that enumeration, so the doc does not settle it. The
purchase modal — a financial action — correctly asks for the passphrase
(`templates/student_shop.html:334`), which is the contrast that makes the
redemption modal look like it was meant to ask for the PIN. Either answer is
defensible; what is not defensible is the current state, where the label, the
input mode, and the verifier disagree. Resolve the contract first, then make all
three agree.

**13. Store offers a second, unguarded hall-pass request path (correctness, domain violation)** — FIXED

A purchased hall pass is *correctly* credited to the hall-pass balance — verified
live: `get_hall_pass_balance(seat 6) == 1` after purchase, and the dashboard
renders it as "Passes Left" (`templates/student_dashboard.html:199`). The
mechanism works.

The defect is that the same entitlement **also** appears in the Store's *My Items*
tab with a *Request* button, and that second path enforces none of the conditions
the first one does. The `hall_pass` branch of `use_item`
(`app/routes/api.py:398`) builds a pending action and calls
`execute_use_item_request` with **no attendance precondition** — nothing checks
whether the student is clocked in. A student who never started work, or who has
already marked themselves done for the day, can request a hall pass from the
Store tab.

This contradicts `DOM-PROD-001`, where a hall pass marks a student *out of an
active work session*: the attendance timeline carries `reason_code = hall_pass`
with the consumed entitlement's `hall_pass_id` (§1, §"MUST set `hall_pass_id`").
Outside a session there is nothing to be marked out of, so the request is
incoherent rather than merely early.

The dashboard Break flow already implements the intended contract: **Break** is
disabled until **Start Work**, and the modal reads "Choose a hall-pass
destination or mark yourself done for the day"
(`templates/student_dashboard.html:234-252`). That is the lawful entry point, and
it is the one that knows the student's attendance state.

**The fix is removal, not a guard.** Adding an attendance check to the Store path
would make it correct but still leave two ways to do one thing, one of which is
in a surface that has no reason to know about attendance. A hall-pass entitlement
should render in *My Items* as a **balance, not an actionable item** — consistent
with `DOM-STORE-001` §VIII.6, which grants the entitlement here while stating
that "the authoritative exercise may be recorded by another domain" and that
Store must "not create a duplicate Store-and-Entitlements `CONSUMED` row when
another domain is the authoritative consumer." Exercise belongs to Productivity;
Store should not offer a button for it.

Raised by the operator: "hall pass should not be under my item. it should be
directly added to hall pass balance. the only time hall pass can be requested is
when the student is currently active and they use the break feature."

*Minor, same surface:* line 199 hardcodes "Passes Left", so a balance of 1 reads
"1 Passes Left".

**14. Sysadmin dashboard 500s: `operational_events` was never created (correctness, dead route)**

First 500 of the deployment. Sysadmin authentication **succeeded** —
`POST /sysadmin/login` returned 302 — and the redirect target failed:

    GET /sysadmin/dashboard  →  500
    psycopg2.errors.UndefinedTable: relation "operational_events" does not exist
    [SQL: SELECT id, created_at, level, message, payload FROM operational_events
          WHERE level IN ('ERROR', 'CRITICAL') ORDER BY created_at DESC, id DESC LIMIT %(limit)s]

`app/routes/system_admin.py:521` → `get_recent_error_events(limit=5)` →
`app/services/operational_event_service.py:61`.

**The table was designed, referenced, and never built.** Migration
`7c3d4e5f6a7b_drop_all_unauthorized_tables.py` drops the old error pipeline with
these comments (§GROUP E, lines 200-205):

    # error_logs   → to be replaced by operational_events(level=ERROR|CRITICAL)
    # error_events → absorbed into operational_events (DOM-OPS-001)
    drop_table_if_exists('error_logs')
    drop_table_if_exists('error_events')

That migration is the **only** mention of `operational_events` anywhere in
`migrations/`. No migration creates it. There is no model for it either —
`app/models.py:1946` carries only the comment "Error events are represented in
operational_events". The predecessors were removed on the strength of a
replacement that does not exist.

**The writer and the reader disagree about where the data lives.** `record()`
(`operational_event_service.py:14`) does not write to any table — its docstring
says "Current storage target is application logs", and it emits through
`current_app.logger`. Only the two read functions
(`get_recent_error_events`, `get_error_events`) expect a table. So even if the
table existed it would always be empty; the dashboard would render, and render
nothing, forever.

**Two sysadmin routes are dead**, not one: `system_admin.py:521` (dashboard) and
`:563` (the full error view via `get_error_events()`).

**Why 2997 passing tests did not catch this.** The only test that fetches the
route is
`tests/dom/operation/test_sysadmin_grafana_auth.py::test_DOM_OPS_001__expired_sysadmin_dashboard_still_redirects_to_login`,
which seeds an **expired** session and asserts a **302 to login** — it never
reaches the handler body. `tests/dom/support/test_tlcp_actor_context_resolution.py:49`
only builds a `test_request_context` for that path and never dispatches it. **The
sysadmin dashboard has never been rendered successfully in a test.** The reads
use raw `sa.text()` rather than ORM entities, so SQLAlchemy never validated the
name against metadata and nothing failed at import or startup. And `conftest.py`
rebuilds the schema from the real migration chain, so the test database is
missing the table too — a test that *did* render the dashboard would have failed
immediately.

This is the same failure shape the repository already legislates against: a
guard, or here a whole route, that is green because nothing ever exercised the
path it covers.

**Grafana itself is probably fine.** `/sysadmin/grafana`
(`system_admin.py:1055`) is a separate route that proxies to `GRAFANA_URL`
(default `http://localhost:3000`) and does not touch `operational_events`.
Verified on the host: `grafana-server` is **active** and listening on
`127.0.0.1:3000`, and `GRAFANA_URL` is absent from `.env`, which is harmless
because the code default already matches. The operator is blocked only because
login lands on the broken dashboard; navigating directly to `/sysadmin/grafana`
should bypass it.

**Fix requires a decision, not just a migration.** Creating an empty
`operational_events` table would stop the 500 and produce a permanently empty
error panel, because nothing writes to it. The real question is whether
`DOM-OPS-001` intends operational events to be durable rows or log lines. If
rows: add the model and a creating migration, and change `record()` to write
them. If logs: delete both read functions and the dashboard panels that call
them. Either is defensible; shipping the current half-state is not.

**15. Grafana proxy 404s on its own directory form (correctness, proxy fragility)**

`/sysadmin/grafana/` — the mount point with a trailing slash — returns 404.
Verified against the origin directly, bypassing Cloudflare and the browser:

    curl -H 'Host: app.classroomtokenhub.com' https://127.0.0.1/sysadmin/grafana
      → 302  https://.../sysadmin/login?next=/sysadmin/grafana      (route matches)
    curl -H 'Host: app.classroomtokenhub.com' https://127.0.0.1/sysadmin/grafana/
      → 404                                                         (matches nothing)

The registered rules are:

    '/sysadmin/grafana'              defaults={'path': ''}   strict_slashes=True
    '/sysadmin/grafana/<path:path>'                          strict_slashes=True

`/sysadmin/grafana/` matches neither: the `path` converter requires at least one
character so it will not match an empty remainder, and with `strict_slashes=True`
Werkzeug does not redirect `/foo/` → `/foo` (it only performs the opposite
redirect, `/foo` → `/foo/`, when the rule itself carries the trailing slash).

**Why this matters more for a proxy than for a page.** Grafana is a single-page
app served at a mount point. It emits its own redirects and resolves assets
relative to its base. A mount point that 404s on its own directory form is
fragile: any Grafana-issued redirect to its root, any relative asset that
resolves to the bare directory, and any user or bookmark that includes the
customary trailing slash all fail — and they fail as a 404, which reads as
"Grafana is not installed" rather than "the route did not match".

**The trailing slash was client-side state — settled by evidence, after one wrong
call.** Neither nginx nor Cloudflare adds it: `$request_uri` passes through
unmodified (both forms tested against the origin), and Cloudflare Access's
redirect carries `"redirect_url":"/sysadmin/grafana"` with no slash. The no-slash
request never reached the server at all from Chrome — absent from the access log
entirely, with the slashed requests carrying referrer `-`.

Proof came from switching browser: the operator's first request in **Firefox**
(`Firefox/156.0`, 21:55:05) went to `/sysadmin/grafana` unmodified and matched the
route, returning 302 to login. Same URL, same server, no slash. The rewrite
therefore lived in the Chrome profile — consistent with a cached permanent
redirect, which a browser honours without issuing a network request, explaining
the total absence of no-slash entries in the log.

Recorded because the first explanation offered — omnibox autocomplete — was
wrong, and was disproved by the operator showing the clean URL in the address bar
before the request. The lesson is the diagnostic, not the theory: when a request
never appears in the server log, the answer is in the client, and changing
browser isolates it in seconds.

Fix: register the directory form as well — add `strict_slashes=False` to the bare
rule, or a `/grafana/` rule carrying the same `defaults={'path': ''}`. One line;
it should be covered by a test asserting both forms resolve, since the failure is
invisible until something requests the directory.

*Grafana itself remains unverified.* `grafana-server` is active on
`127.0.0.1:3000` and `GRAFANA_URL` is unset (harmless — the code default already
matches), but no authenticated request has yet reached the proxy body.

**16. Service worker's auth-route bypass misses every sysadmin route (correctness, caching safety)** — FIXED

`static/sw.js:63` excludes authenticated routes from caching:

    const authRoutes = ['/admin', '/student', '/system-admin', '/api'];
    if (authRoutes.some((route) => url.pathname.startsWith(route))) {
      return;  // Network-only for authenticated routes
    }

The prefix is wrong. The blueprint is registered as
`Blueprint('sysadmin', __name__, url_prefix='/sysadmin')`
(`app/routes/system_admin.py:71`) — there is no `/system-admin` prefix anywhere in
the application. `'/sysadmin/...'.startsWith('/system-admin')` is false, so **no
sysadmin route has ever matched this bypass**, and every one of them falls
through to the caching strategies below it.

The comment on that block is "multi-tenancy safety", which is precisely the
property it is failing to provide for the operator role. Navigation requests land
in `handleNavigation`, which does a plain `fetch` and is harmless; non-navigation
requests reach `cacheFirst`, so sysadmin subresource responses are cached in the
shared service-worker cache.

**Not established as the cause of finding 15's symptom.** It was found while
investigating that, and the two are not yet connected by evidence — the
diagnosis there is still open. This entry stands on its own: a guard list naming
a prefix that does not exist is a defect regardless of what else it explains.

A test asserting each registered blueprint prefix appears in the service worker's
`authRoutes` would have caught it, and would catch the next prefix rename. The
string is duplicated between Python and JavaScript with nothing tying them
together.

**17. Grafana proxy returns 502: HTML is blocked by design (correctness, caused by today's nginx decision)**

Sysadmin login succeeded and redirected to `/sysadmin/grafana`; the proxy ran,
reached Grafana, and refused its response:

    WARNING in system_admin: Blocked proxied Grafana response with potentially
    unsafe content type: text/html; charset=utf-8 for path:
    "GET /sysadmin/grafana HTTP/1.0" 502 124

`grafana_proxy` streams only an allowlist of MIME prefixes
(`app/routes/system_admin.py:1153`): `image/`, `text/plain`, `text/css`,
`application/json`, JavaScript, `application/octet-stream`, `application/pdf`,
`text/csv`. The comment above it is explicit — "Everything else (including
HTML/XML or missing/unknown types) is blocked."

Grafana is a web UI. Its entry point is HTML. **This route can serve Grafana's
stylesheets, scripts, JSON APIs and images, but never the document that loads
them**, so the dashboard cannot render through it at any path. Nothing is
misconfigured in Grafana: `grafana-server` is active on `127.0.0.1:3000`, it
answered, and the proxy discarded the answer.

**Root cause is this deployment's nginx decision, and the reasoning behind it was
wrong.** The site config written today (`/etc/nginx/sites-available/classroom`,
header comment) states:

> Grafana is NOT proxied here: v2 serves it through the Flask route
> sysadmin.grafana_proxy ... The v1 config sent /sysadmin/grafana/ straight to
> :3000 behind an nginx auth_request; porting that forward would bypass v2's own
> authorization entirely, because the Flask route would never execute.

The premise is false. The nginx `auth_request` pattern does not bypass Flask — it
**delegates to** Flask. `grafana_auth_check` (`system_admin.py:1013`) resolves
canonical context, requires a `BoundaryContext` with `actor_role == 'sysadmin'`,
enforces the sysadmin session timeout, and returns `X-Auth-User` for Grafana's
auth-proxy login. Its docstring states its purpose outright: "Auth check endpoint
for nginx auth_request." Authorization remains Flask's decision in both designs;
only the byte-streaming differs. Omitting the nginx block did not harden
anything — it stranded `grafana_auth_check` as dead code and sent traffic down a
path that cannot serve HTML.

The v1 runbook
(`docs/archive/v1-docs/.../SOP-DEP-008_Grafana_Fix_Guide.md` — archived, cited as
history) documents both options and names nginx "Recommended for Production", describing the Flask proxy
as a "reliable fallback" — a characterisation the content-type allowlist
contradicts for any UI traffic.

**Resolution — restore the nginx location block.** It is the documented path, it
keeps authorization in Flask, and it revives an endpoint that currently serves no
purpose. The v1 block (adjusting the auth_request path to the v2 route) is:

    location /sysadmin/grafana/ {
        auth_request /sysadmin/grafana/auth-check;
        auth_request_set $auth_user $upstream_http_x_auth_user;
        error_page 401 = @grafana_login_redirect;
        proxy_pass http://127.0.0.1:3000;   # no trailing slash: preserves path
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-WEBAUTH-USER $auth_user;
        proxy_set_header X-WEBAUTH-ROLE Admin;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

Adding `text/html` to the Flask allowlist is the alternative and is **not**
recommended: that allowlist is deliberate containment against serving arbitrary
proxied markup from the application's own origin, and widening it for a UI is a
larger security change than restoring the documented integration.

Note the block is keyed on `/sysadmin/grafana/` **with** a trailing slash, which
interacts with finding 15 — the bare `/sysadmin/grafana` would continue to fall
through to Flask. Both forms need to resolve to the same place.

**18. Tempo has been crash-looping for ~20 days; tracing is silently dead (operational)**

`systemctl is-active tempo` reports `activating (auto-restart)`, never `active`.
The restart counter reads **570,097** — at roughly one restart per three seconds
that is about **20 days of continuous failure**.

    failed parsing config: /etc/tempo/config.yml: yaml: unmarshal errors:
      line 16: field ingester not found in type app.Config
      line 19: field compactor not found in type app.Config
      line 26: field traces_storage not found in type generator.Config
      line 29: field local_blocks not found in type generator.ProcessorConfig

The installed binary is **Tempo 3.0.2**; the config is in Tempo 2.x format, where
`ingester`, `compactor`, `metrics_generator.traces_storage` and
`processor.local_blocks` were top-level or differently nested. Tempo 3.0
restructured them. This is an unattended major-version upgrade whose config was
never migrated — consistent with the operator's account that the host was left
untouched apart from security patching.

**Consequences:**

1. Nothing listens on `:3200` (Tempo API) or `:4318`/`:4317` (OTLP receivers) —
   confirmed by `ss -ltn`.
2. The application has `OTEL_TRACES_ENABLED=true` with
   `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces`, so every
   span is exported to a closed port.
3. Grafana's `tempo` datasource cannot resolve; any trace panel is dead.
4. systemd has been spawning and reaping a failing process twice a second for
   three weeks.

**No traces were lost, and the 20 days is not a data-loss window.** The
application was shut down when v1 closed and only started serving today, so there
was no traffic to trace for the whole of that period. The restart counter
measures how long the misconfiguration has sat unnoticed, not an outage of a
working feature. Recorded that way because the raw number invites the opposite
reading.

**The finding that matters is forward-looking, and it is the silence.**
Application logs contain **zero** OTEL or connection-refused entries over a
30-minute sample taken while the app was live and serving the §XI test traffic:
the OTLP exporter retries and drops spans without surfacing anything. Traces are
being dropped *now*, with real traffic, and nothing says so. Had the app been
running for those three weeks, the same silence would have hidden it the whole
time — which is the property worth fixing, independent of how much was actually
lost.

Compare `/health/status`, which explicitly refuses to report an unmonitored
surface as healthy (§X.5). The same principle is not held here: a trace exporter
pointed at a dead collector should be loud, or the flag should be off.

**Rest of the stack is healthy:** `prometheus` (:9090), `loki` (:3100),
`promtail`, `prometheus-node-exporter` (:9100) and `grafana-server` are all
active. Only Tempo is down. `alloy` and `node-exporter` are inactive, which
appears intentional — `prometheus-node-exporter` is the one serving :9100.

Fix is to migrate `/etc/tempo/config.yml` to the 3.x schema, or pin Tempo to 2.x,
or disable `OTEL_TRACES_ENABLED` until the collector is restored. Leaving the
flag on against a dead endpoint is the one option to avoid, because it looks like
tracing works.

**19. Surviving v1 Grafana dashboards query labels v2 does not emit — and render as zeros (correctness, monitoring)**

Four dashboards survived from v1: *Economy Health*, *Errors and Log Monitoring*,
*Production Health*, *Node Exporter Full*. Their queries were compared against
the labels Loki actually holds.

Loki is **healthy** and ingesting: `service="classroom-economy"` from
`/var/log/classroom-economy/app.log`, 270 error-level lines in the sampled hour.
Available labels are `detected_level`, `filename`, `host`, `job`, `method`,
`service`, `service_name`, `status`, `unit`. `job` values are
`classroom_economy_app`, `nginx_access`, `nginx_error`, `systemd-journal`.

| Dashboard query | Reality |
|---|---|
| `logger="app.services.invariant_runner"`, `message="invariant_check*"` | `app/services/invariant_runner.py` does not exist in v2, and no code emits those messages |
| `unit="gunicorn.service"` | the unit is `classroom-economy.service`; `gunicorn.service` is not among Loki's `unit` values |
| `level=~"WARNING\|ERROR\|CRITICAL..."` | there is no `level` label; the label is `detected_level` and `/label/level/values` returns empty |
| `job="nginx"` | no such job; the values are `nginx_access` and `nginx_error` |

Resulting panel status:

- **Economy Health — 0 of 9 panels functional.** Every panel targets the v1
  invariant-runner log stream.
- **Errors and Log Monitoring — 1 of 4.** Only `sum by (job) (count_over_time({job=~".+"}[5m]))`
  resolves; the other three use `level` and/or `unit="gunicorn.service"`.
- **Production Health — node metrics work** (`prometheus-node-exporter` is
  active on :9100), **both 5xx panels are dead** (`job="nginx"`).
- *Node Exporter Full* is stock and unaffected.

**The failure mode is the dangerous one: they render zeros, not errors.** A Loki
stream selector that matches nothing returns an empty result, which these panels
display as `0`. "Total Invariant Failures: **0**" is indistinguishable from a
healthy economy, and "5xx errors: **0**" from a healthy edge. An operator reading
these would conclude the system is quiet when the truth is that nothing is being
measured.

This is the third instance in this record of the same principle — `/health/status`
refuses to report an unmonitored surface as healthy (§X.5); the teacher dashboard
does not (finding 4); these dashboards do not either. The codebase holds the rule
in one place and not the others.

`gunicorn.service` is the same stale unit name already noted in
`toggle-maintenance.yml`, which restarts a unit that does not exist. Two
independent artifacts carry the pre-rename name.

**Setting these up is a rewrite, not a repair**, for Economy Health at least: the
v2 equivalent of the invariant-runner stream has to be identified (or the
emission added) before the panels have anything to point at. The label fixes for
the other two are mechanical — `unit`, `detected_level`, `nginx_access|nginx_error`.

**20. The lawful hall-pass path required no credential at all (correctness, security)** — FIXED

Found while auditing every credential call site against the normative matrix for
finding 12, not from the browser.

`/api/hall-pass/request` (`app/routes/api.py`) — the Break-flow path, and after
finding 13 the *only* way to exercise a pass — enforced the two preconditions the
Store path lacked (`get_hall_pass_balance(...) <= 0`, and the latest attendance
event being `active`, refusing with "Start work before requesting a hall pass"),
but verified **no credential whatsoever**. FEAT-IDEN-002's credential boundary is
explicit that this is the one action assigned to the PIN: "Hall-pass use is the
explicit exception to the entitlement rule and uses the PIN."

Consequence: anyone holding a student's session — an unattended classroom
machine being the obvious case, and the reason the 10-minute student session
timeout exists — could spend a pass off that seat's balance and put the student
on the attendance timeline as out of the room. No credential, no prompt.

The front end matched: `requestHallPass()` in `static/js/attendance.js` posted
only a destination, while its immediate neighbour in the same modal ("done for
the day") prompted for a PIN before calling `performTap`.

**Full audit result, for the record.** Every other call site already matched the
matrix: store purchase and insurance purchase/cancel take the passphrase
(`api.py`, `student.py`), attendance tap and checking↔savings transfer take the
PIN. The matrix had one violation in the server and one in the UI, and both were
on hall passes — the one row of the table that is an exception to its own rule,
which is exactly the row an implementer is most likely to get wrong.

## §XI continued — 2026-09-20/21

Testing resumed against the same deployment (`8c5cff7c8`) rather than a fresh
one, deliberately: the remaining §XI items are in areas the remediation PR did
not touch, so exercising them on the old build finds their defects in time to be
fixed in one batch and deployed once. Every finding below is checked against
current `main` before being recorded as work, since 53 commits have landed since
this SHA.

**Verified in this session**

| Item | Evidence |
|---|---|
| `/docs` renders | `GET /docs` → 308 → `/docs/` → 200 (12,200 bytes). Operator confirmed from a mobile browser at 23:15:57Z; origin probe matches. The 308 is Werkzeug's `strict_slashes` redirect in the direction that works — the rule carries the trailing slash, unlike finding 15's Grafana mount. |
| Teacher current-class switching | Second class created (`POST /admin/create-class` → 302), switched back (`POST /admin/current-class` → 200). Both canonical pointers moved together: `last_active_class_id` = class A and `last_active_seat_id` = 1, which is the teacher seat *in class A*. Updating one without the other is the failure the code at `admin.py` warns about, and it did not occur. Two teacher seats now exist, one per class, both with `claimed_at` NULL — correct, since that column is student-specific (DOM-IDEN-002 §Schema Contract). |
| Roster upload into a second class | `POST /admin/upload-students` created 30 seats in one request. All 30 carry an `IdentityProfile`, `class_id`, `roster_fingerprint` and both claim hashes; none is bound to a user; no duplicate fingerprints. |
| Selected-class export scopes to the session's class | Class A active → 1 row (the single claimed seat). Class B active → header only. The two classes differing in claimed count (1 and 0) makes this unusually legible: the export is specified to list claimed seats only, and it did. |

**A query parameter does not choose the class — verified as a controlled
comparison.** The same URL, carrying class A's id, was requested from both
sessions:

    02:48:19  actor class_id=6135423f (class A)  ?class_id=<A>  -> 200, 158 bytes  (1 row)
    02:49:06  actor class_id=c20854ad (class B)  ?class_id=<A>  -> 200, 111 bytes  (header only)
    02:49:22  actor class_id=c20854ad (class B)  ?class_id=<A>  -> 200, 111 bytes

Identical input, different session context, different output — which is stronger
evidence than a single empty file, because it rules out the export merely being
broken or empty for an unrelated reason. The actor resolved to the class-local
teacher seat each time (`teacher:b675e002…` for class A, `teacher:ff5176d7…` for
class B), so context resolution and export scoping agree.

**Class-scoped admin actions cannot cross the selected class boundary — verified
against a real stale tab.**

The strongest available form of this test, and it arose from the operator's own
observation rather than a crafted request. Class context is one server-side value
per teacher, so a second tab switching class changes the first tab's context
while that tab still displays the old class (finding 22). Submitting the form
already on screen therefore posts class A identifiers into a class B session —
which is how this failure actually happens in a classroom, not as an attack but
as two open tabs.

    submit time   actor=teacher:ff5176d7…  class_id=c20854ad   (class B)
    form carried  Alex Morgan's seat                            (class A)
    result        POST /admin/payroll/manual-payment -> 302
                  transactions for that seat: 7, unchanged, all from 2026-09-19

Nothing was written. `payroll_manual_payment` resolves the scope from the session
and skips any seat outside it (`if student is None or student.class_id !=
selected_class_id: continue`), so the class A seat was passed over.

Worth recording that this was a *prediction* before it was a result: the guard
was read in the source first, the expected outcome stated (no ledger row, flash
reading "applied to 0 student(s)"), and then the submission confirmed it. A pass
observed without a prior expectation would not have distinguished "the guard
fired" from "the request never arrived".

That technique, and the others this session relied on, are now written up as
`SOP-DEP-001` §XI.A so the next operator inherits the method rather than
rediscovering it.

Note also what did **not** happen: the write path did not move the active class.
The operator's initial read was that the submit had switched back to class A and
applied correctly; the log shows the switch was a separate, later
`POST /admin/current-class` — their own use of the nav switcher, which
INV-ARC-010 makes the sole legal way to change class.

**All five isolation items now pass**: current-class switching, add/switch class
(teacher side), export scoping by session, export ignoring a forced query
parameter, and cross-boundary write refusal.

**21. The student export labels `section` as "Block" (wording)** — FIXED

`app/routes/admin.py:7945` writes the CSV header as:

    'First Name', 'Last Name', 'Block', 'Checking Balance', ...

"Block" is the retired v1 name for what v2 calls `section`. The teacher-facing
UI has already moved: `templates/admin_customizations.html:110` labels the field
**Section**, and no teacher-facing template renders the word "Block" at all. The
export is the last surface still using the old term, so a teacher who fills in
"Section" downloads a column called "Block".

The *value* is legitimate — `section` is display metadata and an export is a
display surface, which is exactly where it is allowed to appear. Only the label
is wrong.

Present on current `main` (checked), so it is work rather than an artefact of the
old build. Same family as finding 5's "Global Default": v1 vocabulary surviving
on a surface the rest of the app has already renamed.

**22. A second tab silently changes the first tab's class, which keeps showing the old one (correctness, usability)** — FIXED

Raised by the operator: open class A in one tab, switch to class B in a second
tab, return to the first tab and refresh — it is now class B.

The refresh behaviour is correct and follows from the design: class context is
**one value per teacher, held server-side**. `resolve_canonical_context` reads
`user.last_active_class_id` (`app/services/context_resolver.py:104`), not
anything tab-scoped, so there is exactly one active class per teacher at a time.
A second tab is not a second session.

The hazard is the state *before* that refresh. Tab 1 keeps displaying class A —
its roster, its students, its join code — while the session it posts into has
become class B. Nothing on the page indicates the change. A teacher with two
tabs open during a class period is an ordinary situation, not a contrived one.

Every action taken from that stale view then targets class A identifiers under a
class B context. **No data crosses the boundary** — the writes are scoped, and
`payroll_manual_payment` skips any seat whose `class_id` differs from the
selected scope (`admin.py`, `if student is None or student.class_id !=
selected_class_id: continue`). The isolation holds. What fails is the
explanation:

* Manual credit reports **"Manual credit of $X applied to 0 student(s)!"**,
  flashed as `success`, after the teacher deliberately selected a student.
* Other routes hit `_admin_write_has_join_code_conflict` and return a mismatch
  error that does not mention the second tab.

The count is honest and the styling is not; more importantly nothing names the
cause, so the likely conclusion is "this feature is broken" rather than "my
context moved". The fix is not to make the context per-tab — one active class per
teacher is a deliberate invariant (INV-ARC-010 makes the nav switcher the sole
legal switcher). It is to make a stale view detectable: stamp the rendered class
into the page and have a mismatch say so plainly.

**23. Seven `print()` calls in the canonical context resolver (hygiene, latent)** — FIXED

`app/services/context_resolver.py` lines 108-134 emit seven `DEBUG:`-prefixed
`print()` statements on identity-resolution failures, including one carrying
identifiers:

    print(f"DEBUG: Missing class_id! user_id={user_id}, last_active_class_id={...}")

They bypass the application's logging entirely. The app has structured logging
with correlation ids, actor and class context, and level filtering; `print()`
goes to stdout, which gunicorn captures and promtail ships to Loki as
unstructured text with none of that. These fire on precisely the conditions
where a correlated log line would be most useful — a seat pointer that does not
match its class, a seat that does not belong to the authenticated user.

**Latent, not active: zero `DEBUG:` lines appear in the journal since
2026-09-19.** None of the guarded conditions has occurred on this deployment, so
nothing has been emitted. This is cleanup, not an incident.

Scope checked and narrower than it first appeared: `grep` finds 30 `print(`
matches under `app/`, but 7 are docstring `Example:` blocks in
`class_configuration_query_service.py` and 7 more are legitimate CLI output in
`cli_commands.py`. Only the context resolver's are executable application code.

### Rent lifecycle — reconciliation verified

Exercised by invoking `run_rent_reconciliation_job()` directly on the host rather
than waiting for its schedule. Cycle genesis needs no waiting; the advance path
was reached by backdating `next_assessment_at`. Row counts were snapshotted
before each run so every write could be attributed.

| Step | Result |
|---|---|
| Genesis | `reason=CREATED_INITIAL cycles=[1] assessments=1`. Cycle row carries the class, `internal_ref` `rent:<class_id>`, `policy_uuid`, and all three boundaries; the assessment carries seat, class, `bill_cycle_id`, and correlation `rent:<class>:<seat>:cycle:1`. |
| Unclaimed-seat exclusion | **1** assessment for **30** student seats, because only one is claimed. Correct: an unclaimed seat takes part in no economic run. |
| Idempotency | Second run wrote nothing — `bill_cycles` 1→1, `assessment_events` 1→1, `ledger_transaction` 7→7. |
| Advance | `reason=ADVANCED cycles=[2] assessments=1`, with `cycle_number + 1`, its own assessment, and a distinct correlation. |
| Catch-up bound | `_MAX_CATCHUP_CYCLES` caps the advance loop, so a long-dormant class cannot spin out unbounded cycles. |

**One result looked like a defect and was not.** The advance produced a cycle 2
whose boundary (Sep 20) preceded cycle 1's (Oct 19) — chronologically
incoherent. The cause was the test, not the code: the successor's schedule is
derived from the predecessor's `next_assessment_at`
(`local_date_of_instant` → `resolve_cycle_schedule`), and the value backdated to
make the advance fire was 2026-09-21 03:30 UTC, which is **Sep 20** 20:30 in the
class's timezone. The system honoured exactly what it was given. Recorded because
the raw output reads like a bug and would otherwise be re-investigated later.

**Hardening note, not a finding.** Nothing asserts that a successor cycle's
boundary follows its predecessor's. The advance loop trusts
`next_assessment_at` unconditionally. That is safe while the value is only ever
written by the scheduler, and this session did not establish whether a settings
change mid-cycle can move it backwards; it is worth an ordering assertion on
general principle rather than on evidence.

**FEAT-OBL-002 runs without an idempotency key.** Every reconciliation logs
`FEAT-INTEGRITY-WARNING: FEAT FEAT-OBL-002 (Blast=MED) missing idempotency_key`,
and `execute_reconcile_rent` accepts an `idempotency_key` the scheduled caller
never passes. The FEAT holds no row locks either.

Concurrency safety is nonetheless real, but it comes from the database rather
than from the designed mechanism: `bill_cycles` carries
`uq_bill_cycles_ref_cycle (internal_ref, cycle_number)`, so two schedulers racing
to create the same cycle would collide and one transaction would roll back.
`assessment_events` has **no** unique constraint — it is protected only because
assessments are written inside the same transaction as their cycle. That holds
today, and it holds because of where the code happens to put the writes rather
than because anything enforces it.

This matters more after launch than now: a single gunicorn worker means one
scheduler, which is why `-w 1` was chosen. Scaling to two workers without leader
election would make the constraint the only thing standing between the app and
duplicate cycles, and the warning that fires on every run is the one signal
saying so.

### Verified — rent policy changes cannot reach a cycle already assessed (B1)

Tracker blocker **B1** ("Rent settings mutate in place, retroactively rewriting
prior obligations", closed 2026-09-04) was re-verified live, and the
circumstances make it stronger evidence than the regression test: the operator
was not testing the invariant. They were trying to shorten their way to a
payable rent bill by extending the bill-preview window, and the invariant
refused.

After two edits to rent settings:

| id | policy_uuid | availability_state | bill_preview_days |
|---|---|---|---|
| 1 | `535435b4…` | RETIRED | 21 |
| 2 | `8a4caa47…` | RETIRED | 30 |
| 3 | `73103ce5…` | **IN_USE** | 30 |

    bill_cycles: cycle 1 -> policy_uuid 535435b4…   (the original, now RETIRED)

Every edit produced a **new row** and retired its predecessor; no row was
mutated. Cycle 1 remained bound to the policy it was assessed under, so a student
assessed on the original terms is not retroactively subject to terms written
afterwards. The new settings take effect from cycle 2.

This is the invariant behaving exactly as specified, and the operator's own
framing is the best summary of why it exists: it prevents a teacher changing
their mind halfway through and hurting students. It was inconvenient here for the
same reason it is protective in a classroom — a cycle's terms are fixed once
students are assessed against them.

Recorded because an invariant that blocks a legitimate-looking action is
indistinguishable, from the UI, from a change that silently failed to save. The
database is what distinguishes them, and it says the change saved correctly and
was correctly scoped forward.

**24. Rent pricing recommendation is unavailable until rent is already configured (correctness, two causes)** — FIXED

First finding in the rent domain. On a class that has never configured rent, the
Rent Settings page shows:

> **Recommendation unavailable — insufficient data.**
> *Calculation details:* Your current Classroom Wage Index (CWI) is **$405.00**
> per week. You have selected the **Default** economic policy. Under this policy,
> rent should fall between **35%** and **50%** of your CWI.

The data is not insufficient. Every operand needed is printed directly beneath
the message: CWI $405.00, policy Default, band 35-50%. The answer is
$141.75-$202.50. After the teacher saves a rent amount, the same page renders
the recommendation correctly ($616.36-$880.51 per month) with no other change —
which is the confirmation that nothing was missing.

**A recommendation exists to inform a decision that has not been made yet**, so
being unavailable until after the decision is made inverts its purpose. A
first-time teacher sees "insufficient data" precisely when they most need the
number, then sees the number once they no longer do.

Two independent causes, both required:

**(a) The server-rendered band is gated on rent settings already existing.**
`app/routes/admin.py` builds it under `if settings and payroll_settings:`, where
`settings` is the class's existing `RentSettings` row. With no row, the template
emits no `data-canonical-min`/`-max` on `#cwi-info`, and the client falls through
to its async path. Verified live: payroll settings present, rent settings
missing, CWI resolvable at 405.0, and `rent_band(cwi, 'daily')` returning
`{'min': 20.25, 'max': 28.93}` when called directly — the band computes fine
without any rent row.

**(b) The async fallback cannot rescue it, because the validate endpoint resolves
payroll only from a client-supplied `class_id`.**
`/admin/api/economy/validate/rent` returned **200 with 111 bytes** on each
pre-save attempt — the body
`{"status":"warning","message":"Configure payroll first to get
recommendations.","is_valid":true,"warnings":[]}` — although payroll *is*
configured for that class.

The cause is `_resolve_admin_payroll_settings_for_class_id(canonical_context,
class_id)`, which takes the canonical context as its first argument and **never
reads it**:

    if not class_id:
        return None

`class_id` comes from `data.get('class_id')` in the request body, and
`EconomyBalanceChecker.validate()` in `static/js/economy-balance.js` sends
`{value, frequency, frequency_type, custom_*}` and no `class_id` — correctly, since
the session already knows the class. So the resolver returns None, the endpoint
reports payroll unconfigured, and the client renders "insufficient data".

Worth noting the direction of the dependency: `.claude/rules/multi-tenancy.md`
records that a client-supplied `class_id` is "an assertion, not authority". Here
a server-side resolver is *depending* on that assertion and failing without it,
while ignoring the authoritative context it was handed. The fix is to fall back
to `canonical_context.class_id` — the parameter is already there.

Each cause alone would be masked by the other working, which is why the symptom
survived: (a) is why the band is missing at first render, (b) is why the retry
does not supply it.

Present on current `main` (both sites checked).

**25. Rent's first due date is stored as UTC midnight — a SPEC-TIME-001 violation, and the third site of finding 6A (correctness)** — FIXED

The rent settings row written from the browser, and the cycle the reconciliation
job then built from it:

    first_rent_due_date   2026-10-20 00:00:00+00:00     <- UTC midnight
    due_day_of_month      20

    cycle_boundary_at     2026-10-19 07:00:00+00:00     = Oct 19 00:00 PDT
    grace_boundary_at     2026-10-24 07:00:00+00:00     = Oct 24 00:00 PDT
    next_assessment_at    2026-11-20 08:00:00+00:00     = Nov 20 00:00 PST

The teacher entered October 20 and the page displays "First Due Date: October 20,
2026". As UTC midnight that instant is **17:00 on October 19** in the class's
timezone, so the cycle boundary landed on the **19th**. Rent closes a day before
the date the teacher was shown.

The two date fields in the same row now contradict each other:
`cycle_boundary_at` derives from `first_rent_due_date` and says the 19th, while
`next_assessment_at` derives from `due_day_of_month = 20` and correctly says the
20th.

**And the contradiction is user-visible on two live surfaces at once.** Observed
in the browser on 2026-09-20:

| Surface | Due date shown |
|---|---|
| Teacher — Rent Management, "First Due Date" | **October 20, 2026** |
| Student — /student/rent, "Upcoming Due Date" | **October 19, 2026** |

The teacher page formats the stored `first_rent_due_date` in UTC and prints the
20th; the student page derives from `cycle_boundary_at`, which was computed from
that same instant in class-local time and is the 19th. Two people looking at the
same obligation are told different days, and the one the system will actually act
on is the student's.

This is worth recording as the concrete harm rather than the mechanism. A
one-day storage offset sounds like a rounding detail; "the teacher and the
student see different rent due dates" is the thing a classroom would notice, and
it would be reported as a dispute about who was late.

Cause, identical to finding 6A (`app/routes/admin.py`):

    'first_rent_due_date': (
        datetime.strptime(first_due_date_str, '%Y-%m-%d')
        if first_due_date_str else None
    ),

**This violates an existing normative contract rather than revealing a missing
one.** `SPEC-TIME-001` §CLE lists the class-scoped evaluations whose authority is
the Canonical Class Timezone, and the list names these cases explicitly:

> - productivity and payroll
> - **obligation due dates**
> - hall-pass timing
> - **store item expiry**
> - class-local day boundaries

It goes further: "every CLE primitive evaluates in Canonical Class Timezone, even
when the calculation would be mathematically equivalent in UTC", and callers
"must not independently convert them to class-local time before calling the
resolver."

So every site of finding 6A — payroll first pay date, store activation and
delist, rent due date — was already named in the spec as class-timezone
territory. The rule was written; nothing enforced it.

**The remediation missed this one for an instructive reason.** PR #1405 fixed 6A
at the payroll and store call sites: the ones a browser session had exposed. Rent
was never exercised, so its instance survived a remediation whose own commit
message named the defect class. The class was understood and the search was not
done. `grep -rn "strptime(.*'%Y-%m-%d')" app/` finds it in seconds.

**The durable fix is a structural guard, not a fourth patch.** Per SOP-TEST-003
§IX.A, a guard enumerating writes to class-scoped deadline columns and asserting
each routes through CLE — shipped with a mutation proof feeding it a naive
`strptime` — closes the class. Patching site four leaves site five.

**Related and unassessed: the same primitive as a query boundary.** The same grep
surfaces naive parses used as *filters* rather than stored values:

    query = query.filter(Transaction.timestamp >= datetime.strptime(start_date, '%Y-%m-%d'))
    end_date_inclusive = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)

`Transaction.timestamp` is timezone-aware, so a naive bound compares as UTC: a
teacher filtering "September 20" gets 17:00 on the 19th through 17:00 on the
20th in their own timezone. The edges of the day fall out of the report and the
previous evening falls in. Same defect class, different consequence — a wrong
report rather than a wrong charge. Further sites of this shape exist in
`api.py` and `admin.py` (attendance, audit and payroll ranges) and need
individual assessment.

Present on current `main`.

**26. No CI rule enforces SPEC-TIME-001, so every instance of finding 6A passed every gate (process, root cause)** — FIXED

Findings 6A and 25 are three instances of one defect, and the question worth
answering is not why each was written but why none was stopped. Raised by the
operator: time logic must use the canonical resolver and declare its evaluation
mode, so anything else should fail CI.

It should. It does not.

`SPEC-TIME-001` §I is unambiguous about scope — the resolver is the object

> "that all DOM specifications, FEAT specifications, runtime services, scheduled
> jobs, route handlers, and tests must use"

and "`canonical_temporal_resolver` is the only public temporal evaluation
helper." §CLE then names the very cases involved: obligation due dates, store
item expiry, payroll.

The enforcement harness exists and runs. `.github/workflows/policy-guardrails.yml`
invokes `scripts/policy_guardrails.py` on every pull request and push, with
`--strict --no-waivers` on the protected path. That script is AST-based, has a
waiver mechanism with expiry dates, and enforces nine rules:

    check_route_commit                      check_no_audit_update_delete
    check_write_on_get                      check_no_lineage_backfill_on_read
    check_scope_fallback                    check_no_direct_lineage_token_assignment
    check_student_context_fallback          check_no_unscoped_audit_emit
    check_tap_event_null_scope

**None of them is temporal.** A `datetime.strptime(value, '%Y-%m-%d')` assigned
to a class-scoped deadline column passes every gate the project has: the
guardrails ignore it, the type checker sees a valid `datetime`, and the test
suite has no assertion about which authority produced it. The three instances
were not missed by a guard that failed — they were never inspected.

This is the difference between a rule and a control. INV-ARC-007 ("no writes on
GET") is a rule *with* a control, so it cannot regress silently. SPEC-TIME-001 is
a rule without one, and it regressed three times in code written by people who
knew the rule — including, most recently, a remediation whose own commit message
named the defect class.

**The fix is rule ten, not patch four.** The guard's existing shape suits it: a
check that enumerates assignments to class-scoped temporal columns and requires
each to trace to a CLE resolution. The columns are enumerable —
`first_rent_due_date`, `first_pay_date`, `next_payroll_date`, `activation_at`,
`auto_delist_date`, `collective_goal_expires_at`, `cycle_boundary_at`,
`grace_boundary_at`, `next_assessment_at` — and the forbidden constructions are
few: naive `strptime`, `datetime.combine(..., tzinfo=timezone.utc)` on
teacher-entered input, `date.today()`, `datetime.now()`/`utcnow()`, and
`SYSTEM_LEVEL_EVALUATION` for a class-scoped concern.

Per SOP-TEST-003 §IX.A it must ship with a mutation proof: feed the detector the
exact line from `admin.py` that produced finding 25 and assert it is reported.
Without that, the new guard would go green on a codebase already fixed and prove
nothing about whether it detects anything.

Worth stating plainly for the launch decision: **the defect class is closed by
this guard, not by the three or four patches.** Patching the known sites leaves
the next one to be found by a teacher whose rent closes a day early.

**27. Attendance immutability is stated four times and enforced nowhere (correctness, control gap)** — FIXED

`DOM-PROD-001` is emphatic that attendance rows are permanent:

> §108 "Once written, an `attendance_sessions` row is permanent. It SHALL NOT be
> edited, deleted, soft-deleted, marked as deleted, hidden from payroll, or
> corrected in place."
> §176-177 "MUST be append-only" / "MUST treat every written attendance row as
> immutable and permanent"
> §184 "MUST NOT provide delete, soft-delete, mark-deleted, edit, or
> correction-in-place behavior for attendance rows"
> §185 "MUST NOT correct payroll outcomes by mutating attendance history"

The database enforces none of it. `attendance_sessions` carries **no triggers**
and no chain columns — no `previous_hash`, no `event_hash`. A direct `UPDATE`
succeeds silently.

Four other tables *are* protected:

    audit_events         audit_events_no_update / no_delete
    ledger_transaction   ledger_transaction_no_rewrite
    economic_engine      economic_engine_no_update / no_delete
    class_features       class_features_no_update / no_delete

The asymmetry is the point. `ledger_transaction` — the *output* — cannot be
rewritten. `attendance_sessions` — the input that justifies every dollar that
output contains — can be. Payroll reads attendance; nothing else determines what
a student is paid. The money is defended and the evidence for it is not.

No application code violates the rule today. The only writes are the class-scoped
deletions performed when a class or teacher account is destroyed, which is
teardown rather than correction-in-place and is consistent with the rule's
intent. **The active path is `app/services/teacher_destruction.py`**, reached
from `admin.py` and `teacher_lifecycle.py`.

An earlier revision of this paragraph also named `app/utils/deletion.py`. That
was wrong and is corrected here: the module imports four models that no longer
exist, so it cannot be imported at all, and nothing under `app/` references it
(finding 37). Naming it gave false evidence about which code can exercise the
DELETE exception the immutability migration grants.

So this is finding 26's shape again, in a different domain: a rule stated more
emphatically than most, with no control behind it. The operator confirmed the
intent independently — teachers are not permitted to correct attendance and no UI
offers it — which removes the alternative reading that the absence of enforcement
was a deliberate allowance for legitimate corrections.

**28. The documented remedy for a disputed attendance row is unreachable (correctness)** — FIXED

`DOM-PROD-001` §187 names the correction path precisely:

> "If a teacher believes an attendance row produced an incorrect payroll outcome,
> the correction path is a payroll reversal through `FEAT-PROD-003`, not mutation
> of the attendance row."

That path does not exist in practice.

`record_payroll_reversal` (`app/feats/prod.py:689`) appears **exactly once in the
repository — its own definition.** No route calls it, no service calls it, no
test covers it. The payroll template can *render* a reversal
(`entry.is_reversal`, a `REVERSAL` badge in `admin_payroll.html`), so the read
side anticipates rows the write side never produces.

Meanwhile the dispute does reach a teacher. A student can report a specific
attendance session (`/student/help-support/attendance-session/<id>/report`), and
the ticket arrives with the attendance session as its subject. But an attendance
issue carries no `related_transaction_id`, so the resolution control in
`templates/admin_view_issue.html` offers exactly two options:

* **Manual Adjustment (I'll handle it)** — which does nothing. The handler's own
  comment reads "Owner/admin handles manually (no automatic action)"; it records
  a resolution note and moves no money.
* **Deny Issue**

So a student can raise an attendance dispute, a teacher can acknowledge or deny
it, and there is no mechanism to remedy it. A teacher wanting to make the student
whole must leave the ticket and issue a manual credit from Payroll — a different
operation with different provenance (`manual_credit`, not `reversal`), which is
the one thing §185 warns against in spirit: correcting a payroll outcome by a
route that does not record itself as a correction.

Raised by the operator, who knew the dispute could be filed and did not know what
could be done about it. The answer is nothing, and the reason is that the
specified remedy was never wired up.

### Decision — attendance is never corrected; payroll reversal is the only remedy

**Operator decision, 2026-09-21**, in response to findings 27 and 28: do not build
any attendance-correction capability. Tell the teacher plainly that a wrong
attendance record is remedied by reversing the payroll it produced, and put the
remaining effort into making that reversal actually work.

This adopts `DOM-PROD-001` §187 as the implemented path rather than inventing
policy, and it has a property worth stating: **if no correction surface exists,
there is nothing to misuse.** The concern is not a teacher acting in bad faith;
it is a well-meaning one "fixing" a record that payroll has already paid against,
leaving the money and its justification permanently out of step.

It also narrows the work. Instead of designing correction semantics — who may
edit, what is preserved, how payroll re-derives — the task is to wire one
existing FEAT to one surface.

**What the wiring requires.** `record_payroll_reversal` resolves its target by
`correlation_id`: it finds the `PayrollEvent` matching
`(class_id, target_seat_id, correlation_id)`, inherits that event's
`policy_version_id` ("a reversal carries the provenance of the event it
compensates"), locates the linked `Transaction`, and negates its amount. Nothing
is hand-entered, so a reversal cannot disagree with what was paid.

**Two consequences the teacher-facing copy must carry:**

1. **A reversal is whole-event, not per-row.** Payroll pays a cycle's aggregate
   attendance as one event under one correlation, so reversing the payment a
   disputed row contributed to reverses that seat's **entire cycle payment**. The
   correct amount is then re-issued. This is right — the amount is derived rather
   than typed — but a teacher expecting to claw back a few minutes will instead
   see the whole payment reversed and replaced.

2. **It requires payroll to have already run.** Before settlement there is no
   `PayrollEvent` carrying that correlation, and the call raises `LookupError`.
   A dispute filed mid-cycle cannot be remedied until the cycle pays out, so the
   resolution control must either be unavailable with an explanation or the
   ticket must be holdable until settlement.

**Scope of the work this implies:**

- A `reverse_payroll` resolution action on attendance issues in
  `templates/admin_view_issue.html`, replacing the present choice between a
  no-op and a denial.
- Resolution of the disputed `attendance_session_id` to the payroll event that
  paid for it, to supply the `correlation_id`. This mapping does not exist today
  and is the only genuinely new logic required.
- Re-issue of the corrected payment after reversal, so the student is not simply
  left short.
- Copy stating that the attendance record itself is permanent and why — the rule
  is currently invisible to the teacher, who has no way to know that "fixing the
  record" was never an option.
- The immutability trigger from finding 27, so that the absence of a correction
  surface is enforced rather than merely current. A decision not to build one
  today does not stop someone building one later.

**29. Hall-pass approval is completely broken: a FEAT nested inside itself (correctness, P0-shaped)** — FIXED

Approving a pending hall pass returns **500 on every attempt**. The teacher sees
"Pending hall pass not updated — The pending hall pass could not be updated.
Please try again", and retrying cannot succeed.

    POST /api/hall-pass/request/<id>/approve -> 500
    FEAT-ENTRY: feat=FEAT-PROD-002 | idempotency_key=hall_pass_approve:<class>:<id>
    FEATContextError: FATAL: Nested FEAT context forbidden — exactly one FEAT
    executes per request (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).
    Active=FEAT-PROD-002, attempted=FEAT-PROD-002.

`Active` and `attempted` are the same FEAT. `app/routes/api.py` opens the context
and then calls a function that opens it again:

    with FEATContext("FEAT-PROD-002", idempotency_key=idempotency_key):
        record_hall_pass_log(...)          # @requires_feat_context("FEAT-PROD-002")

`record_hall_pass_log` carries the decorator at `app/feats/prod.py:501`. Either
the explicit context or the decorator is correct; both together cannot be.

**The 500 rather than a handled error is a second defect in the same block.** The
route catches `ValueError` and `SQLAlchemyError`. `FEATContextError` is neither,
so it escapes to Flask's handler — which is why the operator saw a generic
failure rather than a specific one, and why the response is 500 rather than the
400 the route intended.

**This is the third instance of the same pattern in this codebase**, which is
what makes it worth more than a one-line fix:

* `FEAT-PROD-001` executing itself made daily-limit auto tap-out silently
  non-functional — tracker blocker **B9**, closed 2026-09-04.
* `store_management` carried a `@requires_feat_context("FEAT-STOR-001")`
  decorator while opening `FEAT-SETTINGS-001` inside, raising the same error;
  fixed and documented in the route's own docstring.
* This one.

`tests/test_feat_no_nested_execution.py` exists. It did not catch this, so
whatever it asserts does not cover a route that opens a context and calls a
decorated function inside it. Worth reading before fixing, because the guard is
the thing that should have made a third instance impossible — the same
rule-versus-control gap as findings 26 and 27.

**Impact.** Hall passes cannot be issued at all. A student can buy one, hold the
balance, request it from the Break flow, and the teacher cannot approve it. The
request stays pending forever; the pass is never consumed; no
`hall_pass_logs` row is written and no attendance row records the student as out
of the room. For a classroom tool, "the student cannot be let out of the room" is
a launch blocker.

Present on current `main` (both the nesting and the exception handling).

Found by the operator while testing whether Alex could go to the bathroom.

**30. The rent page presents the pending policy as the current one (correctness, misreport)** — FIXED

Found as the direct consequence of the B1 verification above. The invariant is
right; the page describing it was not.

Two different questions resolve to two different rent policies, and the admin
page only ever asked one of them:

| Surface | Resolver | Answers |
|---|---|---|
| `/admin/rent-settings` | `get_rent_settings(class_id)` | newest `IN_USE` row |
| `/student/rent` | `get_rent_settings_for_context` → cycle's `policy_uuid` | the row the open cycle froze |

While a cycle is open those are the same row only until the teacher saves. After
a mid-cycle save they diverge for the rest of the cycle, and the admin page went
on rendering the newest row — the *pending* policy — under the heading **"Current
Rent Configuration"**, with the settings form pre-filled from it and a flash
reading "Rent settings updated successfully!".

Every part of that is literally true and collectively misleading. The save did
succeed. The row is the current policy *for new work*. But no student is billed
under it, and nothing on the page said so. A teacher who raised rent from $50 to
$75 saw $75 echoed back in a card labelled current, and would have had no reason
to look further.

**Why it matters more than a wording bug.** The deferral is the protection B1
exists to provide — a cycle already underway is never altered. A protection the
operator cannot see is one they will route around: the natural response to "my
change didn't take" is to try something else, which is exactly the sequence that
produced the attempted `UPDATE` on a RETIRED policy row during this session.
Telling the teacher plainly what is happening is cheaper than defending against
what they do when they are not told.

The precedent already existed one accordion away. The Rent Benefits panel says a
store-side change "applies from the **next** rent cycle, so a cycle already
underway is never altered." The rent policy itself, the higher-stakes setting,
said nothing.

**Operator request, 2026-09-21:** surface it at save *and* as a standing alert
whenever a policy is enforced, since the divergence outlives the request that
created it.

**Fix.** `_resolve_rent_policy_deferral` (`app/routes/admin.py`) compares the open
cycle's frozen `policy_uuid` against the newest `IN_USE` row and, when they
differ, returns both sets of terms plus the effective date. The effective instant
is the cycle's **`next_assessment_at`**, not `cycle_boundary_at`: `reconcile_rent`
mints the successor when `now >= next_assessment_at` and binds whatever policy is
in force at that moment, so that is the instant the pending policy takes effect.
It is rendered as a **class-local** date through CLE (SPEC-TIME-001 §CLE) — a UTC
reading of the same instant shows the previous day for a US class, which is
finding 25's defect in display form.

Three surfaces now carry it: a standing alert on both tabs, the Overview card
heading relabelled from "Current" to "Saved" while a policy is pending, and a
flash at save that names the in-force terms and the date the new ones start. A
terminal cycle (`next_assessment_at IS NULL`) gets its own wording, because the
saved policy will not bind at all until billing resumes.

`tests/test_rent_policy_deferral_notice.py` — 7 tests, including the no-divergence
cases asserting the notice is **absent** and the heading still reads "Current".
Mutation-proved per `SOP-TEST-003` §IX.A: forcing the resolver to return `None`
turns the four positive tests red and leaves the three absence tests green.

### Status page — context and launch decisions

**CORRECTION (2026-09-19).** An earlier revision of this section stated that
"the status service is a notice board, not a health poller", that it does not
read `/health/status`, and that nothing from Grafana is needed "by design". **All
three claims were wrong**, and are retained here only as the error they were.
They were reached by reading one implementation path — the Firestore notice reads
in `status_service/app.py` — and generalising it into the design. The design
lives in `status/projection.py` and `status/contracts.py`, which say something
different. Corrected account follows.

**The status contract has four evidence sources, not one.**
`status/projection.py:35` defines:

    class EvidenceSource(str, Enum):
        INVARIANT_VERIFIER  = "INVARIANT_VERIFIER"
        GRAFANA_TELEMETRY   = "GRAFANA_TELEMETRY"
        EXTERNAL_PROBE      = "EXTERNAL_PROBE"
        DOM_OPS_PUBLICATION = "DOM_OPS_PUBLICATION"

Operator-written notices are `DOM_OPS_PUBLICATION` — one source of four. Health
probing and Grafana telemetry are first-class members of the same contract.

**The application publishes a health endpoint built for exactly this.**
`app/routes/main.py:76` — `/health/status` — states its purpose in its first
line: "Return bounded capability and platform signals for status publication." It
emits `{key, layer, outcome, epistemic_state, diagnostic_code}` per signal, which
is the `Observation` shape, and its capability keys (`login`, `attendance`,
`payroll`, `roster`, `classroom_economy`) are exactly the keys in
`CAPABILITY_LABELS` (`status/projection.py:42`). The two vocabularies were
designed against each other. That is the `EXTERNAL_PROBE` source.

Today it executes exactly one real check — `SELECT 1`, reported as the `database`
platform signal. Every other signal returns UNKNOWN/UNAVAILABLE with
`CHECK_NOT_REGISTERED`, and the docstring is emphatic that this "is the contract,
not a gap: a capability reports UNKNOWN until a lawful read-only probe is
registered for it, so the endpoint can never imply health it has not observed
(INV-ARC-017)."

**Grafana already has a translation seam.** `status/telemetry.py` exists solely
to convert a bounded telemetry result into an observation, and its module
docstring says: "Grafana and Prometheus are evidence sources; this module only
translates an already bounded, approved result into the status observation
contract." `TelemetryResult.healthy` is deliberately tri-state — `None` means the
source could not establish a state "and must not be treated as healthy". It is
covered by `tests/test_status_telemetry.py`.

**What is actually missing is the transport layer.** `status/telemetry.py` says
the "transport/query layer is deliberately outside this module", and no module
implements it: nothing fetches `/health/status`, nothing queries Grafana, and
`public_status()` currently projects capability cards and platform checks from
notices alone. So the seams are specified, contracted and unit-tested, but
unwired — which is a very different statement from "not needed by design", and
the distinction is the whole point of this correction.

The operator's proposal — have Grafana emit a signal on specific log keywords —
lands precisely on the built seam: a Loki/Grafana alert becomes a
`TelemetryResult`, which `to_observation()` converts to a `GRAFANA_TELEMETRY`
observation. Note this depends on finding 19: the surviving dashboards query
labels v2 does not emit, so keyword rules must be written against the real label
set (`detected_level`, `unit="classroom-economy.service"`,
`job=nginx_access|nginx_error`), not the v1 ones.

**Ordering: probes before transport.** A first draft of this section called the
transport layer the step that "unblocks everything". It is not. Building
transport while no probe is registered would carry UNKNOWN from the endpoint to
the page and change nothing a visitor could see — the reason would move from
"nothing is wired" to "nothing is measured" with identical output. Registering
real read-only probes is what makes the page say anything; transport is
necessary but produces no observable change on its own. The single exception is
`database`, the one signal with a real check behind it (`SELECT 1`, live: PASS /
KNOWN / `DATABASE_REACHABLE`), which is also one of the three default
`STATUS_PLATFORM_CHECKS`.

**A capability the app cannot answer about itself.** `STATUS_CAPABILITIES`
defaults to `public_service_reachability`, and `/health/status` never emits that
key — it emits `login`, `attendance`, `payroll`, `roster`, `classroom_economy`.
So the one capability card the public page shows by default has no corresponding
signal in the endpoint, and wiring transport would not fill it even in
principle.

That is coherent rather than broken. `public_service_reachability` asks "Can I
access Classroom Token Hub right now?", and an application cannot truthfully
answer that about itself: when it is down it is not answering at all. The signal
is only obtainable outside-in, which is what `EXTERNAL_PROBE` denotes and why
finding 8's `STATUS_PAGE_URL` allowlist is UptimeRobot-shaped. The evidence
sources divide by what each can honestly know:

| Signal | Source | Why that source |
|---|---|---|
| `public_service_reachability` | external prober | self-reported reachability is incoherent |
| `login`, `payroll`, `roster`, `attendance`, `classroom_economy` | app `/health/status` | only the application can exercise them |
| `ledger_correctness` | `INVARIANT_VERIFIER` | requires invariant evaluation, not liveness |
| keyword / rate signals | `GRAFANA_TELEMETRY` | log and metric evidence |

The work is therefore not "wire up the status page" but four independent evidence
feeds, each answering a question only it can answer, with the page reporting
UNKNOWN for anything not yet fed.

**Remaining true from the original account:** nothing in the main application
writes notices, so an outage produces no operator notice on its own. And
`derive_overall_status` deliberately reports UNKNOWN rather than healthy when
there is no active notice — "In the absence of a fresh observation source, no
active notice is deliberately reported as unknown rather than healthy" — which is
the same INV-ARC-017 discipline, correctly held here.

**Access gating — deliberate, revisit at launch.** `status.classroomtokenhub.com`
sits behind Cloudflare Access like the app and operator hostnames, returning 302
to the Access login for unauthenticated visitors. Service-to-service access
(Cloud Run to Firestore, automated checks) is handled by service credentials and
is unaffected.

The open question is human visitors during an outage: a teacher whose class
cannot sign in would also be unable to reach the status page, and if the outage
is auth-related that is the one door they most need. **Operator decision
2026-09-19: keep it gated for now** — pre-launch there is no user base it would
serve, and an openly reachable status page for a product nobody can yet sign up
for would cause confusion rather than resolve it. Revisit when the service opens
to real classes.

### Investigated, not a defect

`GET /favicon.ico` → 404 on every page load. The favicon is *not* missing:
`base.html` and all three layouts declare
`<link rel="icon" type="image/png" sizes="192x192">` pointing at
`static/images/icon-192.png`, which exists, and git history shows no favicon was
ever deleted. The 404 is the browser's unconditional root-level probe, which is
normal for sites serving a PNG icon. Recorded because it was initially raised as
a finding and should not be re-raised.

`Transaction.type` carries an inconsistent casing vocabulary. Writers emit
lowercase `payroll`, `purchase`, `overdraft_fee`, `manual_payment`, but
capitalised `Withdrawal` / `Deposit` (`app/services/ledger_transfer_service.py:65`
and `:71`) and `Interest` (`app/services/ledger_interest_service.py:94`). The
column is a bare nullable `db.String(50)` commented "optional field to describe
the transaction type"; nothing constrains its values.

The field *is* used as a filter key in exact-match comparisons
(`app/payroll.py:258`, `app/feats/ledger_resolution_feat.py:202`,
`app/feats/collective_goal_expiry_feat.py:114`) and in the admin transaction
filter (`app/routes/admin.py:8354`).

**Nothing is broken.** Every exact-match filter targets one of the lowercase
values, and those are written lowercase. Templates render through `|title`, so
display is normalised regardless. The admin filter populates its dropdown from
`SELECT DISTINCT type`, so it offers whatever actually exists.

Recorded as a latent hazard rather than work: a free-text vocabulary used as a
filter key will eventually be filtered on with the wrong casing. The risk is
bounded because `INV-ITR-015` already forbids Interpretation from consulting this
column at all — the codebase has effectively ruled the field untrustworthy for
semantics. Should it ever need to carry meaning, it needs a closed vocabulary
first.

## §XII — Remediation batch, 2026-09-21

Testing stopped and the round's findings were fixed in one batch on
`codex/live-test-launch-readiness`, in six tranches. Every fix was
mutation-proved: the change reverted, the new tests confirmed red, the change
restored. Findings 30 and 21-29 are closed; 31-37 were found during this round
or while fixing it.

| Tranche | Findings | Commit |
|---|---|---|
| A | 29 hall-pass approval, 31 timeout 404, 32 rotate CSRF | `6718823b0` |
| B | 33 CSRF guard, 34 sysadmin passkey | `d34ca2883` |
| C | 25 rent CLE dates, 24 rent band, 35 unhandled CWI `None` | `d0e520775` |
| D | 26 temporal guardrail (rule 10) | `4b17f18aa` |
| E | 21 export label, 22 stale tab, 23 `print()` | `69587130c` |
| F | 27 attendance triggers, 28 payroll reversal surface | `9c378ba52`, `918152945` |

**31. A timed-out teacher gets a bare "Not Found" on the six pages they use most (correctness, misreport)** — FIXED

Blueprint `before_request` hooks run before the view, and therefore before the
view's own `@admin_required`. On an expired session `g.canonical_context` was
not set yet, so every feature resolved `UNRESOLVED` and the fail-closed
capability gate returned a 9-byte `"Not Found"` that short-circuited the request
before the login redirect could happen. Payroll, store, banking, rent, insurance
and hall pass all did this; every other admin page redirected correctly.

The gate is right to fail closed — it was evaluating feature authority before
authentication had been decided, and so could not distinguish "your session
expired" from "this class does not have rent enabled". It picked the wrong one to
say aloud. The page's own background poll meanwhile received the correct
`401 authentication_required`, because `_is_background_request()` routes it past
the gate: the AJAX call knew the session was dead while the page render said the
URL did not exist.

**32. The hall-pass verification link can never be rotated (correctness, security)** — FIXED

`POST /api/hall-pass/verify-token/rotate` omitted `X-CSRFToken`, so Flask-WTF
rejected every attempt with 400 before the route ran. Rotation is the documented
remedy for a leaked or screenshotted link, and that token is the only control
protecting a deliberately non-enumerable public page. Nine of the app's ten POST
sites already route through `AppCore.csrfFetch`; this one reached past it.

The refusal then came back as an HTML error page, so an unguarded `r.json()`
threw into `.catch()` and announced **"Failed to contact the server"** — the one
message that makes an operator retry rather than report. Same family as finding
11: the error path telling the user something the server never said.

**33. Nothing prevented a state-changing fetch from omitting its CSRF token (process, root cause)** — FIXED

`conftest.py` sets `WTF_CSRF_ENABLED=False`, so a missing header is invisible to
every one of the suite's ~3,400 tests. It surfaces only in a browser, as a 400
the route never sees — the feature is disabled, not degraded. The helper existed
and was used nine times out of ten; what was missing was anything that made the
tenth fail. Now a source-level guard with mutation proofs for both shipped
defects. Finding 26's shape, in a different domain.

**34. Sysadmin passkey deletion is unreachable (correctness, two causes)** — FIXED

Found by the CSRF guard before it was finished. The client sent `DELETE` to a
route registered for `POST` only — 405 before CSRF was consulted — *and* carried
no token, so correcting the verb alone would have produced 400. Two independent
breakages, each sufficient, each masking the other's symptom. The teacher-side
equivalent had both right: two implementations of one operation had drifted, and
only the sysadmin copy was wrong.

**35. The economy validator turns a configuration gap into a 500 (correctness)** — FIXED

`calculate_cwi` returns `None` when expected weekly hours are configured nowhere,
and its docstring says callers must handle it. `/admin/api/economy/validate/<f>`
did not, so `.cwi` raised and the generic handler produced a 500 with no
guidance. Unreachable until finding 24(b) was fixed, because the endpoint
previously returned the "configure payroll" warning before reaching it. **Found
by the regression test written for 24, not by review** — which is the argument
for writing the test before trusting the fix.

**36. The test database and production disagree about what a naive datetime means (process)** — OPEN

| | DB session timezone |
|---|---|
| Test database | `America/Los_Angeles` |
| Production | `Etc/UTC` |

A naive datetime is resolved against a different zone in the two environments, so
a timezone defect can pass locally and fail in production *by construction*. This
is the structural reason the 6A family kept shipping: for a Pacific class the
shipped naive parse produced the **correct instant in test and the wrong one in
production**.

Partly mitigated: `Pacific/Kiritimati` (UTC+14) is now a provisioned test
classroom timezone, and the rent date assertions run against it. Its local
midnight is the previous day in UTC and the day before that in a UTC−12 session —
26 hours of civil-date separation, the widest the calendar allows, and almost all
of it convention rather than distance, since Kiritimati and Baker Island lie
2,129 km apart with the International Date Line between them. No host, server or
database clock can make a naive parse land on it by accident.

**Not yet done, and deliberately not bundled here:** running the full suite under
an ambient `Etc/GMT+12`. That changes the footing under ~3,400 tests and answers a
different question — *which tests or runtime paths accidentally depend on the
environment's timezone* — so it is an experiment with results to classify, not a
fix. `INV-ARC-015` gives the classification rule: SLE derives from UTC, CLE from
the Canonical Class Timezone, and neither should derive from wherever the process
happens to think it lives. Production-parity UTC testing remains separately
useful; a hostile-time job would be an addition, not a replacement.

**37. `app/utils/deletion.py` cannot be imported and nothing imports it (correctness, dead code)** — OPEN

Recorded in finding 27 as one of the two legitimate attendance-teardown paths. It
is not a path at all: it imports `StorePurchase`, `Entitlement`,
`EntitlementConsumption` and `RedemptionEvent`, none of which exist in
`app/models.py`, so importing the module raises `ImportError` — and nothing under
`app/` imports it. `app/services/teacher_destruction.py` is the live destruction
path, reached from `admin.py` and `teacher_lifecycle.py`.

Left in place rather than deleted. `collapse_universe()` suggests a code path may
have been lost during the v1→v2 migration, and that deserves investigation rather
than a silent removal — deleting the module would erase the evidence that
something went missing. This corrects the record in finding 27.

**38. One reason code describes four different endings (spec question, NOT a defect)** — ESCALATED

Found by verifying the daily-limit prediction against live data, and worth
recording mainly for what it turned out *not* to be.

**The mechanism is correct.** Seat 6 clocked in at `03:40:06.647847Z`; the
scheduler wrote an `inactive` row at exactly `05:10:06.647847Z` — clock-in plus
5400s to the microsecond, accumulating exactly the 5400s limit, `mechanism =
system`. `DOM-PROD-001` §319's timestamp correction works: the student is not
paid for the ~35 minutes between the cap being reached and the hourly job
noticing.

**The observation.** That row reads `reason_code = done_for_day` — the same code
written when a student chooses to stop, when the class day ends on an open
session, and when a hanging hall pass is closed out. Four events, one code. The
scheduled job composes an explanatory string for two of them ("Daily limit
reached (1.5h)", "Automatically closed at end of day") and passes it to a
`reason` parameter that has **no column behind it**: `attendance_sessions` has
`reason_code` and nothing else, so the text is built and discarded on every run.

Why it seemed to matter: attendance rows are permanent and never corrected
(§108), and the operator decision of 2026-09-21 makes payroll reversal the only
remedy (§187). The row is therefore the evidence a teacher weighs when deciding
whether to reverse. "Why did I stop at 22:10?" is answered by a code that reads
as though the student chose to.

**Why this is not a defect.** `DOM-PROD-001` mandates exactly this, in four
places:

| Clause | Requirement |
|---|---|
| §302 | ``reason_code`` — enumerated: ``hall_pass`` \| ``done_for_day`` \| ``start_work`` |
| §316 | prior-session auto-close SHALL use ``reason_code = done_for_day`` |
| §317 | end-of-day termination SHALL use ``reason_code = done_for_day`` |
| §318 | hanging hall pass SHALL close with ``reason_code = done_for_day`` |
| §319 | the daily limit SHALL generate an inactive row with ``reason_code = done_for_day`` |

The enumeration is closed and the four closures are each specified by name. The
implementation is not drifting from the contract; it is obeying it exactly.

**An attempted fix was reverted, and the reversion is the useful record.** Two
codes (`daily_limit_reached`, `end_of_day`) were added, the lockout queries
widened to a terminal-code set, and the scheduled job taught to record which
close it performed. Three constitutional tests failed immediately —
`test_DOM_PROD_001__later_day_tap_in_closes_prior_session_at_its_own_day_end` and
two in `test_stale_session_sweep.py` — which is what tests named for a rule are
for: the failure said which law broke. The change was reverted in full.

This is the direction-of-authority mistake the documentation hierarchy exists to
prevent, committed while fixing findings that were themselves about rules without
controls. The rule was reconstructed from the code and from reasoning about what
the record *ought* to say, rather than read from the normative document first.
`DOM-PROD-001` is the target state; the code was already there.

**The question for the operator**, which only they can answer:

> Given that attendance is never corrected and payroll reversal is the sole
> remedy, is `done_for_day` sufficient evidence for a teacher deciding whether a
> reversal is warranted — when it cannot distinguish a student who stopped from
> one the system capped?

If the answer is no, the work is an amendment to `DOM-PROD-001` §302 and
§316-§319, and the code follows it. If the answer is yes, this finding closes as
intended behaviour and should not be re-raised. Either way the remedy is not a
code change made first.

Worth noting separately and independently of the enumeration: the `reason`
parameter has no persistence at all. Whether or not the codes change, an
explanatory string is currently computed and thrown away on every automatic
close, which is at best misleading to a future reader of the job.

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

# Resume point — live-test remediation, continued session of 2026-09-21/22

**Superseded by §8.** The "SESSION CLOSED" note below described the state at
end-of-day 2026-09-21/22. The session continued into 2026-09-23 (status
telemetry deploy, two rent-correctness defects, teacher-recovery and
add-class verification, finding 68). See §8 for what happened after this
point; §0-§7 are left as written, per this doc's own method note.

**SESSION CLOSED (as of the original writing).** This is the final state as of end-of-session
2026-09-21/22. Everything in §2 is committed, tested, deployed, and the
host restarted clean. Nothing is mid-flight except finding 66 (diagnosed,
not yet coded) — see §6 for where to start tomorrow.

**Branch:** `main` (direct commits, per operator instruction — this is live-test
remediation, not the official production launch cycle; the full ~3,400-test
suite is reserved for that transition, per `RESUME_2026-09-22.md` §1 and the
operator's own restatement tonight).
**Live server:** `24bca2c8c`, tag `live-test/2026-09-21m` — deployed, migrated,
service healthy. Local `main`, `origin/main`, and the host are confirmed at
the identical SHA. Full tag sequence tonight: `...21i` (start of this doc's
window) → `...21j` → `...21k` (fmt_timestamp/TLCP-trace fix) → `...21l`
(done_for_day) → `...21m` (TLCP invariant-violation noise, final).
**Last recorded deploy before this doc:** `DEPLOY_2026-09-21_b4a639311.md`
(tag `live-test/2026-09-21`). Findings 39-44 (hall-pass hotfixes) and the
Cloudflare Access gate replacement were deployed under tags `...21b`
through `...21f` without an individual audit entry each — this document
is the first record of everything since `b4a639311`, catching the ledger up.

## 0. Tonight in one paragraph

Fixed and shipped 15 defects (findings 45-57, 14, 64, 65, 67), most already
recorded before this final update; the last three were: the long-standing
sysadmin-dashboard 500 (`operational_events` table never created, finding
14), a second 500 it uncovered on ticket detail pages (`fmt_timestamp` choking
on the JSON-sourced ISO-string timestamps in TLCP correlation packs, finding
64), the `done_for_day` UI-blindness bug where a student who tapped "Done for
the Day" still saw active Start Work/Break buttons (finding 65), and
sysadmin's entire blueprint ERROR-logging a "missing canonical context"
invariant violation on every single request, drowning real errors in noise
(finding 67). Operator drove a full student → teacher → sysadmin ticket
lifecycle live and it worked end-to-end, confirmed independently against the
server log rather than taken on report. One thing diagnosed but not yet
fixed: insurance-cancel-visibility (finding 66) — cancellation works
correctly server-side, the student UI just doesn't show it.

---

## 1. Where to pick up

```bash
cd classroom-economy
git log --oneline b4a639311..HEAD --reverse   # full batch, in order
git status                                     # expect clean
flask db heads                                 # expect b8e1f4c2a5d9, single head
```

Nothing is blocked on a redeploy right now — everything in §2 is already
live at `24bca2c8c` / tag `live-test/2026-09-21m`. Start with finding 66
(§4, §6) — it's the only diagnosed-but-uncoded item left.

---

## 2. What shipped since `b4a639311`

Findings 39-44 (hall-pass: hidden-attribute CSS, rotation-message button
reference, start_work-during-hall-pass corruption, Issued/Out tab
duplication) were already written up inline in their own commit messages
during the live-test session and are not re-summarized here — see
`343534c12`, `3da85506b`, `8bfbcc833`, `dea06c1e6`. Continuing the numbering:

| # | Finding | Commit |
|---|---|---|
| 45 | Hall-pass checkin no-ops when an unrelated active attendance row lands between a pass's leave and return (latest-event-only anti-pattern, same shape as 44) | `1e20214ed` |
| 46 | `admin.process_claim` flashes "Claim approved."/"Claim rejected." regardless of whether the domain layer actually succeeded — a refused decision (already-decided, allowance exhausted, missing override reason) left the claim untouched while the teacher was told it worked | `ccfb989ee` |
| 47 | Claim review "Current Status" badge compared `claim.status` (`SUBMITTED`/`APPROVED`/`REJECTED`) against lowercase v1 vocabulary (`pending`/`approved`/`paid`) — no comparison ever matched, badge had no color class, status was effectively invisible | `7ee59c1b9` |
| 48 | Once a claim reached `APPROVED`/`REJECTED` the review form stayed fully editable, inviting a second decision the backend already refused | `7ee59c1b9` |
| 49 | Getting Started's "Set up insurance" was `'insurance': False` — a bare literal, never computed, unlike every sibling checklist item | `7ee59c1b9` |
| 50 | Claim dropdown offered a transaction that already backs a claim — the submission gate already refuses it (`DUPLICATE_CLAIM_SUBJECT`), so listing it just let a student pick it and be refused | `43899fe8a` |
| 51 | TRANSACTION claim's "Briefly describe what happened" field was rendered and submitted but never read into `claim_subject` — Claim Description was guaranteed blank regardless of student input | `43899fe8a` |
| 52 | `waiting_period_days` silently dropped for TRANSACTION/PRODUCTIVITY policies even after being made settable — the per-type field loop only wrote fields *required* for that type, and waiting period is optional-but-permitted, not required | `4db43627d` |
| 53 | `passkey_register_finish()`/`passkey_delete()` (both teacher and sysadmin variants) had no `FEATContext` and no explicit commit — the write staged, the route flashed success, and the row was silently discarded at request teardown | `e87b17f52` |
| 54 | Passkey Registered/Last-used timestamps rendered via bare `.strftime()` — raw UTC, unconverted, unlabeled — while every other timestamp in the app uses `fmt_timestamp` | `d879617fa` |
| 55 | Five icons added earlier tonight (filing-window UI) missing `aria-hidden`, caught by the layout accessibility contract test | `060f3989b` |
| 56 | Sysadmin ticket detail duplicated across `/user-reports/<ref>` and `/issues/<ref>` (two routes, two templates, two disclosure implementations) for what is one `Issue` record; one dead redirect referenced a nonexistent endpoint/blueprint; two latent status-badge/filter bugs compared against non-existent lowercase status strings | `99d8d7d64` |
| 57 | Sysadmin navbar clock used `toLocaleDateString(undefined, ...)` — real browser-local-time detection — the one concrete violation found auditing sysadmin surfaces against the new INV-ARC-015 §X.2 rule | `1d6b25990` |
| 14 | `operational_events` table (DOM-OPS-001 §5) was never created despite `operational_event_service.record()`/`get_recent_error_events()` referencing it since the migration that dropped its v1 predecessors — every `/sysadmin/dashboard` load 500'd. Long-standing launch blocker, carried across multiple sessions, finally root-caused and fixed. | `b7db24437` |
| 64 | TLCP correlation packs (`tlcp.py`) freeze request-trace timestamps as ISO strings inside the JSON pack column; the new unified `sysadmin_view_issue.html` piped `trace.timestamp` straight through `fmt_timestamp`, which only accepted `datetime` — 500'd (`AttributeError: 'str' object has no attribute 'tzinfo'`) on any ticket with a non-empty request trace. Pre-existing bug (identical line in the pre-unification template); tonight's retest of finding 14 is what finally exercised it live. | `182928a79` |
| 65 | Operator (as Jordan) used "Done for Day" on the student dashboard, then reloaded — the dashboard still showed "Active" with enabled Start Work/Break buttons. Server-side `done_for_day` was already correctly computed and enforced (`app/feats/prod.py` already refused a same-day restart, 409) but never exposed to any client code path — initial page render, the 10s poller, or the tap response. Presentation-only; no data corruption was ever possible. Fixed by extracting a shared `is_done_for_day()` helper, exposing `done` from `get_class_attendance_status()` and all 3 `handle_tap()` response points, and wiring `static/js/attendance.js` (`updateAttendanceUI()`/`configureBreakButton()`, all 4 call sites) to disable both buttons and show "Done for Day" when true. | `a9eba02f6` |
| 67 | Every sysadmin request — dashboard, login, support, every ticket view, `/student/login` too — logged `TLCP-INVARIANT-VIOLATION: missing canonical context` at ERROR severity, forever, because sysadmin's permanent by-design absence of class context (INV-ARC-019) was never added to TLCP's exemption lists. Confirmed the noise doesn't reach `operational_events` (found while retesting finding 14, so it wasn't polluting the newly-fixed dashboard), but it drowns real errors in the same log stream. Fixed both directions of the sysadmin/class-context matrix: absent context on a sysadmin request is now silently expected; *present* context on a sysadmin request (which should never happen) now explicitly fails closed with its own invariant-violation log instead of being silently trusted. Verified live by curling `/sysadmin/login` directly on the host before/after and diffing the log. | `24bca2c8c` |

**Features shipped (deliberate builds, not defects):**

- Filing-window override gate for insurance claims, restoring a mechanism
  present pre-rewrite (`main_legacy_v1.10.0`, dropped 2026-08-28) — a late
  TRANSACTION claim now reaches `SUBMITTED` and a teacher can approve it
  anyway only by recording a permanent written reason. `ccfb989ee`
- `waiting_period_days` made settable (not necessarily enforced) on every
  insurance type, per operator decision — the "SPEC §4.5.3-§4.5.5" citation
  restricting it to NON_MONETARY was fabricated; confirmed by exhaustive
  grep across `docs/`. `7119271f5`
- Unified sysadmin ticket detail surface (`sysadmin.view_issue()`), replacing
  the two duplicated routes above. `99d8d7d64`
- UTC/class-time display toggle on that surface, server-resolved,
  presentation-only, defaults to UTC every load. `99d8d7d64`
- `INV-ARC-015` bumped to 2.1, §X.2 added: classroom surfaces default to
  class time, operations surfaces default to UTC with no browser/IP
  inference, and an operations page may offer the toggle above under
  stated constraints. `ab2979160`
- Two migrations: `f2b8c7e4a916` (relax the insurance type-subset CHECK
  constraint) and `a3c7d9e1b204` (add `filing_window_override_reason`).
  Both upgrade/downgrade/upgrade tested, single head confirmed before and
  after.
- **Not mine, but co-resident and deployed in this batch:** another
  worktree's `codex/cloudflare-access-gate` branch replaced
  `MAINTENANCE_MODE` with Cloudflare Access as the sole gating mechanism
  (`fe1c09afe`, merged via PR #1421). Rebased my four commits on top of it
  after a push conflict; the only file overlap was `system_admin.py`, which
  merged clean. Not verified live by me — outside this thread's scope.

Every defect fix above was mutation-proofed (reverted, confirmed the new
test went red for that exact reason, restored) before being counted done.

---

## 3. Verified live this session

- **Passkey registration and sign-in** (finding 53's fix) — operator
  registered `livetest1`, it persisted across requests, sign-in succeeded.
- **Claim review terminal lock + status visibility** (findings 47-48) —
  operator screenshot confirms: "Current Status: Approved" renders visibly,
  "Validation Status: Filed within the filing window" renders correctly, and
  the Process-This-Claim panel correctly shows "This claim was approved on
  Sep 21, 2026, 8:37 PM PDT. Decisions are final — no further changes can be
  made here." instead of a live form.
- **Sysadmin dashboard loads** (finding 14's fix) — operator retried sign-in
  after deploy, `/sysadmin/dashboard` returned 200 (confirmed via server log,
  not just operator report).
- **Full ticket lifecycle, student → teacher → sysadmin** (findings 14, 56,
  64, and the unified `/sysadmin/issues/<ref>` surface generally) — operator
  drove a ticket from student submission through teacher escalation to
  sysadmin resolution end-to-end and confirmed it worked, after the finding-64
  fix landed. This clears the "brand new, zero live testing" item in the old
  §5 for the unified ticket page's escalation/bug-bounty panel state; the
  direct Open/Resolved/Closed and read-only-with-teacher panel states were
  not specifically exercised by this run and remain unconfirmed.
  **Cross-checked against the raw server log, not taken on operator report
  alone** — traced every request in the window: 200s and 302s throughout,
  zero 4xx/5xx besides one unrelated static-asset 404.
- **TLCP invariant-violation noise gone for sysadmin** (finding 67) — curled
  `/sysadmin/login` directly on the host before and after the fix and diffed
  the log: the `ERROR`-level line fired on every hit before, is gone after.
  This is host-log-verified, not exercised through an operator click in the
  browser.

Everything else in §2's finding table — including findings 14, 64, and 65's
fix itself — was confirmed only by the automated test suite or (for 14/64/67)
a direct log check, not by a fresh operator click-through after the fix
landed. See §5.

---

## 4. Open findings (pre-existing, not touched this session)

Carried forward from `RESUME_2026-09-22.md` §3 — status not rechecked:

| # | Finding | Note |
|---|---|---|
| 15, 17, 18, 19 | Grafana/Tempo proxy issues | unfixed |
| 36 | Test DB is `America/Los_Angeles`, production `Etc/UTC` | mitigated, not resolved — see that doc |
| 37 | `app/utils/deletion.py` unimportable dead code | left deliberately pending investigation |

New, found this session, not yet fixed:

| # | Finding | Note |
|---|---|---|
| 58 | PRODUCTIVITY-type claims write their free-text explanation under `additional_information`; the admin review page reads `description`. Same root shape as finding 51, un-fixed for this type. | not fixed |
| 59 | Insurance policy detail page shows `Autopay: Enabled`, `Auto-cancel after 0 days of non-payment`, `Max per claim: Unlimited` as hardcoded literals in `app/routes/student.py` (`autopay=True`, `auto_cancel_nonpay_days=0`, `contract_max_claim_amount=None`) — not backed by any column, not settable, contradicts the real enforced payout cap shown elsewhere on the claim-review page. | not fixed |
| 60 | The same policy page's "Max claims: N per period" shows the raw `claims_per_week_equivalent` rate mislabeled as a period count — the real per-period allowance (what the claim-review page correctly shows) is `ceil(rate × week-equivalent)`, e.g. 3/week reads as "13" elsewhere on the same policy. | not fixed |
| 61 | Payroll → Manual Payments: `payment_type`/`account_type`/`save_action` are hardcoded hidden form inputs behind a UI element ("Action:") that visually resembles a live choice. Investigation was mid-flight (confirmed the client- and server-side hardcoding; had not finished reading `record_payroll_event`'s remaining arguments) when this thread moved to the passkey work. | investigation incomplete |
| 62 | `/static/manifest.json` fetch is intercepted by Cloudflare Access and redirected to its own login page, tripping the page's own CSP (`default-src 'self'`) and producing a permanent `sw.js` cache-first failure loop on every navigation. Cosmetic/console-only — PWA installability and offline caching for that one asset, not a functional break. | not investigated further, deferred by operator |
| 63 | Rent obligation summary showed only 1 of 2 claimed students (Jordan Lee excluded) in an earlier live test. Checked tonight: **zero `ObligationAssessment` rows exist for any student in this class**, including the one claimed since 2026-09-19 — so either the rent cycle genuinely has not run for anyone yet, or `build_class_obligation_summary`/`build_student_obligation_view` compute the widget live rather than from persisted assessments and this check is answering the wrong question. Root cause still not isolated. | operator asked to keep watching; re-check after the next rent cycle boundary |
| 66 | Operator cancelled both of Jordan's insurance policies; the student Insurance page still shows the "Cancel coverage" button/form even though a "This coverage is already set to not renew" banner is present — operator wants the button replaced with "Expires on [date]" once cancelled, for visibility. Confirmed at the data layer: `BillCycle.next_assessment_at IS NULL` on the terminal cycle for both policies, real expiry dates 2026-10-22 — cancellation genuinely took effect server-side; this is purely a display gap. No code changes made yet. | **diagnosed, not fixed — start here tomorrow** |

---

## 5. What has NOT been tested

### Deployed, automated-tested only — needs a fresh live pass
- Waiting-period persistence (finding 52's fix) — operator found it broken,
  fix shipped, not reconfirmed by re-saving a policy afterward
- Claim dropdown exclusion + description capture (50, 51)
- Hall-pass checkin fix (45) — the original corrupted-timeline symptom was
  seen live; the fix itself only re-verified by the automated regression,
  not a fresh live checkin
- Passkey timestamp now in class time instead of raw UTC (54) — registered
  before this fix landed
- **`done_for_day` UI fix (65)** — the original symptom (buttons stayed
  enabled after "Done for the Day") was seen live; the fix itself has only
  been confirmed by the automated regression suite. Operator has not yet
  reloaded the dashboard as a student after tapping "Done for the Day"
  since this deployed.

### Brand new, zero live testing
- Unified ticket page (`/sysadmin/issues/<ref>`): the escalation/bug-bounty
  panel state was exercised end-to-end tonight (see §3) and works; the direct
  Open/Resolved/Closed and read-only-with-teacher panel states are still
  unconfirmed live
- The UTC/class-time toggle itself — page rendered live, but the toggle
  control was not specifically clicked/verified
- Sysadmin navbar clock UTC display

### Entirely dark (carried forward from `RESUME_2026-09-22.md` §5, status
unknown — not touched this session)
- Insurance purchase → claim → payout end-to-end with a *nonzero* waiting
  period (tonight exercised claim review and the filing-window gate, but
  every test policy used waiting period 0 or wasn't checked against it)
- Recovery flows (teacher and student)
- Student-side add/switch class
- Announcements, Analytics, Store collective goals
- A student in two classes at once
- Turnstile across all forms except signup
- Systematic PII/encryption sweep
- Full accessibility pass (INV-ARC-020) — only the layout contract test ran,
  not a manual screen-reader pass

---

## 6. Suggested order for next session

1. **Fix finding 66 (insurance-cancel visibility)** — diagnosed, server-
   verified, no code written yet. Add `cancelled`/`expires_at` to
   `owned_coverage` in `app/routes/student.py` (query `BillCycle` by
   `policy_uuid`+`class_id` for the terminal cycle's `cycle_boundary_at`),
   swap the Cancel-coverage form for "Expires on [date]" in
   `templates/student_insurance_marketplace.html` once cancelled.
2. Live-verify the five "automated-tested only" items in §5 with a fresh
   click-through, `done_for_day` (65) first since it's the newest and the
   original symptom was seen live under the operator's own account.
3. Live-verify the remaining unified-ticket-page panel states
   (Open/Resolved/Closed direct action, read-only-with-teacher) and the
   UTC/class-time toggle control itself.
4. Finish the payroll Manual Payments investigation (61) — was interrupted
   mid-read, not abandoned by decision.
5. Fix 58 (PRODUCTIVITY description key) and 59/60 (fake insurance policy
   fields) — same shape as fixes already shipped this session, small and
   well-scoped.
6. Re-check finding 63 once the class's rent cycle has had a chance to run.
7. Optional, low priority: `/health/status` logs the same
   `TLCP-INVARIANT-VIOLATION` noise finding 67 fixed for sysadmin — spotted
   in passing while verifying 67, explicitly deferred as out of scope for
   that fix. Different endpoint, same underlying shape (a legitimately
   context-free request TLCP doesn't know is legitimate).

---

## 7. Method

Unchanged from `RESUME_2026-09-22.md` §7: predict before producing;
controlled comparison over a single negative; reach the state as a user
would; confirm at the data layer; record evidence, not verdict. Every fix
in §2 was mutation-proofed. This document exists because relying on
conversation memory across a compaction boundary is exactly the kind of
un-recorded state this campaign's whole method exists to avoid.

---

## 8. Continued 2026-09-22/23 — past the original "session closed" point

**Live server:** `2e5ebf0a2`, tag `live-test/2026-09-23a`.

**Also landed this stretch, not part of the live-test surface but deployed
alongside it:** the request-telemetry sampler for the status page
(`docs/ops/STATUS_REQUEST_TELEMETRY_SETUP.md`) — new `cth-status` system
user, `/opt/cth-status-sampler`, `cth-status-sampler.timer` (hourly →
per-minute), and an nginx `location = /health/telemetry` block. Verified
live: the timer fires on its own schedule (not just the manual test run),
`/health/telemetry` serves bounded JSON with the right headers, POST is
denied, and external unauthenticated access gets the same Cloudflare Access
redirect as the existing `/health/status` — no separate Cloudflare
configuration needed.

### Two rent-correctness defects, found live and closed

| # | Finding | Commit |
|---|---|---|
| — | A rent cycle's frozen `policy_uuid` correctly fixed its *terms* (amount, cadence, penalty, due dates) but was also accidentally fixing its *roster* — `reconcile_rent` only ever assessed the roster at the instant a cycle was created or advanced, never on a plain re-run. A seat claimed after that instant got no rent obligation at all until the cycle advanced, potentially over a month later. Reproduced live: a student claimed a seat the day after cycle 1's only assessment pass and had zero rent obligations. Fixed: roster assessment now runs against the current open cycle on every reconciliation, idempotent per (seat, cycle) — never retroactive against a cycle that already closed before the seat was claimed. | `ad4f69933` |
| — | The admin rent page claimed "A rent cycle is already underway, and a cycle underway is never altered" for a cycle whose `cycle_boundary_at` was still a month in the future — directly contradicting the same page's own "Not active yet" / "Not scheduled yet" summary a few lines below. `_resolve_rent_policy_deferral` treated any existing `BillCycle` row as proof of "underway" without checking whether its boundary had actually arrived. Fixed: the deferral notice (and the append-only protection it describes) now only applies once the cycle has actually started. | `3210e8edd` |

Both mutation-proofed (67 tests across `test_rent_lifecycle.py` +
`test_rent_policy_deferral_notice.py` + the broader obligations/store suite,
each new assertion confirmed to fail for the exact right reason before the
fix).

### Finding 68 — /student/add-class never committed the new active-class pointer

**Domain:** Identity · **Severity:** High (silent, user-facing; no data
corruption) · **Commit:** `2e5ebf0a2`

Reported live: "Jordan Lee joined two different classes but he can't switch
classes" — and separately, "he is visible on both teacher's rosters," ruling
out "never actually joined" as the explanation. Confirmed at the data layer:
Jordan (`user_id=4`) had two genuinely claimed seats under one account —
seat 3 in the first class (claimed 2026-09-22) and seat 66 in a second class
(claimed 2026-09-23) — but `User.last_active_class_id` still pointed at the
first class after the second claim, and the server log showed zero hits to
`/student/switch-class/<class_id>` (the dedicated, correctly-working route):
the only route he'd used was `/student/add-class`.

Root cause: `add_class()` set `user.last_active_class_id` /
`last_active_seat_id` directly on the ORM object *after*
`bind_authenticated_student_to_class`'s own `FEAT-IDEN-005` context had
already closed — never inside any FEAT context, no explicit commit. The
write was silently discarded at request teardown, the exact shape of finding
53's passkey-commit bug. The route's own comment ("The IDENTITY FEAT owns
the mutation transaction boundary") was false by the time that line ran.

Fixed by routing through the same `switch_student_session_context()` helper
the dedicated switch-class route already used correctly, under its own
`FEAT-IDEN-005` context. Regression test
(`tests/dom/identity/test_claim_lifecycle.py::test_add_class_route_actually_activates_the_new_class`)
reproduces the defect precisely: without the fix, the dirty, never-committed
`User` row sits unflushed until any later query autoflushes it, at which
point the FEAT enforcement itself raises "Attempted to flush mutated state
outside of a verified FEAT context" — independent proof the write was never
legally guarded, not merely lost. 37 tests across the class-switching
surface re-run green.

### Two more "not yet exercised" corrections

Both caught only because the operator pushed back on a stale claim rather
than accepting it — see `PRODUCTION_READINESS_2026-09.md` §VII for the full
correction and evidence:

- **Hall-pass verification page** — real `hall_pass_logs` rows cross-referenced
  against real GET/POST hits to `/verify/hallpass/<token>` in the server log,
  with the POST response size changing across calls (state transitions, not
  a static reload).
- **Student-assisted teacher account recovery** — confirmed complete, not
  just attempted: `recovery_requests.status='verified'` with a real
  `completed_at`, the class challenge `satisfied_at`, and a
  `student_recovery_codes` row with a genuine `verified_at`. Full request
  chain independently visible in the server log on both the teacher and
  student sides.

The canonical ship tracker (`PRODUCTION_READINESS_2026-09.md`) was updated
in step with all of the above rather than left to drift further out of date.

### Finding 69 — student "Switch Class" dropdown listed only the current class

**Domain:** Identity · **Severity:** High (silent, user-facing) · **Commit:**
`6dc09bbc8`

After finding 68's fix shipped, the operator reported the underlying symptom
was still live: Jordan (two genuinely claimed seats) still couldn't switch
classes, confirmed by two separate screenshots of his dashboard sidebar
showing a "SWITCH CLASS" dropdown with exactly one `<option>` — the class he
was already on. This ruled out finding 68's persistence bug as the (sole)
cause: there was nothing in the list to switch *to*, regardless of whether
`/student/switch-class/<class_id>` itself worked.

Root cause: `inject_student_layout_view()` (`app/__init__.py`) built
`available_classes` from a single line —
`[display_metadata.to_available_class_option()]` — sourced from only the
*current* class's already-resolved display metadata. Structurally incapable
of ever listing more than one class for any student, regardless of how many
seats they'd actually claimed. The teacher-side twin context processor had
already been fixed for the identical defect shape, with a comment
describing it verbatim; the student side was left unfixed until this
finding.

Fixed by sourcing the dropdown from
`_get_identity_bound_seat_options(user_id)` (the same canonical
all-claimed-seats query `select_class_context()` already used) and
resolving display metadata per option, marking the current class via
`to_available_class_option(is_current=True)`. Regression test
(`tests/dom/identity/test_class_context_and_switching.py::test_dashboard_switcher_lists_every_claimed_class`)
reproduces the live report exactly: a 3-class student's dashboard `<select
id="class-switcher-select">` must contain 3 `<option>` elements, not 1.
Confirmed live by the operator after deploy: "jordan class switching
complete."

The same deploy also closed the one HTTP status with no styled error
handler (429 — Flask-Limiter's bare default page was rendering instead of
the branded pages every other status gets). Verified against a real
production 429 on `/metrics`, not just a test: `curl` against the app
directly on the host returned the styled `error_429.html` with the correct
limit description ("500 per 1 day") rather than Werkzeug's default. Not a
launch-readiness finding — recorded here only because it shipped in the
same commit.

### Finding 70 — /admin/recover rate limit shared one bucket across GET and POST

**Domain:** Identity/Recovery · **Severity:** Medium (availability, not a
security gap) · **Commit:** `195162a31`

Reported live via a real browser 429 on `/admin/recover`. Investigated
before changing anything, per explicit instruction: confirmed GET and POST
shared one `"5 per hour"` bucket (no `per_method`), and that Flask-Limiter
consumes from that bucket in its own `before_request` hook, before the view
(and therefore before the in-view Turnstile check) ever runs. GET only
renders the form and resolves no guessable data — the actual sensitive
action, resolving `(join_code, username)` pairs, happens exclusively in the
POST branch. A teacher reloading the page, or a student watching them fill
it out, could exhaust the shared budget through page views alone, before a
single real recovery attempt.

Fixed by scoping the limit to POST only
(`methods=["POST"]`), matching the precedent already in use at
`system_admin.py`'s login route. This is a pure availability fix, not a
security relaxation: GET carries no guessable-data resolution, so removing
its rate limit narrows nothing an attacker could exploit, while POST keeps
its original "5 per hour" threshold undisturbed.

Verified live post-deploy (not just in tests, which run with CSRF
disabled): 8 consecutive GETs all returned 200, then a POST sequence with a
real CSRF token (extracted from a live GET, since production has
`WTF_CSRF_ENABLED=True`) hit `429` exactly on the 5th attempt, rendering
the styled `error_429.html` with `limit_description="5 per 1 hour"`.

### Finding 71 — select_class_context() had the same unguarded-write shape as finding 68

**Domain:** Identity · **Severity:** High (silent, user-facing) · **Commit:**
`195162a31`

Not reported live — found while auditing for other instances of finding
68's defect shape after fixing it. `select_class_context()`
(`app/routes/student.py`) is the fallback gate `app/auth.py:127` redirects
to when no valid canonical context exists at all (a narrower trigger than
`add_class`'s, and distinct from finding 69's dropdown-listing bug). Its
POST branch set `linked_user.last_active_class_id` /
`last_active_seat_id` directly on the ORM object, with no FEAT context and
no explicit commit — silently discarded at request teardown, same shape as
findings 53 and 68. Unlike `add_class`, this route is deliberately not
decorated with `@login_required` (it exists precisely for the case where
`resolve_canonical_context()` would raise), so the fix could not simply
reuse `add_class`'s decorator-adjacent pattern; the mutation is wrapped
inline in its own `FEAT-IDEN-005` context instead, calling the same
`switch_student_session_context()` helper.

Regression test
(`test_select_class_context_route_actually_commits_the_switch`) reproduces
the defect precisely: POSTs a valid class selection, then forces a fresh
`db.session.expire_all()` read to prove the switch actually persisted
rather than passing against an already-mutated in-memory object.
Mutation-proofed: fails with the fix stashed, passes restored. 76 tests
across the affected surfaces (error handlers, accessibility, Turnstile
ingress, class switching, teacher recovery, claim lifecycle) re-run green.

### Finding 72 — PII sweep: student name logged via idempotency key

**Domain:** Identity/Observability · **Severity:** High (real leak,
zero live occurrences so far) · **Commit:** `a484bd6f4`

Part of the pre-launch PII sweep (`SOP-DEP-001` §XI, "not yet exercised"
item). Audited every read of `IdentityProfile.first_name` /
`.last_name` / `.notes` across `app/routes`, `app/feats`,
`app/services`, `app/utils`, and `wsgi.py` for the three things
`.claude/rules/security.md` forbids: PII in URLs, PII in logs, PII in
error/flash messages.

**URLs: clean.** No name field or derived name variable ever reaches a
`url_for`/`redirect`/query string. Independently confirmed against 7
days of production access logs: no name-bearing query params, and two
real students exercised live this week ("Jordan Lee", "Ava Chen") never
appear anywhere in the logs.

**Logs: one real bug, fixed.**
`app/routes/admin.py:4221` (`add_individual_student`) built its
`FEATContext` idempotency key as
`f"...{class_id}:{first_name}:{last_name}:{dedupe_key}"`. That string
is written verbatim to the `FEAT-ENTRY` line on every context entry
(`app/feats/base.py`'s `log_event`, called unconditionally from
`__enter__`), so every manual single-student add logged the student's
plaintext name to the application log — persisted indefinitely,
readable by anyone with server/log access, unlike a flash message
scoped to the acting teacher's own session. Zero hits in 30 days of
production logs (the flow hadn't fired live before this fix), so
latent, not yet exploited. `dedupe_key` already HMAC-encodes
`(class_id, first_name, last_name)`, so dropping the raw-name segment
preserves idempotency semantics exactly. Regression test
(`test_add_individual_student_does_not_log_the_students_name`) asserts
neither name appears in `caplog.text` after the route runs;
mutation-proofed — with the fix stashed, the captured log line reads
`idempotency_key=admin:add-individual-student:...:Confidential:
Surnametoshow:...` verbatim. 19/19 tests in the file re-run green.

**Flash messages: flagged, then reconsidered — not a real finding.**
Four instances in `admin.py` (hall-pass grant, recovery-code reset,
student-edit confirmation, duplicate-add notice) echo a student's name
back in a `flash()` call, matching the letter of the security doc's own
example (`flash(f"...{student.first_name}...")` is its literal "wrong"
case). On examination this doesn't hold up as an actual exposure:
`flash()` is session-scoped, rendered only to the same authenticated
teacher on their next request, never logged, never URL-carried. The
security doc's example is really guarding against a *different* threat
— confirming account existence to an unauthorized/anonymous party
(user enumeration) — which doesn't apply here: the teacher already
selected this exact student and already sees their name on the roster
page in front of them. Left unchanged; a mechanical rule-text match
isn't the same as a real security violation, and treating it as one
here would have been the wrong call.

### Findings 73/74 — the first full-suite run's 4 fails, corrected same day

**Domain:** Attendance/Hall Pass, Templates · **Commits:** the 5-line
CSS/template fix and the hall-pass test fix, committed together.

The full-suite run recorded in `PRODUCTION_READINESS_2026-09.md` §VII
(3597 tests, `a916bbfeb`) surfaced 4 fails beyond the 16 pre-existing
`google.auth` errors. The first pass at explaining them was wrong, and
the operator caught it directly: "How are they preexisting. We checked
every full run and last full run was clean." The check behind the
original claim only asked which commit last touched each file — it
never asked whether that commit came *before or after* the last known-
clean full run (`b4a639311`, 2026-09-21 22:01 UTC, 0 fails/0 errors,
preserved at `docs/ops/audits/evidence/2026-09-21_full_b4a639311/`).
Verified properly with `git merge-base --is-ancestor b4a639311 <sha>`:
every implicated commit landed *after* it, the same evening, well
inside this campaign.

**Finding 73 — R5 design-token regression, real.**
`git log -S'font-size:1em;vertical-align:middle'` confirms `7ee59c1b9`
(09-21, "Show a claim's true status, terminate it once decided, fix
onboarding") added 5 new `style="font-size:1em;vertical-align:middle;"`
spans to `templates/admin_process_claim.html` — a genuinely new
violation, not pre-existing debt as first claimed. No sanctioned class
covered "icon sized to match surrounding body text" (`.icon-xs`
through `.icon-3xl` in `static/css/style.css` are all fixed rem
tokens, meant for standalone icons like headers/buttons, not inline
ones that should scale with the paragraph they sit in). Added
`.icon-inherit { font-size: 1em; }` alongside the existing token
classes and swapped all 5 spans to `class="material-symbols-outlined
me-1 icon-inherit icon-middle"`, dropping the inline style entirely.
Verified the swap is exact, not approximate: injected both the old
inline-style markup and the new class-based markup into a page loading
the real `style.css` in a live browser and diffed `getComputedStyle` —
`fontSize` (`16px`) and `verticalAlign` (`middle`) matched identically
between old and new. 49/49 `test_design_token_contract.py` and 3/3
`test_accessibility.py` (which already covered this page) re-run
green.

**Finding 74 — hall-pass "failures" were a test time bomb, not a
production regression.** The 3 failing tests
(`resolver_reports_left_after_departure`,
`resolver_reports_returned_after_the_full_round_trip`, and a
`StopIteration` in `test_history_reports_returned_and_ignores_an_
unrelated_stray_active_row`) all trace to the same root cause: `dea06c1e6`
(which introduced `test_hall_pass_lifecycle_classification.py`) and
`1e20214ed` hardcoded a literal day-boundary window
(`datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc)` through
`datetime(2026, 9, 22, 7, 0, ...)`) and a literal history-query date
(`"2026-09-21"`). Both were correct exactly on the day they were
written and silently expired the instant real wall-clock time moved
past them — `_leave()`/`_return()` stamp their attendance rows with
genuine current time via the real checkout/checkin routes, regardless
of what date the test's own assertions hardcode. By 2026-09-23 (two
days later), every row landed outside the frozen window, so the
resolver saw zero matching rows and reported `approved` no matter what
had actually happened.

Confirmed this was test-only, not a production defect, by reading the
real callers before touching anything: `app/routes/admin.py`'s
Issued/Out page and `app/routes/api.py`'s checkin route both compute
their day boundary *dynamically*, via
`canonical_temporal_resolver(..., primitive="evaluation_day_boundaries")`
at actual request time — neither has ever hardcoded a literal date.
Fixed the test to do the same: a new `_todays_boundaries()` helper
calls the identical production primitive, and the history query's date
is computed at test-run time instead of hardcoded.

**Mutation-proofed properly, not just re-run to green:** temporarily
rewrote `resolve_hall_pass_lifecycle_status` to unconditionally return
`"approved"`, confirmed 5 of the file's 7 tests fail against that
mutation (the 2 that don't exercise any state transition can't, by
construction, and correctly didn't), restored the resolver from an
untouched backup (`git diff` on it came back empty afterward,
confirming nothing was accidentally left changed), then re-ran the
full file clean — 7/7 pass. This proves the fixed tests are still a
real safety net, not merely patched to stop failing.

Both fixes are unrelated to each other in cause (one is a genuine
front-end regression, the other is a test-authoring defect with zero
production impact) but shipped in the same commit since both were
found investigating the same full-suite run.

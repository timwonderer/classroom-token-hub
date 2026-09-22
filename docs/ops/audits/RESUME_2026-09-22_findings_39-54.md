# Resume point — live-test remediation, continued session of 2026-09-21/22

**SESSION CLOSED.** This is the final state as of end-of-session
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

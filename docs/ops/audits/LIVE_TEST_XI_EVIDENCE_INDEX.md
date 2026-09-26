# §XI Evidence Index — live-test campaign (2026-09-19 → )

**This is a derived lookup surface, not an authority.** Every claim below is a
pointer into one of the four source documents; where this index and a source
disagree, the source wins and this file is what gets corrected.

## Why this exists

`SOP-DEP-001` §XVI makes the deployment complete only when "every §XI path has
recorded evidence." That evidence exists, but it is spread across three
documents that record findings in *prose*, using wording that does not match
the checklist's own. Confirming coverage therefore required archaeology, and
the cost was paid in full at least once: a reviewer searched for the literal
route path `/admin/export-students` and the phrase "audit lineage", found
neither, and reported both §XI lines as unevidenced. Both were fully
documented — as "Selected-class export" and as `correlation_id` /
`audit_events` trigger evidence respectively.

This index exists so the §XIV verifier reviews evidence instead of hunting for
it. It does not replace, merge, or rewrite the source records: the formal
record is append-only and immutable once finalized, and this campaign's
convention is to layer dated amendments rather than rewrite.

## Source documents

| Key | File | What it is |
|---|---|---|
| **LTD** | `LIVE_TEST_DEPLOYMENT_2026-09-19.md` | The formal `SOP-DEP-001` §XV record. Original deploy (`8c5cff7c8`), §XI testing through ~finding 38. |
| **R22** | `RESUME_2026-09-22.md` | Session handoff note (work was on `codex/live-test-launch-readiness` in a separate worktree, invisible from the main clone). |
| **R39** | `RESUME_2026-09-22_findings_39-54.md` | The next session's handoff note, which became the de-facto findings ledger (39→78 plus the 2026-09-23 amendments). |
| **PR** | `docs/TRACKING/PRODUCTION_READINESS_2026-09.md` §VII | Campaign summary; occasionally carries evidence not in the other three. |

Note the naming hazard: the file whose name says "resume point" is the one
holding most of the later evidence.

## The index

Line numbers were verified against the exact line at the time of writing
(2026-09-23). They will drift as the append-only docs grow; the quote is the
durable half of each citation.

| # | §XI checklist line | Evidence | Proof quote | Status |
|---|---|---|---|---|
| 1 | `/admin/login` renders and submits | LTD:235 | "teacher login page rendered through the full chain" | EVIDENCED |
| 2 | `/student/login` renders and submits | LTD:401 | "expiry `18:45:49`, `GET /api/student-status` returned 401 at `18:45:52`" | EVIDENCED |
| 3 | `/docs` renders | LTD:1113 | "`GET /docs` → 308 → `/docs/` → 200 (12,200 bytes). Operator confirmed from a mobile browser at 23:15:57Z" | EVIDENCED |
| 4 | Passwordless enrollment and authentication | PR:1666, R39:126-127 | "`created_at` 04:35:55 and `last_used` 05:39:48 UTC — registered *and* later used to sign in" | EVIDENCED |
| 5 | Turnstile renders on every configured route, real verification succeeds | PR:1746, R39:586; real-verify LTD:237 | "Turnstile sweep complete (`f1a62e0a8`)"; "widget returned \"Success!\"" | EVIDENCED |
| 6 | Teacher creates or accesses a class boundary | LTD:238 | "`users` 1 (teacher), `classes` 1, `seats` 1 (teacher, claimed) … exactly FEAT-CLASS-001 §X" | EVIDENCED |
| 7 | Student seat claim, then a student session | LTD:1261, LTD:401; corroborated R39:302-303 | "**1** assessment for **30** student seats, because only one is claimed" | EVIDENCED |
| 8 | Teacher current-class switching via `POST /admin/current-class` | LTD:1114 | "switched back (`POST /admin/current-class` → 200). Both canonical pointers moved together" | EVIDENCED |
| 9 | Student add-class and switch-class | R39:294, R39:348; summary PR:1690-1708 | "Finding 68 — /student/add-class never committed the new active-class pointer"; "Confirmed complete live by the operator after deploy" | EVIDENCED |
| 10 | Selected-class export via `/admin/export-students` | LTD:1116; controlled comparison LTD:1118-1130 | "Class A active → 1 row. Class B active → header only."; `02:48:19` 200/158 bytes vs `02:49:06`, `02:49:22` 200/111 bytes | EVIDENCED |
| 11 | Hall-pass verification via `/verify/hallpass/<token>` | PR:1656-1660; corroborated R39:334 | "two real `hall_pass_logs` rows exist (Bathroom @ 00:45:37, Water Fountain @ 02:04:41 UTC)" | EVIDENCED |
| 12 | Class-scoped admin actions cannot cross the class boundary | LTD:1148; summary LTD:1168 | "Nothing was written. `payroll_manual_payment` resolves the scope from the session"; "All five isolation items now pass" | EVIDENCED |
| 13 | Attendance, productivity, payroll, obligations, ledger, store paths | PR:1566, LTD:246, LTD:249; rent LTD:1251-1261 | "The economic core is sound. Payroll, store purchase, insufficient-funds refusal, inventory exhaustion, transfers and scheduled settlement all reconcile to the cent" | **PARTIAL** — see Gap 1 |
| 14 | Audit/lineage records produced for protected mutations | LTD:246, LTD:249; triggers LTD:1575-1578 | "one `GRANTED` entitlement event sharing `correlation_id` `corr_9d5785ea…`, written 12 ms apart"; "`audit_events  audit_events_no_update / no_delete`" | EVIDENCED |
| 15 | Export and support/operations surfaces load without 500 | R39:136, R39:147 | "`/sysadmin/dashboard` returned 200 (confirmed via server log)"; "200s and 302s throughout, zero 4xx/5xx besides one unrelated static-asset 404" | EVIDENCED |
| 16 | No PII in URLs, logs, errors, or browser-visible diagnostics | R39:461, R39:464; summary PR:1729 | "**URLs: clean.** No name field or derived name variable ever reaches a `url_for`/`redirect`/query string" | EVIDENCED |
| 17 | Accessibility smoke checks (INV-ARC-020) | R39:636, R39:897 | "**Total: 88/88 real page templates now verified against real WCAG 2 A/AA with zero violations**" | EVIDENCED |

**No §XI line is unevidenced.** The two shortfalls below both sit inside line
13 and are known, recorded, and narrower than their summaries suggest.

## Gap 1 — rent payment (genuinely pending, calendar-blocked)

`PR:1614`: "Rent *payment* remains untested — the class's preview window does
not open until 2026-09-29." Corroborated `R22:158-160`.

Everything else in the rent domain *is* evidenced (`LTD:1251-1261`): genesis,
advance, idempotency, policy binding, reconciliation, and the B1 append-only
invariant re-verified under an adversarial attempt. This is a wait, not a task.

## Gap 2 — insurance waiting-period gate (mis-stated: unreachable, not untested)

`PR:1634` records this as "the waiting-period enforcement gate itself has never
been exercised end-to-end." That is true but reads as a testing gap someone
could close. It cannot be closed, because the gate is unreachable in
production. Verified 2026-09-23 at the code layer:

1. `waiting_period_days` is settable on all three policy types. The code comment
   at `feat_class_003_insurance_policy_management.py:66-73` attributes this to an
   "Operator decision 2026-09-21" holding it "settable on every type (not
   necessarily enforced on every type)". **That attribution is false — the
   operator states they never made that decision** (2026-09-23). See the root
   cause below; a code comment is descriptive and was never authority for it.
2. Enforcement follows that invented rule: only `_enforce_non_monetary_submission`
   (`app/feats/insurance_claim_feat.py:401`) applies the waiting period.
   TRANSACTION and PRODUCTIVITY gate against `coverage_terms.coverage_start_utc`,
   which is the raw grant timestamp (`:221`) with no waiting period applied.
3. NON_MONETARY claims cannot be filed. `app/routes/student.py:1860` is the
   only caller of `submit_insurance_claim` in the application, and it is gated
   behind `claimable = is_transaction_type or is_productivity_type` (`:1822`).
   `templates/student_file_claim.html:87-88` tells the student so: "Claims for
   this policy type aren't available from this form yet."

So the only gate that enforces a waiting period governs the only claim type
with no filing UI. It holds four passing FEAT-level unit tests
(`tests/test_insurance_claim_feat.py::TestNonMonetaryWaitingPeriod`, including
the inside/after/boundary/zero cases) and has no production reachability.
Reclassifying this tracker item is an operator decision and has not been made.

### Root cause of the invented rule — a stale cross-reference

The restriction has no normative basis, and the "operator decision" that
replaced it was invented on the strength of a citation typo:

1. `economic_engine.py:114` and the insurance schema cite "SPEC §4.5.3 /
   §4.5.4 / §4.5.5". Those were the correct insurance sections **when written**.
2. `9bdeccdab` (2026-09-12, "reorganize insurance section and update
   numbering") renumbered insurance §4.5.x → **§4.4.x**. Verified against
   `git show 9bdeccdab^`: the pre-renumber doc has "#### 4.5.3 `TRANSACTION`
   Insurance". The code citations were never updated and now point at §4.5
   *Fines*, which has no §4.5.3.
3. On 2026-09-21 someone resolved those citations, correctly found nothing,
   and concluded "No normative document restricts it to NON_MONETARY" — never
   reaching `SPEC-ECON-003` §4.4.3–§4.4.5, one digit away, which does govern
   insurance coverage parameters.
4. They then invented "settable but not necessarily enforced" and recorded it
   as an operator decision.

**What the governing spec actually says.** `SPEC-ECON-003` §4.4.1 lists waiting
period among the tier-controlled coverage-axis values that "*Depending on
product type … MAY include*", and its axis-separation rule names waiting period
as a coverage parameter economic mode must not change — both stated generally,
for no particular product. Nothing forbids a waiting period on TRANSACTION or
PRODUCTIVITY. What the spec does **not** provide is *preset values* for those
two products: §4.4.3 (TRANSACTION) and §4.4.4 (PRODUCTIVITY) carry no
waiting-period row, while §4.4.5 (NON_MONETARY) does (3/7/3/0 days, range 0–7).
"No preset given" was over-read as "forbidden", then re-invented as "settable
but unenforced". Operator direction 2026-09-23 is that it should be settable on
**all** insurance; the preset values for the two uncovered products are a
genuine gap in the spec, not in the code.

### Adjacent defect found while verifying Gap 2 (reachable, currently latent)

`templates/admin_process_claim.html:170-175` renders, for *any* policy type
carrying a nonzero waiting period:

> Waiting Period: N days — claimable from `<date>`

`coverage_effective_date` is computed with the waiting period applied for every
type (`app/feats/insurance_claim_feat.py:321-323`). On a TRANSACTION or
PRODUCTIVITY policy — the only types whose claims a teacher can actually
review — that line asserts a coverage-start date the enforcement path ignores.
It contradicts `ClaimContractView`'s own docstring invariant: "a review screen
cannot display a number the enforcement path would contradict."

Latent today: both production policies are TRANSACTION with
`waiting_period_days` NULL. It becomes live the first time a teacher uses the
field the 2026-09-21 change enabled. Not yet fixed; awaiting operator
direction on whether the display becomes type-aware or enforcement is extended.

## Caveats for the verifier

- `PR:1758` reads "Still untested: accessibility per INV-ARC-020." That line is
  **stale**, superseded by finding 78 (`R39:636`, `R39:897`). It is retained
  deliberately — this campaign layers dated amendments rather than rewriting —
  so read the amendment that follows it, and cite R39 for line 17, not PR.
- `R39:659-661`: the unified ticket page's "direct Open/Resolved/Closed and
  read-only-with-teacher panel states are still unconfirmed live." A sub-state
  of line 15, whose main path is evidenced.

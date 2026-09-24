> **NON-NORMATIVE HISTORICAL EVIDENCE.** This document records observed V1 behavior. It MUST NOT
> define V2 runtime authority. V2 behavior is governed exclusively by applicable INV/DOM/FEAT
> specifications.

| | |
|---|---|
| Status | Non-normative evidence. Immutable once committed; correct it by dated amendment, not rewrite. |
| Recorded | 2026-09-23 |
| Subject | `origin/main_legacy_v1.10.0` (`db275ee37`) |
| Evidence | `evidence/2026-09-23_v1-insurance-probes_db275ee37/` (30 probes, stored as `.txt`) |

**What this is not.** It is not a specification of what V2 should do, and it is not a claim that V1 behavior
was *correct*. It establishes what users actually had, so that a later V2 contract can say deliberately which
behaviors it preserves and which defects it does not.

**Limits on what it proves.** It shows what the V1 code does when executed against a throwaway database. No
production data was examined, so it is not evidence about how V1 behaved in production. In particular, the
recurring-billing executor is young: `process_insurance_billing_job` and its cadence helper were added in
`6bf864b36` on **2026-04-20**, about eight weeks before the v1.10.0 freeze (2026-06-14). Before that commit V1
had no recurring premium billing at all, and the job's own tests contradict one another (§7.2).

# V1 Insurance Lifecycle — Behavioral Trace

**Subject:** `origin/main_legacy_v1.10.0` (`db275ee37`, 2026-06-14). It is 4 commits past tag `v1.10.0`
(`c5b3e8328`): a dependabot bump, a merge, and a version-number edit — none touch insurance.
**Scope:** runtime code and tests only. V1 is treated as behavioral evidence, not as authority. No V2
architecture is proposed. Documentation was not consulted for any behavioral claim.

## How to read the evidence tags

| Tag | Meaning |
|---|---|
| **[E]** | **Executed.** Behavior observed by running V1 code in an isolated harness (see §9). Probe id given (e.g. `R2`). A prediction was written before each run. |
| **[T]** | A V1 test at this ref covers it. Its status at this ref is given in §7. |
| **[R]** | **Read from code only.** Not executed. Treat as a strong reading, not an observation. |
| **ABSENT** | Searched for and not found. The search performed is stated. |

Line references are to the V1 ref. Places where my first reading was wrong or incomplete are recorded in §8,
because they show which claims needed execution.

---

## 1. Headline findings

Ranked by how much they would surprise someone who assumed insurance "just worked".

1. **V1 has no expiration.** No expiry/end column exists on any insurance model, and nothing writes
   `expired` or `suspended` (both appear only in a model comment). Coverage lasts while `status='active'`.
   **ABSENT.** (§5, T13)
2. **"Renewal" is dead code.** `build_renewed_enrollment` has **zero** production callers — only two tests
   call it. A "renewal" is just the billing job re-charging the *same* enrollment row, which keeps its
   original frozen terms forever. (§5, T14)
3. **Scheduled premium changes never take effect.** Premium rebalances are tagged `insurance_renewal` and
   activate only via the dead renewal path; and even an applied change could not reach existing
   enrollments, because billing uses `frozen_premium`. [R]
4. **Premium charging has no idempotency key.** `insurance_premium` is deliberately absent from
   `IDEMPOTENT_TRANSACTION_TYPES`. Idempotency is an accident of state (`next_payment_due` advancing).
   Claim payouts, by contrast, *do* have a key. **[E** P8d, R10**]**
5. **The billing job charges one period no matter how late, and drifts.** Three missed periods → one charge;
   the next due date is `now + 28d`, not the schedule. Manual payment advances from the *old* due date.
   Same lifecycle, two different clocks. **[E** P6, R7, R7b**]**
6. **Nulls are not frozen.** A term that was `NULL` ("unlimited") at purchase is not frozen at all; the
   `contract_*` properties fall through to the live policy. A later policy edit silently constrains existing
   enrollments. **[E** R1**]**
7. **Several "gates" exist only in the UI.** For `legacy_monetary` claims the waiting period and
   premium-current checks are a disabled submit button; a direct POST files the claim. `max_claims_count`
   is UI-only at filing for **every** type. **[E** R4a, R4b, R4c**]**
8. **Autopay students cannot pay manually.** `pay_insurance` refuses autopay policies. An autopay student
   short of funds has no manual recovery path — only the job's daily retry. **[E** R7**]**
9. **Policy deletion fails once a premium has ever been charged.** `transaction.policy_id` is a plain FK.
   The error is swallowed into a generic message. **[E** R2**]**
10. **Enrollment cancellation is unguarded.** No status check, no refund, no ledger effect; it re-cancels
    cancelled rows and converts `expired` to `cancelled`. **[E** R3**]**
11. **One `NULL` `cancel_date` disables the repurchase cooldown for good.** Two of four cancellation paths
    never set it (mass-remove **executed**, force-delete **read**), and the cooldown reads `ORDER BY cancel_date DESC`, which puts `NULL` first in Postgres.
    **[E** R5a, R5b, R5c**]**
12. **V1's own billing tests cannot all pass in any environment I tried** (four DB timezones and SQLite).
    The same computation is DB-timezone dependent, so the day auto-cancel fires depends on server settings. **[E** §7.2**]**

---

## 2. State model

**`insurance_policies`** (`models.py:1323`) — the policy definition. **Mutable in place.** A `before_update`
listener bumps `version_number` on any edit (`models.py:1453`). Editing does not fork a row. Live fields
that enrollments read *at runtime, not frozen*: `autopay`, `charge_frequency`, `auto_cancel_nonpay_days`,
`bill_preview_days`, `claim_type`, `is_active`, repurchase/bundle rules. [R]

**`student_insurance`** (`models.py:1477`) — one row per enrollment. This is the only lifecycle state holder.
Written statuses: `active`, `cancelled`. Declared but **never written by any code:** `suspended`, `expired`.
Billing state is three columns: `next_payment_due`, `payment_current`, `days_unpaid`. Ten `frozen_*` columns
snapshot terms at purchase (§1.6 for their limits). There is **no** end-of-coverage column.

**`insurance_claims`** (`models.py:1623`) — statuses `pending`, `approved`, `rejected`, `paid`.
`uq_insurance_claims_transaction_id` makes a transaction claimable once. **[T]** (§7)

**`transaction`** — carries the money. Insurance uses types `insurance_premium`, `insurance_reimbursement`,
`overdraft_fee`, and `Withdrawal`/`Deposit` (overdraft-protection transfer pair). It links to insurance only
via `policy_id` (plain FK, no `ON DELETE`) — **not** to the enrollment. `idempotency_key` is unique, but only
`insurance_reimbursement`, `purchase`, and `refund` may use it.

**Ledger mechanics.** Insurance debits/credits are created `PENDING`. Balance = `BalanceCache` (posted) **+
PENDING rows** (`models.py:393-449`), so a pending premium reduces spendable balance immediately.
`PENDING → POSTED` settlement (`banking.py:90`) is **not scheduled**: it runs eagerly when a student's
balances are read (`student.py:427`, a write-on-read), when a claim page is opened (`student.py:2602`), or via
a manual script. `settle_pending_transaction_contexts` has no scheduled caller. [R]

---

## 3. Entrypoint inventory

| Kind | Entrypoint | Location |
|---|---|---|
| Job | `process_insurance_billing_job` — cron **00:05 UTC daily**, `max_instances=1` | `scheduled_tasks.py:290`, `:440-449` |
| Job (sub-step) | `reset_insurance_billing_cycles` — one-time legacy gate, run at the top of every billing run | `scheduled_tasks.py:211` |
| Student | `GET /student/insurance` marketplace | `student.py:2066` |
| Student | `POST /student/insurance/purchase/<policy_id>` | `student.py:2228` |
| Student | `POST /student/insurance/pay/<enrollment_id>` | `student.py:2443` |
| Student | `POST /student/insurance/cancel/<enrollment_id>` | `student.py:2545` |
| Student | `GET,POST /student/insurance/claim/<policy_id>` | `student.py:2565` |
| Student | `GET /student/insurance/policy/<enrollment_id>` (0 write statements, by static count **[R]**) | `student.py:2866` |
| Admin | `POST /admin/insurance/edit/<id>`, `/deactivate/<id>`, `/delete/<id>`, `/mass-remove/<id>` | `admin.py:7143, 7231, 7247, 7318` |
| Admin | `GET,POST /admin/insurance/claim/<claim_id>` | `admin.py:7396` |
| Admin | `POST /admin/void-transaction/<id>` (insurance branch) | `admin.py:7867` |
| Deletion | student / class / teacher / sysadmin cascades | `student_deletion.py:96`, `admin.py:751, 970, 1041`, `system_admin.py:965` |

The billing job and `insurance_billing.py` were both added in `6bf864b36` (2026-04-20); see the limits at the
top of this document.

The scheduler is started per-process (`app/__init__.py:1013`) with **no cross-process guard** — **ABSENT** (no
lock, leader election, or job-store dedupe found). The default `Procfile` passes no `--workers`, so gunicorn's default (one) applies unless `WEB_CONCURRENCY` or
a config file overrides it; production's setting was not inspected. Treat this as unexercised rather than safe.

---

## 4. The lifecycle, transition by transition

Format per transition: **Trigger · Entry · Reads · Writes · Ledger · Temporal · Retry/idempotency · Evidence.**

### T1 — Policy authoring (upstream of everything)
Out of scope for a lifecycle trace, but two facts govern later transitions. Edits mutate the live policy
(only `claim_type`/tier structure are protected, `admin.py:413-425`), and `is_active` can be flipped by the
edit form (`admin.py:610`). Enrollments depend entirely on the snapshot. [R]

### T2 — Purchase, including the initial premium payment
- **Trigger:** student POST. **Entry:** `student.py:2228-2440`.
- **Reads:** class context; policy; existing active enrollment (same policy/class); latest cancelled
  enrollment (`ORDER BY cancel_date DESC`); one-per-tier-group; bundle qualification; checking + savings
  balance; `BankingSettings`.
- **Checks that exist:** teacher ownership; already-enrolled; `no_repurchase_after_cancel`; repurchase
  cooldown; one-policy-per-tier; sufficient funds (with optional savings overdraft protection).
  **[E** R12, R13, R6b**]**
- **Checks that do not exist:** `policy.is_active`, block visibility, and the class `insurance` feature flag.
  Only the marketplace **GET** checks the flag. A direct POST buys an inactive policy with the feature
  disabled. **[E** R6**]** No global before-request gate exists. **ABSENT.**
- **Writes:** one `student_insurance` row: `status='active'`, `purchase_date=now`, `last_payment_date=now`,
  `next_payment_due=now+cadence`, `coverage_start_date=now+waiting_period_days`, `payment_current=True`,
  frozen snapshot; then `frozen_premium` is **overwritten with the bundle-discounted premium**. **[E** R6c**]**
- **Ledger:** one `PENDING` `insurance_premium` debit (`-premium`, checking, `policy_id`). If savings covers a
  shortfall and protection is on: a `Withdrawal`(savings)/`Deposit`(checking) pair sharing
  `transfer_correlation_id`. **[E** R11b**]**
- **Insufficient funds:** no enrollment; if `overdraft_fee_enabled`, an `overdraft_fee` debit is charged on
  the *declined* purchase — **again on every retry**, progressive tiers escalating per calendar month.
  **[E** R11a**]**
- **Temporal:** all UTC instants. Waiting period = `now + N×24h`, an instant, not a calendar boundary.
  `monthly` cadence = **28 days** (`insurance_billing.py:13-22`); `weekly` 7, `biweekly` 14, `semester` 112.
- **Retry/idempotency:** **no key.** The only duplicate guard is a read-then-write "already enrolled" check.
  Sequential double-POST is refused **[E** R6b**]**, but the only migrated index on `student_insurance` is
  **non-unique** (`ix_student_insurance_student_join_code`), so a concurrent double-POST is not prevented by
  the schema. **[R]** (race not executed)
- **Tests:** **none** for the purchase route. Only `test_insurance_snapshots.py` (freeze) touches the state it
  creates. **ABSENT** (grep of `tests/` for `insurance/purchase`: no hits).

### T3 — Subsequent premium: autopay success
- **Trigger:** cron 00:05 UTC. **Entry:** `process_insurance_billing_job` → `_charge_insurance_enrollment`
  (`scheduled_tasks.py:258`).
- **Reads:** enrollments with `status='active' AND next_payment_due IS NOT NULL AND next_payment_due <= now`
  (`:304-316`); `policy.autopay`; `student.get_checking_balance(join_code)`; `contract_premium`
  (= `frozen_premium`, so the purchase-time bundle discount persists). **It does not read `policy.is_active`.**
- **Writes:** `last_payment_date=now`, `next_payment_due=now+cadence`, `payment_current=True`,
  `days_unpaid=0`. Per-enrollment `commit()`.
- **Ledger:** one `PENDING` `insurance_premium` debit, `policy_id` only — **no idempotency key, no enrollment
  reference.** **[E** P8d**]**
- **Temporal:** charge fires only when `next_payment_due <= now`. The new due date is measured **from `now`**,
  so lateness shifts the whole schedule. One period is charged per run **regardless of how many were missed**;
  missed periods are skipped, not billed. **[E** P6**]** A deactivated policy is still billed. **[E** P7**]**
- **Retry/idempotency:** state-shape only. Re-running at the same instant is a no-op **because
  `next_payment_due` moved** **[E** P6**]** — not because the charge is keyed.
- **Tests:** `test_billing_job_charges_autopay_student_and_scopes_by_join_code` **[T]** — but see §7.2.

### T4 — Subsequent premium: manual payment
- **Trigger:** student POST. **Entry:** `pay_insurance`, `student.py:2443`.
- **Checks:** active enrollment, owned, in-class; **policy must NOT be autopay** **[E** R7**]**; payable only
  if `not payment_current` or `days_until_due <= bill_preview_days` (default 5); checking balance ≥ premium
  (no savings/overdraft path, no fee on failure); a **30-second** time-window duplicate guard keyed on
  student+policy (not on the enrollment).
- **Writes:** `last_payment_date=now`; `next_payment_due = old_next_due + cadence` (**from the old due date**);
  `payment_current=True`; `days_unpaid=0`.
- **Ledger:** one `PENDING` `insurance_premium` debit, no key.
- **Temporal:** **advances one period from the old due date**, unlike the job. Paying a policy 70 days late
  leaves `next_payment_due` still in the past — the enrollment is immediately "due" again for the job's next
  run. **[E** R7b**]**
- **Retry:** a time-window heuristic only. An immediate repeat is refused; **a repeat after the window charges
  again** whenever the enrollment is still "payable" (e.g. still past due after a late payment).
  **[E** R7c**]**
- **Tests:** **none.** **ABSENT.**

### T5 — Insufficient funds during billing, overdue, and recovery
- **Entry:** the `else` branch of `process_insurance_billing_job`, `scheduled_tasks.py:341-354`.
- **Trigger conditions:** manual-pay policy (always), or autopay with `balance < premium` or `premium IS NULL`.
- **Writes:** `days_unpaid = max(0, today_utc − due_date)` (**recomputed each run, not incremented**),
  `payment_current=False`; if `auto_cancel_nonpay_days > 0 and days_unpaid >= threshold` → `status='cancelled'`,
  `cancel_date=now`. **[E** P8b**]** A threshold of `0` **never** cancels. **[E** P8c**]**
- **Ledger:** **none.** No NSF/overdraft fee, no penalty, no notification. **ABSENT** (`notif` grep across the
  three billing files: no hits; `overdraft_fee` E-check in P8a: 0 rows).
- **Retry:** the enrollment stays in the due set daily. An autopay enrollment that later becomes funded is
  charged on the next run and returns to `payment_current=True`. **[E** P8a**]** This is the only automated
  retry, and the only recovery path for autopay.
- **Temporal:** `days_unpaid` uses `.date()` on a DB-returned datetime with no `ensure_utc`
  (`scheduled_tasks.py:343`), so it depends on the connection's timezone. §7.2.
- **Consequences while overdue:** claims are blocked (T9/T10); coverage is not otherwise suspended (`suspended`
  is never written).

### T6 — One-time legacy billing reset
`reset_insurance_billing_cycles` (`scheduled_tasks.py:211`) gives enrollments purchased before
`2026-04-19` one fresh cycle at the top of each billing run, then stops qualifying. It is a launch-migration
gate, not part of the steady-state lifecycle. Post-launch enrollments never trigger it. **[T]** `test_enrollment_reset_migration_only_resets_legacy_active_plans`. Noted because my own first probe fixture tripped it (§8).

### T7 — Claim filing
- **Entry:** `file_claim`, `student.py:2565-2863`. Requires an **active** enrollment for `(student, policy,
  class)`. Three claim types with different rules:

| Gate | `transaction_monetary` | `legacy_monetary` | `non_monetary` |
|---|---|---|---|
| Coverage started (waiting period) | **enforced on POST** (eligibility helper) | **UI only** | **UI only** |
| `payment_current` | **enforced on POST** | **UI only** | **UI only** |
| `max_claims_count` | UI only | UI only | UI only |
| Filing window (`claim_time_limit_days`) | enforced | enforced | enforced |
| Period payout cap | enforced (remaining cap ≤ 0 → refuse) | enforced | n/a |
| One claim per transaction | enforced (row lock + unique index) | n/a | n/a |

  Evidence: **[E** R4a, R4b, R4c**]**. "UI only" means the POST branch never reads the `errors` list; the
  template only disables the submit button (`student_file_claim.html:154`). The filing window is checked from
  the *incident*, not the enrollment.
- **Eligibility for `transaction_monetary`** (`insurance_eligibility.py:120-202`): debit, `POSTED`, non-void,
  not a premium/reimbursement/interest, not an internal transfer, premium current, after coverage start,
  within the filing window, same class, not already claimed, not already reimbursed, and delayed-use items must
  have been *used*. A transaction from **inside the waiting period is ineligible forever**.
- **Writes:** one `insurance_claims` row, `status='pending'`. **Ledger:** none.
- **Side effect:** the claim page eagerly settles the student's pending transactions (write-on-read) **[T]**
  `test_transaction_claim_page_settles_pending_purchase_before_render`.
- **Idempotency:** the DB unique index on `transaction_id` for transaction claims **[T]**; nothing for the
  other types (a double POST files two claims).
- **Tests:** the *student filing gates are untested* apart from two Decimal-type regressions
  (`test_decimal_type_errors.py:423, 512`). **ABSENT** for the gate logic.

### T8 — Claim review, eligibility, and payout
- **Entry:** `process_claim`, `admin.py:7396-7697`.
- **Reads (at review time, not filing time):** `enrollment.payment_current` and — for transaction claims —
  `enrollment.status` are **re-read now**. Only the *date* gates use `filed_date`. **[E** R15**]**
- **Validation split:** "hard" errors block *payout*; "time limit" errors block unless a written override
  reason is given (`time_limit_override_reason`). **[T]** `test_claim_filed_late_*`,
  `test_claim_filed_in_time_not_blocked_when_reviewed_late`.
- **Claim-type asymmetry:** a `non_monetary` claim is approvable with every validation error present
  (payment lapsed, still in waiting period). **[E** R14**]**
- **Cancellation after filing:** a pending `transaction_monetary` claim on a cancelled enrollment cannot be
  approved; a pending `legacy_monetary` claim **is** paid. **[E** R9**]**
- **Payout amount:** transaction claims = `|tx.amount| × frozen_coverage_percent`; legacy = teacher-entered
  `approved_amount`; then clamped by per-claim cap (non-transaction only) and remaining period cap.
  **[T]** `test_admin_claim_approval_uses_frozen_coverage_percent`,
  `test_transaction_claim_ignores_per_claim_cap_and_uses_coverage_percent`,
  `test_variable_claim_can_be_approved_after_prior_claim_when_period_cap_remaining`.
- **Ledger:** `create_idempotent_transaction` → one `PENDING` `insurance_reimbursement` credit, key
  `txn:insurance:claim:{claim_id}:reimbursement`, `original_transaction_id`, `policy_id`. **[T]**
  `test_insurance_approval_creates_reimbursement_transaction` and the key assertion in
  `test_admin_claim_approval_uses_frozen_coverage_percent`.
- **Idempotency:** real — a pre-check, the unique key, and a partial unique index
  `uq_insurance_reimbursement_source_policy` on `(original_transaction_id, policy_id)`. Approve → pending →
  approve pays **once**. **[E** R10**]** *Limitation:* V1's duplicate-reimbursement test collides on the key
  *and* the index at once, so it cannot show the index alone works.
- **Both `approved` and `paid` trigger the payout**; going from one to the other does not pay twice. There is
  no separate payment step. **[E** R10**]**
- **Period semantics:** "period" for count/payout caps is the **calendar** month/semester/year
  (`get_claim_period_bounds`), counted by different fields at filing (`filed_date`, incl. pending) and at
  approval (`processed_date`, approved/paid only). [R]

### T9 — Reversal of a claim decision
Moving an approved/paid claim to `rejected` or `pending` **does not reverse the reimbursement**: no clawback,
no void. **[E** R10**]** The payout can only be reversed through the generic void route (T11), which does not
touch the claim.

### T10 — Cancellation
Four writers of `status='cancelled'`. (My first search found only two; see §8.)

| Path | Entry | `cancel_date` | Ledger | Guards |
|---|---|---|---|---|
| Student | `student.py:2545` | set | none | **none** — any status, any repeat **[E** R3**]** |
| Auto (non-payment) | `scheduled_tasks.py:350` | set | none | threshold; `0` disables **[E** P8b, P8c**]** |
| Admin mass-remove | `admin.py:7340, 7350` | **NOT set** | none | active enrollments in scope **[E** R5a**]** |
| Admin force-delete | `admin.py:7291` | **NOT set** | none | precedes a hard delete of the rows |

- **Refund / proration:** **ABSENT** in all four.
- **Effect on open claims:** see T8 (transaction claims blocked, legacy claims still payable).
- **Repurchase rules** read the *latest cancelled row* via `ORDER BY cancel_date DESC`:
  `no_repurchase_after_cancel` blocks permanently **[E** R12**]**; a cooldown blocks by days **[E** R5b**]**.
  Because two paths leave `cancel_date NULL` and Postgres sorts `NULL` first under `DESC`, one such row
  **masks every later dated cancellation**, and the cooldown never applies again. **[E** R5a, R5c**]**
  (This is database-dependent; SQLite sorts `NULL` last.)
- **Tests:** only the auto-cancel case (§7.2). **No test** for student cancel, mass-remove, or repurchase
  rules. **ABSENT.**

### T11 — Voiding a premium or reimbursement
- **Entry:** `admin.py:7867-7899`. Matches an enrollment by `student + teacher + policy title parsed from the
  description + class`, then picks the one whose `purchase_date` is closest to the transaction time. There is
  no enrollment FK.
- **Writes:** `payment_current=False`, `days_unpaid=max(1, …)` on the matched enrollment; the transaction is
  voided and a reversal is created if it was already posted. It does **not** touch `next_payment_due`,
  `status`, or any claim.
- **Defect exposed:** a bundle-discounted premium has a description suffix, so the title parse fails and the
  enrollment is **not** flagged. **[E** R8**]**
- **Tests:** `test_void_insurance_premium_marks_enrollment_unpaid` — the plain case only. **[T]**
- **Voiding a reimbursement** goes through the generic reversal branch and leaves the claim `approved`/`paid`.
  Because the reimbursement key and the source/policy index are not conditional on `is_void`, a voided
  reimbursement likely prevents re-payment. [R] (not executed)

### T12 — Policy edit and deactivation (effect on existing enrollments)
- **Edit:** mutates the live policy; snapshot fields protect only non-`NULL` terms. **[E** R1**]** Live-read
  fields (`autopay`, `charge_frequency`, `auto_cancel_nonpay_days`, `bill_preview_days`, `claim_type`) change
  behavior of *existing* enrollments immediately. [R]
- **Deactivate:** hides the policy from the marketplace only. Existing enrollments keep billing **[E** P7**]**
  and keep covering claims; the purchase POST still works **[E** R6**]**.
- **Tests:** `test_insurance_policy_version_increments_on_edit` and
  `test_student_insurance_keeps_frozen_snapshot_after_policy_edit` **[T]** — the latter mutates
  `max_claims_count` but never asserts it, which is exactly the leaking field. `test_economy_policy_mode.py`
  adds edit-route tests (contract-shape rejection, preset-locked fields, premium display) that cover
  *authoring constraints*. **No test asserts what an edit does to an existing enrollment.**

### T13 — Expiration
**ABSENT.** Searches: (a) `coverage_end|expires_at|expiry|end_date` across `models.py` in the three insurance
models — none; (b) every writer of enrollment status — only `cancelled` is ever written; (c) `expired` and
`suspended` appear only in a model comment (`models.py`, `StudentInsurance.status`). No job, route, or
property ends coverage other than cancellation.

### T14 — Renewal and non-renewal
- **Renewal:** **ABSENT as a distinct transition.** `build_renewed_enrollment` (`models.py:1529`) has zero
  production callers **[R]** (searched whole ref, not just `app/`); only `test_insurance_snapshots.py:345, 410`
  call it. Those tests validate behavior that never runs in production. Renewal in practice = T3 on the same
  row.
- **Consequence 1:** frozen terms never refresh, so a policy edit reaches an existing student only by
  cancel-and-repurchase. [R]
- **Consequence 2:** scheduled premium rebalances (`activation_event='insurance_renewal'`,
  `economy_rebalance.py:57`) apply only when `activate_due_rebalances(..., renewal_policy_id=…)` is called,
  and the only caller passing it is the dead builder. **They never activate.** [R]
- **Non-renewal:** ABSENT as a transition. Stopping recurrence == cancellation (T10). There is no
  "cancel at period end".

### T15 — Deletion

| Scope | Entry | Insurance handling | Tested |
|---|---|---|---|
| Single policy | `admin.py:7247` | force-delete cancels, then deletes claims, enrollments, policy. **Fails at the FK if any premium `Transaction` references the policy**; the failure is swallowed into "internal error". **[E** R2**]** | none |
| Student | `student_deletion.py:96-118` | deletes claims (by student, enrollment, or transaction) then enrollments [R] | no insurance data in tests |
| Class (join code) | `admin.py:751-804` | deletes claims + enrollments by `join_code`; policies are teacher-owned and survive [R] | no insurance data |
| Teacher account | `admin.py:970, 1041-1072` | deletes transactions first (`:725`, `:955`), *then* claims, enrollments, blocks, policies — so the FK problem is avoided here [R] | no insurance data |
| Sysadmin | `system_admin.py:965-983` | deletes enrollments/claims for exclusive students and by policy [R] | not located |

Existing deletion tests (`test_multi_teacher_hardening.py`, `test_teacher_block_cleanup.py`) reference **no**
insurance model.

---

## 5. Explicitly absent behaviors

Each was searched for; the search is stated.

| Behavior | Search | Result |
|---|---|---|
| Coverage expiry / end date | model columns; status writers; `expir*` | **ABSENT** |
| `expired`, `suspended` states | every write of enrollment status (incl. dict-form bulk `.update`) | **ABSENT** (comment only) |
| Renewal transition in production | callers of `build_renewed_enrollment`, whole ref | **ABSENT** (tests only) |
| Refund / proration on cancel | all four cancel paths | **ABSENT** |
| Cancel-at-period-end | all cancel paths | **ABSENT** |
| Penalty / late fee on missed premium | billing job, manual pay | **ABSENT** |
| NSF/overdraft fee on failed *autopay* or *manual pay* | job (**[E** P8a: 0 fee rows**]**), `pay_insurance` (read) | **ABSENT** (only the *purchase* charges one) |
| Notification of overdue / auto-cancel / claim decision | `notif` in billing + eligibility; student routes | **ABSENT** |
| Idempotency key for premium charges | `IDEMPOTENT_TRANSACTION_TYPES` | **ABSENT** |
| Enrollment ↔ premium-transaction link | `Transaction` columns | **ABSENT** (`policy_id` only) |
| Unique constraint on enrollments | model constraints + migrations | **ABSENT** (one non-unique index) |
| Multi-period catch-up billing | **[E** P6**]** | **ABSENT** |
| Reversal of a paid claim | **[E** R10**]** | **ABSENT** |
| Cross-process scheduler guard | `init_scheduled_tasks`, `Procfile` | **ABSENT** |
| Class feature-flag check on POST routes | 4 student POST routes + global hooks | **ABSENT** (GET only) |
| Scheduled ledger settlement | callers of `settle_pending_transaction_contexts` | **ABSENT** (script + on-read only) |
| Tests for purchase / manual pay / student cancel / policy delete / deactivate / mass-remove / repurchase / bundle / feature gating | grep of `tests/` for each route and field | **ABSENT** |

---

## 6. Temporal semantics, gathered

| Concern | V1 behavior |
|---|---|
| Time base | UTC instants everywhere; no class-timezone concept in insurance |
| Job time | 00:05 UTC daily |
| Cadence | weekly 7d, biweekly 14d, monthly **28d**, semester 112d; `build_renewed_enrollment` (dead) uses 30d |
| Next-due (job) | `now + cadence` — **drifts** |
| Next-due (manual) | `old_due + cadence` — anchored |
| Waiting period | `purchase + N×24h` (instant) |
| Overdue days | `today_utc_date − due_date` — **DB-timezone dependent** (§7.2) |
| Claim filing window | `(filed − incident).days` (floor of 24h units) |
| Claim "period" | UTC calendar windows from `get_claim_period_bounds` (`time.py:113`): month, year, **semester = fixed Jan–Jun / Jul–Dec halves**, weekly = Monday-start, biweekly anchored to 1970-01-05 |
| Billing vs claim period | independent: a `semester` policy bills every 112 days but its claim window is the calendar half-year |

---

## 7. Test evidence

### 7.1 Coverage map (V1's own tests)

| Transition | V1 test(s) | Notes |
|---|---|---|
| Purchase (T2) | none | ABSENT |
| Autopay charge (T3) | `test_billing_job_charges_autopay_student_and_scopes_by_join_code` | see 7.2 |
| Manual pay (T4) | none | ABSENT |
| Overdue / auto-cancel (T5) | `test_billing_job_manual_pay_policy_skipped_and_marked_overdue`, `test_billing_job_cancels_after_threshold` | see 7.2 |
| Legacy reset (T6) | `test_enrollment_reset_migration_only_resets_legacy_active_plans` | |
| Claim filing (T7) | only `test_decimal_type_errors.py` (2 regressions) | gates ABSENT |
| Claim review/payout (T8) | 3 in `test_insurance_snapshots.py`, 1 in `test_core_invariants_smoke.py`, 8 in `test_insurance_security.py` | strongest coverage in V1 |
| Reversal (T9) | none | ABSENT |
| Cancellation (T10) | auto-cancel only | ABSENT for the other three |
| Void (T11) | `test_void_insurance_premium_marks_enrollment_unpaid` | plain description only |
| Edit / freeze (T12) | 2 in `test_insurance_snapshots.py`; 3 edit-route tests in `test_economy_policy_mode.py` | authoring constraints only; misses the NULL leak |
| Renewal (T14) | 2 in `test_insurance_snapshots.py` | test **dead code** |
| Deletion (T15) | none with insurance data | ABSENT |
| Scoping | `test_insurance_class_scoping.py` (5) | join-code/block filtering (by test name; not read in detail) |

### 7.2 A contradiction inside V1's own billing tests

`test_insurance_recurring_billing.py` cannot fully pass in any environment I tried. The job recomputes
`days_unpaid = today_utc − due_date` (`scheduled_tasks.py:343`) from a datetime the database returns in the
**connection's session timezone**, without `ensure_utc`. Results of the same four tests, DB session tz flipped
via `ALTER DATABASE … SET timezone`:

| DB session tz | reset | charges_autopay | manual_pay_skipped | cancels_after_threshold |
|---|---|---|---|---|
| UTC | pass | pass | pass | **FAIL** |
| Asia/Tokyo (ahead) | pass | pass | pass | **FAIL** |
| America/Los_Angeles (behind) | pass | **FAIL** | **FAIL** | pass |
| America/New_York (behind) | pass | **FAIL** | **FAIL** | pass |
| SQLite in-memory (naive) | pass | pass | pass | **FAIL** |

Zones at or ahead of UTC (and naive SQLite) fail `cancels_after_threshold` (it expects `days_unpaid == 2`;
the job yields `1`). Zones behind UTC fail the other two (they yield `2`, tests expect `1`). The recompute line
and this test entered in the **same commit** (`6bf864b36`, 2026-04-20), so it is not a stale test from an older
incrementing implementation. Practical effect on the *product*, independent of tests: the day on which
`auto_cancel_nonpay_days` triggers depends on the database's session timezone. Whether production's is UTC
was not checked. **[E]**

### 7.3 Baseline of the other insurance-relevant V1 tests

Run on Postgres (UTC, throwaway DB) and on V1's SQLite fallback. Identical results under V1's exact pinned
`SQLAlchemy 2.0.50` / `pytest 9.0.3`, so the differences below are not dependency drift for those libraries.

| Test file | Postgres, per file | SQLite |
|---|---|---|
| `test_insurance_modularization.py` (2) | 2 pass | 2 pass |
| `test_insurance_class_scoping.py` (5) | 5 pass | 5 pass |
| `test_insurance_snapshots.py` (7) | 7 pass, 3 teardown errors | 7 pass |
| `test_insurance_security.py` (9) | 7 pass, teardown error, then **hangs**; the last 2 pass **in isolation** | 9 pass |
| `test_void_…_marks_enrollment_unpaid` | pass + teardown error | pass |
| `test_core_…_creates_reimbursement_transaction` | pass + teardown error | pass |
| `test_insurance_recurring_billing.py` (4) | 3 pass, 1 fail (7.2) | 3 pass, 1 fail |

The Postgres teardown errors (`errors while tearing down … savepoint does not exist`) occur in tests whose
route commits during approval. In `test_insurance_security.py` the failed teardown leaves a transaction open;
the next test inserts the same fixture username (`teacher-insurance`) and blocks on it, so the file
self-deadlocks. Every test in it passes when run alone. Treat these as **V1 fixture behavior on Postgres**, and
note that V1's test evidence is therefore strongest on its SQLite path — which does not enforce foreign keys
(so it could never have caught the policy-delete failure, finding 9).

### 7.4 Probes added for this trace

30 probes (6 billing, 24 route-level), all passing on a clean database at end state. Each states its prediction
in its docstring; paired controls isolate causes where the claim is an absence (R4a/R4b, R5a/R5b/R5c, R2,
R8). Where a prediction was wrong or incomplete it is recorded in §8.

---

## 8. Corrections to my own reading

Recorded because each marks a claim that was only trustworthy after execution.

1. **Cancellation writers.** My first grep for `.status = 'cancelled'` found two. The dict-form
   `.update({'status': 'cancelled'})` in mass-remove and force-delete added two more. Those two are exactly the
   ones that omit `cancel_date`, which is what produced finding 11.
2. **`view_policy` writes.** A helper of mine printed "(empty)" unconditionally and briefly mis-reported a
   `commit()` as absent. The `commit()` belongs to `shop()`; `view_policy` has zero writes, re-verified by a
   bounded count.
3. **Probe R5.** The first control failed. That was not noise — it revealed the `NULL`-first masking, which I
   then predicted and confirmed as R5c.
4. **Probe fixtures.** My first billing probes all failed identically because my fixture dated enrollments
   before the launch cutoff, tripping the T6 gate. Uniform failure was the tell.
5. **Teardown errors.** I first attributed them to my nesting an explicit `app.app_context()` inside V1's
   `client` fixture, and removed the nesting. The errors persisted, and **V1's own tests produce the same
   errors** (§7.3), also under V1's pinned dependencies. So they are V1's Postgres fixture behavior, not my
   harness. They occur after assertions pass.
6. **Edit-route tests.** I first credited policy edit with two tests. `test_economy_policy_mode.py` adds three
   more, covering authoring constraints; the conclusion (nothing tests an edit's effect on existing
   enrollments) stands.
7. **A hung background run** (the first multi-file baseline) was self-deadlocked by the teardown cascade in
   §7.3, verified in `pg_stat_activity` before I stopped it. Its "completed" notification was my own kill, not
   a result; I discarded it and re-ran per file.

---

## 9. Reproduction

Harness: an export of the V1 ref (`git archive`, no `.env`), run with the current venv against a **throwaway
Postgres database** whose name ends in `_test` (V1's own guard), `TEST_DATABASE_URL` set explicitly, DB
session timezone `UTC`. No shared database was reachable.

The probes are committed beside this document as
`evidence/2026-09-23_v1-insurance-probes_db275ee37/test_v1_probes_billing.py.txt` (6) and
`…/test_v1_probes_routes.py.txt` (24), each stating its prediction in its docstring. They are stored with a
`.txt` suffix so they cannot be collected by this repository's `pytest` — they import V1 modules and only run
against a V1 export. To reproduce:

1. `git archive origin/main_legacy_v1.10.0 | tar -x -C <dir>` (no `.env` in the export).
2. Copy the two files into `<dir>/tests/`, dropping the `.txt` suffix.
3. Create an empty database named `*_test` and set its timezone: `ALTER DATABASE … SET timezone TO 'UTC'`.
4. From `<dir>`: `TEST_DATABASE_URL=postgresql://…/<that db> python -m pytest tests/test_v1_probes_*.py -rA`.
   V1's fixtures `drop_all()` at session start, so never point this at a database you care about, and never
   run two sessions against the same database.

To test the pinned-dependency claim in §7.3: `pip install --no-deps --target <p> SQLAlchemy==2.0.50
pytest==9.0.3` and prepend `<p>` via `PYTHONPATH`.

Not executed and therefore **[R]** only: the concurrent double-purchase race, voiding a reimbursement,
force-delete's `cancel_date` omission, and every deletion cascade other than single-policy delete. Harness
limits: I used the current venv (dependency versions differ slightly from V1's pins; the two that matter most
were re-run under V1's exact pins), a local Postgres rather than V1's production environment, and I did not
inspect production's DB timezone or worker count.

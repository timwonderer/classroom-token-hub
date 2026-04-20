# Insurance Recurring Billing — Implementation Plan

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-INS-002 | 1.0 | 2026-04-19 | N/A | Normative |

**Feature:** Insurance Recurring Billing & Student Bill Display
**Date:** 2026-04-19
**Status:** Approved for implementation
**Branch:** `insurance-logic`

---

## 1. Audit Findings (Current State)

### 1.1 What Works

- Students pay a **one-time premium at purchase**. A `Transaction` of type `insurance_premium` is created and debited from checking.
- `next_payment_due`, `last_payment_date`, `payment_current`, `days_unpaid` fields all exist on `StudentInsurance`.
- `autopay`, `charge_frequency`, and `auto_cancel_nonpay_days` fields all exist on `InsurancePolicy`.
- Claim eligibility correctly blocks claims when `payment_current = False`.
- Admin voiding an `insurance_premium` transaction correctly sets `payment_current = False` and increments `days_unpaid`.

### 1.2 What Does Not Work

| Feature | Status | Evidence |
|---------|--------|---------|
| Recurring premium charges | ❌ Not implemented | No scheduled job creates subsequent `insurance_premium` transactions |
| `autopay` enforcement | ❌ Not implemented | Field is stored but never read by any enforcement code |
| `auto_cancel_nonpay_days` enforcement | ❌ Not implemented | Field is stored but no job checks it |
| `days_unpaid` auto-increment | ❌ Not implemented | Only updated on manual admin void |
| `payment_current` auto-update | ❌ Not implemented | Only updated on manual admin void |
| Multi-policy (bundle) discounts | ❌ Not implemented | Fields exist but not applied at purchase |
| Student bill due date display | ❌ Not implemented | `next_payment_due` is never surfaced to students |
| Teacher bill-preview-window setting | ❌ Not implemented | No such field exists |

### 1.3 Net Effect

Every student who has ever purchased an insurance policy is currently receiving **free coverage indefinitely** after the initial premium. Policies are never charged again, never marked past due, and never auto-cancelled. The `autopay` toggle and `charge_frequency` settings have no mechanical effect.

### 1.4 Existing Data Exposure

As of 2026-04-19, the only live operator is the developer (single-user environment). No real student data is at risk from the migration strategy below.

---

## 2. Multi-Policy (Bundle) Discount — Separate Finding

Bundle discount fields (`bundle_with_policy_ids`, `bundle_discount_percent`, `bundle_discount_amount`) exist on `InsurancePolicy` and are settable via the teacher UI. The discount is **never applied** at purchase time. This is a separate fix from billing enforcement and is tracked as a distinct item in Section 6.

---

## 3. Existing Policy Handling Strategy

Because recurring billing was never enforced, all active enrollments have a `next_payment_due` that is already in the past. Enabling enforcement naively would immediately cancel every active policy.

**Decision: Reset all active enrollments to a fresh billing cycle before enabling enforcement.**

### 3.1 Migration Steps (run once, before deploying billing job)

1. For every `StudentInsurance` with `status = 'active'`:
   - Set `next_payment_due = now + 1 billing period` (using the policy's `charge_frequency`)
   - Set `last_payment_date = now`
   - Set `payment_current = True`
   - Set `days_unpaid = 0`
2. Log the count of enrollments reset for audit trail.

This gives every student one free billing cycle grace and then enforcement begins normally.

### 3.2 Rationale

- No retroactive charges — students are not billed for past periods they were never asked to pay.
- No retroactive cancellations — policies continue uninterrupted.
- Enforcement starts cleanly from a known state.
- Consistent with how a real insurer would handle a billing system launch (prospective-only).

---

## 4. Build Plan

### Phase 1 — Recurring Billing Scheduled Job

**File:** `app/scheduled_tasks.py`

Add a nightly job `process_insurance_billing_job()` that runs after midnight. Logic:

```
for each StudentInsurance where status = 'active' and next_payment_due <= now:

    if autopay is True:
        attempt to debit frozen_premium from student checking (join_code-scoped):
            if sufficient funds:
                create Transaction(type='insurance_premium', amount=-frozen_premium)
                set last_payment_date = now
                set next_payment_due = now + 1 billing period
                set payment_current = True
                set days_unpaid = 0
            else:
                increment days_unpaid by 1
                set payment_current = False
                if days_unpaid >= auto_cancel_nonpay_days:
                    set status = 'cancelled'
                    set cancel_date = now

    if autopay is False:
        increment days_unpaid by 1
        set payment_current = False
        if days_unpaid >= auto_cancel_nonpay_days:
            set status = 'cancelled'
            set cancel_date = now
```

**Scoping rules:**
- Use `frozen_premium` (not live `policy.premium`) — student is billed at the rate locked at purchase.
- All transactions scoped by `join_code`.
- Balance check uses `student.get_checking_balance(join_code, teacher_id)`.
- Cancelled enrollments are not re-processed.

**One-time migration:**
- Before the first run of the job, execute the enrollment reset described in Section 3.1.
- Can be implemented as a separate `reset_insurance_billing_cycles()` function called once on first deploy.

---

### Phase 2 — Teacher Setting: Bill Preview Window

**Purpose:** When autopay is off, control how many days before the due date a student can see and manually pay their bill.

#### 2a. Model change (`app/models.py`)

Add to `InsurancePolicy`:
```python
bill_preview_days = db.Column(db.Integer, nullable=False, default=5)
```

Constraint: minimum value of 5 enforced at form validation level.

#### 2b. Migration

```
flask db migrate -m "Add bill_preview_days to InsurancePolicy"
```

Follow full migration workflow per `.claude/rules/database-migrations.md`.

#### 2c. Form (`app/forms.py`)

Add to `InsurancePolicyForm`:
```python
bill_preview_days = IntegerField(
    'Display insurance bill _ days before due',
    validators=[NumberRange(min=5)],
    default=5
)
```

#### 2d. Teacher UI (`templates/admin_insurance.html` or edit template)

- Add `bill_preview_days` field adjacent to the existing `autopay` toggle.
- Show/hide with JS: only visible when `autopay` is unchecked.
- Label: "Display insurance bill [ ] days before due (minimum 5)"

---

### Phase 3 — Student Persistent Bill Display

**Location:** `templates/student_insurance_marketplace.html`, "My Policies" tab

For each enrolled policy, add a status banner containing:

| Condition | Display |
|-----------|---------|
| `payment_current = True` and `autopay = True` | ✅ Paid — Next autopay: [date] for $[amount] |
| `payment_current = True` and `autopay = False` and `days_until_due > bill_preview_days` | ✅ Paid — Next bill due: [date] for $[amount] |
| `payment_current = True` and `autopay = False` and `days_until_due <= bill_preview_days` | ✅ Paid — **Bill due [date] for $[amount] — Pay now** |
| `payment_current = False` | 🔴 Past Due — $[amount] overdue |

The "Pay now" action posts to a new route that manually charges the premium (same debit logic as autopay path).

**New student route:**
```
POST /student/insurance/pay/<enrollment_id>
```
- Validates `autopay = False` and `payment_current = False` (or due within preview window)
- Debits `frozen_premium` from checking
- Updates `last_payment_date`, advances `next_payment_due`, resets `days_unpaid = 0`, sets `payment_current = True`

---

### Phase 4 — Multi-Policy Bundle Discount Fix

**File:** `app/routes/student.py`, `purchase_insurance()` (line ~2295)

After resolving the policy and before checking balance:

```python
# Check if student holds any policies in bundle_with_policy_ids
discount_amount = Decimal('0')
if policy.bundle_with_policy_ids:
    bundle_ids = [int(x) for x in policy.bundle_with_policy_ids.split(',') if x.strip()]
    active_bundle_policies = StudentInsurance.query.filter(
        StudentInsurance.student_id == student.id,
        StudentInsurance.join_code == join_code,
        StudentInsurance.policy_id.in_(bundle_ids),
        StudentInsurance.status == 'active'
    ).count()
    if active_bundle_policies > 0:
        if policy.bundle_discount_percent:
            discount_amount = policy.premium * (Decimal(str(policy.bundle_discount_percent)) / 100)
        elif policy.bundle_discount_amount:
            discount_amount = Decimal(str(policy.bundle_discount_amount))

effective_premium = max(Decimal('0'), policy.premium - discount_amount)
```

Apply `effective_premium` to the balance check and transaction amount. Store `effective_premium` in `frozen_premium` so recurring billing charges the discounted rate.

---

## 5. Implementation Order

| Step | Task | Depends On |
|------|------|------------|
| 1 | One-time enrollment reset migration | Nothing |
| 2 | Phase 1: Billing scheduled job | Step 1 |
| 3 | Phase 2a–d: `bill_preview_days` model + form + UI | Nothing |
| 4 | Phase 3: Student bill display (read-only) | Step 2 |
| 5 | Phase 3: Manual pay route | Step 2, Step 3 |
| 6 | Phase 4: Bundle discount fix | Nothing |

Steps 3 and 6 can be worked in parallel with Steps 1–2.

---

## 6. Out of Scope for This Branch

- UI for teachers to view per-student payment history (already available via student policy detail page)
- Email/notification on failed autopay (no email system exists)
- Partial payment handling
- Grace period configuration (currently hard-coded to `auto_cancel_nonpay_days`)

---

## 7. Testing Requirements

Per `.claude/rules/testing.md`:

- `test_billing_job_charges_autopay_student` — autopay student with sufficient funds is charged and `next_payment_due` advances
- `test_billing_job_insufficient_funds_increments_days_unpaid` — autopay student with no funds gets `payment_current = False`
- `test_billing_job_cancels_after_threshold` — student reaching `auto_cancel_nonpay_days` is cancelled
- `test_billing_job_manual_pay_policy_skipped` — manual-pay policy not charged by job
- `test_billing_job_scoped_by_join_code` — charges only affect correct class period
- `test_enrollment_reset_migration` — all active enrollments get fresh `next_payment_due`
- `test_bundle_discount_applied_at_purchase` — discount reduces effective premium when bundle policy held
- `test_bundle_discount_not_applied_without_bundle_policy` — no discount when no qualifying policy held
- `test_student_bill_display_shows_within_preview_window` — banner appears when within `bill_preview_days`
- `test_manual_pay_route_advances_next_payment_due` — manual payment updates all fields correctly

---

**Last Updated:** 2026-04-19
**Author:** Timothy Chang
**Status:** Ready for implementation

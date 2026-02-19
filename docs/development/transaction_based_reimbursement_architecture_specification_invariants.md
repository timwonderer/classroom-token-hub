# Transaction-Based Reimbursement Architecture — Specification & Invariants

This document defines the **architecture** for transaction-based insurance reimbursement (claim type: `transaction_monetary` or of similar type).

It focuses on **specification**, **invariants**, and **system boundaries** so the implementation remains correct under manual review, retries, and future feature growth.

---
## 1. Definitions

### 1.1 Core Objects

- **Debit Transaction**: A ledger entry representing a student expense (amount < 0).
- **Reimbursement Transaction**: A ledger entry representing insurance payout (amount > 0).
- **Transaction-Based Claim**: An insurance claim linked to exactly one debit transaction.

### 1.2 Claim Types (Context)

This architecture applies only to:
- `claim_type = 'transaction_monetary'`

It does not define behavior for:
- `non_monetary`
- `legacy_monetary`

---
## 2. Architectural Goals

1. **Ledger Integrity**: All money movement is represented as transactions.
2. **Determinism**: For a given transaction + policy state, eligibility and payout amount are deterministic.
3. **Idempotency**: Safe under retries; never double-pays.
4. **Teacher Agency**: Teachers control eligibility and automation mode.
5. **Explainability**: Every decision is traceable to rules (system + teacher + policy).

---
## 3. System Components

### 3.1 Ledger (Transactions)
The ledger is the sole authority on spending and payouts.

Responsibilities:

- Record all debits (store, fines, fees).
- Record all reimbursements as credits.
- Provide stable identifiers (`transaction_id`).

### 3.2 Policy & Enrollment

- `InsurancePolicy`: defines claim limits and claim type.
- `StudentInsurance`: defines whether a student is covered (active, paid, waiting period).

### 3.3 Eligibility Rules Layer

Eligibility is determined by a **layered ruleset**:

1. **System Hard Deny** (non-overrideable)
2. **Correctness Rules** (e.g., delay-use must be used)
3. **Teacher Eligibility Config** (what students can claim)
4. **Policy Limits** (waiting period, time window, caps)

This layer must be callable from:

- Student claim UI (to hide transactions)
- Manual review workflow (to validate claims)

### 3.4 Claim Service

Responsibilities:

- Create claims (manual or automated).
- Enforce 1:1 transaction→claim.
- Store decision state (pending/approved/paid/rejected).


## 4. Data Contracts

### 4.1 Transaction Classification Contract

Every debit transaction that could be eligible must expose or deterministically derive:

- `category` (required)
- `store_item_id` (nullable)
- `is_void`
- `is_internal_transfer`
- `is_delay_use_item`
- `use_timestamp` / `expire_timestamp` (for delay-use)

Unclassified transactions are **ineligible**.

### 4.2 Claim Link Contract

For `transaction_monetary` claims:

- `InsuranceClaim.transaction_id` is required.
- The claim references exactly one debit transaction.
- The claim does not store independent “incident amount”; it is derived from the linked transaction.

### 4.3 Reimbursement Link Contract

Every reimbursement transaction must reference the source debit transaction:

- `Transaction.original_transaction_id = <debit_transaction_id>`
- `Transaction.type = 'insurance_reimbursement'`

This enables idempotency and audit.

---
## 5. Non-Negotiable Invariants

### INV-1: Ledger-Only Money Movement
No balances may be changed directly.
All payouts are recorded via a reimbursement transaction.

### INV-2: One Claim Per Transaction
A debit transaction can be claimed at most once.

- Enforce in DB (preferred): unique constraint on `insurance_claims.transaction_id` where not null.
- Also enforce in code (required): check before insert.

### INV-3: One Reimbursement Per Debit Transaction Per Policy
A debit transaction can generate at most one reimbursement transaction for a given claim.

- Enforce with `original_transaction_id` and uniqueness on (`type='insurance_reimbursement'`, `original_transaction_id`, `policy_id` if stored).

### INV-4: Pay-First, Reimburse-Later
A claim must reference an existing debit transaction.
No reimbursement may occur without an underlying paid expense.

### INV-5: System Hard Deny Cannot Be Overridden
The following are never eligible:

- rent (including bundled rent late fees)
- insurance premiums
- transfers / internal account movements
- insurance reimbursements

### INV-6: Delay-Use Correctness
Delay-use items are eligible only if:

- used (use_timestamp present and in the past)
- not expired at time of use

Expired ≠ used.

### INV-7: Deterministic Payout Calculation
For a claim, approved amount must be:

`min(raw_cost, per_claim_cap, remaining_period_cap)`

Where:

- `raw_cost = abs(debit_transaction.amount)`
- `per_claim_cap = policy.max_claim_amount`
- `remaining_period_cap = policy_period_cap - sum(approved in period)`

### INV-8: Caps Apply in This Order

1. Reject if claim count cap is exceeded.
2. Reject if period payout cap is exhausted.
3. Clamp by per-claim cap.
4. Clamp by remaining period cap.

### INV-9: Same Eligibility Rules Everywhere
The same eligibility logic must govern:

- what students can select
- what admins can approve
- what automation can process

No duplicated eligibility logic in templates/controllers.

---
## 6. End-to-End Flows

### 6.1 Manual (Teacher Approval)

1. Student pays for an item/fine → debit transaction created.
2. Claim UI shows only eligible transactions.
3. Student selects one transaction → submits claim.
4. Claim service validates eligibility + 1:1 invariant.
5. Admin approves:
   - compute payout
   - create reimbursement transaction
   - mark claim paid


---
## 7. Eligibility Model (Layered)

Eligibility is the conjunction of:

### 7.1 System Safety
- not hard-denied category
- not internal transfer
- not reimbursement

### 7.2 Correctness
- delay-use rules pass

### 7.3 Teacher Configuration
- category allowed
- item allowed
- explicit denials applied

### 7.4 Policy Enrollment
- student insured
- paid/current
- waiting period complete
- claim time window satisfied

If any layer fails, the transaction is not claimable.

---
## 8. Observability & Debugging Requirements

Every skipped transaction must produce a single primary reason code:

- HARD_DENY_CATEGORY
- INTERNAL_TRANSFER
- DELAY_USE_NOT_USED
- DELAY_USE_EXPIRED
- NOT_ALLOWED_BY_TEACHER
- EXPLICITLY_DENIED_BY_TEACHER
- NO_ACTIVE_POLICY
- PREMIUM_NOT_CURRENT
- WAITING_PERIOD
- TIME_LIMIT_EXCEEDED
- ALREADY_CLAIMED
- REIMBURSEMENT_ALREADY_EXISTS
- UNCLASSIFIED_TRANSACTION

Admin tools must allow filtering by reason.

---
## 9. Backfill & Migration Notes

Transaction classification must be backfilled before enabling automation.

- Backfill sets categories/flags only; never changes amounts.
- Unclassified transactions remain ineligible.

---
## 10. Security & Abuse Resistance

- Students cannot claim transactions they did not generate.
- Students cannot claim the same transaction twice.
- Students cannot claim reimbursement transactions.
- Teachers can deny categories/items to prevent “insurance farming.”

---
# End of Architecture Specification

# Obligations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OBL-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Obligations domain as the authority over rent-payment truth, insurance enrollment truth, and claim lifecycle state.

## II. Scope

This domain owns committed obligation records and claim/enrollment history. It does not own money movement.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `rent_payments`
- `insurance_policies`
- `insurance_policy_blocks`
- `student_insurance`
- `insurance_claims`

It may require Ledger effects through FEAT or `ledger_service`, but it does not own ledger rows.

## V. Owned Tables

### `rent_payments`
- Recorded rent payment truth for a scoped class period.

### `insurance_policies`
- Insurance product templates and policy terms.

### `insurance_policy_blocks`
- Block visibility mapping for insurance policies.

### `student_insurance`
- Student enrollment contracts and coverage/payment state.

### `insurance_claims`
- Claim filing, resolution, and reimbursement-link truth.

## VI. Schema Contract

### `rent_payments`
- Key fields:
  - `student_id`
  - `join_code`
  - `period`
  - `amount_paid`
  - `coverage_month`
  - `coverage_year`
  - `late_fee_charged`

### `insurance_policies`
- Key fields:
  - `policy_code`
  - `teacher_id`
  - `join_code`
  - `class_id`
  - `title`
  - `premium`
  - `claim_type`
  - `max_claim_amount`
  - `max_payout_per_period`
  - `is_active`

### `insurance_policy_blocks`
- Key fields:
  - `policy_id`
  - `block`
  - `join_code`

### `student_insurance`
- Key fields:
  - `student_id`
  - `policy_id`
  - `join_code`
  - `status`
  - `purchase_date`
  - `coverage_start_date`
  - frozen policy snapshot fields

### `insurance_claims`
- Key fields:
  - `student_insurance_id`
  - `policy_id`
  - `student_id`
  - `transaction_id`
  - `status`
  - `claim_amount`
  - `approved_amount`
  - `processed_by_teacher_id`

## VII. Constraints

- Obligation truth is append/history preserving once committed.
- Claim approval and reimbursement are separate responsibilities: Obligations owns claim state; Ledger owns the payout event.
- Policy snapshots frozen into enrollment rows are part of obligation truth.

## VIII. Derived / Cross-Domain Rules

- Rent payment FEAT coordinates Obligations and Ledger.
- Insurance purchase and claim approval FEATs coordinate Obligations and Ledger.
- `transaction_id` on claims is a cross-domain reference to the underlying incident; it does not transfer ledger ownership.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.

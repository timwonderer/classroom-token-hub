# Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Ledger domain as the sole money-state mutation authority.

## II. Scope

This domain owns ledger event persistence, balance-cache persistence, legal money transitions, and money-state query semantics.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `INV-CORE-001_Authority_Model.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `ARC-OPS-013_Money_Handling.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `transaction`
- `balance_cache`
- `payroll_cache`

No other domain may define fields, impose lifecycle rules, or mutate these tables directly.

## V. Owned Tables

### `transaction`
- Canonical financial event log.
- All money movement, pending holds, settlements, voids, and compensations are expressed here.

### `balance_cache`
- Posted-balance snapshot cache by scoped account holder / class context.

### `payroll_cache`
- Cached payroll breakdowns derived for class-scoped payroll execution and display.

## VI. Schema Contract

### `transaction`
- Key fields:
  - `id`
  - `student_id`
  - `teacher_id`
  - `join_code`
  - `amount`
  - `account_type`
  - `status`
  - `type`
  - `description`
  - `idempotency_key`
  - `original_transaction_id`
  - `policy_id`
  - `reversal_transaction_id`
  - `date_funds_available`
- Status vocabulary:
  - `pending`
  - `posted`
  - `void`

### `balance_cache`
- Key fields:
  - `student_id`
  - `seat_id`
  - `join_code`
  - `posted_checking_balance_cents`
  - `posted_savings_balance_cents`
  - `last_settlement_at`

### `payroll_cache`
- Key fields:
  - `teacher_id`
  - `join_code`
  - `class_id`
  - `cached_breakdown`
  - `last_calculated_at`

## VII. Constraints

- `ledger_service` is the only legal constructor path for `Transaction` rows.
- Posted truth is never silently rewritten or deleted.
- Pending truth may transition only through explicit ledger commands.
- Compensation creates new rows; it does not edit historical amounts in place.
- Transfers must net to zero within the scoped class boundary.
- Balance is derived from ledger truth and settlement/cache logic, never from model convenience properties.

## VIII. Derived / Cross-Domain Rules

- FEAT modules may request money transitions, but they do not own ledger rows.
- `join_code` is the class boundary for ledger queries and transfer invariants.
- `original_transaction_id` and `reversal_transaction_id` are relationship links, not shared ownership.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.

# Class Configuration Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CLASS-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Class Configuration domain as the authority over persisted class-scoped settings and class anchor records.

## II. Scope

This domain owns class anchors, feature enablement, and persisted class-level settings. It does not interpret those settings into money, attendance, entitlement, or eligibility outcomes.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `class_economies`
- `class_features`
- `feature_settings`
- `hall_pass_settings`
- `rent_settings`
- `payroll_settings`
- `banking_settings`

It returns persisted settings only. FEAT or the owning operational domain interprets them.

## V. Owned Tables

### `class_economies`
- Canonical class anchor rows.

### `class_features`
- Feature enablement by class.

### `feature_settings`
- Economy and feature-related persisted settings.

### `hall_pass_settings`
- Hall-pass configuration values.

### `rent_settings`
- Rent policy configuration values.

### `payroll_settings`
- Payroll configuration values.

### `banking_settings`
- Banking/overdraft/interest configuration values.

## VI. Schema Contract

### `class_economies`
- Key fields:
  - `class_id`
  - `join_code`
  - `teacher_id`
  - `display_name`
  - `status`

### `class_features`
- Key fields:
  - `class_id`
  - `feature_name`

### `feature_settings`
- Key fields:
  - `teacher_id`
  - `join_code`
  - `class_id`
  - economy policy and rebalance fields

### `hall_pass_settings`
- Key fields:
  - `teacher_id`
  - `join_code`
  - `class_id`
  - queue / timing / pass-count settings

### `rent_settings`
- Key fields:
  - `teacher_id`
  - `join_code`
  - `class_id`
  - `block`
  - rent amount/frequency/grace/late policy fields

### `payroll_settings`
- Key fields:
  - class scope identifiers
  - pay rates
  - timing / automation controls

### `banking_settings`
- Key fields:
  - class scope identifiers
  - overdraft policy
  - interest policy
  - transfer / balance behavior settings

## VII. Constraints

- This domain stores configuration; it does not compute operational outcomes.
- It does not mutate ledger, attendance, obligations, store, or identity tables.
- Missing row vs existing row semantics are part of persisted configuration truth and must remain explicit.

## VIII. Derived / Cross-Domain Rules

- Attendance reads hall-pass limits from configuration but still owns attendance history.
- Ledger/payroll logic may consume payroll or banking settings, but configuration does not execute those workflows.
- `class_economies` anchors class existence; membership truth still belongs to Identity.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.

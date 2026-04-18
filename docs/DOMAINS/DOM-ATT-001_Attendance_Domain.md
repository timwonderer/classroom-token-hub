# Attendance Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ATT-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Attendance domain as the source of attendance facts, session history, and hall-pass event history.

## II. Scope

This domain owns attendance event persistence, session-state persistence, time-calculation inputs/outputs, and hall-pass execution history.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `tap_events`
- `hall_pass_logs`

It may read configuration supplied by the Class Configuration domain, but it does not own payroll, balances, or eligibility policy.

## V. Owned Tables

### `tap_events`
- Append-style work-state events and attendance timeline truth.

### `hall_pass_logs`
- Runtime hall-pass history and leave/return event state.

## VI. Schema Contract

### `tap_events`
- Key fields:
  - `student_id`
  - `join_code`
  - `period`
  - `status`
  - `timestamp`
  - `reason_code`

### `hall_pass_logs`
- Key fields:
  - `student_id`
  - `teacher_id`
  - `join_code`
  - `status`
  - `time_out`
  - `time_in`

## VII. Constraints

- Attendance returns facts only.
- Attendance does not compute wage policy, payroll amounts, affordability, or solvency.
- Completed tap and hall-pass history must not be silently erased.
- Anchors, limits, and policy inputs are supplied from outside this domain.

## VIII. Derived / Cross-Domain Rules

- Payroll FEAT consumes attendance facts and requests money movement from Ledger.
- Hall-pass settings are owned by Class Configuration even though hall-pass execution history is owned here.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.

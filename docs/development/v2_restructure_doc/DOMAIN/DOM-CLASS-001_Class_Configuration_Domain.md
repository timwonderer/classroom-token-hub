# Class Configuration Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md` (class identity anchor `classes`)

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `class_features`
- `feature_settings`
- `hall_pass_settings`
- `rent_settings`
- `payroll_settings`
- `payroll_rewards`
- `payroll_fines`
- `banking_settings`

It returns persisted settings only. FEAT or the owning operational domain interprets them.

## VI. Owned Tables

### 1. `class_features`

Feature enablement by class. One row per enabled feature per class. Absence of a
row means the feature is disabled.

### 2. `feature_settings`

Economy policy mode and rebalance tracking for a class.

### 3. `hall_pass_settings`

Hall-pass queue, timing, and per-type configuration values for a class.

### 4. `rent_settings`

Rent policy configuration: amount, frequency, grace period, late penalty, and billing
rules for a class.

### 5. `payroll_settings`

Payroll rate, schedule, overtime, and automation configuration for a class.

### 6. `payroll_rewards`

Teacher-defined reward presets for payroll bonus events.

### 7. `payroll_fines`

Teacher-defined fine presets for payroll deduction events.

### 8. `banking_settings`

Savings interest, overdraft protection, and transfer behavior configuration for a class.

## VII. Schema Contract

### 1. `class_features`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `feature_name` — `payroll` | `insurance` | `banking` | `rent` | `hall_pass` | `store`
- `created_at`

Rules:

- Unique constraint on `(class_id, feature_name)`.
- Feature existence means enabled. Absence means disabled.
- `feature_name` is a closed enumeration; open-ended strings are not permitted.
- This table does not store configuration values — only enablement.

### 2. `feature_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — explicit class anchor per INV-CORE-000
- `economy_policy_mode`
- `economy_policy_updated_at`
- `economy_last_rebalanced_at`
- `economy_last_rebalanced_by` — `user_id` of the actor who triggered the rebalance
- `economy_pending_rebalance_json`

Rules:

- One record per class. Created when the class is first configured.
- `economy_policy_mode` controls how the payroll engine interprets rates.
  It is read-only to all domains except Class Configuration.

### 3. `hall_pass_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — explicit class anchor per INV-CORE-000
- `queue_enabled` — boolean
- `queue_limit` — max concurrent passes across all types
- `pass_types` — JSON; list of pass-type configurations, each with:
  - `name`
  - `queue_limit`
  - `simultaneous_limit`
  - `enabled`
- `created_at` / `updated_at`

Rules:

- One record per class.
- `pass_types` defaults to the system-defined set of five types when absent.
- This table stores configuration only. Execution history lives in Attendance.

### 4. `rent_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — explicit class anchor per INV-CORE-000
- `is_enabled`
- `rent_amount` — Numeric
- `frequency_type` — `daily` | `weekly` | `monthly` | `custom`
- `custom_frequency_value` / `custom_frequency_unit`
- `first_rent_due_date`
- `due_day_of_month`
- `grace_period_days`
- `late_penalty_amount`
- `late_penalty_type` — `once` | `recurring`
- `late_penalty_frequency_days`
- `bill_preview_enabled` / `bill_preview_days`
- `allow_incremental_payment`
- `prevent_purchase_when_late`
- `bypass_cwi_warnings`
- `updated_at`

Rules:

- One record per class.
- This table defines rent policy only. Rent payment history lives in Obligations.

### 5. `payroll_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — explicit class anchor per INV-CORE-000
- `pay_rate` — Numeric; dollars per minute of tap time
- `payroll_frequency_days`
- `daily_limit_hours` — simple-mode auto tap-out threshold
- `time_unit` / `overtime_enabled` / `overtime_threshold`
- `max_time_per_day` / `max_time_per_unit`
- `pay_schedule_type` / `rounding_mode`
- `next_payroll_date`
- `is_active`
- `expected_weekly_hours` — used for economy balance validation only
- `created_at` / `updated_at`

Rules:

- One record per class.
- Payroll execution logic lives in FEAT; this table stores the configuration inputs.

### 6. `payroll_rewards`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `join_code` — explicit class anchor per INV-CORE-000
- `name`
- `description`
- `amount` — positive Numeric; bonus amount per occurrence
- `is_active`

Rules:

- Rewards are class-scoped policy definitions. They define what a teacher can offer
  as a payroll bonus; they do not themselves create ledger entries.
- FEAT orchestrates the ledger credit when a reward is applied to a seat.
- `is_active = false` rewards may not be selected for new payroll events but must
  be retained for display on historical payroll records.

### 7. `payroll_fines`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `join_code` — explicit class anchor per INV-CORE-000
- `name`
- `description`
- `amount` — positive Numeric; stored as a magnitude; ledger deduction semantics
  are applied by FEAT
- `is_active`

Rules:

- Fines are class-scoped policy definitions. They define what a teacher can apply
  as a payroll deduction; they do not themselves create ledger entries.
- FEAT orchestrates the ledger debit when a fine is applied to a seat.
- `is_active = false` fines may not be selected for new payroll events but must
  be retained for historical display.

### 8. `banking_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — explicit class anchor per INV-CORE-000
- `savings_apy` / `savings_monthly_rate`
- `interest_calculation_type` — `simple` | `compound`
- `compound_frequency`
- `interest_schedule_type` — `weekly` | `monthly`
- `interest_schedule_cycle_days`
- `interest_payout_start_date`
- `overdraft_protection_enabled`
- `overdraft_fee_enabled`
- `overdraft_fee_type` — `flat` | `progressive`
- `overdraft_fee_flat_amount`
- `overdraft_fee_progressive_1` / `_2` / `_3` / `_cap`
- `is_active`
- `created_at` / `updated_at`

Rules:

- One record per class.
- Interest computation and overdraft fee application live in FEAT/Ledger;
  this table provides the configuration inputs only.

## VIII. Constraints

- This domain stores configuration; it does not compute operational outcomes.
- It does not mutate ledger, attendance, obligations, store, or identity tables.
- All settings tables are scoped by `class_id` (from `classes`) as the primary
  class identity anchor. `join_code` is carried explicitly per `INV-CORE-000`.
- No settings table uses `teacher_id` as a scoping key. The class (`class_id`) is
  the scope boundary, not the teacher.
- Missing row vs existing row semantics are part of persisted configuration truth
  and must remain explicit.

## IX. Derived / Cross-Domain Rules

- Attendance reads hall-pass limits from `hall_pass_settings` but owns the execution
  history in `hall_pass_logs`.
- Payroll FEAT reads `payroll_settings`, `payroll_rewards`, and `payroll_fines` but
  does not own those rows.
- Ledger reads `banking_settings` for interest and overdraft policy but does not own
  that configuration.
- Class identity (`classes.class_id`, `classes.join_code_token`) is owned by Identity.
  This domain reads `class_id` as a FK but does not own the class record.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.

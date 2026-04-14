# Rent Feature: Comprehensive Analysis

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-RENT-003    | 1.0     | 2026-04-12     | N/A        | Informational   |

**Feature:** Rent System — Logic, Routes, and Invariant Audit  
**Date:** 2026-04-12  
**Status:** Analysis complete

---

## Overview

This document provides a detailed analysis of every component the rent feature touches: data models, routes, helper functions, design invariants, and identified fragility concerns. It is intended as a reference for developers working on the rent system.

---

## 1. Data Model Layer

### 1.1 Core Tables

#### `rent_settings`

Per-teacher, per-block rent configuration.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `teacher_id` | FK → `admins.id` | NOT NULL, indexed |
| `join_code` | VARCHAR(20) | Indexed; class isolation |
| `join_code_id` | FK → `join_codes.join_code_id` | CASCADE DELETE |
| `block` | VARCHAR(10) | NULL = global default |
| `is_enabled` | BOOLEAN | Default TRUE |
| `rent_amount` | NUMERIC(12,2) | Default 50.00 |
| `frequency_type` | VARCHAR(20) | `daily`, `weekly`, `monthly`, `custom` |
| `custom_frequency_value` | INTEGER | For custom frequency |
| `custom_frequency_unit` | VARCHAR(20) | `days`, `weeks`, `months` |
| `first_rent_due_date` | DATETIME(tz) | Anchor for frequency-based schedule |
| `due_day_of_month` | INTEGER | Legacy fallback; default 1 |
| `grace_period_days` | INTEGER | Default 3 |
| `late_penalty_amount` | NUMERIC(12,2) | Default 10.00 |
| `late_penalty_type` | VARCHAR(20) | `once` or `recurring` |
| `late_penalty_frequency_days` | INTEGER | For recurring penalty |
| `bill_preview_enabled` | BOOLEAN | Default FALSE |
| `bill_preview_days` | INTEGER | Default 7 |
| `allow_incremental_payment` | BOOLEAN | Default FALSE |
| `prevent_purchase_when_late` | BOOLEAN | Default FALSE |
| `bypass_cwi_warnings` | BOOLEAN | NOT NULL, default FALSE |
| `updated_at` | DATETIME(tz) | Auto-updated |

**Relationships:**
- `teacher` → `Admin` (backref: `rent_settings`)
- `rent_items` → `RentItem[]` (cascade all, delete-orphan)

---

#### `rent_payments`

Individual student payment records.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `student_id` | FK → `students.id` | NOT NULL |
| `period` | VARCHAR(10) | Block/period identifier |
| `join_code` | VARCHAR(20) | Indexed; class isolation |
| `amount_paid` | NUMERIC(12,2) | NOT NULL |
| `period_month` | INTEGER | Month payment was *made* |
| `period_year` | INTEGER | Year payment was *made* |
| `payment_date` | DATETIME(tz) | Timestamp of payment |
| `coverage_month` | INTEGER | Month this payment *covers* |
| `coverage_year` | INTEGER | Year this payment *covers* |
| `was_late` | BOOLEAN | Default FALSE |
| `late_fee_charged` | NUMERIC(12,2) | Default 0.00 |

> **Note:** `period_month/year` (when paid) is distinct from `coverage_month/year` (which billing cycle is covered). This is the foundation of the pre-paid system.

---

#### `rent_waivers`

Exemptions from rent for a date range.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `student_id` | FK → `students.id` | NOT NULL |
| `join_code` | VARCHAR(20) | Indexed |
| `waiver_start_date` | DATETIME(tz) | NOT NULL |
| `waiver_end_date` | DATETIME(tz) | NOT NULL |
| `periods_count` | INTEGER | Number of rent periods waived |
| `reason` | TEXT | Optional admin reason |
| `created_by_admin_id` | FK → `admins.id` | Nullable |
| `created_at` | DATETIME(tz) | Default `utc_now` |

---

#### `rent_items`

Itemized components of rent (e.g. desk, chair, locker).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `rent_setting_id` | FK → `rent_settings.id` | NOT NULL, indexed |
| `join_code` | VARCHAR(20) | Indexed |
| `join_code_id` | FK → `join_codes.join_code_id` | CASCADE DELETE |
| `name` | VARCHAR(100) | NOT NULL |
| `description` | TEXT | |
| `order_index` | INTEGER | Display order |
| `is_available_in_store` | BOOLEAN | Default FALSE |
| `store_price` | NUMERIC(10,2) | À la carte price |
| `purchase_duration` | VARCHAR(20) | `per_use` or `per_period` |
| `store_item_id` | FK → `store_items.id` | Nullable |
| `rent_item_type` | VARCHAR(20) | `privilege`, `per_use`, `hall_pass` |
| `use_limit` | INTEGER | NULL = unlimited; integer = capped |
| `hall_pass_count` | INTEGER | Passes granted if type is `hall_pass` |
| `created_at` | DATETIME(tz) | |
| `updated_at` | DATETIME(tz) | Auto-updated |

---

### 1.2 Auxiliary Fields on Other Models

| Model | Field | Purpose |
|-------|-------|---------|
| `Student` | `is_rent_enabled` | Per-student rent toggle |
| `StudentBlock` | `rent_hall_passes` | Tracks passes that came from rent (for top-off) |
| `StoreItem` | `is_rent_linked` | Marks store items managed by rent settings |

---

## 2. Routes

### 2.1 Admin Routes (`app/routes/admin.py`)

| Route | Methods | Function | Purpose |
|-------|---------|----------|---------|
| `/rent-settings` | GET, POST | `rent_settings()` | Configure settings, view status overview, manage rent items. ~600 lines. |
| `/rent-waiver/add` | POST | `add_rent_waiver()` | Add waivers for students (scopes: `past_due`, `current`, `future`) |
| `/rent-waiver/<id>/remove` | POST | `remove_rent_waiver()` | Remove entire waiver or cancel one upcoming period |
| `/rent/reverse-cycle-penalties` | POST | `reverse_cycle_penalties()` | Reverse wrongly-applied late fees when rate changed mid-cycle |

#### `rent_settings()` (GET)

Renders `admin_rent_settings.html` with:
- Rent status counts (paid / 1-month behind / 2-months behind / 3+ months behind)
- Payment log and unpaid student log
- Current and upcoming coverage due dates
- Waiver history
- Rent items list

#### `rent_settings()` (POST)

Handles the following form fields:
- `is_enabled`, `rent_amount`, `frequency_type`, `custom_frequency_value/unit`
- `first_rent_due_date`, `due_day_of_month`, `grace_period_days`
- `late_penalty_amount`, `late_penalty_type`, `late_penalty_frequency_days`
- `bill_preview_enabled`, `bill_preview_days`
- `allow_incremental_payment`, `prevent_purchase_when_late`, `bypass_cwi_warnings`
- `apply_to_all` — copies settings across all blocks
- Rent item fields: `rent_item_name_{i}`, `rent_item_type_{i}`, `rent_item_description_{i}`, `rent_item_store_available_{i}`, `rent_item_store_price_{i}`, `rent_item_use_limit_{i}`, `rent_item_hall_pass_count_{i}`

**Mid-period lock:** If any student has already paid for the current cycle, certain semantic fields (rent amount, frequency) cannot be changed.

#### `add_rent_waiver()` (POST)

Parameters: `student_ids[]`, `waiver_scope[]` (`past_due`, `current`, `future`), `past_due_dates[]`, `future_periods_count`, `reason`, `settings_block`.

Creates one `RentWaiver` record per student per covered period and records an `AnalyticsEvent` for audit trail.

#### `remove_rent_waiver()` (POST)

Parameters: `settings_block`, `coverage_due_date` (optional ISO datetime).
- If `coverage_due_date` provided: cancels just that period (splits waiver into before/after if needed).
- If absent: deletes the entire waiver record.
- Prevents cancelling waivers that are `current` or `used`; only `upcoming` periods are cancellable.

#### `reverse_cycle_penalties()` (POST)

Determines the "locked rate" (amount paid by the first valid payer in the cycle). For each student who paid ≥ locked rate by the grace deadline but was still marked late, creates a `Rent Late Fee Reversal` transaction and clears `was_late` / `late_fee_charged` on the `RentPayment`.

---

### 2.2 Student Routes (`app/routes/student.py`)

| Route | Methods | Function | Purpose |
|-------|---------|----------|---------|
| `/rent` | GET | `rent()` | Display rent status dashboard |
| `/rent/pay/<period>` | POST | `rent_pay(period)` | Process full or partial payment |

#### `rent()` (GET)

1. Validates: feature flag `rent` is on, rent settings enabled, class context and block exist.
2. Calculates `_calculate_rent_timeline()` to get due dates, grace dates, preview window.
3. Checks if preview period is valid (current coverage must be settled first).
4. Fetches `RentPayment` rows for the current coverage period and filters out those with voided transactions (via 300-second timestamp match).
5. Fetches `RentWaiver` rows and expands them into per-period entries.
6. Computes: `total_paid`, `total_due` (rent + late fee if applicable), `remaining_amount`, `is_paid`, `is_late`, `is_waived`.
7. Builds payment/waiver history (last 24 entries).
8. Renders `student_rent.html`.

#### `rent_pay(period)` (POST)

1. Validates: settings enabled, `student.is_rent_enabled`, period matches current class.
2. Calls `_calculate_rent_timeline()` and determines if rent is active.
3. Enforces preview-period ordering (overdue must be paid before pre-paying).
4. Determines `coverage_month/year` for the RentPayment record.
5. Fetches existing payments for the period; filters voided transactions.
6. Calculates `effective_rent_amount` (rate-locked), `is_late`, `late_fee`, `remaining_amount`.
7. Validates payment mode (`full` vs `partial`), parses and bounds-checks `payment_amount`.
8. Calls `evaluate_overdraft_allowance()` and `_charge_overdraft_fee_if_needed()` if needed.
9. Creates `Transaction` (`type='Rent Payment'`, `amount=-payment_amount`, `account_type='checking'`).
10. Creates `RentPayment` record.
11. If overdraft protection triggers: creates a savings `Withdrawal` + checking `Deposit` pair.
12. If this payment completes the full rent:
    - Calls `_ensure_rent_hall_pass_top_off()` to award hall passes.
    - Grants `StudentItem` records for `per_use` rent items (top-off if existing).
13. Commits all in one `db.session.commit()`.

---

### 2.3 API Route — Store Purchase Block (`app/routes/api.py`)

When `prevent_purchase_when_late=True` and the student is past the grace period and unpaid:
- If rent items are configured, blocks all purchases **except** items that are linked to rent (`rent_item_store_ids`) — those may still be purchased à la carte.
- If no rent items are configured, blocks all store purchases.

---

## 3. Helper Functions

### 3.1 Timeline and Due-Date Functions

| Function | Location | Description |
|----------|----------|-------------|
| `_calculate_rent_deadlines(settings, ref_date)` | student.py:3000 | Returns `(due_date, grace_end_date)` for the current period. Handles all frequency types and timezone clamping. |
| `_calculate_rent_coverage_due_date(settings, ref_date)` | student.py:3510 | Returns the most recently **passed** due date — foundation of the pre-paid system. |
| `_calculate_upcoming_rent_due_date(settings, due, coverage)` | student.py:3148 | Returns the next future due date. |
| `_calculate_rent_timeline(settings, now)` | student.py:3167 | Master function; returns dict: `{due_date, grace_end_date, coverage_due_date, upcoming_due_date, preview_start_date, rent_is_active, is_preview_period_candidate}`. |
| `_get_rent_period_delta(settings)` | student.py:3122 | Returns timedelta/relativedelta for one rent period. |
| `_add_rent_period(dt, delta)` | student.py:3143 | Adds a period delta to a datetime. |
| `_get_rent_timezone(settings)` | student.py:2987 | Returns server-side timezone for rent schedule semantics. |

**Parallel implementation:** `_calculate_due_dates(rent_setting, now)` in `api.py:98` is a simpler, separate implementation of due-date logic — not shared with the above.

---

### 3.2 Payment Validation Functions

| Function | Description |
|----------|-------------|
| `_filter_valid_rent_payments(payments, student_id, join_code)` | Filters to payments with a matching, non-void Transaction (300s tolerance). |
| `_total_paid_by_grace(payments, grace_end)` | Sums amounts paid on or before the grace deadline. |
| `_get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due)` | Locks rate at the first valid payer's base amount to prevent mid-cycle change unfairness. |
| `_get_effective_rent_amount_for_coverage_period(settings, payments, coverage_due, join_code)` | Returns the applicable rent amount for a coverage period, respecting rate-locking. |
| `_is_coverage_period_paid(settings, valid_payments, coverage_due, include_late_fee, join_code)` | Returns True when total paid ≥ effective rent (+ late fee if applicable). |
| `_is_student_coverage_period_paid(settings, student_id, period, join_code, coverage_due, ...)` | High-level wrapper: checks waivers first, then payment totals. |

---

### 3.3 Waiver Functions

| Function | Description |
|----------|-------------|
| `_get_active_rent_waiver(student_id, join_code, coverage_due)` | Returns waiver if `waiver_start ≤ coverage_due ≤ waiver_end` for matching `join_code`. |
| `_has_active_rent_waiver(student_id, join_code, coverage_due)` | Boolean wrapper over the above. |
| `_iter_rent_waiver_coverage_dates(settings, waiver)` | Expands a waiver into its individual coverage due dates. |
| `_expand_rent_waiver_history(settings, waivers, now)` | Builds display rows with status (`current`/`upcoming`/`used`) and cancellability flags. |
| `_cancel_rent_waiver_period(waiver, coverage_due, settings)` | Removes one date from a waiver; splits into replacement waivers for remaining dates. |
| `_group_consecutive_waiver_dates(dates, settings)` | Groups consecutive coverage dates into contiguous waiver windows (for waiver splitting). |
| `_get_rent_coverage_label(coverage_due)` | Returns a human-readable label, e.g. `"Jan 2025"`. |

---

### 3.4 Perk and Item Functions

| Function | Description |
|----------|-------------|
| `_ensure_rent_hall_pass_top_off(student, context, settings, now)` | Awards/revokes hall passes based on current rent payment status; tracks via `StudentBlock.rent_hall_passes`. |
| `_clear_expired_rent_perk_items(student_id, join_code, teacher_id, now)` | Deletes expired rent-granted `StudentItem` rows. |
| `_sync_rent_items_to_store(rent_settings, teacher_id, block)` | Creates or updates `StoreItem` records for rent items marked as available in store. |
| `_block_rent_linked_store_item(item)` | Prevents deletion of store items managed by rent. |
| `_get_rent_privileges_for_student(student, teacher_id, join_code)` | Returns privilege items available to student (from rent payment or store purchase). |
| `_build_rent_privileges_by_block(admin, blocks, join_codes, students)` | Batched version for admin overview (avoids N+1 queries). |

---

### 3.5 Admin Helper Functions

| Function | Description |
|----------|-------------|
| `_delete_teacher_rent_rows(teacher_id)` | Deletes all `RentItem` and `RentSettings` rows when a teacher is removed. |
| `_calculate_base_rent_amount(rent_settings, year, month)` | Normalises configured rent to a monthly-equivalent value (used for CWI balance checks). |
| `_format_frequency_label(frequency, value, unit)` | Human-readable frequency label (e.g. `"every 3 weeks"`). |

---

## 4. Key Design Invariants

### INV-RENT-001 — Pre-Paid Coverage System

RentPayment has two separate date fields:
- `period_month/year` — when the payment was *made*
- `coverage_month/year` — which billing cycle it *covers*

A payment made in January with `coverage_month=2` covers the student through the February due date.

**Enforcement:** Students must settle overdue coverage before pre-paying for an upcoming period. Both `rent()` and `rent_pay()` call `_is_student_coverage_period_paid()` before permitting preview-period payments.

---

### INV-RENT-002 — Rate Locking

Once the first valid, non-voided payment is recorded for a `(join_code, coverage_due_date)` cycle, the rent amount is locked at that payment's base amount for all subsequent payers and validation in that cycle.

**Enforcement:** `_get_locked_rent_amount_for_join_code_cycle()` queries the earliest matching `Transaction` for the cycle and returns its absolute amount as the locked rate.

**Recovery:** If a teacher changes the rate mid-cycle, `reverse_cycle_penalties()` lets them correct wrongly-applied late fees.

---

### INV-RENT-003 — Waiver Coverage Check

A `RentWaiver` applies to a coverage period when:
```
waiver_start_date ≤ coverage_due_date ≤ waiver_end_date
AND (waiver.join_code == context_join_code OR waiver.join_code IS NULL)
```

`join_code IS NULL` waivers match any class (used for global exemptions).

---

### INV-RENT-004 — Payment-Transaction Linkage

`RentPayment` and `Transaction` are **not linked by a foreign key**. Validity is established at runtime by matching:
```
student_id == student.id
AND type == 'Rent Payment'
AND join_code == payment.join_code
AND |timestamp - payment_date| ≤ 300 seconds
AND amount == -payment.amount_paid
AND NOT is_void
```

A `RentPayment` with no matching valid transaction is treated as if it does not exist.

---

### INV-RENT-005 — Class Isolation via join_code

All rent queries are scoped by `join_code`. This is the authoritative tenant identifier. `join_code` appears on all four rent tables and is mandatory on every query that checks student status.

---

### INV-RENT-006 — Hall Pass Top-Off

When a student's rent becomes fully paid, hall passes are reconciled to the configured `hall_pass_count` total. When rent becomes unpaid (e.g. transaction voided), passes are revoked proportionally. `StudentBlock.rent_hall_passes` tracks the number of passes attributed to rent, isolating them from passes granted by other means.

---

### INV-RENT-007 — Per-Use Item Grants

When rent is fully paid, a `StudentItem` is created for each `per_use` rent item. The item expires at the next rent due date. If a non-expired item already exists for the student, it is topped off (uses reset) rather than duplicated.

---

### INV-RENT-008 — Store Purchase Blocking

When `prevent_purchase_when_late=True`:
- If the student is past the grace period and unpaid, store purchases are blocked.
- Exception: items whose `store_item.id` is in the set of linked rent item store IDs are still purchasable (à la carte alternative).
- If no rent items are configured, all store purchases are blocked for late students.

---

### INV-RENT-009 — Rent-Linked Store Item Protection

Store items created from rent items carry `is_rent_linked=True`. Attempting to delete such an item from the store is blocked by `_block_rent_linked_store_item()`. They must be removed from rent settings instead.

---

## 5. Economy Policy Integration

### CWI Balance Checks (`app/utils/economy_balance.py`)

```
RENT_MIN_RATIO  = 2.0   (monthly rent / weekly CWI)
RENT_MAX_RATIO  = 2.5
RENT_DEFAULT_RATIO = 2.25
```

`check_rent_balance()` normalises the configured rent amount to a weekly equivalent, then compares against these ratios. Warnings are generated at three levels: `CRITICAL`, `WARNING`, `INFO`.

`validate_rent_value()` is the admin-facing validator; it returns structured recommendation dicts used in the rent settings UI.

### Economy Rebalance (`app/utils/economy_rebalance.py`)

When the economy rebalancer schedules a rent amount change, it uses `_get_rent_effective_at()` to mark the change effective at the **next** due date (not immediately). This prevents mid-cycle disruption and is consistent with the rate-locking invariant.

---

## 6. Templates

| Template | Size | Purpose |
|----------|------|---------|
| `templates/student_rent.html` | ~16 KB | Student rent dashboard: status card, payment buttons (full/partial), rent items list, payment history table |
| `templates/admin_rent_settings.html` | ~88 KB | Admin rent management: four-tab layout (Overview, Settings, Waivers, Corrections), rent item builder, CWI balance warnings |

---

## 7. Transaction Types

| Type String | Direction | Created By |
|-------------|-----------|------------|
| `Rent Payment` | Debit (negative, checking) | `rent_pay()` |
| `Withdrawal` | Debit (negative, savings) | `rent_pay()` — overdraft protection |
| `Deposit` | Credit (positive, checking) | `rent_pay()` — overdraft protection |
| `Rent Late Fee Reversal` | Credit (positive, checking) | `reverse_cycle_penalties()` |

All rent transactions include `join_code` and `teacher_id` for multi-tenancy isolation.

---

## 8. Fragility Concerns

### 8.1 Payment-Transaction Matching is Duplicated in 6+ Locations

The 300-second timestamp-tolerance matching pattern appears inline in:
- `rent()` GET route (student.py ~3735)
- `rent_pay()` POST route (student.py ~3975)
- `_filter_valid_rent_payments()` (student.py ~3298)
- `_get_locked_rent_amount_for_join_code_cycle()` (student.py ~3236)
- `reverse_cycle_penalties()` (admin.py ~6904)
- Dashboard store check (student.py ~1505)

**Risk:** If tolerance, field names, or matching criteria change, all six locations must be updated in lockstep. Additionally, two payments within 300 seconds for the same student/join_code could match the wrong transaction.

**Recommendation:** Centralise the match into a single SQL query helper or add a `rent_payment_id` FK column to `Transaction`.

---

### 8.2 No Foreign Key Between RentPayment and Transaction

RentPayment and Transaction have no referential integrity link. The only connection is the runtime timestamp heuristic. A voided transaction causes the corresponding payment to silently disappear from payment totals on the next page load.

**Risk:** Clock skew between application and database, or a delayed `db.session.flush()`, could cause a payment to be unmatched immediately after creation.

---

### 8.3 Monolithic Admin Route (~600 Lines)

`rent_settings()` handles GET display, POST settings update, rent item CRUD, store sync, waiver display, payment status calculation, and CWI warnings in a single function.

**Risk:** Difficult to unit-test; any regression in one area affects the entire route.

---

### 8.4 Circular Cross-Module Imports

Several functions import from `student.py` at call time to avoid circular imports at module level:
- `admin.py` → `student._iter_rent_waiver_coverage_dates`, `student._add_rent_period`, `student._get_rent_period_delta`
- `admin.py` → `student._get_rent_coverage_label`
- `economy_rebalance.py` → `student._add_rent_period`, `student._calculate_rent_timeline`, `student._get_rent_period_delta`
- `admin.py` → `student._cancel_rent_waiver_period`

**Risk:** Deferred imports obscure the real dependency graph and make refactoring error-prone.

**Recommendation:** Move shared rent utilities to `app/utils/rent_utils.py`.

---

### 8.5 Duplicate Due-Date Calculation Logic

`_calculate_rent_deadlines()` (student.py) and `_calculate_due_dates()` (api.py) both compute rent due dates but are separate implementations. The student.py version is timezone-aware and handles all frequency types; the api.py version is simpler and used internally.

**Risk:** The two implementations can diverge silently, causing different due dates to be calculated depending on which code path is hit.

---

### 8.6 No Background Enforcement

There are no scheduled tasks for rent. Late fee status is calculated lazily at view/payment time, and `prevent_purchase_when_late` only activates at purchase time. No notifications are sent for upcoming or overdue rent.

---

### 8.7 No Idempotency Guard on Payment Submission

`rent_pay()` has no explicit idempotency key. The only guard is the `remaining_amount <= 0` check. A concurrent double-submission (e.g. double-click or network retry) could create duplicate payments before the first commit's balance update is visible.

---

### 8.8 O(N) Queries per Coverage-Paid Check

`_is_student_coverage_period_paid()` calls `_filter_valid_rent_payments()`, which issues one `Transaction` query per payment row to validate each one. For students with many incremental payments, this is O(N) queries per check — and this check is called multiple times per page load.

**Recommendation:** Batch the transaction lookup across all `payment_date` values in a single windowed query.

---

### 8.9 Inconsistent Block/join_code Relationship

`get_rent_settings_for_context()` looks up settings by `block` then falls back to a teacher-wide record. The `join_code` and `block` columns on `rent_settings` are populated by convention but are not backed by a composite unique constraint, making it possible for inconsistent states to arise if settings are created through unusual paths.

---

## 9. File Index

| File | Role |
|------|------|
| `app/models.py:1186–1309` | `RentSettings`, `RentPayment`, `RentWaiver`, `RentItem` models |
| `app/models.py:336` | `Student.is_rent_enabled` |
| `app/models.py:893` | `StudentBlock.rent_hall_passes` |
| `app/models.py:1060` | `StoreItem.is_rent_linked` |
| `app/routes/student.py:2987–4256` | Rent helper functions + student routes |
| `app/routes/admin.py:5811–6980` | Admin rent routes + helper functions |
| `app/routes/api.py:73–130, 382–420` | Due-date helpers + store purchase block |
| `app/utils/economy_balance.py:281–360` | CWI rent balance validation |
| `app/utils/economy_rebalance.py:33–92` | Rent rebalance effective-date logic |
| `templates/student_rent.html` | Student rent dashboard |
| `templates/admin_rent_settings.html` | Admin rent settings UI |

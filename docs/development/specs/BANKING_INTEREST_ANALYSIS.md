# Banking Interest Feature: Comprehensive Analysis Report

**Date:** 2026-05-19  
**Branch:** `codex/v2.0`  
**Scope:** Analysis of the current implementation of banking interest — schema, setup, triggering, calculation, and disbursement, with focus on simple vs. compound interest logic and implementation gaps.

---

## 1. Database Schema

**Table:** `banking_settings`

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `savings_apy` | `Numeric(8,6)` | `0.000000` | Annual Percentage Yield, e.g., `5.0` = 5% |
| `savings_monthly_rate` | `Numeric(8,6)` | `0.000000` | Monthly rate (stored but not used in execution logic) |
| `interest_calculation_type` | `String(20)` | `'simple'` | `'simple'` or `'compound'` |
| `compound_frequency` | `String(20)` | `'monthly'` | `'daily'`, `'weekly'`, or `'monthly'` |
| `interest_schedule_type` | `String(20)` | `'monthly'` | `'weekly'` or `'monthly'` |
| `interest_schedule_cycle_days` | `Integer` | `30` | Cycle length in days |
| `interest_payout_start_date` | `DateTime(tz)` | `NULL` | First payout date |
| `class_id` | FK → `classes` | nullable | Class boundary anchor |
| `block` | `String(10)` | nullable | Period/block identifier (NULL = global for class) |

---

## 2. Interest Setup (Configuration)

**Teacher UI (Admin):** Teachers configure banking via `GET /admin/banking` → `banking()` route, which populates a `BankingSettingsForm` and renders `admin_banking.html`. Saved via `POST /admin/banking/settings` → `banking_settings_update()`.

**Fields saved:**
- `savings_apy` — stored as 6-decimal precision Numeric
- `interest_calculation_type` — `'simple'` or `'compound'`
- `compound_frequency` — `'daily'`, `'weekly'`, `'monthly'`
- `interest_schedule_type` and `interest_schedule_cycle_days` — saved to DB
- `interest_payout_start_date` — saved to DB

Settings are **per-class-per-block**, with a fallback to NULL-block (global default for the class). `apply_to_all=true` pushes settings to all enabled blocks for that teacher.

---

## 3. Interest Triggering

> **⚠️ Critical Gap: Interest is never triggered by any scheduled job.**

The `init_scheduled_tasks()` function (`app/scheduled_tasks.py`) registers four scheduled jobs:

1. `enforce_daily_limits` (hourly) — auto tap-out
2. `database_maintenance` (2 AM nightly)
3. `run_rent_cycles` (every hour at :05)
4. `audit_invariant_check` (3 AM nightly)

**No interest disbursement job exists.** There is no scheduled runner that calls `_apply_monthly_savings_interest` or any variant of it across all seats/students.

The only confirmed runtime caller of `apply_savings_interest` is the **test suite** (`tests/test_interest.py`). The `apply_savings_interest()` function in `app/routes/student.py` is exported via `app/__init__.py`'s `__all__` but is not called anywhere in the application's runtime request handlers or schedulers. The v2 authority guardrail test (`tests/test_v2_authority_guardrails.py`) explicitly **asserts** that `apply_savings_interest(` does NOT appear inside the student `dashboard()` source — meaning the old GET-triggered disbursement was intentionally removed and never replaced with a scheduled equivalent.

---

## 4. Calculation Logic

**Execution path:**

```
(No runtime trigger) → app/services/ledger_service.py → _apply_monthly_savings_interest()
```

### Entry Points

| Function | Location | Notes |
|----------|----------|-------|
| `apply_monthly_savings_interest()` | `ledger_service.py:299` | Public FEAT-shell (wraps commit) |
| `_apply_monthly_savings_interest()` | `ledger_service.py:310` | Core logic |
| `apply_savings_interest()` | `routes/student.py:1830` | Legacy compat wrapper; not called at runtime |

### Deduplication Guard

Before calculating, the function checks if a non-void transaction with `description == "Monthly Savings Interest"` already exists for the current calendar month+year:

- **V2 path:** uses class timezone for month/year resolution via `get_class_now(seat.class_id)`
- **Legacy path:** uses UTC via `utc_now()`

If a match is found, returns `None` immediately.

### Eligible Balance Calculation

Iterates all savings transactions for the seat/student and:

- **Excludes:** voided transactions, zero/negative amounts, any transaction where `type == 'Interest'` or `'Interest'` is in the description
- **Only includes** positive savings deposits where `date_funds_available` was ≥ 30 days ago
- Sums qualifying amounts into `eligible_balance`

### Interest Calculation Formula

```python
monthly_rate = annual_rate / Decimal("12")
interest = quantize(eligible_balance * monthly_rate)
```

This is **always simple interest** applied to the sum of qualifying principal deposits, regardless of teacher settings:

> `interest = (Σ eligible principal deposits) × (APY / 12)`

The `interest_calculation_type` and `compound_frequency` fields from `BankingSettings` are **not consulted** during disbursement.

### Disbursement

- **V2 path:** calls `create_pending_transaction(...)` with `type="Interest"` and `description="Monthly Savings Interest"`, creating a PENDING ledger entry that flows through the standard settlement pipeline
- **V1 legacy path:** directly calls `db.session.add(Transaction(...))` — bypasses FEAT layer

---

## 5. Forecast/Projection (Display Only — Not Disbursement Logic)

On the **student transfer page** (`/student/transfer`), the code reads `interest_calculation_type` and `compound_frequency` from `BankingSettings` to render a **display-only** 12-month projection chart:

| Mode | Formula per period |
|------|--------------------|
| Simple | `principal × (APY/12)` on original balance |
| Compound daily | `balance × ((1 + APY/365)^30 − 1)` |
| Compound weekly | `balance × ((1 + APY/52)^4.33 − 1)` |
| Compound monthly | `balance × (APY/12)` ← identical to simple |

**The student dashboard** (`/student/dashboard`) hard-codes `0.045` (4.5% APY) for the `forecast_interest` display, completely ignoring teacher-configured settings:

```python
# app/routes/student.py line 1221
forecast_interest = _quantize_currency(savings_balance * Decimal('0.045') / Decimal('12'))
```

Only the transfer page reads the actual `BankingSettings`.

---

## 6. Gaps in Implementation Logic

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| G1 | **No scheduled interest disbursement** | 🔴 Critical | No scheduled job calls `_apply_monthly_savings_interest` on any student/seat. `interest_payout_start_date` and `interest_schedule_type` are stored but never read by any execution logic. |
| G2 | **`interest_calculation_type` ignored at disbursement** | 🔴 Critical | `_apply_monthly_savings_interest` always uses `annual_rate / 12` regardless of whether the teacher chose `'simple'` or `'compound'`. Compound logic exists only in the display/projection code. |
| G3 | **`compound_frequency` ignored at disbursement** | 🔴 Critical | `'daily'`, `'weekly'`, `'monthly'` compound frequency has no effect on actual payouts. |
| G4 | **V1 legacy path bypasses FEAT layer** | 🔴 Critical (arch) | The legacy branch inside `_apply_monthly_savings_interest` directly calls `db.session.add()` on a `Transaction`, violating the v2 FEAT/domain authority model (INV-ARC-001). |
| G5 | **Settings not passed to the disbursement function** | 🟡 Medium | `apply_savings_interest()` always passes the hardcoded default `annual_rate=0.045` without reading `BankingSettings.savings_apy`. |
| G6 | **`savings_monthly_rate` field unused in execution** | 🟡 Medium | Stored and form-exposed but the execution path only uses `annual_rate` (from `savings_apy`). The "monthly rate" input mode is dead. |
| G7 | **Annual rate defaults to hardcoded 4.5%** | 🟡 Medium | Both `_apply_monthly_savings_interest` and the dashboard forecast fall back to `Decimal("0.045")` when no banking settings exist — hidden default invisible to teachers. |
| G8 | **Dashboard forecast ignores teacher-configured APY** | 🟡 Medium | `forecast_interest` on the student dashboard is hardcoded to 4.5% APY; only the transfer page reads the actual `savings_apy` setting. |
| G9 | **Eligible balance ignores savings withdrawals** | 🟡 Medium | The eligible balance logic sums all positive non-interest savings deposits older than 30 days without subtracting outflows. A student who has withdrawn most of their savings still earns interest on the full historical deposit total. |
| G10 | **Simple interest projection uses current balance, not principal** | 🟠 Low | In the transfer page projection, the `'simple'` branch uses `savings_balance` (which includes prior interest credits) as the base — inconsistent with the label "Simple interest: calculate only on principal." |
| G11 | **`interest_payout_start_date` and `interest_schedule_cycle_days` are dead config** | 🟠 Low | Stored and displayed in the UI; read by zero execution code. No logic checks "has enough time elapsed since payout start." |
| G12 | **Weekly schedule option unsupported** | 🟠 Low | `interest_schedule_type = 'weekly'` is offered in the UI but the deduplication guard is calendar-month-based — weekly payouts would be suppressed after the first monthly disbursement. |
| G13 | **Compound monthly formula collapses to simple** | 🟠 Low | In the projection code, `'compound'` + `'monthly'` uses `balance × (APY/12)`, which is arithmetically identical to simple monthly interest. |

---

## 7. Summary

The interest schema is comprehensive and well-modeled, but the execution layer is largely unimplemented beyond a prototype state:

- **No interest is ever paid out in a running production instance** because no scheduled job calls the disbursement function.
- **`interest_calculation_type` (simple/compound)** and **`compound_frequency`** settings only drive a read-only display chart; the actual ledger disbursement always uses the same simple monthly rate formula.
- **`interest_payout_start_date`**, **`interest_schedule_type`**, **`interest_schedule_cycle_days`**, and **`savings_monthly_rate`** fields are inert — stored but never consumed by any runtime logic.

### Recommended Next Steps

1. Implement a scheduled interest disbursement job (e.g., nightly cron) that iterates all active `Seat` records, reads the class's `BankingSettings`, and calls `apply_monthly_savings_interest` with the correct `annual_rate`.
2. Plumb `BankingSettings.savings_apy` (and `interest_calculation_type`, `compound_frequency`) into `_apply_monthly_savings_interest` so disbursed amounts reflect teacher-configured rates.
3. Implement true compound disbursement logic inside `_apply_monthly_savings_interest` (currently only the projection display implements this).
4. Fix the eligible balance calculation to account for savings withdrawals (i.e., use net savings balance, not raw deposit sum).
5. Implement `interest_payout_start_date` / `interest_schedule_cycle_days` gating so interest only pays on the configured schedule.
6. Remove or migrate the V1 legacy path that bypasses the FEAT layer.

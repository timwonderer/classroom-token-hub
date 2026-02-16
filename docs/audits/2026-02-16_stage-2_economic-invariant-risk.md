# Stage 2 – Economic Invariant Risk Audit

**Date:** 2026-02-16
**Status:** Complete
**Auditor:** Jules (AI Agent)

## Objective
Identify logic that could compromise financial invariants, ledger integrity, tenant isolation, or audit trails.

## Scope
*   Payroll logic
*   Transactions & Void logic
*   Balance calculations
*   Multi-tenant boundaries
*   Redemption flow

## Findings

### 1. Multi-tenant Balance Leakage (Global Balance Calculation)
*   **Severity:** Critical
*   **File:** `app/models.py`
*   **Line Range:** ~190-210 (`Student.checking_balance`, `Student.savings_balance`)
*   **Category:** Multi-tenant Boundary Violation
*   **Description:** The `checking_balance` and `savings_balance` properties on the `Student` model calculate the sum of `Transaction.amount` filtering only by `student_id`. They do not filter by `join_code`.
*   **Why This Violates Financial Invariants:** In this multi-tenant architecture, a `join_code` represents a distinct economy (Class). By summing globally, funds earned in one class (e.g., "Period 1") are available for spending in another class (e.g., "Period 2") if the student uses the same account. This breaks the isolation of class economies.
*   **Worst Case Scenario:** A student earns massive amounts in a "test" or "easy" class and uses those funds to purchase high-value items or disrupt the economy in a "strict" or "real" class.
*   **Confidence:** 100%

### 2. Void Logic Double Deduction
*   **Severity:** Critical
*   **File:** `app/routes/admin.py`
*   **Line Range:** ~5100-5150 (`void_payroll_transaction`)
*   **Category:** Financial Logic Error
*   **Description:** When voiding a transaction, the code performs two actions:
    1.  Sets `transaction.is_void = True`.
    2.  Creates a *new* reversal transaction with a negative amount (`-amount`).

    The balance calculation (`app/models.py`) sums all transactions where `is_void == False`.
    *   The original transaction is excluded (balance - X).
    *   The reversal transaction is included (balance - X).
*   **Why This Violates Financial Invariants:** This results in the amount being deducted twice from the student's balance.
*   **Worst Case Scenario:** A teacher corrects a mistake (voids a payroll), and the student is penalized double the amount, potentially driving their balance negative and destroying trust in the banking system.
*   **Confidence:** 100%

### 3. Random Ledger Assignment in Bulk Bonuses
*   **Severity:** High
*   **File:** `app/routes/admin.py`
*   **Line Range:** ~620-660 (`give_bonus_all`)
*   **Category:** Ledger Integrity / Logic Error
*   **Description:** The function constructs a `join_code_map` dictionary: `{student_id: join_code}`. If a student is enrolled in multiple classes (blocks) with the same teacher, the dictionary comprehension overwrites previous entries, leaving only the `join_code` of the last processed block. The bonus transaction is then created using this single `join_code`.
*   **Why This Violates Financial Invariants:** The bonus is applied to an arbitrary class economy. The student receives the money, but it appears in the wrong ledger, or only in one ledger when it might have been intended for all (or a specific one).
*   **Worst Case Scenario:** Financial records become corrupt as funds appear in class ledgers where no corresponding activity (attendance/behavior) occurred, making per-class reporting inaccurate.
*   **Confidence:** 95%

### 4. Float Usage in Financial Calculations
*   **Severity:** High
*   **File:** `app/models.py`, `app/routes/api.py`
*   **Line Range:** Multiple
*   **Category:** Precision Error
*   **Description:**
    *   `Student.checking_balance` returns a `float`.
    *   `Transaction.amount` is a `Decimal`.
    *   `app/routes/api.py` performs comparisons using floats (e.g., `if student.checking_balance < amount:`).
*   **Why This Violates Financial Invariants:** Floating-point arithmetic is imprecise for currency. `0.1 + 0.2 != 0.3`. Mixing `float` and `Decimal` can lead to subtle comparison failures (e.g., allowing a purchase when balance is `0.000000001` less than price, or blocking valid purchases).
*   **Worst Case Scenario:** Ledger drift over time; "phantom pennies" appearing or disappearing; strict equality checks failing in reconciliation scripts.
*   **Confidence:** 100%

### 5. Hard Deletion of Financial Records
*   **Severity:** Medium
*   **File:** `app/routes/admin.py`
*   **Line Range:** ~450-500 (`_hard_delete_join_code_scope`)
*   **Category:** Audit Trail Violation
*   **Description:** The `_hard_delete_join_code_scope` function executes `DELETE` statements on the `transactions` table when a class is deleted.
*   **Why This Violates Financial Invariants:** Financial systems generally require immutable audit trails. Even if a class is "deleted", the record of financial transactions should ideally be archived or soft-deleted to maintain a history of system activity and prevent fraud (e.g., a teacher deleting a class to hide illicit transfers).
*   **Worst Case Scenario:** A dispute arises regarding past payments or a system bug, but the data is permanently gone, making investigation impossible.
*   **Confidence:** 100%

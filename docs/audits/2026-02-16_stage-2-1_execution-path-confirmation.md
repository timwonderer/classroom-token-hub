# Stage 2.1 – Execution Path Confirmation

## Summary
This audit validates the reachability and runtime impact of findings from the Stage 2 Economic Invariant Risk Audit. The analysis confirms that **Critical** findings related to multi-tenant balance leakage and void logic are actively reachable in production flows. The **High** risk finding regarding bulk bonuses appears to be an orphaned route not exposed in the current UI.

## Finding 1 – Multi-tenant Balance Leakage (Global Balance Calculation)

### Call Graph
*   **Definition:** `app/models.py:290-300` (`Student.checking_balance`, `Student.savings_balance`)
*   **Active Callers:**
    *   `app/routes/api.py:456`: `if student.checking_balance < total_price:` (Inside `purchase_item`)
    *   `app/routes/api.py:457`: `shortfall = total_price - student.checking_balance`
    *   `app/routes/admin.py:680` (approx): `total_balance = sum(s.checking_balance ...)` (Admin Dashboard stats)

### Join Code Enforcement
*   **Property Definition:** The properties iterate `self.transactions` without filtering by `join_code`.
*   **API Usage (`purchase_item`):** The purchase authorization logic uses these global properties directly. While the subsequent transaction *write* uses `join_code`, the *check* for sufficient funds sums all classes.
*   **Student Dashboard Usage:** `app/routes/student.py` correctly uses `get_checking_balance(join_code=...)` or inline filtering, avoiding display errors for the student.

### Reachability Classification
**Actively reachable in production flow.**
Any student enrolled in multiple classes can exploit this to spend funds earned in Class A within Class B via the standard purchase API.

### Confidence
100%

## Finding 2 – Void Logic Double Deduction

### Call Graph
*   **Definition:** `app/routes/admin.py:6456` (`void_payroll_transaction`)
*   **Active Callers:**
    *   `templates/admin_payroll.html`: `fetch('/admin/payroll/transactions/${transactionId}/void', ...)`

### Join Code Enforcement
*   The logic correctly propagates `join_code` to the reversal transaction.
*   **The Flaw:** It sets `is_void=True` on the original *and* creates a negative reversal. The balance calculation excludes voided transactions and includes the negative reversal, effectively deducting the amount twice.

### Reachability Classification
**Actively reachable in production flow.**
Teachers clicking "Void" on the Payroll History tab will trigger this double deduction.

### Confidence
100%

## Finding 3 – Random Ledger Assignment in Bulk Bonuses

### Call Graph
*   **Definition:** `app/routes/admin.py:899` (`give_bonus_all`)
*   **Active Callers:** None found in `templates/`.
    *   `templates/admin_payroll.html` uses `payroll_manual_payment` instead.

### Join Code Enforcement
*   The function iterates students and overwrites `join_code` in a dictionary loop, resulting in a random single class assignment for multi-class students.

### Reachability Classification
**Only reachable via unused route.**
The route `/admin/bonuses` exists but has no UI entry point. It is technically callable via API tools but is not part of the standard user flow.

### Confidence
90%

## Finding 5 – Hard Deletion of Financial Records

### Call Graph
*   **Definition:** `app/routes/admin.py:258` (`_hard_delete_join_code_scope`)
*   **Active Callers:**
    *   `app/routes/admin.py:2779`: `delete_block`
    *   `app/routes/admin.py:2817`: `delete_join_code`
    *   `templates/admin_students.html`: "Delete All Students in [Block]" button calls `delete_block`.

### Join Code Enforcement
*   The function deletes based on `join_code`.
*   **The Flaw:** It executes `DELETE FROM transaction ...` which permanently destroys the audit trail.

### Reachability Classification
**Actively reachable in production flow.**
Teachers deleting a class section will permanently erase all financial history for that economy.

### Confidence
100%

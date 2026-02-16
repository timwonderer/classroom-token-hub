# Stage 2 – Economic Invariant Risk Audit

**Date:** 2026-02-16
**Status:** Complete

## Findings

### 1. Cross-Tenant Fund Leakage in Purchase Authorization
**Severity:** Critical
**File:** `app/routes/api.py`
**Line Range:** 408-413
**Category:** Multi-tenant boundaries
**Description:**
The `purchase_item` route authorizes purchases by checking `student.checking_balance` (a global property summing funds across all classes) against the item price, instead of using the class-scoped balance calculated earlier.
**Why This Violates Financial Invariants:**
This allows a student with funds in Class A to purchase items in Class B even if they have $0 or negative balance in Class B. The transaction is then recorded in Class B (correctly scoped), driving Class B's ledger into negative territory based on funds that exist only in Class A. This breaks tenant isolation and fund segregation.
**Worst Case Scenario:**
A student uses funds earned in a high-paying class to drain the economy of a stricter class, effectively counterfeiting currency across tenant boundaries.
**Confidence:** 100%

### 2. Global Balance Properties Violate Tenant Isolation
**Severity:** Critical
**File:** `app/models.py`
**Line Range:** 463-473
**Category:** Multi-tenant boundaries
**Description:**
The `Student.checking_balance` and `Student.savings_balance` properties calculate balances by summing *all* non-void transactions for a student, ignoring `join_code`.
**Why This Violates Financial Invariants:**
Any logic relying on these properties (like the purchase check above, or CSV exports) inherently mixes data from different tenants. A student belonging to multiple classes has no isolated "balance" in this model, only a global aggregate.
**Worst Case Scenario:**
System-wide confusion where students see inflated balances, and financial decisions (overdrafts, purchases) are made on incorrect global aggregates rather than the relevant class economy.
**Confidence:** 100%

### 3. Ledger Mutability via Direct Voiding
**Severity:** High
**File:** `app/routes/admin.py`
**Line Range:** 6597 (void_payroll_transaction), 6629 (void_transactions_bulk), 9454 (resolve_issue)
**Category:** Void logic
**Description:**
Transactions are voided by setting the `is_void` flag to `True` on the original record.
**Why This Violates Financial Invariants:**
Financial ledgers should be immutable. Voids should be implemented as a new transaction with an inverted amount (reversal) linked to the original. Modifying the original record destroys the historical state of the ledger at the time the transaction occurred and complicates point-in-time reconstruction.
**Worst Case Scenario:**
An admin voids a transaction from a closed accounting period, changing historical reports retroactively without a clear audit trail of *when* the void happened.
**Confidence:** 95%

### 4. Precision Loss due to Float Usage
**Severity:** High
**File:** `app/models.py` (Line 467, 473), `app/routes/admin.py` (Line 2225)
**Category:** Balance calculations
**Description:**
Financial values are frequently cast to `float` for calculations or API responses. `Student.checking_balance` explicitly casts `Decimal` to `float`.
**Why This Violates Financial Invariants:**
Floats are imprecise for currency. Accumulating float errors can lead to "penny shaving" issues, where ledger sums do not equal the sum of their parts (e.g., $0.10 + $0.20 != $0.30).
**Worst Case Scenario:**
Balances drift over time due to rounding errors, causing reconciliation failures or allowing students to exploit fractional discrepancies.
**Confidence:** 100%

### 5. Audit Trail Destruction in Join Code Cleanup
**Severity:** Medium
**File:** `app/routes/admin.py`
**Line Range:** 212-313
**Category:** Audit trails
**Description:**
`_hard_delete_join_code_scope` performs hard deletes (`.delete()`) on `Transaction`, `RentPayment`, `InsuranceClaim`, and other financial records.
**Why This Violates Financial Invariants:**
While intended for cleaning up deleted classes, hard deleting financial records prevents any future audit or dispute resolution regarding that data. "Deleted" classes should ideally be archived (soft deleted) or at least their financial history preserved for a retention period.
**Worst Case Scenario:**
A teacher deletes a class by mistake or maliciously to hide embezzlement/fraud, and the financial history is permanently lost.
**Confidence:** 90%

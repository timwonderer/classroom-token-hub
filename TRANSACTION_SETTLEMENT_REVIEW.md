# Transaction Settlement & Invariant Runner Analysis

## Executive Summary

The transaction state handling and balance settlement logic are **fundamentally sound and correct**. Earlier drafts of this document identified a potential timing window for the invariant runner and treated negative-balance settlements as expected/intentional outcomes; both assessments were incorrect. This revision corrects those conclusions based on a closer reading of the implementation and database isolation semantics.

---

## Transaction State Flow

### 1. Transaction Creation
- **Default status**: `POSTED` (models.py:798-800)
- **Lifecycle**: Created → Optional pending → Posted → Optionally void
- **Status enum** (models.py:76-79):
  ```python
  class TransactionStatus(str, enum.Enum):
      PENDING = 'pending'
      POSTED = 'posted'
      VOID = 'void'
  ```
  > **Note:** The values above (`'pending'`, `'posted'`, `'void'`) are the Python enum `.value` strings. The persisted database enum labels are uppercase (`PENDING`, `POSTED`, `VOID`) because the DB enum was created with uppercase labels (`migrations/versions/ec84c1f59c15_add_ledger_and_settlement_models.py:84`) and SQLAlchemy stores the enum *name* by default. All raw SQL queries against the `transaction` table (including invariant checks) must use the uppercase forms.

### 2. Amount Consistency
- **Dual representation**: `amount` (Decimal) + `amount_cents` (Integer)
- **Sync mechanism** (models.py:838-844): Before-insert/before-update event listener automatically syncs `amount_cents` from `amount`
  ```python
  target.amount_cents = int(_quantize_currency(target.amount) * 100)
  ```
- **Why**: Prevents floating-point errors like -0.00 and ensures exact cent tracking

---

## Settlement Workflow

### Entry Point
`app/utils/banking.py::settle_pending_transaction_contexts()`

**For each student/class context:**
1. Lock BalanceCache row (creates if needed)
2. Fetch all PENDING transactions
3. Fetch any legacy POSTED transactions missing `posted_at` timestamp
4. Transition PENDING → POSTED or VOID
5. Compute authoritative posted totals from ledger
6. Update BalanceCache with new totals

### Critical Code Path

```python
# Step 1: Lock cache (banking.py:118-145)
cache = (
    BalanceCache.query
    .filter_by(student_id=student_id, join_code=join_code)
    .with_for_update()  # ← Row-level lock
    .first()
)

# Step 2: Fetch PENDING transactions (banking.py:149-159)
pending_txs = (
    Transaction.query
    .filter_by(
        student_id=student_id, 
        join_code=join_code, 
        status=TransactionStatus.PENDING
    )
    .with_for_update()  # ← Lock all rows
    .all()
)

# Step 3: Populate timestamps, then transition PENDING -> POSTED/VOID (banking.py:187-228)
for tx in pending_txs:
    if not tx.posted_at:
        tx.posted_at = now  # ← Set BEFORE the void check; voided-pending rows also get posted_at
    if tx.is_void:
        tx.status = TransactionStatus.VOID
        if not tx.voided_at:
            tx.voided_at = now
        # Note: tx.posted_at is already populated above even for VOID transitions
    else:
        tx.status = TransactionStatus.POSTED

# Step 4: Compute authoritative total (banking.py:230-233)
# Query ALL POSTED transactions (includes rows just marked POSTED above;
# VOID rows are excluded from this total even though posted_at was populated)
authoritative_checking_cents, authoritative_savings_cents = _authoritative_posted_totals(
    student_id,
    join_code,
)

# Step 5: Update cache atomically (banking.py:240-241)
cache.posted_checking_balance_cents = authoritative_checking_cents
cache.posted_savings_balance_cents = authoritative_savings_cents
cache.last_settlement_at = now
```

---

## Invariant Checks

### 1. Transaction State Validity (`transaction_state.py`)
**Checks**: All transactions have valid status (PENDING, POSTED, VOID)
```sql
SELECT DISTINCT status FROM transaction 
WHERE status NOT IN ('PENDING', 'POSTED', 'VOID')
```
**Status**: ✅ Safe — Settlement only sets valid statuses

---

### 2. Ledger ↔ Balance Cache Consistency (`ledger_consistency.py`)
**Checks**: Sum of POSTED transactions matches BalanceCache for each student/class
```sql
HAVING
    SUM(POSTED checking cents) != bc.posted_checking_balance_cents
    OR
    SUM(POSTED savings cents) != bc.posted_savings_balance_cents
```

**Safety analysis**:
- ✅ Settlement computes authoritative totals from ledger after marking txs as POSTED
- ✅ Updates cache atomically with these totals
- ✅ **Under Postgres READ COMMITTED** (the default): all status updates *and* the cache write happen inside a single DB transaction. Other sessions operating under READ COMMITTED cannot see uncommitted rows, so the invariant runner will observe either the pre-settlement state (old cache, no new POSTED rows) or the post-settlement state (updated cache + new POSTED rows) — never the mid-flight state where rows are POSTED but the cache is stale.
- ⚠️ A mismatch **can** legitimately be observed if: (a) settlement is split across two separate commits, (b) the invariant runner shares the *same* SQLAlchemy session as the in-flight settlement (i.e., it reads its own session's dirty state), or (c) the invariant queries run against a streaming replica with replication lag.

---

### 3. Balance Rules (`balance_rules.py`)
**Checks**:
1. Savings balance never negative
2. Checking balance only negative if overdraft enabled

```sql
-- Savings never negative
SELECT * FROM balance_cache WHERE posted_savings_balance_cents < 0

-- Checking negative without overdraft
SELECT bc.* FROM balance_cache bc
INNER JOIN banking_settings bs ON bs.join_code = bc.join_code
WHERE bc.posted_checking_balance_cents < 0
  AND bs.overdraft_protection_enabled = FALSE
```

**Safety analysis**:
- ✅ Settlement computes correct totals from actual ledger
- ✅ If ledger contains only valid transactions, cache will reflect that
- ✅ **By design, the system prevents negative savings balances at the point of transaction creation**, so settlement should never produce a negative savings cache under normal operation (see enforcement paths below).
- ⚠️ If a negative savings balance *is* observed after settlement, it indicates a pre-existing validation bypass or data corruption — not an expected transient state.

---

## The Timing Window Issue

### When a Mismatch Can Actually Be Observed

The application runs on Postgres, which defaults to **READ COMMITTED** isolation. All settlement writes (transaction status changes + cache update) happen within a **single DB transaction** that is committed atomically after `settle_balances` returns. Under READ COMMITTED, no other session can read uncommitted data, so an external invariant runner will never see a partial state where transactions are POSTED but the cache is not yet updated.

A genuine mismatch would require one of the following:

1. **Split commits**: If settlement were ever refactored to commit the transaction-status updates in one transaction and the cache update in a separate transaction, there would be a window between the two commits.
2. **Shared session / dirty read**: If the invariant runner runs inside the *same* SQLAlchemy session as an in-progress settlement, it would see session-dirty state before the commit (SQLAlchemy's identity map shows the pending writes). This cannot happen today because invariants are run in separate request contexts.
3. **Async read replica lag**: If invariant queries are routed to a streaming replica, replication lag could expose the state from a committed but not-yet-replicated partial write.

```
Under current architecture (Postgres READ COMMITTED, single commit):

[Settlement DB transaction]
  ├─ Mark -$100 PENDING → POSTED       (uncommitted, invisible to other sessions)
  ├─ Compute authoritative total: -$100 (uncommitted, invisible to other sessions)
  ├─ Update cache to -$100             (uncommitted, invisible to other sessions)
  └─ COMMIT ─────────────────────────→ Both POSTED rows and updated cache become
                                        visible atomically to all other sessions
```

### Root Cause (Residual Risk)
1. The theoretical window (residual risk) exists if settlement is split across commits or queries run against a replica.
2. With the current single-commit design on Postgres, a false-positive mismatch is not expected during normal operation.

---

## Balance Rules Enforcement

### How the System Prevents Negative Balances

The negative-balance invariants (`balance_rules.py`) are **not** expected to produce false positives during normal settlement. The system enforces sufficient-funds checks before any transaction reaches the PENDING state:

1. **Student transfers** (`student.py:1827-1837`): Explicitly rejects if `amount > checking_balance` or `amount > savings_balance` — the transaction is never created if it would overdraw.
2. **Admin fines / charges** (`admin.py`, `student.py`): Uses `evaluate_overdraft_allowance()` to determine whether a charge may proceed; if not allowed, the fine is skipped or an overdraft fee path is taken.
3. **Savings invariant** (`balance_rules.py:30-34`): "Savings balance must never be negative" — this is an absolute rule, not a transient state.
4. **Checking overdraft**: Only flagged when `overdraft_protection_enabled = FALSE` is confirmed via INNER JOIN on `banking_settings`.

### What a Balance Rules Failure Actually Means

A `balance_rules` FAIL after settlement means **one of the following**:
- A transaction was created that bypassed the sufficient-funds guard (validation bug).
- Data was modified directly in the DB outside the application layer (corruption).
- A rounding or amount derivation bug accumulated incorrectly across many transactions.

**It does not mean settlement is "working correctly with intentional negative balances."**

### Residual Scenario: Admin-Issued Penalties

There may be specific admin-only write paths (e.g., administrative fines with override capability) where a teacher explicitly authorizes a transaction that results in a negative balance. In those cases, the system is still expected to handle the overdraft logic correctly; the invariant FAIL would indicate the overdraft guard was bypassed rather than operating as intended. Any such path should enforce overdraft rules and update `banking_settings.overdraft_protection_enabled` accordingly so the invariant does not false-flag it.

---

## Current Safeguards

### 1. Transactional Isolation
- Settlement uses `with_for_update()` locks on BalanceCache and Transaction rows
- Updates are atomic within the Flask app context

### 2. Authoritative Recomputation
- Settlement doesn't update balances incrementally
- It recomputes from scratch from the ledger: `_authoritative_posted_totals()`
- This prevents cumulative rounding errors

### 3. Read-Only Guard
```python
# From banking.py:109-110
if getattr(g, "read_only", False):
    raise RuntimeError("Settlement attempted during read-only request context")
```

### 4. Ledger Immutability
- Transactions are append-only (via settlement flow)
- Can't modify posted amounts (only add new compensation transactions)

---

## Potential Issues

### Issue #1: Invariants Running During Settlement
**Severity**: Low (not a real risk under current architecture)
**Likelihood**: Negligible under Postgres READ COMMITTED

**Analysis**:
- Settlement runs entirely within a single DB transaction; Postgres READ COMMITTED prevents other sessions from seeing uncommitted writes.
- The only realistic risk scenarios are: (a) invariants share the same SQLAlchemy session as in-flight settlement, (b) settlement is refactored to split across multiple commits, or (c) invariant queries are routed to a streaming replica with lag.
- **Recommendation**: Maintain the single-commit settlement design. If routing reads to replicas in the future, exclude invariant-runner queries from replica routing or add a configurable replica lag tolerance.

---

### Issue #2: Balance Rules Flagging a Genuine Violation
**Severity**: High (if it occurs)
**Likelihood**: Very low under normal operation

**What it means**: A `balance_rules` FAIL is **not** a false positive from settlement. It indicates a real problem: a transaction bypassed the sufficient-funds guard, data was manipulated outside the application, or a rounding bug accumulated. The invariant is correctly identifying corruption or a validation gap.

**Current behavior**:
- Savings violations are flagged unconditionally (savings must never be negative).
- Checking violations are only flagged when overdraft is explicitly disabled — uses INNER JOIN to banking_settings to avoid false positives where RLS filters rows.

**Recommendation**:
- Investigate the write path that produced the negative balance.
- Do **not** add a "settlement in progress" flag to suppress this invariant — it protects a real invariant and masking it would hide data corruption.
- If admin-override fine paths can legitimately produce negative savings balances, those paths should be explicitly documented and guarded, with corresponding tests.

---

## Recommended Improvements

### 1. Guard Against Split-Commit Refactors
Add an assertion or comment in `settle_balances()` making explicit that the cache write and transaction status updates must remain in the same DB transaction:
```python
# IMPORTANT: All status updates and cache writes MUST be committed in a single
# DB transaction. Splitting into two commits creates a window where the
# ledger_consistency invariant will observe a mismatch (POSTED rows but stale cache).
```

### 2. Invariant Runner: Note Replica Routing
If invariant queries are ever routed to a read replica, add a note to each invariant module:
```python
# WARNING: Do not run this invariant against a streaming replica. Replication lag
# can expose a state where transaction rows are POSTED but the cache write has not
# yet replicated, producing a spurious FAIL.
```

### 3. Add Settlement Timeline to Invariant Output
```python
# Add last_settlement_at to invariant output for debugging context
result = {
    "name": "ledger_balance_consistency",
    "status": "PASS",
    "last_settlement_at": cache.last_settlement_at.isoformat() if cache else None,
}
```

### 4. Concurrency Tests
```python
def test_no_partial_state_visible_during_settlement():
    # In a separate connection, poll ledger_consistency invariant
    # while settlement is running in the main session.
    # Assert invariant never returns FAIL during settlement.
```

---

## Verdict

### Transaction State Handling ✅
- **Status**: Correct
- **No issues found**
- **Note**: DB stores uppercase enum labels (`PENDING`/`POSTED`/`VOID`); Python enum `.value` strings are lowercase.

### Settlement Logic ✅
- **Status**: Correct and safe
- **Locking is proper**
- **Authoritative recomputation prevents drift**
- **Correction**: `posted_at` is populated for all pending rows (including voided ones) before the void check — voided-pending rows will have `posted_at` set in addition to `voided_at`.

### Invariant Runner ✅
- **Status**: Works correctly; does not produce false positives during normal settlement
- **Why**: Under Postgres READ COMMITTED, all settlement writes are invisible to other sessions until the single DB transaction is committed atomically. The invariant runner operates in a separate session and will never observe a mid-flight state.
- **Residual risk**: Only if settlement is split across multiple commits, invariants share the same SQLAlchemy session, or queries run against a lagging replica.

### Balance Settlement & Invariants Integration ✅
- **Status**: Invariants correctly reflect real violations — not false positives
- **Correction**: Negative savings balances are **not** expected or intentional outcomes of settlement. The system enforces sufficient-funds checks at transaction creation time. A `balance_rules` FAIL after settlement indicates a real bug or data corruption, not a transient state.
- **Recommendation**: Treat `balance_rules` FAIL as a high-severity alert requiring investigation of the write path that bypassed the guard.

---

## Testing Recommendations

### 1. Verify No Partial State Observed During Settlement
```python
def test_no_partial_state_visible_during_settlement():
    # Run settlement in one session; poll ledger_consistency invariant
    # in a *separate* DB connection concurrently.
    # Assert: invariant never returns FAIL during settlement.
    # (Validates single-commit atomicity guarantee under READ COMMITTED)
```

### 2. Large Pending Transaction Batches
```python
def test_settlement_with_1000_pending_transactions():
    # Create many PENDING transactions
    # Settle them
    # Verify cache matches ledger exactly
```

### 3. Voided-Pending Timestamp Behavior
```python
def test_voided_pending_transaction_has_posted_at():
    # Create a PENDING transaction, set is_void=True
    # Run settlement
    # Verify tx.status == VOID
    # Verify tx.posted_at is NOT NULL (populated before void check)
    # Verify tx.voided_at is NOT NULL
```

### 4. Insufficient Funds Guard Prevents Negative Savings
```python
def test_transfer_rejects_amount_exceeding_savings_balance():
    # Attempt a savings withdrawal larger than current balance
    # Assert: transaction is rejected, no PENDING row created
    # Assert: balance_rules invariant still passes after attempt
```

---

## Summary Table

| Component | Status | Issues | Severity |
|-----------|--------|--------|----------|
| Transaction creation | ✅ | None | N/A |
| Transaction state enum | ✅ | DB stores uppercase labels; Python values lowercase | Note |
| Settlement locking | ✅ | None | N/A |
| Settlement POSTED marking | ✅ | `posted_at` set before void check (voided rows also get `posted_at`) | Note |
| Cache update atomicity | ✅ | None | N/A |
| Invariant: transaction_state | ✅ | None | N/A |
| Invariant: ledger_consistency | ✅ | No false positives under READ COMMITTED single-commit design | N/A |
| Invariant: balance_rules | ✅ | FAIL = real violation, not expected transient state | N/A |
| Overall safety | ✅ | No data corruption risk | N/A |

---

## Conclusion

The transaction settlement logic is **well-designed and safe**. The four original concerns are resolved as follows:

1. **Enum values**: The Python enum `.value` strings are lowercase, but the persisted DB labels are uppercase (`PENDING`, `POSTED`, `VOID`). Raw SQL must use uppercase.
2. **`posted_at` ordering**: `posted_at` is populated before the void check, so voided-pending rows also carry a `posted_at` timestamp in addition to `voided_at`. This is harmless but should be noted in documentation.
3. **Timing window**: Under Postgres READ COMMITTED, the settlement's single DB transaction is invisible to other sessions until committed atomically. No false-positive invariant mismatch is expected during normal settlement. The residual risk (replica lag, shared session, or split commits) is a future-design concern, not a current bug.
4. **Negative-balance invariants**: `balance_rules` FAILs are real violations, not expected or intentional outcomes of settlement. The system enforces sufficient-funds checks before transactions are created; a FAIL means a guard was bypassed or data was corrupted.

The system is working as designed. The recommendations above are for **transparency**, **observability**, and **future-proofing against architectural changes**.

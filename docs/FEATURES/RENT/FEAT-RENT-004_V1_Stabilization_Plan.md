# V1 Stabilization Plan — Rent System

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-RENT-004    | 1.0     | 2026-04-13     | N/A        | Normative       |

**Scope:** Rent System — Operational Hardening  
**Horizon:** V1 lifecycle (through June)  
**Status:** Active

---

## 1. Purpose

Ensure the V1 rent system remains:

- **Stable** — no unexpected crashes or data loss
- **Predictable** — consistent behavior across all entry points
- **Non-destructive** — no partial writes or silent corruption

No architectural changes are permitted under this plan.

---

## 2. Non-Goals

The following are explicitly out of scope for V1:

- No schema changes
- No feature additions
- No behavioral redesign
- No refactor for cleanliness

---

## 3. Stability Strategy

> **Convert catastrophic failure → controlled failure**

Failures must be visible, recoverable, and scoped. Silent corruption and unhandled exceptions are not acceptable outcomes.

---

## 4. Required Fixes (High Priority)

### 4.1 Centralize Payment Validation

**Create:** `_filter_valid_rent_payments(...)`

Replace all inline payment ↔ transaction matching logic across routes with a single shared function.

**Goal:** eliminate drift between the six or more locations that independently implement the 300-second timestamp-tolerance match.

---

### 4.2 Pre-Insert Guard

Before creating a `RentPayment` record:

```python
if remaining_amount <= 0:
    abort safely
```

This guard must be evaluated **immediately before** the database insert — not earlier in the request lifecycle — to prevent race-condition windows from allowing duplicate or zero-value payments.

---

### 4.3 Transaction Boundary Protection

Wrap `rent_pay()` in:

- An explicit database transaction
- A rollback on any unhandled failure

**No partial writes allowed.** If any step in the payment flow fails (Transaction insert, RentPayment insert, hall-pass top-off, StudentItem grant), the entire unit must roll back atomically.

---

### 4.4 Duplicate Submission Soft Guard

Implement **one** of the following:

**Option A — Frontend:**
- Disable the payment submit button immediately on click; re-enable on error response.

**Option B — Backend:**
- Check for an existing `RentPayment` for the same `student_id`, `join_code`, and `coverage_month/year` submitted within the last 5 seconds. If found, return a non-error idempotent response.

Either option is acceptable. Do not implement both.

---

### 4.5 Logging (Non-blocking)

Log the following anomalies using the application logger. Do **not** block execution or raise exceptions based on these conditions:

| Anomaly | Log Level |
|---------|-----------|
| `RentPayment` with no matching valid `Transaction` | `WARNING` |
| Negative `remaining_amount` after summing valid payments | `WARNING` |
| Two or more payments for the same student/coverage period within 5 seconds | `WARNING` |

---

## 5. Conditional Fix

### 5.1 Timeline Logic Unification

**If low risk:** The API route (`api.py:_calculate_due_dates`) must be updated to call the same `_calculate_rent_timeline()` function used by the student route. This eliminates the parallel implementation that can silently diverge.

**If risky:** Leave unchanged and accept the known divergence as a documented accepted risk.

Risk assessment must be made before any change is attempted. Do not unify if doing so would require changes to call signatures, imports, or shared state that touch more than the timeline function itself.

---

## 6. Known Accepted Risks

The following deficiencies are **explicitly accepted** for V1 and will not be fixed:

| Risk | Notes |
|------|-------|
| Timestamp-based transaction matching (300s tolerance) | Non-ideal but functional in practice |
| No FK integrity between `RentPayment` and `Transaction` | Voided payments are handled by soft filtering |
| Duplicated due-date logic in `api.py` vs `student.py` | Accepted if 5.1 is deemed risky |
| O(N) validation queries per payment check | Acceptable at current class sizes |
| Monolithic `rent_settings()` admin route (~600 lines) | Deferred to V2 refactor |

These will **not** be fixed in V1.

---

## 7. Operational Guardrails

The following behaviors must not change as a result of any stabilization fix:

- `rent_settings` behavior (admin form logic, block-level inheritance)
- Waiver semantics (`waiver_start_date ≤ coverage_due_date ≤ waiver_end_date`)
- Rate locking (`_get_locked_rent_amount_for_join_code_cycle`)
- All UI flows affecting student-facing payment pages

---

## 8. Incident Response Rule

If the rent system breaks in production:

1. Disable the rent feature flag if necessary to stop further impact
2. Restore from the last known working state
3. **Do not** attempt deep fixes under production pressure
4. Defer root cause analysis and resolution to V2

---

## 9. Freeze Directive

After stabilization fixes (Section 4) are applied:

> **The rent system enters feature freeze.**

Only the following change types are permitted post-freeze:

- **Crash prevention** — fixing unhandled exceptions that cause 500 errors
- **Data corruption prevention** — preventing partial writes or silent data loss

All other changes require escalation to V2.

---

## 10. Success Criteria

The V1 rent system is considered stable when all of the following hold under normal use:

| Criterion | Measurement |
|-----------|-------------|
| No 500 errors during normal payment or settings flows | Zero unhandled exceptions in production logs |
| No duplicate payments in practice | No two `RentPayment` rows for the same student/coverage period unless they represent valid incremental payments |
| No inconsistent UI states across pages | Student rent dashboard and admin overview agree on paid/unpaid status |
| Failures are recoverable and visible | All anomalies appear in application logs; failed payments roll back cleanly |

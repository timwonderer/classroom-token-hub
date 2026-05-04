# FEAT-VIOLATION-CATEGORIZATION: Execution Integrity Migration Map

**Last Updated:** 2026-04-25  
**Status:** Active categorization baseline; runtime stabilization in progress

This document categorizes the 156 identified FEAT Constitutional violations into a tiered migration plan.

**2026-04-25 Note:** The tier model remains the prioritization authority. The violation counts in this document are classification-era totals and not a live unresolved-count feed.

| Priority | Risk Profile | Target | Violation Count (Est) |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | High Financial/Identity Risk | Money, Obligations, PII Binding | 45 |
| **MEDIUM** | Operational State Risk | Attendance, Store Config, Issues | 70 |
| **LOW** | Low Impact / Support | Admin Tools, Cleanup, CLI | 41 |

---

## I. CRITICAL MIGRATIONS (Tier 1)
*Must be migrated first to secure the economic core.*

### 1. Money & Ledger (`app/utils/banking.py`, `app/payroll.py`)
- Direct balance updates in payroll.
- Interest calculation and overdraft fee application.
- Legacy transfer logic.

### 2. Identity & Recovery (`app/routes/recovery.py`, `app/routes/auth.py`)
- Seat claiming outside `FEAT-IDEN-001`.
- Passwordless login state mutations.
- Teacher account recovery.

### 3. Obligations (`app/utils/overdraft.py`, `app/utils/economy_rebalance.py`)
- Automatic rent assessment logic.
- Delinquency status updates.

---

## II. MEDIUM MIGRATIONS (Tier 2)
*Ensures operational consistency for student/teacher interaction.*

### 1. Attendance (`app/attendance.py`, `app/routes/api.py`)
- Session creation/closing.
- Hall pass quota consumption.

### 2. Store & Items (`app/utils/store.py`, `app/routes/student.py`)
- Inventory decrements.
- Standard purchase recording.

### 3. Issue Tracking (`app/utils/issue_helpers.py`)
- Ticket status transitions.
- Reward fulfillment.

---

## III. LOW MIGRATIONS (Tier 3)
*Maintenance and non-student facing tools.*

### 1. System Admin (`app/routes/system_admin.py`)
- Global maintenance toggles.
- Teacher deletion/audit.

### 2. Scheduled Tasks (`app/scheduled_tasks.py`, `app/cli_commands.py`)
- Expired session cleanup.
- Database maintenance.

---

## IV. Enforcement Policy
1. **New Code**: Zero tolerance. PRs introducing new `commit()` or `flush()` calls outside `app/feats/` will be blocked.
2. **Refactoring**: When touching a legacy route with a violation, that route MUST be migrated to a FEAT shell as part of the PR.
3. **Emergency**: `FEATBypass` may be used only with a documented reason and is strictly blocked in production.

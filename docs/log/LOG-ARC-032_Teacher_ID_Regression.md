# Incident Post-Mortem: `teacher_id` Removal Regression

**Date:** 2026-01-12
**Severity:** Critical (Production Regression)
**Impact:** 

- Students unable to claim accounts (Validation Error 200 OK)
- Students unable to transfer funds (Internal Server Error)
- Admin/System Admin crash on legacy cleanup logic (Internal Server Error)
- Deployment blocked/diverged due to missing foreign key handling in initial migration.

## 1. Executive Summary
On January 11-12, 2026, a schema migration to remove the legacy `teacher_id` column from the `students` table was deployed. This change caused widespread regressions in critical user flows (account claiming, transfers) because the application code still contained hidden dependencies on this column, despite an initial audit. The regression required an emergency hotfix and a sync with `main` to resolve.

## 2. Root Cause Analysis (Systemic)

**Reframed Root Cause:** Process Design Failure.
While the immediate cause was lingering code references, the underlying failure was the **absence of a formal compatibility window** (Expand and Contract strategy) for schema contraction. The attempt to delete legacy schema (DB) and enforcement (Model) simultaneously left zero margin for error.

### Canonical Failure Pattern
This incident followed a repeatable dangerous pattern:

1.  **Schema Pivot:** Transition from single-tenant (`teacher_id`) to multi-tenant (`StudentTeacher`) association.
2.  **False Cleanliness:** Audit via `grep` appeared clean, missing indirect usages.
3.  **Mechanical Test Fixes:** Tests were adjusted to match the new constructor signature without validating if the logic *inside* needed the data.
4.  **Legacy Runtime Paths:** Critical flows (claim, transfer, cleanup) exercised legacy logic only in production.
5.  **Hard Delete:** Concurrent removal of Column and Model attribute turned silent coupling into crashes.

## 3. Corrective Policies

### A. Enforceable Schema Change Gate
All schema-affecting changes must pass the **Expand / Contract** gate:

1.  **Release 1 (Expand):** Application reads new schema; old schema exists and is populated/ignored.
2.  **Release 2 (Contract Code):** Attribute removed from SQLAlchemy Model. DB column REMAINS. Application must run fully without it.
3.  **Release 3 (Contract DB):** Migration drops the column.

### B. Technical Guardrails
1.  **Deprecated Symbols:** Deprecated attributes must be listed and checked by CI.
2.  **Model-Only Removal:** Removing the Model attribute *before* the DB column is mandatory to force runtime discovery of hidden dependencies.

### C. Migration Robustness
1.  **Constraint Agnosticism:** Migrations must use dynamic inspection to find constraint names. Never hardcode names like `students_teacher_id_fkey`.
2.  **Rehearsal:** Migrations must be verified against a production-like clone (same schema history).

### D. Testing Policy
1.  **No Mechanical Fixes:** If a schema change breaks a test setup, the *entire test* must be reviewed for logic dependencies.
2.  **Critical Workflow Coverage:** Account claiming, Money transfer, and Student creation must have valid route-level tests.

## 4. Prevention Plan (Action Items)

### Immediate Actions coverage
- [x] Fix all remaining `teacher_id` references (Completed).
- [x] Verify `task.md` checklists are accurate.

### Process Improvements (To be added to DEVELOPMENT.md)
1.  **Schema Safe-Removal Policy**:
    - Mandatory 3-step process for column removal:
        1.  **Code Scorn**: Rename column in model/DB to `deprecated_col` or remove all python references while keeping DB column.
        2.  **Ignored**: Use `deferred()` or exclude from model to ensure App runs without it.
        3.  **Drop**: Dedicated release solely for the migration.

2.  **Migration Robustness**:
    - Migrations interacting with Constraints must use dynamic inspection (like the fix in `1e07c37d3c7c`) instead of hardcoded names.

3.  **Testing Strategy**:
    - "Smoke Test" critical paths (Claim, Transfer, Layout) manually or via end-to-end tests before merging a schema change.
    - If a test fails due to Model changes, the *entire test logic* must be reviewed, not just the setup.

### Long-Term
- Implement **Continuous Integration (CI)** that runs migrations against a production-like clone to catch constraint name mismatches.
- Add **Static Analysis** to CI to catch attribute errors (`Student.teacher_id`) before runtime.

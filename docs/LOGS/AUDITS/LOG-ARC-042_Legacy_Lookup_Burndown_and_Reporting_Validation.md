# LOG-ARC-042: Legacy Lookup Burndown and Reporting Validation

**Date:** 2026-03-07  
**Branch:** `codex/fix-database-model-for-dob-sum-storage`

## Scope

This snapshot tracks progress on three priorities:

1. Add regression coverage for cross-join-code mutation attempts.
2. Produce a concrete legacy lookup (`teacher_id`-anchored) burndown.
3. Validate seat-scoped identity behavior in reporting/export/diagnostics paths.

## 1) Regression Coverage Added

New tests in [tests/test_api_tenancy.py](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_api_tenancy.py):

- `test_admin_block_tap_settings_get_ignores_out_of_scope_join_code_row`
- `test_admin_block_tap_settings_post_preserves_out_of_scope_join_code_row`

These cover class-scope correctness for `/api/admin/block-tap-settings` GET/POST when a shared student has a conflicting `StudentBlock` row from another join code.

## 2) Legacy Lookup Burndown Snapshot

Command snapshot (`rg` over runtime files):

- `teacher_id` references across runtime files: **682**
- `teacher_id` references by file (top hotspots):
  - `app/routes/admin.py`: **336**
  - `app/routes/student.py`: **99**
  - `app/routes/api.py`: **75**
  - `app/models.py`: **56**
  - `app/routes/system_admin.py`: **32**
  - `app/routes/analytics.py`: **31**

Interpretation:

- Remaining `teacher_id` usage is still concentrated in route orchestration and legacy compatibility surfaces.
- Not all occurrences are defects (many are compatibility shims or ownership checks), but this identifies where remaining migration effort is largest.

## 3) Reporting/Export/Diagnostics Validation and Hardening

### Diagnostics Endpoint Hardening

Updated [app/routes/api.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/api.py):

- `/api/admin/block-tap-settings` GET now resolves admin-scoped join codes per student+block and ignores out-of-scope `StudentBlock` rows.
- `/api/admin/block-tap-settings` POST now updates only scoped rows and skips conflicting legacy rows that belong to a different join-code scope.

### Export Path Hardening

Updated [app/routes/admin.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py):

- `/admin/export-students` now accepts optional `join_code` and validates it belongs to the logged-in admin.
- With `join_code` set:
  - exported student set is filtered to that class scope,
  - balances/earnings are computed with join-code scoped methods,
  - insurance prefetch is join-code scoped,
  - block column is derived from the scoped seat.

Updated [templates/admin_students.html](/Users/timothychang/Documents/GitHub/classroom-economy/templates/admin_students.html):

- Export action now passes `session.current_join_code` to keep exports aligned with active class context.

### Validation Tests Added

New tests in [tests/test_export_students_scoping.py](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_export_students_scoping.py):

- `test_export_students_scopes_students_and_balances_by_join_code`
- `test_export_students_rejects_invalid_join_code_scope`

## Verification

Executed and passing:

- `pytest -q tests/test_api_tenancy.py -k "block_tap_settings or student_block_settings or tap_entries"`  
  Result: **5 passed**
- `pytest -q tests/test_export_students_scoping.py`  
  Result: **2 passed**

## Next Burndown Targets

1. Reduce route-level `teacher_id` dependency in `app/routes/admin.py` by preferring join-code-first helper interfaces.
2. Audit analytics/report windows for any teacher-global fallback that should be class-scoped when a join code is selected.
3. Continue shrinking compatibility shims where schema and session guarantees now make legacy fallback unnecessary.

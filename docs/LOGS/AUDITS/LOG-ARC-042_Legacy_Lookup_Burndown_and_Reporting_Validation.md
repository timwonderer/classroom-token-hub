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

## 4) Class-Scoped Analytics and Economy API Hardening (2026-03-08)

Updated [app/routes/analytics.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/analytics.py) and [app/utils/analytics_engine.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/utils/analytics_engine.py):

- Selected-class analytics windows (`pay_cycle`, `rent_cycle`) now resolve settings with join-code-first precedence.
- `AnalyticsEngine._get_cwi()` now resolves payroll settings using join-code-first precedence, with legacy block-scoped fallback only.

Updated [app/routes/admin.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py):

- `/admin/economy-health`, `/admin/api/economy/analyze`, and `/admin/api/economy/validate/<feature>` now resolve selected-class payroll/rent/banking settings with join-code-first precedence.
- Block-selected requests no longer fall through to teacher-global `block=None` settings.

Validation tests added/updated:

- [tests/test_analytics.py](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_analytics.py)
- [tests/test_economy_api.py](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_economy_api.py)

Verification:

- `pytest -q tests/test_analytics.py` -> **16 passed**
- `pytest -q tests/test_economy_api.py` -> **26 passed**

## 5) Public Identity Surface Hardening (2026-03-08)

Updated [app/routes/api.py](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/api.py):

- `/api/hall-pass/available-types` now supports `join_code` and `teacher_public_id` as primary identity inputs.
- Student sessions with explicit class context reject out-of-scope `join_code` values.
- Numeric `teacher_id` remains as compatibility fallback.

Validation tests added:

- [tests/test_api_tenancy.py](/Users/timothychang/Documents/GitHub/classroom-economy/tests/test_api_tenancy.py)
  - `test_hall_pass_available_types_accepts_join_code_without_teacher_id`
  - `test_hall_pass_available_types_rejects_out_of_scope_join_code`
  - `test_hall_pass_available_types_supports_teacher_public_id`

## Next Burndown Targets

1. Continue route-level `teacher_id` dependency reduction in `app/routes/admin.py` and `app/routes/student.py` by preferring join-code-first helper interfaces.
2. Complete external identity rollout by replacing remaining user-facing numeric teacher route parameters (for example legacy student switching paths) with `teacher_public_id` or `join_code`.
3. Continue shrinking compatibility shims where schema and session guarantees now make legacy fallback unnecessary.

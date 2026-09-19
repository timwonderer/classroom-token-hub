# Pytest Run Summary (full)

## Run Metadata

- generated_utc: 2026-09-19T05:17:03.763933+00:00
- git_commit: 8c5cff7c8
- pytest_label: full
- exitstatus: 0
- tests_recorded: 2997
- csv: 20260919_pytest_full_results.csv
- failures_log: 20260919_pytest_full_failures.log

## Outcome Counts

- pass: 2983
- skip: 14

## Runtime Stats

- success_percentage: 99.53%
- total_runtime_ms: 704004
- average_duration_ms: 234.90
- median_duration_ms: 1.00

## Slowest 10 Tests

| duration_ms | outcome | nodeid |
|---:|---|---|
| 5214 | pass | tests/test_axe_compliance.py::test_published_pages_have_no_axe_violations |
| 2265 | pass | tests/test_docs_site_image_advisory_guard.py::test_docs_site_has_no_image_assets |
| 1884 | pass | tests/test_admin_store_edit_route.py::test_admin_store_edit_get_rejects_foreign_class_item |
| 1701 | pass | tests/dom/identity/test_unassigned_visibility.py::test_DOM_IDEN_001__cross_teacher_isolation |
| 1482 | pass | tests/dom/ledger/test_seat_balance_serialization.py::test_INV_LED_015__settlement_waits_for_a_debit_holding_the_seat_lock |
| 1436 | pass | tests/dom/identity/test_unclaimed_seat_economic_exclusion.py::test_DOM_IDEN_002__the_roster_modification_feat_also_refuses_an_unclaimed_seat |
| 1399 | pass | tests/dom/identity/test_teacher_lifecycle.py::test_stale_account_destruction_reuses_all_class_teardown |
| 1379 | pass | tests/dom/class/test_feature_scope_single_active_class.py::test_DOM_CLASS_001__feature_options_never_include_sibling_class |
| 1379 | pass | tests/dom/identity/test_teacher_lifecycle.py::test_last_students_delete_only_target_class_when_sibling_exists |
| 1351 | pass | tests/dom/identity/test_teacher_last_class_deletion.py::test_deleting_one_of_several_classes_preserves_the_teacher_principal |

## Failure Groups

No failed/error/xpass outcomes in this run.
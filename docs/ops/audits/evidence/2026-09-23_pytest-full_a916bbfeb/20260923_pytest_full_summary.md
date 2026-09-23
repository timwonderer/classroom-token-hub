# Pytest Run Summary (full)

## Run Metadata

- generated_utc: 2026-09-23T15:03:59.899274+00:00
- git_commit: a916bbfeb
- pytest_label: full
- exitstatus: 1
- tests_recorded: 3597
- csv: 20260923_pytest_full_results.csv
- failures_log: 20260923_pytest_full_failures.log

## Outcome Counts

- error: 16
- fail: 4
- pass: 3561
- skip: 16

## Runtime Stats

- success_percentage: 99.00%
- total_runtime_ms: 783368
- average_duration_ms: 217.78
- median_duration_ms: 1.00

## Slowest 10 Tests

| duration_ms | outcome | nodeid |
|---:|---|---|
| 4942 | pass | tests/test_axe_compliance.py::test_published_pages_have_no_axe_violations |
| 1857 | pass | tests/test_admin_store_edit_route.py::test_admin_store_edit_get_rejects_foreign_class_item |
| 1837 | pass | tests/test_class_configuration_query_service.py::TestSettingsQueries::test_get_hall_pass_settings_multi_tenancy |
| 1647 | pass | tests/dom/identity/test_unassigned_visibility.py::test_DOM_IDEN_001__cross_teacher_isolation |
| 1625 | pass | tests/dom/prod/test_attendance_immutability_enforced.py::test_the_teardown_flag_does_not_outlive_its_transaction |
| 1617 | pass | tests/test_insurance_purchase_route.py::test_already_claimed_transaction_is_excluded_from_the_dropdown |
| 1458 | pass | tests/test_store_item_type_gating_browser.py::test_create_form_shows_enables_and_submits_exactly_each_contract |
| 1441 | pass | tests/dom/ledger/test_seat_balance_serialization.py::test_INV_LED_015__settlement_waits_for_a_debit_holding_the_seat_lock |
| 1430 | pass | tests/dom/attendance/test_hall_pass_verify.py::test_DOM_PROD_002__post_verify_finds_match_beyond_first_20_records |
| 1393 | pass | tests/dom/identity/test_teacher_lifecycle.py::test_stale_account_destruction_reuses_all_class_teardown |

## Failure Groups

### ModuleNotFoundError

- failures: 16
- first_project_frame: tests/test_status_page.py:21
- representative_message: No module named 'google.auth'
- affected_tests:
  - tests/test_status_page.py::test_public_page_separates_measurements_and_notices
  - tests/test_status_page.py::test_stale_snapshot_never_displays_old_latency_as_current
  - tests/test_status_page.py::test_corrupt_persisted_snapshot_fails_closed
  - tests/test_status_page.py::test_not_found_measurement_does_not_claim_system_failure
  - tests/test_status_page.py::test_public_operator_endpoints_remain_unavailable
  - tests/test_status_page.py::test_notice_display_never_invents_timezone[2026-09-22T01:00:00+02:00-2026-09-21 23:00 UTC]
  - tests/test_status_page.py::test_notice_display_never_invents_timezone[2026-09-22T01:00:00-2026-09-22 01:00 (timezone not provided)]
  - tests/test_status_page.py::test_notice_display_never_invents_timezone[invalid-Time unavailable]
  - tests/test_status_page.py::test_notice_display_never_invents_timezone[None-Time unavailable]
  - tests/test_status_page.py::test_mockup_order_and_simple_cards
  - tests/test_status_page.py::test_teacher_estimate_thresholds[20-1-Probably not]
  - tests/test_status_page.py::test_teacher_estimate_thresholds[10-5-Possibly down]
  - tests/test_status_page.py::test_teacher_estimate_thresholds[9-5-Probably not]
  - tests/test_status_page.py::test_teacher_estimate_thresholds[5-0-Not recently verified]
  - tests/test_status_page.py::test_global_unmapped_request_failure_controls_hero
  - tests/test_status_page.py::test_human_notice_prevents_reassuring_hero

### AssertionError

- failures: 1
- first_project_frame: tests/test_design_token_contract.py:50
- representative_message: R5: no inline style attribute that is static on every render
- affected_tests:
  - tests/test_design_token_contract.py::test_SPEC_DES_001__templates_conform[R5]

### AssertionError

- failures: 1
- first_project_frame: tests/test_hall_pass_lifecycle_classification.py:138
- representative_message: assert 'approved' == 'left'
- affected_tests:
  - tests/test_hall_pass_lifecycle_classification.py::test_resolver_reports_left_after_departure

### AssertionError

- failures: 1
- first_project_frame: tests/test_hall_pass_lifecycle_classification.py:157
- representative_message: assert 'approved' == 'returned'
- affected_tests:
  - tests/test_hall_pass_lifecycle_classification.py::test_resolver_reports_returned_after_the_full_round_trip

### StopIteration

- failures: 1
- first_project_frame: tests/test_hall_pass_lifecycle_classification.py:276
- representative_message: 
- affected_tests:
  - tests/test_hall_pass_lifecycle_classification.py::test_history_reports_returned_and_ignores_an_unrelated_stray_active_row

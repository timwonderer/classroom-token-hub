# Pytest Run Summary (full)

## Run Metadata

- generated_utc: 2026-10-15T08:15:18.316161+00:00
- git_commit: 388ffdb91
- pytest_label: full
- exitstatus: 0
- tests_recorded: 5474
- csv: 20261015_pytest_full_results_1.csv
- failures_log: 20261015_pytest_full_failures_1.log

## Outcome Counts

- pass: 5458
- skip: 16

## Runtime Stats

- success_percentage: 99.71%
- total_runtime_ms: 1790085
- average_duration_ms: 327.02
- median_duration_ms: 1.00

## Slowest 10 Tests

| duration_ms | outcome | nodeid |
|---:|---|---|
| 59639 | pass | tests/test_axe_fixture_pages.py::test_no_axe_violations_in_registered_fixture_states |
| 44809 | pass | tests/test_axe_app_pages.py::test_no_axe_violations_across_pages_needing_no_domain_setup |
| 11681 | pass | tests/dom/class/test_policy_lineage_retirement_migration.py::test_upgrade_drops_the_payroll_mirrors_and_both_tables |
| 11274 | pass | tests/dom/prod/test_payroll_settings_authority_migration.py::test_upgrade_remaps_every_event_to_its_classs_payroll_setting |
| 11225 | pass | tests/dom/prod/test_historical_reconstruction_recovery.py::test_genuine_multi_origin_recovery_resolves_aggregate_protection_once[9-False-0--8-9] |
| 10934 | pass | tests/dom/prod/test_historical_reconstruction_recovery.py::test_genuine_v1_reconstruction_recovers_exactly_and_preserves_history[graph] |
| 10911 | pass | tests/dom/prod/test_historical_reconstruction_recovery.py::test_genuine_multi_origin_recovery_resolves_aggregate_protection_once[3-True-0--8-3] |
| 10645 | pass | tests/dom/prod/test_historical_reconstruction_recovery.py::test_genuine_multi_origin_recovery_resolves_aggregate_protection_once[9-True-8-0-1] |
| 10385 | pass | tests/dom/core/test_users_id_uuid_migration.py::test_downgrade_and_upgrade_keep_every_principal_link |
| 10017 | pass | tests/dom/class/test_policy_lineage_retirement_migration.py::test_upgrade_refuses_a_version_outside_payroll |

## Failure Groups

No failed/error/xpass outcomes in this run.
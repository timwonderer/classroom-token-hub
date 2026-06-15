# V2 FEATBypass Dependency Report

**Generated:** 2026-06-10 02:49 UTC
**Commit:** `3a2e70d9`
**Plan:** [V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md](./V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md) — this is the Phase 1 output.

---

## Executive findings

**Dead-route surface is 4 unique mutating endpoints — far smaller than the audit-plan ceiling of ~78** derived from `143 mutating route decls − 65 @feat_shell decorators`. Most undecorated routes delegate to FEAT-wrapped service functions. The Phase 4 dead-route backlog is bounded.

**GET-side-effect surface is 0 unique endpoints.** INV-ARC-007 (GETs must be pure) is largely respected in runtime — a meaningful absence of a finding.

**Fixture-only bypass dependency: 585 tests.** The bulk of Phase 2 migration work is fixture-seeding consolidation, not route fixing. The top callsite hotspot is `tests/helpers/class_scope.py:create_class_scope` (several line numbers — see Fixture callsites section).

**226 of 816 collected tests produced no flushes** — either they errored before reaching any DB operation (the existing baseline failures) or they are pure-read/import tests. The observed cohort is 590.

---

## Methodology

For every test that ran in the suite, a SQLAlchemy `before_flush` listener (installed by `tests/_feat_bypass_audit.py`) inspected the active FEAT stack. Any flush where `FEATBypass` was the only thing in scope — and the session held new/dirty/deleted entities — would have raised `FEATContextError` under production enforcement. Those flushes are the data behind this report.

Each test is bucketed by what its bypass dependency looks like:

- **`passes_under_enforcement`** — no bypass-hidden flushes observed. Test would run cleanly with enforcement on.
- **`fixture_only_bypass`** — bypass-hidden flushes seen during setup/teardown or in test bodies that are not inside a Flask route dispatch. Fixture infrastructure needs an explicit `with FEATBypass():` wrap; the route call itself is not dead.
- **`get_side_effect`** — a bypass-hidden flush happened inside a GET handler. This is an [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) candidate: GETs are required to be side-effect free. Separate category from dead-route since the fix is "remove the write" rather than "add `@feat_shell`".
- **`dead_route_dependent`** — a bypass-hidden flush happened inside a mutating-method (POST/PUT/DELETE/PATCH) route handler. The route is mutating state without `@feat_shell` and would return HTTP 500 under enforcement. **These are the dead routes Phase 4 will need to fix.**

The dispatch discriminator uses the call stack (looking for Flask's `wsgi_app`, `full_dispatch_request`, `dispatch_request`, or `preprocess_request` frames), not `has_request_context()`. pytest-flask leaves a dangling request context around fixture code, so the stack check is the reliable signal for "is a real route handler running right now."

---

## Summary

| Bucket | Tests | % of recorded |
|---|---:|---:|
| Pass under enforcement     |     0 |   0.0% |
| Fixture-only bypass        |   585 |  99.2% |
| GET side-effect            |     0 |   0.0% |
| Dead-route dependent       |     5 |   0.8% |
| **Total tests observed**   | **590** | 100.0% |

_Total tests collected by pytest: 816. Difference vs observed = tests that errored before any flush ran (typically import/collect failures) or tests that produced no flushes at all._

---

## Dead-route inventory — POST/PUT/DELETE/PATCH endpoints flushed under bypass

These mutating-method endpoints performed at least one flush while only `FEATBypass` kept the session-level enforcement quiet. Each is a candidate to either (a) get a `@feat_shell` decorator or (b) confirm it routes mutation through a separately-decorated service function.

| Method | Endpoint | Flush count | First observed in |
|---|---|---:|---|
| POST | `admin.process_claim` | 10 | `tests/test_core_invariants_smoke.py::test_insurance_approval_creates_reimbursement_transaction` |
| POST | `sysadmin.resolve_escalated_issue` | 5 | `tests/test_sysadmin_issue_rewards.py::test_sysadmin_resolve_issue_issues_bug_reward_transaction` |
| POST | `admin.rent_settings` | 2 | `tests/test_rent_settings_class_scope.py::test_rent_settings_update_persists_class_scoped_row` |
| POST | `admin.passkey_auth_finish` | 1 | `tests/test_canonical_auth_session.py::test_admin_passkey_finish_sets_canonical_user_session` |

_4 unique mutating endpoints surfaced; top 4 shown above._

---

## GET-side-effect inventory — INV-ARC-007 candidates

GET handlers are required to be side-effect free. These endpoints flushed mutated state during a GET. The fix is to remove the write (typically a lazy-create or reconciliation pattern), not to add `@feat_shell`.

_No GET-side-effect flushes observed under bypass._

---

## Top fixture-only flush callsites

These are the source locations where bypass-hidden flushes most frequently originate in fixture/setup code. Phase 2 fixture consolidation should target these hotspots first.

| Callsite | Flush count |
|---|---:|
| `tests/helpers/class_scope.py:35 create_class_scope` | 204 |
| `tests/helpers/class_scope.py:50 create_class_scope` | 201 |
| `tests/test_admin_multi_tenancy.py:214 test_system_admin_flag_not_set_accidentally` | 200 |
| `tests/helpers/class_scope.py:95 create_class_scope` | 141 |
| `tests/helpers/class_scope.py:62 create_class_scope` | 41 |
| `tests/test_core_invariants_smoke.py:95 _link_student_to_teacher` | 36 |
| `tests/test_api_tenancy.py:188 _create_class_scope` | 34 |
| `tests/test_api_tenancy.py:36 _create_admin` | 31 |
| `tests/test_api_tenancy.py:66 _create_student` | 26 |
| `tests/test_hall_pass_verify.py:327 test_post_verify_finds_match_beyond_first_20_records` | 25 |
| `tests/test_rent_item_types.py:28 student_in_class` | 25 |
| `tests/test_rent_item_types.py:46 student_in_class` | 25 |
| `tests/test_collective_goal_progress.py:32 _create_student` | 24 |
| `app/services/audit_service.py:345 emit_audit_event` | 23 |
| `tests/test_economy_api.py:29 admin_with_payroll` | 23 |
| `tests/test_economy_api.py:39 admin_with_payroll` | 23 |
| `tests/test_economy_policy_mode.py:81 _create_teacher_seat` | 22 |
| `tests/test_economy_policy_mode.py:95 _create_teacher_seat` | 22 |
| `tests/test_collective_goal_expiration.py:53 _create_student` | 21 |
| `tests/test_economy_policy_mode.py:107 _create_admin_with_block` | 21 |


---

## Raw data

Machine-readable per-test data lives in `V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json`.

# v2 Multitenancy Hardening Matrix

Date: 2026-03-08
Branch: `codex/v2.0`

| Workstream | Must Be True Before v2 live testing | Status | Current Coverage / Evidence | Corresponding Tests |
|---|---|---|---|---|
| Core tenancy boundary | `join_code` is the primary isolation boundary | Complete | `ClassEconomy` and `ClassMembership` are live in ORM and migrations | `tests/test_class_context_and_switching.py`, `tests/test_join_code_generation.py` |
| Public teacher identity | Public teacher references are non-numeric | Complete | `Admin.public_id` aliases `teacher_public_id`; verification APIs use public identity | `tests/test_api_tenancy.py`, `tests/test_route_authorization_sweep.py` |
| Membership auth primitives | Class actions require membership validation | Complete | Admin/API/student hardening uses membership-owned join-code scope | tenancy and membership suites |
| Route authorization sweep | Class-scoped endpoints reject missing or unauthorized scope | Complete for current merge scope | Recent branch merge removed remaining high-risk join-code leaks in admin/api/student flows | `tests/test_admin_tenancy.py`, `tests/test_api_tenancy.py`, `tests/test_multi_teacher_hardening.py` |
| Query inversion | Access control no longer depends on `teacher_id`, `block`, or TeacherBlock fallbacks | Complete for active v2 flows | Current-class decisions and scoped reads use join-code + membership authority | route tests + regression fixes |
| Student class switching | Students switch by join-code/public identity-backed class context | Complete | Numeric switch route is disabled; session uses `current_join_code` | `tests/test_class_context_and_switching.py` |
| Hall-pass verification scope | Public verification uses teacher public identity and teacher-owned join-code scope | Complete | API verification endpoint uses public teacher identifier and membership-derived join codes | `tests/test_api_tenancy.py`, `tests/test_hall_pass_verify.py` |
| Redemption/admin mutation scoping | Admin mutations enforce class access through membership | Complete | Approval, tap-entry, deletion, payroll, and export flows are membership-gated | admin/api tenancy suites |
| Class deletion semantics | Join-code deletion destroys the tenant boundary with guardrails | Complete | Confirmation flow plus hard-delete cleanup is tested | `tests/test_class_deletion.py`, `tests/test_join_code_deletion_semantics.py` |
| Migration head hygiene | Repo has a coherent v2 head state | Complete | Merge migration added and validated in current integration branch | migration review |
| Full regression evidence | PostgreSQL test suite passes on consolidated branch | Complete | `664 passed, 1 skipped` on `classroom_economy_test` | full suite |
| Migration compliance status | Current exceptions and safe operator workflow are documented | In Progress | Historical audit exists; current-state operator doc now needs follow-through and rehearsal | `SOP-DB-009`, `SOP-DEP-022`, `SOP-DEP-023` |
| Archived economy behavior | Archived classes have explicit read-only / mutation policy | Not Started | Not yet documented as a complete runtime contract | doc + test work needed |
| Sysadmin tenancy audit | Sysadmin flows meet the same v2 authority model | Not Started | Not yet documented or fully audited in this wave | route audit needed |
| Transitional compatibility cleanup | Legacy aliases are documented as transitional and eventually removable | In Progress | Compatibility aliases remain in models but are no longer part of intended v2 runtime behavior | code/doc review |

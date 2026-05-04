# V2 Schema Gap Audit (Wave 1)

This audit maps the DOM-CORE-002 canonical tables to the current schema snapshot and identifies migration work. Wave assignments follow the V2 migration plan.

| Canonical Table | Current Table (if any) | Columns To Add | Columns To Drop | FK/Relation Changes | Port Wave |
|---|---|---|---|---|---|
| users | users | role normalization columns as needed | legacy auth bridge fields (if introduced) | become primary auth principal | 3 |
| seats | seats | enforce canonical `user_id`, `class_id`, role metadata | `join_code`, `student_id`, legacy bridge fields | point to `classes.class_id`; remove student bridge FK | 3 |
| classes | class_economies | canonical class metadata | legacy naming/duplicate fields | rename table + retarget all class FKs | 3 |
| identity_profiles | identity_profiles | `seat_id` binding (if missing), profile metadata normalization | legacy profile fallback columns | FK to seats | 3 |
| user_invite_tokens | none | full table | n/a | FK to classes/users as designed | 3 |
| user_recovery_tokens | recovery_requests + student_recovery_codes (logic source) | full table | n/a | FK to users | 3 |
| class_features | class_features | missing feature policy fields | none expected | validate class FK to canonical classes | 4 |
| feature_settings | feature_settings | settings payload normalization | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| hall_pass_settings | hall_pass_settings | canonical policy fields | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| rent_settings | rent_settings | canonical rent policy fields | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| payroll_settings | payroll_settings | canonical payroll policy fields | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| payroll_rewards | payroll_rewards | canonical reward metadata | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| payroll_fines | payroll_fines | canonical fine metadata | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| banking_settings | banking_settings | canonical banking policy fields | `teacher_id`, `join_code` | enforce class-only scope FK | 4 |
| attendance_sessions | tap_events | canonical attendance session fields | tap-only legacy fields | retarget seat/class FKs | 6 |
| hall_pass_logs | hall_pass_logs | class/seat canonical scoping fields (if partial) | legacy student/join_code scoping | retarget to seats/classes | 6 |
| seat_attendance_state | none | full table | n/a | FK to seats/classes | 6 |
| assessment_events | none | full table | n/a | FK to seats/classes | 7 |
| obligation_lifecycle | rent_payments + insurance_policies + student_insurance | full canonical lifecycle columns | legacy obligation-specific fields | normalize to class/seat + lifecycle keys | 7 |
| obligation_satisfaction | none | full table | n/a | FK to obligation_lifecycle | 7 |
| obligation_reversal | none | full table | n/a | FK to obligation_lifecycle | 7 |
| entitlement_events | none | full table | n/a | FK to seats/classes | 7 |
| ledger_transaction | transaction | canonical event typing, actor metadata | legacy student/join_code bridges | retarget to seat/class | 5 |
| ledger_balance_snapshot | balance_cache | canonical snapshot metadata | cache-specific legacy fields | FK to seats/classes | 5 |
| store_items | store_items | canonical policy/metadata fields | legacy join_code/student bridge fields | class FK normalization | 8 |
| store_item_visibility | store_item_blocks | canonical visibility dimensions | legacy block-only shaping | FK to store_items/seats/classes | 8 |
| store_purchases | student_items | canonical purchase event columns | legacy student inventory shape | FK to seats/store_items/classes | 8 |
| redemption_events | redemption_audit_logs | canonical redemption event fields | redundant legacy audit columns | FK to store_purchases | 8 |
| operational_events | error_events + actor_request_trace (partial overlap) | unified operational payload schema | fragmented event-specific columns | standardized event FK strategy | 9 |
| audit_log | none (or fragmented in existing logs) | full table | n/a | optional FK to class/seat actors | 9 |
| incident_events | user_reports + issue-linked incident fields (partial overlap) | canonical incident event structure | duplicated support/ops fields | normalize incident stream | 9 |
| incident_summary | none | full table | n/a | FK as needed to classes/incidents | 9 |
| alert_events | analytics_alerts (semantic overlap) | canonical alert event fields | analytics-only alert coupling | decouple from analytics snapshots | 9 |
| invariant_run_events | none | full table | n/a | no strict class FK required | 9 |
| job_events | none | full table | n/a | no strict class FK required | 9 |
| health_check_events | none | full table | n/a | no strict class FK required | 9 |
| interpretation_snapshots | analytics_snapshots | canonical interpretation payload fields | analytics-specific naming coupling | class FK to canonical classes | 9 |
| interpretation_annotations | none | full table | n/a | FK to interpretation_snapshots | 9 |
| issues | issues | canonical issue lifecycle metadata | legacy class/join_code bridges | ensure canonical class linkage | 10 |
| issue_status_history | issue_status_history | canonical status transition metadata | none expected | FK to issues | 10 |
| issue_resolution_actions | issue_resolution_actions | canonical resolution metadata | none expected | FK to issues | 10 |
| ticket_correlation_packs | ticket_correlation_pack | pluralized target table + canonical payload fields | singular legacy table name/shape | rename + FK normalization | 10 |
| announcements | announcements | canonical scope metadata | legacy scoping bridges | FK to classes | 10 |
| issue_categories | issue_categories | canonical taxonomy metadata | none expected | FK usage from issues | 10 |

## Notes

- Wave 1 is model and planning only. No migrations are applied in this wave.
- “Current table” values are mapped from `app/models.py` and indicate likely lineage, not guaranteed one-to-one field compatibility.
- Exact column-level diffs are finalized in each domain migration wave once service/feat requirements are locked.

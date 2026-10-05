# Pathfinder 2026-10-04 — Feature Inventory

> **Authority note.** Features are the normative domains defined under `docs/DOMAIN/`
> (authority chain INV-CORE → INV-ARC → DOM → FEAT). Code is mapped *onto* them and is
> descriptive only. `docs/MAP/`, CHANGELOG and `.claude/` are not cited as justification.
> This whole directory is descriptive analysis, not a normative document.

## Boundary decisions

- **Identity is split in two**, because the documents split it: student/canonical identity
  (DOM-IDEN-001/002/005/007) and teacher identity & recovery (DOM-IDEN-003).
  Context resolution (DOM-IDEN-006) owns no tables (§V–VI) and is treated as infrastructure.
- **DOM-CLASS-002/003** are slices of DOM-CLASS-001 (CLASS-001 §I) → one feature.
- **DOM-OPS-001/002** → one feature.
- **FEAT-OBL-004** is an unratified draft contradicting ratified DOM-OBL-001 §II.B. Insurance
  purchase is assigned to STORE, the bill cycle to OBL, insurance definitions to POL.
  Note: ratified FEAT-STOR-001 v3.1 (L28-32, L332) itself routes insurance to FEAT-OBL-004 —
  a normative-doc conflict that needs an owner ruling (see 02/03).

## Features

| # | Feature | Governing docs | Owns (tables) | FEAT contracts | Primary code |
|---|---|---|---|---|---|
| F1 | `class-configuration` | DOM-CLASS-001/002/003 | `classes`, `economic_engine`, `class_features`, `feature_settings`; banking/overdraft directive (§X) | FEAT-CLASS-001…006, 008; FEAT-ECON-001 | `app/feats/class_configuration/*`, `class_configuration_query_service.py`, `economic_engine.py`, `utils/economy_*.py`, `banking.py` |
| F2 | `identity-student` | DOM-IDEN-001/002/005/007 | `users`, `seats`, `identity_profiles` | FEAT-IDEN-001…004, 006 | `feats/identity_feat.py`, `identity_service.py`, `student_setup.py`, `student_recovery.py`, `utils/student_deletion.py` |
| F3 | `identity-teacher` | DOM-IDEN-003 | `recovery_requests`, `student_recovery_codes`, `passkey_credentials`, `teacher_signup_attempts`, `recovery_class_challenges` | FEAT-IDEN-007, 101…107 | `teacher_signup_feat.py`, `teacher_recovery_feat.py`, `passkey_service.py`, `teacher_destruction.py` |
| F4 | `ledger` | DOM-LED-001 | `ledger_transaction`, `ledger_balance_snapshot`, `ledger_command_reservation` | FEAT-LED-000…002 | 18 `services/ledger_*` modules, `transfer_feat.py`, `transaction_void_feat.py` |
| F5 | `obligations` | DOM-OBL-001 | `assessment_events`, `bill_cycles`, `obligation_command_reservation` | FEAT-OBL-001…003 | `obligations_service.py`, `rent_payment_feat.py`, `schedule_next_bill_cycle_feat.py`, `reconcile_rent_feat.py` |
| F6 | `policies` | DOM-POL-001/001A | `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `hall_pass_settings`, `store_products`, `store_item_visibility`, `insurance_policies` | FEAT-POL-001 (sole write surface, §VI.1) | `policy_reference_service.py`, `insurance_*_service.py`, `store_policy_resolver.py`, `services/payroll/settings.py` |
| F7 | `productivity-payroll` | DOM-PROD-001 | `attendance_sessions`, `attendance_interval_invalidation`, `hall_pass_logs`, `payroll_event`, `payroll_cycle_completion` | FEAT-PROD-001…006 | `feats/prod.py`, `complete_payroll_cycle.py`, `attendance_service.py`, `services/payroll/*` |
| F8 | `store-entitlements` | DOM-STORE-001 | `entitlement_events`, `pending_actions`, `insurance_claims`, `insurance_claim_productivity_dates`; insurance coverage lifecycle | FEAT-STOR-001…004, 007 | `store_service.py`, `entitlement_service.py`, `store_purchase_feat.py`, `insurance_claim_feat.py` |
| F9 | `support` | DOM-SUP-001 | `issues`, `issue_*`, `ticket_correlation_packs`, `user_reports`, `announcements`, `actor_request_trace` | FEAT-SUP-001, 002 | `issue_service.py`, `tlcp.py`, `announcement_service.py` |
| F10 | `operations-audit` | DOM-OPS-001/002 | `audit_events`, `chain_heads`, `integrity_status`, operational event tables | FEAT-OPS-001 | `audit_service.py`, `utils/audit_verifier.py`, `system_admin.py` |
| F11 | `interpretation` | DOM-ITR-001 | `interpretation_cycle_record` | none (side effect of FEAT-PROD-004) | `services/interpretation/*`, `analytics.py` |

## Cross-cutting infrastructure (mandated by INV-ARC / SPEC)

| Mandate | Location |
|---|---|
| FEAT base & enforcement (FEAT-CORE-000, INV-ARC-006) | `app/feats/base.py` — `FEATContext` L277, `requires_feat_context` L618, `FEAT_REGISTRY` L196 |
| Context resolution (DOM-IDEN-006) | `app/services/context_resolver.py:resolve_canonical_context` L80; boundary call `app/__init__.py` L451 |
| Temporal resolver (SPEC-TIME-001) | `app/utils/canonical_temporal_resolver.py` |
| Command idempotency (SPEC-LED-002) | `ledger_command_service.py`; `LedgerCommandReservation`, `ObligationCommandReservation` |
| Audit emission (FEAT-OPS-001) | `feats/base.py:audit_protected` L557; `audit_service.py:emit_audit_event` L221 |
| Display identity (SPEC-DISPLAY-001) | `app/utils/display_metadata.py` |
| Page rendering (SPEC-UI-001, INV-ARC-022) | per-domain `services/*/builders.py` + generic `view_model_builders.py` |
| Scheduler | `app/scheduled_tasks.py` (13 jobs) |

## Route files serving multiple domains (shape, not a feature)

`app/routes/admin.py` (10,870 lines, 91 routes, all 10 business domains), `student.py`
(3,465; IDEN/LED/OBL/STORE/SUP/PROD), `api.py` (1,858; STORE/PROD/POL).

## Unowned behaviour (no normative owner found in Phase 0)

`/tips` (`api.py` L232), `docs.py`, `system_admin.py` `/test-errors/*`, `FEAT-BYPASS-LEGACY`
honoured in prod code (`models.py` L709, `base.py` L522-549), dead DOB parsers
(`admin.py` L639, L798 — DOB is forbidden by DOM-IDEN-002), no-op `database_maintenance_job`.

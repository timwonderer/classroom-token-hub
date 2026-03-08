# Multi-Tenancy Hardening Progress Log (v2.0)

Date: 2026-03-08
Branch: `codex/v2.0`

## Scope and Rule of Truth

- `join_code` is the primary class boundary.
- `ClassEconomy` and `ClassMembership` are the authority for class scope.
- `student_teachers` is the teacher ownership model, not the class-boundary authority.
- `current_join_code` is the active class context in teacher and student sessions.
- v2.0 does not treat TeacherBlock fallback as intended runtime behavior.

## Completed

- Added ORM parity for `ClassEconomy` and `ClassMembership` so runtime models match the schema already present in migrations.
- Hardened `ClassMembership` integrity with enum-backed statuses/roles and DB check constraints.
- Completed strict join-code scoping across the recent merge set:
  - student route settings and financial displays
  - admin class selection, deletion, export, payroll, and issue-resolution flows
  - API tap-entry, redemption, attendance-history, hall-pass, and verification flows
- Removed or blocked key legacy behavior from live v2 flows:
  - no `join_code IS NULL` settings fallback in student/settings purchase paths
  - no numeric student switch route as a valid class-switch mechanism
  - no teacher-seat fallback in admin API scope checks
- Moved public teacher references to stable public identity:
  - `Admin.public_id` aliases `teacher_public_id`
  - hall-pass verification uses public teacher identity and teacher-owned join-code scope
- Consolidated the integration branches into `codex/v2.0` and pruned obsolete merge branches.
- Resolved the remaining v2 migration heads in repo:
  - `a11213ca4afb_harden_class_economy_membership_checks.py`
  - `e8f1a2b3c4d5_merge_remaining_v2_heads.py`

## Validation Snapshot

- Full suite on PostgreSQL test DB:
  - `DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy_test pytest -q`
  - Result: `664 passed, 1 skipped`
- Merge path validation completed:
  - `fix-database-model` fast-forwarded to the validated tip
  - `codex/v2.0` fast-forwarded to the same tip
  - redundant branches pruned

## Current Assessment

### Ready Now

- Runtime class authority is coherent around `ClassMembership` and `ClassEconomy`.
- The branch topology is clean and points all active v2 work at `codex/v2.0`.
- Route scoping, public teacher identity, and key ledger/class deletion guardrails are in place.
- Repository migration heads are resolved and documented.

### Required Before Live Testing

- Publish operator-facing v2 live-test runbook.
- Refresh migration-compliance status from historical audit mode into current-state readiness mode.
- Rehearse migration upgrade flow with explicit verification queries and rollback triggers.
- Confirm smoke-route checklist and seed expectations are documented for someone other than the branch author.

### Required Before Production

- Complete v2 production transition runbook with operator sign-off steps.
- Rehearse backup, maintenance-mode, and rollback procedures against the intended deployment topology.
- Reconfirm production-safe migration and downgrade posture for live data.

### Post-Live-Test Cleanup

- Continue shrinking compatibility aliases and transitional schema notes.
- Sweep lower-priority docs and historical logs for consistency notes.
- Expand lower-risk guide coverage once operator docs are stable.

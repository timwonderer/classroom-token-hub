# V2 Class ID Invariant Backlog

**Status:** Deferred / backburner  
**Priority:** Post-launch hardening  
**Scope:** Remove class-lifecycle and membership-lifecycle semantics that conflict with the v2 class-identity model

## Problem Statement

Some remaining code and compatibility shims still imply that class scope or class membership can be described with labels such as `active`, `inactive`, `archived`, or similar lifecycle states.

That is not the v2 model.

## Canonical Invariants

- `class_id` either exists or never existed.
- `join_code` is the current public entry point that resolves to a single class universe.
- Labels such as `block`, `period`, `section`, and `display_name` are metadata only, not identity.
- A student exists in a class only if that student has a valid association with that class universe.
- Student-in-class state is limited to:
  - unclaimed
  - claimed
- Deletion from a `class_id` means erasure from that universe as if the student never existed there.
- If a student loses the last remaining class association, that student is erased from the system.

## Deferred Cleanup Targets

- Remove compatibility-only `ClassEconomy.status` semantics and any writes that imply class lifecycle state.
- Eliminate any membership code that models class participation as `active` / `inactive` / `archived` instead of existence.
- Replace cleanup and lifecycle logic that keys off labels or teacher-wide label groupings instead of surviving class associations.
- Revisit settings models and cleanup rules that still act like `teacher_id + block` is a durable ownership boundary.
- Remove stale tests that still construct impossible class worlds through deprecated lifecycle fields.

## Explicit Non-Goals For Current Launch Work

- No broad architecture rewrite during live-test blocker reduction.
- No taxonomy-wide documentation rewrite tied to this cleanup.
- No schema migration churn unless required by a validated post-launch implementation plan.

## Trigger To Resume

Resume this backlog after launch-critical validation blockers are closed and the post-port refactor lane is open, alongside:

- `docs/development/V2_ADMIN_ROUTE_REFACTOR.md`
- `docs/development/V2_Class_Scope_Normalization_Target.md`


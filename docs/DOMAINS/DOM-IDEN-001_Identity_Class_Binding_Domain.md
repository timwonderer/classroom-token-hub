# Identity and Class Binding Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 1.0 | 2026-04-18 | N/A | Normative |

## I. Purpose

Define the Identity domain as the authority for who is bound to what inside a class-scoped universe.

## II. Scope

This domain owns identity binding, class membership truth, seat linkage, teacher-student binding, and roster-seat assignment structures.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `ARC-IDEN-001_Admin_Identity_Handling.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `students`
- `student_teachers`
- `seats`
- `teacher_blocks`
- `class_memberships`

It owns identity and class binding truth only. It does not own balances, entitlements, attendance standing, or affordability.

## V. Owned Tables

### `students`
- Student identity and credential container.

### `student_teachers`
- Teacher-student ownership binding.

### `seats`
- Normalized class seat assignments.

### `teacher_blocks`
- Roster / claim linkage by teacher block and join-code scope.

### `class_memberships`
- Membership truth for admin/student presence inside a class boundary.

## VI. Schema Contract

### `students`
- Key fields:
  - `id`
  - encrypted identity fields
  - `identity_id`
  - `salt`
  - hashed auth / recovery fields

### `student_teachers`
- Key fields:
  - `student_id`
  - `teacher_id`
  - `created_at`

### `seats`
- Key fields:
  - `student_id`
  - `class_id`
  - `join_code`
  - `block`
  - `role`

### `teacher_blocks`
- Key fields:
  - `teacher_id`
  - `student_id`
  - `join_code`
  - `block`
  - `is_claimed`

### `class_memberships`
- Key fields:
  - `join_code`
  - `admin_id`
  - `student_id`
  - `role`
  - `status`

## VII. Constraints

- Membership is class-scoped and existence-based.
- Identity does not grant financial, entitlement, or attendance authority.
- Class binding must remain scoped to `join_code` / `class_id` truth.
- No identity helper may become a cross-domain profile aggregator.

## VIII. Derived / Cross-Domain Rules

- Other domains may reference `student_id`, `teacher_id`, and `join_code`, but that does not transfer identity ownership.
- Class membership and seat binding determine who participates in a class; they do not determine what that actor can afford or claim.

## IX. Amendment

Revisions require version increment, effective-date update, and continued consistency with higher-order invariants.

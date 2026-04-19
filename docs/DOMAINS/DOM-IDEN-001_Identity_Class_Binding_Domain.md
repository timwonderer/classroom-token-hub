# Identity and Class Binding Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 2.0 | 2026-04-18 | 1.0 | Normative |

## I. Purpose

Define the Identity domain as the authority for:

- who a human is in the system
- which class-local actor record that human owns
- which class universe that actor belongs to

## II. Scope

This domain owns:

- global human identity
- class-local actor binding
- display identity
- roster and claim binding
- active class-actor context resolution

This domain does not own:

- balances
- entitlements
- attendance standing
- affordability
- feature policy

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `docs/development/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over the target identity model:

- `users`
- `seats`
- `identity_profiles`
- `classes`

This domain owns identity and class-binding truth only.

## V. Owned Tables

### `users`

- Global human identity.
- Authentication, recovery, and session identity state.

### `seats`

- Class-local actor binding.
- One participant record inside one class universe.

### `identity_profiles`

- Human-facing display identity for one seat.

### `classes`

- Class universe anchor and lookup/UI record.

## VI. Schema Contract

### `users`

Key fields:

- `id`
- `public_id`
- username/auth fields
- recovery fields
- session identity fields

Rules:

- one row per human identity
- not a membership table
- not a financial or attendance table

### `seats`

Key fields:

- `id`
- `public_id`
- `user_id`
- `class_id`
- `role`
- claim/roster fields

Rules:

- one seat belongs to exactly one class universe
- one seat belongs to at most one user
- seat existence expresses class participation
- `seat_id` is the participant identity key

### `identity_profiles`

Key fields:

- `id`
- `seat_id`
- display-name fields

Rules:

- exactly one display profile per seat
- display identity does not replace seat identity

### `classes`

Key fields:

- `class_id`
- `join_code_token`
- `section`
- `display_name`

Rules:

- one row defines one class universe
- class existence is existence-based, not lifecycle-state based
- this table is not a membership table
- `join_code_token` is a public lookup token, not an internal domain foreign key

## VII. Constraints

- Identity is modeled through `users`, `seats`, `identity_profiles`, and `classes`.
- Separate `Student` and `Teacher/Admin` identity tables are not part of the target model.
- Seat existence, not a separate membership lifecycle label, defines whether a participant
  exists in a class.
- Identity does not grant financial, entitlement, or attendance authority.
- No identity helper may become a cross-domain profile aggregator or mutable state sink.

## VIII. Legacy Table Interpretation

The following tables are legacy implementation structures, not target-state identity
anchors:

- `students`
- `teachers` / `admins`
- `teacher_blocks`
- `student_teachers`

They may exist in current runtime code, but they do not define the target domain model.

## IX. Derived / Cross-Domain Rules

- Other domains may reference `seat_id` and `class_id`, but that does not transfer
  identity ownership.
- `user_id` is for authentication, recovery, and global identity only.
- `seat_id` is for participant and class-local actor identity.
- `class_id` is for class-universe identity and class-wide configuration scope.
- Domain tables that describe participant activity should reference `seat_id`.
- Domain tables that describe class-wide policy should reference `class_id`.

## X. Amendment

Revisions require version increment, effective-date update, and continued consistency
with higher-order invariants.

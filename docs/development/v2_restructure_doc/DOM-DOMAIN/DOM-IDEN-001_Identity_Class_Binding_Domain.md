# Identity and Class Binding Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 2.1 | 2026-04-22 | 2.0 | Normative |

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
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/development/specs/V2_TEACHER_IDENTITY_ARCHITECTURE.md`

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
- `user_role` — `'teacher'` | `'student'`; determines credential scheme
- `username_hash` / `username_lookup_hash`
- `totp_secret_encrypted` — teacher only; nullable for students
- `passkey_credential_id` — teacher only, optional
- `pin_hash` — student only; nullable for teachers
- `passphrase_hash` — student only, financial gate; nullable for teachers
- recovery fields (`reset_code_hash`, `reset_code_expires_at`)
- session fields (`current_session_started_at`, `current_session_expires_at`, `current_session_nonce`)
- `money_action_cooldown_until`
- `has_completed_setup`

Rules:

- one row per human identity, regardless of role
- `user_role` is immutable after creation
- teacher-credential fields are NULL for student rows and vice versa
- no DOB or DOB-derived hash is stored in any form
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
- `user_role` determines the credential scheme on `users`.
- `role` on `seats` determines the operational role within a class.
- Authentication flows are specified per role in:
  - `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md` — student credential and claim flow
  - `DOM-IDEN-003_Teacher_Identity_Architecture.md` — teacher credential and session flow
- Recovery flows are specified in `DOM-IDEN-002_Account_Recovery.md`.

## X. Transitional Reality

The following tables are legacy implementation structures active in the current
runtime. They are not target-state identity anchors:

- `students` — legacy student credential and financial state table; superseded by `users` + `seats`
- `teachers` / `admins` — legacy teacher credential table; superseded by `users` + `seats`
- `teacher_blocks` — legacy roster-seat table; superseded by `seats`
- `student_teachers` — legacy teacher–student membership join; superseded by class-scoped `seats`

Current gaps:

- `classes` table does not exist; `class_economies` serves as the interim class anchor
- `User` model in `models.py` does not yet match the `users` schema contract above;
  it has a placeholder shape pending unified credential design completion
- `IdentityProfile` in `models.py` does not yet have a `seat_id` FK; it is currently
  accessed via `TeacherBlock.identity_id` and `Student.identity_id`
- `Seat` model exists as scaffolding; runtime identity still flows through `Admin`/`Student`
- `Admin.dob_sum_hash` must be removed before Project 9 cutover (DOB is not part of
  the target model for any role)

Full cutover from legacy tables to `users`/`seats`/`classes` is Project 9, post-launch.

## XI. Amendment

Revisions require version increment, effective-date update, and continued consistency
with higher-order invariants.

# Teacher Identity Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-003     | 1.0     | 2026-04-22     | ARC-IDEN-001 v2.0 | Normative |

## I. Purpose

This document defines the v2 identity model for teacher (admin) participation inside CTH.

It is a companion to `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`.
Both roles use the same `users`, `seats`, and `classes` tables, differentiated by
`user_role` on the `users` row and `role` on the `seat`.

This document assumes the clean v2 identity redesign. It is not a v1-to-v2 migration
plan and does not preserve v1 data model constraints.

Supersedes `docs/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`.

## II. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-002_Account_Recovery.md`
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

## III. Core Design Principle

CTH uses a unified identity model. Both teachers and students are represented as `users`
with one or more `seats`. The role differentiates behavior, not the table.

```text
users (user_role = 'teacher' | 'student')
  └─< seats (role = 'teacher' | 'student') >─ classes
         │
         └─1:1 identity_profiles
```

No DOB is stored or used anywhere in the v2 identity model for either role.

---

## Identity Layers

### Users (Unified Credential Store)

Purpose: authentication, recovery, and global security state for all principals.

The `users` table is shared by teachers and students. The `user_role` field identifies
which credential scheme and authentication flow applies.

Key fields:

- `id`
- `public_id`
- `user_role` — `'teacher'` | `'student'`
- `username_hash` — HMAC of the normalized username; primary auth lookup key
- `username_lookup_hash` — secondary lookup index (indexed separately)
- `totp_secret_encrypted` — **teacher only**; base64-encoded encrypted TOTP seed
- `passkey_credential_id` — **teacher only, optional**; opaque reference to passkey
  registration (e.g. via passwordless.dev); nullable until enrolled
- `pin_hash` — **student only**; hashed PIN used for login
- `passphrase_hash` — **student only**; hashed passphrase used to gate financial actions
- `reset_code_hash` — hashed recovery code; applicable to both roles
- `reset_code_expires_at`
- `current_session_started_at`
- `current_session_expires_at` — fixed window set at login, does not slide forward
- `current_session_nonce` — regenerated at each login; binds requests to one session
- `money_action_cooldown_until` — rate-limit guard for financial mutations
- `has_completed_setup`
- `created_at`
- `updated_at`

Rules:

- One `users` row per human identity, regardless of role.
- `user_role` is set at account creation and does not change.
- Teacher-credential fields are `NULL` for student rows.
- Student-credential fields are `NULL` for teacher rows.
- No DOB, DOB hash, DOB sum, or any birth-date-derived field is stored on `users`.
- A teacher user may own multiple seats across multiple classes (one seat per class).
- Session window fields behave identically for both roles.
- Only one active session is supported per user identity.

### Classes

Same as defined in `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`.
Teachers and students both participate in the same class universe anchored by the
`classes` table.

### Seats

A seat represents one actor inside one class universe.

Seat `role` field values:

- `'student'` — a participant in the economy (earns, spends, claims)
- `'teacher'` — the operator of the economy (administers, configures, approves)

Key fields (shared with student seats, same table):

- `id`
- `public_id`
- `class_id → classes.class_id`
- `user_id → users.id` (nullable until account setup is complete)
- `role` — `'teacher'` | `'student'`
- `block_identifier` — the class period identifier this seat belongs to
- `teacher_notes_encrypted` — optional operator-visible notes (not in student view)
- `roster_fingerprint` — used for claim matching (students); not applicable for teachers
- `dedupe_code` — used for DOPO handling (students); not applicable for teachers
- `claimed_at`
- `created_at`
- `updated_at`

Rules:

- A teacher seat is created when the teacher sets up a class.
- A teacher seat belongs to exactly one class universe.
- A teacher may hold seats in multiple classes (one seat per class).
- Teacher seats do not use `roster_fingerprint` or `dedupe_code`; those fields are
  `NULL` for teacher seats.
- `teacher_notes_encrypted` is accessible only to the seat's teacher and system admins.

### Identity Profiles

Same table and structure as student identity profiles. One profile per seat. Contains
display identity only.

Key fields:

- `id`
- `seat_id → seats.id`
- `first_name_encrypted`
- `last_initial`
- `created_at`
- `updated_at`

Rules:

- One identity profile per seat, regardless of role.
- Teacher display names are stored here, not on a separate teacher table.
- `last_initial` is used for display and does not derive from any PII source.

---

## Authentication Flows

### Teacher Login

```text
1. Teacher submits username.
2. Backend computes username_lookup_hash and finds the users row.
3. Backend verifies user_role == 'teacher'.
4. If passkey is enrolled and the client supports it → passkey challenge (preferred).
5. Otherwise → TOTP challenge using totp_secret_encrypted.
6. On success: write current_session_started_at, current_session_expires_at,
   current_session_nonce.
7. Load teacher's available seats and set active seat context.
```

TOTP is required for all teacher accounts. Passkey is an optional second authentication
method — when enrolled, it replaces the TOTP step for that device.

### Teacher Account Creation

```text
1. System admin or invite flow creates a users row (user_role = 'teacher').
2. Teacher completes TOTP setup (required before has_completed_setup = true).
3. Teacher optionally enrolls a passkey.
4. A seat is created for the teacher's first class (role = 'teacher').
5. An identity profile is created for that seat.
```

### Teacher Session

Session semantics are identical to students:

- `current_session_expires_at` is set once at login. It does not slide forward on activity.
- `current_session_nonce` is checked on every request.
- All three session fields are replaced on the next successful login.

### Teacher Financial Actions

Teachers administering financial actions (adjustments, payroll, approvals) are
authenticated by the existing session. There is no additional passphrase gate for
teachers — the TOTP at login is the authentication signal.

---

## What Is Not In The Target Model

The following patterns are explicitly excluded from the v2 teacher identity model:

- **Separate `teachers` / `admins` table** — target model uses `users` + `seats`
- **DOB or DOB-derived hashes** — no birth date is stored or used for teacher identity
  or recovery at any point
- **Plaintext username** — `username` column does not exist; only `username_hash` and
  `username_lookup_hash`
- **`teacher_public_id` as a separate field** — display identity lives in `identity_profiles`
- **`dob_sum_hash` / `salt` for DOB** — removed; no DOB recovery mechanism
- **`has_assigned_students` flag** — setup state belongs on `has_completed_setup`
- **`AdminCredential` as a separate table for passkeys** — passkey enrollment reference
  lives on the `users` row directly

---

## Credential Comparison: Teacher vs. Student

| Credential | Teacher | Student |
|------------|---------|---------|
| Username | `username_hash` / `username_lookup_hash` | `username_hash` / `username_lookup_hash` |
| Primary auth factor | TOTP (`totp_secret_encrypted`) | PIN (`pin_hash`) |
| Secondary / optional factor | Passkey (`passkey_credential_id`) | Passphrase (`passphrase_hash`) |
| Passphrase use | N/A | Gates financial actions only |
| DOB | **Not stored** | **Not stored** |
| Recovery | `reset_code_hash` | `reset_code_hash` |
| Session | Nonce + expiry window | Nonce + expiry window |

---

## Legacy Table Interpretation

The following tables are legacy implementation structures, not target-state teacher
identity anchors:

- `teachers` / `admins` — encodes teacher credentials outside the `users` model
- `teacher_credentials` — passkey table; superseded by `users.passkey_credential_id`
- `system_admins` — separate sysadmin credential table; future target is a `user_role`
  variant or separate admin tier (not in scope for this spec)
- `teacher_blocks` — legacy roster-seat table; superseded by `seats`
- `student_teachers` — legacy teacher–student membership join; superseded by
  class-scoped `seats`

These tables may exist in current runtime code, but they do not define the target domain
model.

---

## Transitional Reality

Current runtime code uses `Admin` (mapped to `teachers` table) as the active teacher
identity. The `Seat` model exists as scaffolding with a `role` field and `user_id` FK,
but teacher authentication and session management still flow through `Admin`.

The `Admin` model retains:
- `totp_secret` (encrypted) — correct pattern, will migrate to `users`
- `dob_sum_hash` — **legacy; must be removed before Project 9 cutover**
- `AdminCredential` (passkey metadata table) — will merge into `users` row

Full cutover from `Admin` to `users`/`seats` is Project 9, explicitly post-launch.

---

## Canonical Identity Invariants

- `users.id` is the internal credential identity key for all principals.
- `seat_id` is the participant identity inside a class for all principals.
- `class_id` is the class-universe identity.
- `user_role` on `users` determines the credential scheme; `role` on `seats` determines
  the operational role within a class.
- No DOB is stored in any form at any point in the identity lifecycle.
- Teacher authentication always requires TOTP or passkey. PIN is for students only.
- Student financial actions always require passphrase re-verification. This gate does
  not apply to teachers.

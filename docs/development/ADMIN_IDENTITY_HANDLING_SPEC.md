# Admin (Teacher) Identity Handling Specification

Status: Active (Normative)
Last Updated: 2026-02-24
Owner: Platform / Identity & Security

## 1. Purpose

Define the identity model for teacher/admin and system admin accounts with minimal PII exposure.
This spec covers authentication identity, public-facing teacher identity, sysadmin-facing identity, and legacy migration behavior.

## 2. Design Goals

- Remove plaintext usernames from durable storage for authentication.
- Separate authentication identity from display identity.
- Minimize PII exposure for students and sysadmins.
- Keep deterministic login behavior during legacy migration.
- Preserve account continuity without lockout for valid users.

## 3. Canonical Identity Fields

Teacher/admin (`admins`):
- `username` (legacy plaintext, nullable, deprecated).
- `username_hash` (auth hash, required for migrated records).
- `username_lookup_hash` (deterministic lookup hash for login).
- `salt` (per-account salt for username hashing).
- `teacher_public_id` (public identifier, unique).
- `display_name` (teacher-managed app name; privacy handling applies).
- `hall_pass_verify_token` (public verification capability token, unique, rotatable).

Logical capability token name:
- `hallpass_public_token` (maps to DB field `admins.hall_pass_verify_token`).

System admin (`system_admins`):
- `username` (legacy plaintext, nullable, deprecated).
- `username_hash` (auth hash).
- `username_lookup_hash` (login lookup hash).
- `salt` (per-account salt).
- `totp_secret` (encrypted at rest).

## 4. Identifier Semantics

Authentication username:
- Used only for authentication and credential recovery flows where needed.
- Must not be used as the app-facing identifier for students or sysadmins.

Teacher public identifier (`teacher_public_id`):
- Generated as three words from approved preset dictionary.
- Format: `word1_word2_word3`.
- Unique across teachers.
- Default app display name when teacher has not set custom display name.
- Required display identifier for sysadmin views (always).

Teacher display name (`display_name`):
- Teacher-managed label shown in teacher/student app contexts.
- If not set, app display falls back to `teacher_public_id`.
- If set, app shows display name; sysadmin still sees `teacher_public_id`.
- Must be encrypted at rest as PII.

## 5. Generation Rules

On teacher account creation:
1. Normalize input username.
2. Generate `salt`.
3. Compute/store `username_hash` and `username_lookup_hash`.
4. Do not persist plaintext `username`.
5. Generate unique `teacher_public_id` from preset word list.
6. Generate `hall_pass_verify_token`.

On system admin account creation:
1. Normalize input username.
2. Generate `salt`.
3. Compute/store `username_hash` and `username_lookup_hash`.
4. Do not persist plaintext `username`.
5. Encrypt and store TOTP secret.

## 6. Login and Lookup Rules

Teacher/system admin login lookup order:
1. Find by `username_lookup_hash` (normalized input).
2. Fallback to legacy plaintext `username` only for pre-migration accounts.

Post-migration record requirements:
- `username_hash` and `username_lookup_hash` must both be non-null.
- `username` should be null.

## 7. Legacy Migration UX Contract

When a legacy account logs in and lacks hashed username fields:
- Show mandatory one-time migration screen before normal dashboard access.
- Offer two actions:
  1. Continue using current username (hash and store it).
  2. Update to a new username (validate uniqueness, then hash/store).

Teacher-specific warning:
- If teacher has no students linked, show explicit no-recovery warning before migration confirmation.

After confirmation:
- Persist `username_hash`, `username_lookup_hash`, and `salt`.
- Set legacy plaintext `username` to null.
- Ensure teacher has `teacher_public_id` and `hall_pass_verify_token`.

## 8. Display Policy (PII Minimization)

Student-facing:
- Show teacher `display_name` if set.
- Else show `teacher_public_id`.

Teacher-facing self context:
- Show `display_name` if set.
- Else show `teacher_public_id`.

System admin-facing:
- Always show `teacher_public_id` for teacher identity display.
- Never require or prefer teacher auth username for display.

## 9. Security Requirements

- Username hashing must use account salt plus project pepper strategy.
- TOTP secrets must remain encrypted at rest.
- Public verify URLs must use `hall_pass_verify_token`, not teacher username or numeric ID.
- No public endpoint may accept numeric primary keys or `teacher_id` for routing.
- Identity updates must be committed atomically to avoid partial migration states.
- Username uniqueness checks must include hashed-lookup and legacy fallback windows.

## 10. Public Capability Tokens

Certain features may expose public, unauthenticated endpoints scoped to a teacher account.
These endpoints must use high-entropy capability tokens rather than internal identifiers.

`hallpass_public_token`:
- Purpose: allows office staff to verify same-day hall pass records without authentication.
- Storage mapping: `admins.hall_pass_verify_token`.

Properties:
- 256-bit cryptographically secure random value.
- Generated using secure random source.
- Unique indexed.
- Stored in teacher table.
- Not derived from `teacher_id`.
- Not derived from `join_code`.
- Not guessable.
- Rotatable by teacher.
- Invalidated upon teacher deletion.

Security invariants:
- Token alone grants read-only access to limited, same-day operational data.
- Token does not expose historical multi-day records.
- Token does not expose lists or roster.
- Token does not expose internal identifiers.
- Token cannot mutate system state.

Rotation policy:
- Teacher may regenerate at any time.
- Old token immediately invalid.
- Migration ensures all teachers have token populated.

Non-goals:
- Token is not an authentication credential.
- Token is not tied to login identity.
- Token is not reused across features.

## 11. Operational Requirements

- CLI/admin creation commands must create hashed username records, not plaintext.
- Migrations must be idempotent and tested with upgrade/downgrade rehearsal.
- Sysadmin and teacher auth flows must continue to function for migrated and unmigrated records during transition.

## 12. Acceptance Criteria

Functional:
- New teacher and sysadmin accounts persist no plaintext username.
- New teacher receives unique `teacher_public_id` and `hall_pass_verify_token`.
- Legacy accounts are prompted once and migrated successfully at next login.

Privacy:
- Sysadmin UI shows `teacher_public_id`, not teacher auth username.
- App display behavior follows: display name if set, otherwise `teacher_public_id`.
- Teacher custom display name is encrypted at rest.

Resilience:
- Migration path does not lock out valid users who know current credentials.
- Duplicate username prevention works across migrated and legacy records.

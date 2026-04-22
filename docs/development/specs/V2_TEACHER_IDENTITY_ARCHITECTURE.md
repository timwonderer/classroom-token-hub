# V2 Teacher Identity Architecture: Migration & Tracking

This document tracks the transitional state and migration TODOs for moving from the current v1 runtime (using `Admin`, `TeacherBlock`, etc.) to the pure v2 Identity model defined in `DOM-IDEN-001`, `DOM-IDEN-003`, and `DOM-IDEN-004`.

It specifies the "Current -> v2" paths that must be completed during Project 9.

## 1. Core Identity Migration (Project 9)

**Current Runtime:**
- Active teacher identity lives in the `Admin` model (mapped to `teachers` table).
- Teacher authentication and session management flow through `Admin`.
- The `Seat` model exists only as scaffolding.
- Passkeys are stored in the separate `AdminCredential` table.

**Target (v2) Migration:**
- Cutover teacher identity to the `users` table (`user_role = 'teacher'`).
- Migrate `Admin.totp_secret` to `users.totp_secret_encrypted`.
- Merge `AdminCredential` records into `users.passkey_credential_id`.
- Transition the session management to flow exclusively through `users`.
- Drop the `teachers` and `AdminCredential` tables once migration is complete.

## 2. DOB Eradication (Project 9 Blocker)

**Current Runtime:**
- `Admin.dob_sum_hash` is still present in the schema.
- Previously used as a factor in the teacher account recovery flow, it has been stripped from the runtime logic but the database column persists.

**Target (v2) Migration:**
- Delete the `dob_sum_hash` column from the `Admin` table in the next Alembic migration.
- Ensure no code relies on or writes to this column.
- The target model is strictly **PII-free**; no DOB should exist anywhere in the application.

## 3. Account Recovery Refactor (Project 9)

**Current Runtime:**
- The account recovery form resolves `(join_code, username)` pairs to establish identity.
- This is currently implemented using the legacy `TeacherBlock` model:
  `join_code → TeacherBlock rows → teacher_id + [student_id list] → username_lookup_hash within that set`.
- The hop to identify the class scope is implicit through `TeacherBlock`.
- `RecoveryRequest` model correctly uses an FK to the teacher, but it currently points to `Admin`.

**Target (v2) Migration:**
- Replace `TeacherBlock` usage in recovery with the new `classes` and `seats` tables.
- The resolution chain will become:
  `join_code` → `classes` (via `join_code_token`) → `class_id` → `seats` (to get roster)
- Update `RecoveryRequest.teacher_id` to point to `users.id` instead of `Admin.id`.
- Drop `TeacherBlock` completely from the schema.

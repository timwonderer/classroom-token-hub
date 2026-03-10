# Identity Management & Class Association — Core Flow Reference

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-010     | 1.0     | 2026-03-10     | N/A        | Reference       |

## Purpose

Comprehensive description of two foundational flows in the Classroom Token Hub:

1. **Identity Management** — the full lifecycle of teacher and student accounts from creation through deletion, including every database operation at each stage.
2. **Class Association** — how classes are created, how students join them, how multi-enrollment works, and how class deletion cascades.

This document is intended as the authoritative source of truth for planning the v2.0 rework.

---

## Table of Contents

1. [Teacher Identity Lifecycle](#1-teacher-identity-lifecycle)
   - 1.1 [Registration (Signup)](#11-registration-signup)
   - 1.2 [Login](#12-login)
   - 1.3 [Legacy Username Migration](#13-legacy-username-migration)
   - 1.4 [Session Management](#14-session-management)
   - 1.5 [Profile & Settings](#15-profile--settings)
   - 1.6 [Account Recovery Setup](#16-account-recovery-setup)
   - 1.7 [Account Recovery Flow](#17-account-recovery-flow)
   - 1.8 [Logout](#18-logout)
   - 1.9 [Deletion](#19-deletion)
   - 1.10 [Admin Model — Complete Schema](#110-admin-model--complete-schema)
2. [Student Identity Lifecycle](#2-student-identity-lifecycle)
   - 2.1 [Roster Upload (Seat Creation)](#21-roster-upload-seat-creation)
   - 2.2 [Account Claim (Self-Registration)](#22-account-claim-self-registration)
   - 2.3 [Username Creation](#23-username-creation)
   - 2.4 [PIN & Passphrase Setup](#24-pin--passphrase-setup)
   - 2.5 [Login](#25-login)
   - 2.6 [Profile & Settings](#26-profile--settings)
   - 2.7 [Account Recovery](#27-account-recovery)
   - 2.8 [Deactivation & Deletion](#28-deactivation--deletion)
   - 2.9 [Student Model — Complete Schema](#29-student-model--complete-schema)
3. [Class Association Flow](#3-class-association-flow)
   - 3.1 [Class Creation & Join Code Generation](#31-class-creation--join-code-generation)
   - 3.2 [Student Enrollment (Initial Claim)](#32-student-enrollment-initial-claim)
   - 3.3 [Adding Additional Classes](#33-adding-additional-classes)
   - 3.4 [Class Context & Switching](#34-class-context--switching)
   - 3.5 [Student Removal from a Class](#35-student-removal-from-a-class)
   - 3.6 [Class Deletion (Hard Delete)](#36-class-deletion-hard-delete)
   - 3.7 [Multi-Enrollment Data Model](#37-multi-enrollment-data-model)
4. [Supporting Models](#4-supporting-models)
   - 4.1 [TeacherBlock (Roster Seats)](#41-teacherblock-roster-seats)
   - 4.2 [StudentBlock (Per-Period State)](#42-studentblock-per-period-state)
   - 4.3 [StudentTeacher (Many-to-Many)](#43-studentteacher-many-to-many)
   - 4.4 [AdminCredential (Passkeys)](#44-admincredential-passkeys)
   - 4.5 [RecoveryRequest & StudentRecoveryCode](#45-recoveryrequest--studentrecoverycode)
5. [Cryptographic Summary](#5-cryptographic-summary)
6. [Known Debt & v2.0 Considerations](#6-known-debt--v20-considerations)

---

## 1. Teacher Identity Lifecycle

### 1.1 Registration (Signup)

**Route:** `POST /admin/signup` (`app/routes/admin.py:2021`)

**Prerequisites:** A valid, unused, unexpired invite code in `admin_invite_codes`.

**Flow (two-phase, single route):**

**Phase 1 — Initial submission:**

1. Teacher submits: `username`, `invite_code`, `dob` (date of birth), `tos_agreed`.
2. Username normalized via `normalize_auth_username()`.
3. DOB parsed → `dob_sum = month + day + year` (integer).
4. Invite code validated:
   ```sql
   SELECT * FROM admin_invite_codes WHERE TRIM(code) = :code
   ```
   Checks: `used = FALSE`, `expires_at > NOW()` (if set).
5. Username uniqueness checked via `_auth_username_exists()` (queries `username_lookup_hash`).
6. TOTP secret generated: `pyotp.random_base32()`.
7. Secret + username + dob_sum stored in Flask session (ephemeral).
8. QR code rendered for authenticator app enrollment.
9. Returns the TOTP confirmation template — **no DB writes yet**.

**Phase 2 — TOTP confirmation:**

1. Teacher submits the 6-digit TOTP code from their authenticator app.
2. Code verified: `pyotp.TOTP(secret).verify(totp_code)`.
3. On success, the following DB operations execute **atomically**:

| Operation | Table | Details |
|-----------|-------|---------|
| Mark invite used | `admin_invite_codes` | `UPDATE SET used = TRUE WHERE id = :id AND used = FALSE` (CAS-style) |
| Generate salt | (in-memory) | `get_random_salt()` → 16 random bytes |
| Hash DOB sum | (in-memory) | `hash_hmac(str(dob_sum).encode(), salt)` → HMAC-SHA256 |
| Build auth hashes | (in-memory) | `_build_admin_auth_fields(username, salt)` → `(salt, username_hash, username_lookup_hash)` |
| Generate public ID | (in-memory) | `_generate_unique_teacher_public_id()` → `word1_word2_word3` format |
| Encrypt TOTP secret | (in-memory) | `encrypt_totp(totp_secret)` → Fernet-encrypted, base64-encoded |
| Generate hall pass token | (in-memory) | `secrets.token_hex(32)` → 256-bit capability token |
| **INSERT Admin** | `admins` | See row details below |

**Admin row created:**

```
admins:
  username           = NULL              (plaintext deprecated)
  username_hash      = HMAC(salt+username, pepper)
  username_lookup_hash = HMAC(username, pepper)  (deterministic, no per-user salt)
  teacher_public_id  = "brave_coral_fox"  (three-word random)
  display_name       = NULL              (set later in settings)
  totp_secret        = <Fernet-encrypted base64 string>
  dob_sum_hash       = HMAC(dob_sum, salt)
  salt               = <16 random bytes>
  hall_pass_verify_token = <64-char hex string>
  tos_accepted       = TRUE
  tos_accepted_at    = UTC NOW
  created_at         = UTC NOW
  last_login         = NULL
  has_assigned_students = FALSE
```

4. Session cleared of signup ephemeral data.

---

### 1.2 Login

**Route:** `POST /admin/login` (`app/routes/admin.py:1895`)

**Flow:**

1. Clear any existing admin session keys.
2. Normalize username via `normalize_auth_username()`.
3. Look up admin via `_find_admin_by_auth_username(username)`:
   - Computes `hash_username_lookup(username)` (deterministic HMAC).
   - `SELECT * FROM admins WHERE username_lookup_hash = :hash`.
   - Falls back to legacy `WHERE username = :username` for un-migrated accounts.
4. Decrypt TOTP secret: `decrypt_totp(admin.totp_secret)` (Fernet decryption).
5. Verify TOTP: `pyotp.TOTP(secret).verify(code, valid_window=1)` (30-second window ± 1).
6. On success:

| Operation | Table | Details |
|-----------|-------|---------|
| Update last_login | `admins` | `SET last_login = UTC NOW` |
| Set session | (server-side) | `admin_id`, `is_admin=True`, `admin_auth_username`, `last_activity` |

7. If admin requires username migration (has plaintext `username` set), redirect to `/admin/username-migration`.
8. Otherwise redirect to `/admin/dashboard`.

**On failure:** Generic "Invalid credentials or TOTP code" flash — no information leakage.

---

### 1.3 Legacy Username Migration

**Route:** `POST /admin/username-migration` (`app/routes/admin.py:1948`)

**Trigger:** Login detects `admin.username IS NOT NULL` (plaintext still stored).

**Flow:**

1. Teacher can keep current username or choose a new one.
2. On submit:

| Operation | Table | Details |
|-----------|-------|---------|
| Rebuild auth hashes | `admins` | `salt`, `username_hash`, `username_lookup_hash` recomputed |
| Null plaintext | `admins` | `SET username = NULL` |
| Assign public ID | `admins` | `teacher_public_id` if not already set |
| Assign hall pass token | `admins` | `hall_pass_verify_token` if not already set |

3. Session updated, migration flag cleared.

---

### 1.4 Session Management

**Session keys set on login:**

| Key | Value | Purpose |
|-----|-------|---------|
| `is_admin` | `True` | Role guard |
| `admin_id` | `int` | Identity |
| `admin_auth_username` | `str` | Display / cache |
| `last_activity` | ISO timestamp | Timeout enforcement |

**Timeout:** Checked by `@admin_required` decorator. Compares `last_activity` against configured threshold. Updated on each authenticated request.

**No `current_join_code` in admin session by default** — teachers see all their blocks. Block context is passed per-request as parameters.

---

### 1.5 Profile & Settings

**Route:** `POST /admin/settings` (`app/routes/admin.py:2769`)

**Mutable fields:**

| Field | Table | Notes |
|-------|-------|-------|
| `display_name` | `admins` | PIIEncryptedType; falls back to `teacher_public_id` if NULL |
| `class_label` | `teacher_blocks` | Per-block display name; bulk-updated for all seats sharing a block value |

**DB operations:**

```sql
UPDATE admins SET display_name = :encrypted_name WHERE id = :id;
UPDATE teacher_blocks SET class_label = :label WHERE teacher_id = :id AND block = :block;
```

Display name cache updated in session via `set_admin_display_name_cache()`.

---

### 1.6 Account Recovery Setup

**Route:** `POST /admin/setup-recovery` (`app/routes/admin.py:2743`)

**Purpose:** Legacy teachers who signed up before DOB-based recovery was required.

**Flow:**

1. Teacher enters date of birth.
2. `dob_sum = month + day + year`.
3. Fresh salt generated: `get_random_salt()`.
4. Hash stored:

| Operation | Table | Details |
|-----------|-------|---------|
| Store DOB hash | `admins` | `dob_sum_hash = hash_hmac(str(dob_sum).encode(), salt)`, `salt = <new salt>` |

---

### 1.7 Account Recovery Flow

**Route:** `POST /admin/recover` (`app/routes/admin.py:2281`)

**Actors:** Teacher (initiator) + Students (verifiers)

**Phase 1 — Teacher initiates:**

1. Teacher provides: student usernames (comma-separated), date of birth.
2. Students looked up via `hash_username_lookup()` → `username_lookup_hash`.
3. All students must share exactly **one common teacher** (via `student_teachers` join).
4. DOB sum verified against teacher's stored `dob_sum_hash` using same salt.
5. **Coverage check:** Students must cover all of the teacher's active blocks (one student per period minimum).
6. Recovery request created:

| Operation | Table | Details |
|-----------|-------|---------|
| INSERT request | `recovery_requests` | `admin_id`, `dob_sum_hash`, `status='pending'`, `expires_at = NOW + 5 days` |
| INSERT codes | `student_recovery_codes` | One row per nominated student: `recovery_request_id`, `student_id` |

**Phase 2 — Students verify (separate route):**

**Route:** `POST /student/verify-recovery/<code_id>` (`app/routes/student.py:4185`)

Each nominated student logs in and sees a recovery verification prompt. They enter their passphrase to confirm.

| Operation | Table | Details |
|-----------|-------|---------|
| Mark verified | `student_recovery_codes` | `status='verified'`, `verified_at = NOW`, `verification_hash = bcrypt(passphrase)` |

**Phase 3 — Threshold met:**

When all students have verified, the `RecoveryRequest.status` transitions to `'verified'`. The teacher can then re-register their TOTP secret (new QR code generated, old encrypted secret replaced).

| Operation | Table | Details |
|-----------|-------|---------|
| Update TOTP | `admins` | `totp_secret = encrypt_totp(new_secret)` |
| Update status | `recovery_requests` | `status = 'verified'` |

---

### 1.8 Logout

**Route:** `GET /admin/logout` (`app/routes/admin.py:2817`)

**Operations:**
- `clear_admin_display_name_cache()` (server-side cache).
- Pop all admin session keys: `is_admin`, `admin_id`, `admin_auth_username`, `last_activity`, `force_admin_username_migration`, `passkey_auth_username`.

No database writes.

---

### 1.9 Deletion

**Route:** `POST /sysadmin/delete-admin/<admin_id>` (`app/routes/system_admin.py:919`)

**Actor:** System admin only. Teachers cannot self-delete (line 1227 explicitly blocks it).

**Flow:**

1. Fetch all students linked via `student_teachers WHERE admin_id = :id`.
2. Partition into:
   - **Exclusive students** — only linked to this teacher (no other `student_teachers` rows).
   - **Shared students** — also linked to other teachers.
3. For **shared students**: Delete only the `student_teachers` link (detach, don't destroy).
4. For **exclusive students**, cascade delete in order:

| Order | Table | Filter |
|-------|-------|--------|
| 1 | `transaction` | `student_id IN (exclusive_ids)` |
| 2 | `tap_event` | `student_id IN (exclusive_ids)` |
| 3 | `hall_pass_log` | `student_id IN (exclusive_ids)` |
| 4 | `student_item` | `student_id IN (exclusive_ids)` |
| 5 | `rent_payment` | `student_id IN (exclusive_ids)` |
| 6 | `student_insurance` | `student_id IN (exclusive_ids)` |
| 7 | `insurance_claim` | `student_id IN (exclusive_ids)` |
| 8 | `student_teachers` | `student_id IN (exclusive_ids)` |
| 9 | `student_blocks` | `student_id IN (exclusive_ids)` |
| 10 | `teacher_blocks` | `student_id IN (exclusive_ids)` |
| 11 | `students` | `id IN (exclusive_ids)` |

5. Delete the `Admin` record itself (cascades `admin_credentials`, `recovery_requests` via FK).
6. Commit.

---

### 1.10 Admin Model — Complete Schema

**Table:** `admins` (`app/models.py:1862`)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | Integer | PK | Auto-increment |
| `username` | String(80) | Yes | **DEPRECATED** — legacy plaintext, set to NULL after migration |
| `username_hash` | String(64) | Yes | `HMAC(salt + username, pepper)` — per-account salted |
| `username_lookup_hash` | String(64) | Yes | `HMAC(username, pepper)` — deterministic, indexed, used for login lookup |
| `teacher_public_id` | String(120) | Yes | `word1_word2_word3` — student-facing identifier, unique |
| `display_name` | PIIEncryptedType | Yes | Fernet-encrypted; teacher-set display name |
| `totp_secret` | String(200) | No | Fernet-encrypted base64 TOTP secret |
| `dob_sum_hash` | String(64) | Yes | `HMAC(dob_sum, salt)` — for account recovery |
| `salt` | LargeBinary(16) | Yes | Per-account random salt |
| `created_at` | DateTime(tz) | Yes | UTC |
| `last_login` | DateTime(tz) | Yes | Updated on each successful login |
| `has_assigned_students` | Boolean | No | One-time flag for initial roster setup |
| `tos_accepted` | Boolean | No | Terms of Service acknowledgment |
| `tos_accepted_at` | DateTime(tz) | Yes | When ToS was accepted |
| `hall_pass_verify_token` | String(64) | Yes | 256-bit random capability token; rotatable; unique, indexed |

**Relationships:**
- `credentials` → `admin_credentials` (one-to-many, cascade delete)
- Via `student_teachers` → many-to-many with `students`
- Via `teacher_blocks` → roster seats (one-to-many)

---

## 2. Student Identity Lifecycle

### 2.1 Roster Upload (Seat Creation)

**Route:** `POST /admin/upload-students` (`app/routes/admin.py:8285`)

**Actor:** Teacher uploads a CSV file.

**Per-student row processing:**

1. Parse: `first_name`, `last_name`, `date_of_birth`, `period/block`.
2. Generate salt: `get_random_salt()` → 16 random bytes.
3. Compute `dob_sum = month + day + year`.
4. Compute `first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, salt)` — this is the credential that students use to claim their seat.
5. Compute `last_name_hash_by_part = hash_last_name_parts(last_name, salt)` — JSON array of per-part hashes for fuzzy matching.
6. Get or generate `join_code` for this teacher + block combination.

**DB operation:**

| Operation | Table | Details |
|-----------|-------|---------|
| INSERT seat | `teacher_blocks` | One row per student-period. See full columns below. |

**TeacherBlock row (unclaimed state):**

```
teacher_blocks:
  teacher_id              = <uploading teacher's ID>
  block                   = "A" (from CSV)
  first_name              = <Fernet-encrypted first name>
  last_initial            = "S"
  last_name_hash_by_part  = ["hash1", "hash2"]  (JSON)
  dob_sum                 = 2025  (month + day + year)
  salt                    = <16 random bytes>
  first_half_hash         = <HMAC hash of "first_initial + dob_sum">
  join_code               = "A7K2M9"
  student_id              = NULL
  is_claimed              = FALSE
  claimed_at              = NULL
  is_teacher              = FALSE
  created_at              = UTC NOW
```

**Important:** No `Student` record exists yet. The `TeacherBlock` row acts as an unclaimed "seat" in the roster.

---

### 2.2 Account Claim (Self-Registration)

**Route:** `POST /claim-account` (`app/routes/student.py:577`)

**Actor:** Student, unauthenticated.

**Input:** `join_code`, `first_initial`, `last_name`, `date_of_birth`.

**Flow:**

**Step 1 — Find matching seat:**

```sql
SELECT * FROM teacher_blocks
WHERE join_code = :join_code AND is_claimed = FALSE
```

Then in-memory: match `first_initial`, `dob_sum`, and fuzzy-match `last_name` against seat hashes.

**Step 2 — Deduplication check:**

```sql
SELECT * FROM students WHERE first_half_hash = :hash
```

- If student **already exists** (enrolled in another class): Link existing student to this seat, create `StudentTeacher` if needed, redirect to login.
- If student **is new**: Continue to Step 3.

**Step 3 — Create Student record:**

| Operation | Table | Details |
|-----------|-------|---------|
| INSERT student | `students` | See row details below |

```
students:
  first_name                    = <Fernet-encrypted>  (copied from seat)
  last_initial                  = "S"
  block                         = "A"  (from seat)
  salt                          = <16 bytes>  (copied from seat)
  first_half_hash               = <hash>  (copied from seat, UNIQUE)
  second_half_hash              = <hash of dob_sum>  (backward compat)
  dob_sum                       = 2025  (TEMPORARY — cleared after setup)
  last_name_hash_by_part        = [...]  (TEMPORARY — cleared after setup)
  has_completed_setup           = FALSE
  has_completed_profile_migration = FALSE
  is_teacher                    = FALSE
  is_active                     = TRUE
  recovery_status               = 'active'
  username_hash                 = NULL  (set in step 2.3)
  username_lookup_hash          = NULL  (set in step 2.3)
  pin_hash                      = NULL  (set in step 2.4)
  passphrase_hash               = NULL  (set in step 2.4)
```

**Step 4 — Link seat to student:**

| Operation | Table | Details |
|-----------|-------|---------|
| UPDATE seat | `teacher_blocks` | `student_id = :new_id`, `is_claimed = TRUE`, `claimed_at = NOW` |
| **PII cleanup** | `teacher_blocks` | `dob_sum = NULL`, `last_name_hash_by_part = NULL` |
| INSERT link | `student_teachers` | `student_id = :new_id`, `admin_id = :teacher_id` |

**Step 5:** Set `session['claimed_student_id']` and redirect to username creation.

---

### 2.3 Username Creation

**Route:** (follows claim flow, `app/routes/student.py:816`)

**Input:** A "write-in word" (3-12 characters chosen by student).

**Username formula:**

```
username = f"{adjective}{write_in_word}{dob_sum}{initials}"
```

Example: `"bravecat2025JS"`

**DB operations:**

| Operation | Table | Details |
|-----------|-------|---------|
| Hash username (salted) | `students` | `username_hash = HMAC(salt + username, pepper)` |
| Hash username (lookup) | `students` | `username_lookup_hash = HMAC(username, pepper)` — deterministic, unique, indexed |

The plaintext username is **never stored**. It is shown to the student once and must be memorized.

---

### 2.4 PIN & Passphrase Setup

**Route:** (follows username creation, `app/routes/student.py:860`)

**Input:** Numeric PIN + text passphrase.

**DB operations:**

| Operation | Table | Details |
|-----------|-------|---------|
| Hash PIN | `students` | `pin_hash = werkzeug.generate_password_hash(pin)` — bcrypt, 12+ rounds |
| Hash passphrase | `students` | `passphrase_hash = werkzeug.generate_password_hash(passphrase)` — bcrypt, 12+ rounds |
| PII cleanup | `students` | `dob_sum = NULL`, `last_name_hash_by_part = NULL` |
| Mark complete | `students` | `has_completed_setup = TRUE`, `has_completed_profile_migration = TRUE` |

**After this step:** The student's `dob_sum` and `last_name_hash_by_part` are permanently erased from both `students` and `teacher_blocks`. The only remaining claim credentials are the hashed `first_half_hash` (used for deduplication, not login).

---

### 2.5 Login

**Route:** `POST /student/login` (`app/routes/student.py:3676`)

**Input:** Username + PIN.

**Flow:**

1. Compute lookup hash: `hash_username_lookup(username)`.
2. Query: `SELECT * FROM students WHERE username_lookup_hash = :hash`.
3. Fallback for legacy: scan accounts with `username_hash` using per-account salt.
4. Verify PIN: `werkzeug.check_password_hash(student.pin_hash, pin)`.
5. Check `is_active = TRUE`.
6. Create session:

| Key | Value |
|-----|-------|
| `student_id` | `int` |
| `login_time` | ISO timestamp |
| `last_activity` | ISO timestamp |

**Session timeout:** 10 minutes strict from `login_time` (enforced in `@student_required` decorator, `app/auth.py:19`).

---

### 2.6 Profile & Settings

**Mutable student fields:**

| Field | When Changed | Table |
|-------|-------------|-------|
| `is_rent_enabled` | Student or teacher toggles | `students` |
| `insurance_plan` | Student enrolls | `students` |
| `hall_passes` | Payroll/rent system modifies | `students` |
| `block` | New class added (comma-appended) | `students` |

Students **cannot** change their username, PIN, or passphrase through normal settings — only via recovery.

---

### 2.7 Account Recovery

Student PIN/passphrase can be reset by the teacher. The student's `recovery_status` field tracks the state:
- `'active'` — normal operation.
- `'to_be_claimed'` — credentials reset, student must re-setup.

Teacher generates a reset code → student uses it to re-enter PIN & passphrase via the same `setup_pin_passphrase()` flow as initial registration.

**DB fields involved:**

| Column | Table | Purpose |
|--------|-------|---------|
| `reset_code` | `students` | 8-char alphanumeric, unique |
| `reset_code_expires_at` | `students` | Expiration timestamp |
| `recovery_status` | `students` | State machine: `active` ↔ `to_be_claimed` |
| `money_action_cooldown_until` | `students` | Prevents financial actions during recovery window |

---

### 2.8 Deactivation & Deletion

**Soft removal (from one teacher):**

**Route:** `POST /students/delete` (`app/routes/admin.py:3746`)

**Logic:** `remove_student_from_teacher_scope()` (`app/utils/student_deletion.py:150`)

| Step | Operation | Table |
|------|-----------|-------|
| 1 | Delete teacher link | `student_teachers WHERE student_id = :id AND admin_id = :teacher_id` |
| 2 | Unclaim seats | `teacher_blocks SET student_id = NULL, is_claimed = FALSE WHERE student_id = :id AND teacher_id = :teacher_id` |
| 3 | Check orphan | `SELECT COUNT(*) FROM student_teachers WHERE student_id = :id` |
| 4 | If orphaned → hard delete | See below |

**Hard delete (orphaned student):**

`hard_delete_student_if_orphaned()` (`app/utils/student_deletion.py:132`)

Deletes in order (all scoped to `student_id`):

| Order | Table |
|-------|-------|
| 1 | `redemption_audit_log` |
| 2 | `issue_resolution_action`, `issue_status_history` |
| 3 | `insurance_claim`, `student_insurance` |
| 4 | `issue`, `transaction`, `tap_event`, `hall_pass_log` |
| 5 | `student_item`, `rent_payment`, `rent_waiver` |
| 6 | `student_blocks`, `balance_cache` |
| 7 | `students` |

---

### 2.9 Student Model — Complete Schema

**Table:** `students` (`app/models.py:264`)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | Integer | PK | Auto-increment |
| `first_name` | PIIEncryptedType | Yes | Fernet AES-128 encrypted |
| `last_initial` | String(1) | Yes | Single character |
| `block` | String(10) | Yes | Comma-separated period list, e.g. `"A,B"` |
| `salt` | LargeBinary(16) | Yes | Per-account random salt |
| `first_half_hash` | String(64) | Yes | `HMAC(first_initial + dob_sum, salt)` — **UNIQUE**, dedup key |
| `second_half_hash` | String(64) | Yes | `HMAC(dob_sum)` — backward compat |
| `username_hash` | String(64) | Yes | `HMAC(salt + username, pepper)` — per-account salted |
| `username_lookup_hash` | String(64) | Yes | `HMAC(username, pepper)` — deterministic, **UNIQUE**, indexed |
| `pin_hash` | Text | Yes | bcrypt (Werkzeug) |
| `passphrase_hash` | Text | Yes | bcrypt (Werkzeug) |
| `dob_sum` | Integer | Yes | **TEMPORARY** — nulled after setup |
| `last_name_hash_by_part` | JSON | Yes | **TEMPORARY** — nulled after setup |
| `has_completed_setup` | Boolean | No | `FALSE` until PIN/passphrase set |
| `has_completed_profile_migration` | Boolean | No | Legacy migration flag |
| `is_active` | Boolean | No | Soft deactivation |
| `is_teacher` | Boolean | No | Prevents accidental deletion of teacher-student accounts |
| `is_rent_enabled` | Boolean | No | Default `TRUE` |
| `insurance_plan` | String | Yes | `"none"`, plan name |
| `insurance_last_paid` | DateTime(tz) | Yes | Last insurance premium payment |
| `hall_passes` | Integer | No | Default 3 |
| `second_factor_type` | String | Yes | Reserved for future 2FA |
| `second_factor_enabled` | Boolean | No | Default `FALSE` |
| `reset_code` | String(8) | Yes | Unique, for password recovery |
| `reset_code_expires_at` | DateTime(tz) | Yes | Recovery code expiration |
| `money_action_cooldown_until` | DateTime(tz) | Yes | Prevents financial ops during recovery |
| `recovery_status` | String(20) | Yes | `'active'` or `'to_be_claimed'` |
| `join_code` | String(20) | Yes | **Legacy** — current class (indexed) |
| `join_code_id` | String(36) | Yes | FK to `join_codes.join_code_id` |

**Key Relationships:**
- `teachers` → many-to-many via `student_teachers`
- `roster_seats` → `teacher_blocks` (backref)
- `student_blocks` → per-period state (passive deletes)
- `transactions` → financial history (backref)

---

## 3. Class Association Flow

### 3.1 Class Creation & Join Code Generation

**Trigger:** Teacher uploads CSV roster (`app/routes/admin.py:8305`).

Classes are **not created explicitly** — they are implicitly created when the first roster is uploaded for a teacher + block combination.

**Join code generation:** (`app/utils/join_code.py:12`)

- Format: 6 characters from `[A-Z minus O,I] + [2-9]` (avoids ambiguous characters).
- Example: `A7K2M9`.
- Uniqueness enforced: query `teacher_blocks WHERE join_code = :code` across all teachers.
- Up to 10 retry attempts; fallback to timestamp-based code.

**Per-block, one join code:** All students in the same teacher + block share one `join_code`. Different blocks get different codes.

**DB operations during roster upload:**

For each unique block encountered:

| Operation | Table | Details |
|-----------|-------|---------|
| Generate join_code | (in-memory) | `generate_join_code(length=6)` |
| Check uniqueness | `teacher_blocks` | `SELECT ... WHERE join_code = :code` |
| INSERT seats | `teacher_blocks` | One row per student (see 2.1 above) |

---

### 3.2 Student Enrollment (Initial Claim)

See [Section 2.2](#22-account-claim-self-registration) for the full claim flow.

**Summary of DB changes during enrollment:**

| Table | Operation |
|-------|-----------|
| `students` | INSERT (new student) |
| `teacher_blocks` | UPDATE: `student_id`, `is_claimed=TRUE`, PII nulled |
| `student_teachers` | INSERT: student ↔ teacher link |

**Important:** `StudentBlock` is **NOT** created during enrollment. It is created lazily on first access (during tap events, payroll, etc.).

---

### 3.3 Adding Additional Classes

**Route:** `POST /student/add-class` (`app/routes/student.py:910`)

**Prerequisites:** Student already logged in with completed setup.

**Flow:**

1. Student enters new `join_code`.
2. System finds unclaimed seats: `teacher_blocks WHERE join_code = :code AND is_claimed = FALSE`.
3. Credential matching against seat hashes (same algorithm as initial claim).
4. Cross-check: encrypted `first_name` + `last_initial` must match the logged-in student.
5. Check for duplicate enrollment (same teacher, same block).

**DB operations:**

| Operation | Table | Details |
|-----------|-------|---------|
| Link seat | `teacher_blocks` | `student_id = :id`, `is_claimed = TRUE`, PII nulled |
| Create teacher link | `student_teachers` | Only if new teacher (unique constraint: `student_id + admin_id`) |
| Update blocks | `students` | Append to comma-separated `block` field, e.g. `"A"` → `"A,B"` |

---

### 3.4 Class Context & Switching

**Context resolution:** `get_current_class_context()` (`app/routes/student.py:83`)

```python
# Returns:
{
    'join_code': 'A7K2M9',
    'teacher_id': 42,
    'block': 'A',
    'seat_id': 156
}
```

**Logic:**

1. Fetch all claimed seats: `teacher_blocks WHERE student_id = :id AND is_claimed = TRUE`.
2. Check session for `current_join_code`.
3. If not set or invalid, default to first seat.
4. Store in session and return.

**Switching route:** `POST /student/api/class/<join_code>/switch` (`app/routes/student.py:3898`)

1. Verify student has a claimed seat for target `join_code`.
2. Update `session['current_join_code'] = join_code`.
3. No database writes — purely session-based.

**For teachers:** No `current_join_code` concept. Teachers operate on explicit block/join_code parameters per request.

---

### 3.5 Student Removal from a Class

**Route:** `POST /students/delete` (`app/routes/admin.py:3777`)

**Logic:** `remove_student_from_teacher_scope()` (`app/utils/student_deletion.py:150`)

| Step | DB Operation |
|------|-------------|
| 1 | `DELETE FROM student_teachers WHERE student_id = :id AND admin_id = :teacher_id` |
| 2 | `UPDATE teacher_blocks SET student_id = NULL, is_claimed = FALSE, claimed_at = NULL WHERE student_id = :id AND teacher_id = :teacher_id` |
| 3 | Check: `SELECT COUNT(*) FROM student_teachers WHERE student_id = :id` |
| 4 | If count = 0 → `hard_delete_student_if_orphaned(:id)` (see 2.8) |

**Key behavior:**
- Removing from one teacher does NOT delete the student if they're enrolled with other teachers.
- Only orphaned students (no remaining `student_teachers` links) are hard-deleted.
- The seat becomes available for reclaiming (unclaimed state restored).

---

### 3.6 Class Deletion (Hard Delete)

**Route:** `DELETE /join-code` (`app/routes/admin.py:3883`)

**Prerequisite:** Teacher must type `DELETE JOIN CODE <code>` as confirmation.

**Core logic:** `_hard_delete_join_code_scope()` (`app/routes/admin.py:439`)

**Deletion cascade (all scoped to the join_code):**

| Order | Category | Tables Deleted |
|-------|----------|----------------|
| 1 | Financial | `transaction` |
| 2 | Attendance | `tap_event`, `student_blocks` (matching join_code) |
| 3 | Hall passes | `hall_pass_log` |
| 4 | Store | `student_item`, `store_item` (class-specific), `store_item_block` |
| 5 | Insurance | `student_insurance`, `insurance_claim` |
| 6 | Rent | `rent_payment` |
| 7 | Issues | `issue`, `issue_resolution_action` |
| 8 | Roster | `teacher_blocks` (teacher_id + join_code) |
| 9 | Cache | `balance_cache` |
| 10 | Analytics | `analytics_snapshot`, `analytics_event` |
| 11 | Announcements | `announcement` |
| 12 | Audit | `redemption_audit_log` |

**Orphan student cleanup** (after class-scoped deletion):

1. Find students whose only seats were in the deleted class.
2. Delete their `student_teachers` links.
3. Hard-delete the `Student` records themselves.

**Block settings cleanup:**

For `payroll_settings` and `rent_settings` (scoped to `teacher_id + block`):
- Only deleted if no remaining `teacher_blocks` rows exist for that block name.
- Preserves settings if teacher still teaches the same block under a different join_code.

---

### 3.7 Multi-Enrollment Data Model

**Same teacher, different periods:**

```
Student #5 (first_name="John", block="A,B")
  ├── teacher_blocks #100  (teacher=10, block="A", join_code="CODE1", claimed)
  ├── teacher_blocks #101  (teacher=10, block="B", join_code="CODE2", claimed)
  ├── student_teachers #50 (student=5, admin=10)          ← SINGLE link
  ├── student_blocks #200  (student=5, period="A", join_code="CODE1")
  └── student_blocks #201  (student=5, period="B", join_code="CODE2")

Transactions:
  - (student=5, join_code="CODE1", amount=50)   ← isolated to Period A
  - (student=5, join_code="CODE2", amount=75)   ← isolated to Period B
```

**Different teachers:**

```
Student #5
  ├── teacher_blocks #100  (teacher=10, block="A", join_code="CODE1", claimed)
  ├── teacher_blocks #102  (teacher=11, block="1", join_code="CODE3", claimed)
  ├── student_teachers #50 (student=5, admin=10)   ← link to teacher 10
  └── student_teachers #51 (student=5, admin=11)   ← link to teacher 11
```

**Critical isolation rule:** All financial data, balances, store items, insurance — everything is scoped by `join_code`, never by `teacher_id` alone. Each `join_code` represents a completely independent economic context.

---

## 4. Supporting Models

### 4.1 TeacherBlock (Roster Seats)

**Table:** `teacher_blocks` (`app/models.py:192`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `teacher_id` | Integer | FK → `admins.id` (CASCADE) |
| `block` | String(10) | Period identifier ("A", "1", etc.) |
| `class_label` | String(50) | Teacher-customizable display name |
| `first_name` | PIIEncryptedType | Student name (encrypted) |
| `last_initial` | String(1) | |
| `last_name_hash_by_part` | JSON | Fuzzy matching hashes; **nulled after claim** |
| `dob_sum` | Integer | Claim credential; **nulled after claim** |
| `salt` | LargeBinary(16) | Per-seat salt |
| `first_half_hash` | String(64) | Claim credential hash |
| `join_code` | String(20) | **Class isolation key** (indexed) |
| `join_code_id` | String(36) | FK → `join_codes.join_code_id` |
| `student_id` | Integer | FK → `students.id`; NULL until claimed |
| `is_claimed` | Boolean | Default `FALSE` |
| `claimed_at` | DateTime(tz) | When student claimed |
| `is_teacher` | Boolean | Flag for teacher-as-student accounts |
| `created_at` | DateTime(tz) | |

**State machine:** `is_claimed=FALSE, student_id=NULL` → (claim) → `is_claimed=TRUE, student_id=N, dob_sum=NULL, last_name_hash=NULL`

---

### 4.2 StudentBlock (Per-Period State)

**Table:** `student_blocks` (`app/models.py:831`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `student_id` | Integer | FK → `students.id` (CASCADE) |
| `period` | String(10) | Block name |
| `join_code` | String(20) | Class isolation key (indexed) |
| `tap_enabled` | Boolean | Default `TRUE` |
| `done_for_day_date` | Date | Locks student out for the day |
| `rent_hall_passes` | Integer | Hall passes from rent top-off |
| `created_at` | DateTime(tz) | |
| `updated_at` | DateTime(tz) | |

**Unique constraint:** `(student_id, period)`

**Creation:** Lazy — not created during claim. Created on first tap event or first access to period-specific functionality.

---

### 4.3 StudentTeacher (Many-to-Many)

**Table:** `student_teachers` (`app/models.py:612`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `student_id` | Integer | FK → `students.id` (CASCADE) |
| `admin_id` | Integer | FK → `admins.id` (CASCADE) |
| `join_code` | String(20) | Optional context |
| `created_at` | DateTime(tz) | |

**Unique constraint:** `(student_id, admin_id)` — one link per student-teacher pair, regardless of how many classes they share.

---

### 4.4 AdminCredential (Passkeys)

**Table:** `admin_credentials` (`app/models.py:1943`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `admin_id` | Integer | FK → `admins.id` (CASCADE) |
| `credential_id` | Text | Optional; not needed for passwordless.dev SaaS |
| `authenticator_name` | String(100) | User-friendly name |
| `created_at` | DateTime(tz) | |
| `last_used` | DateTime(tz) | |

---

### 4.5 RecoveryRequest & StudentRecoveryCode

**Table:** `recovery_requests` (`app/models.py:1969`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `admin_id` | Integer | FK → `admins.id` |
| `join_code` | String(20) | Optional |
| `dob_sum_hash` | String(64) | Verification trail |
| `status` | Enum | `pending`, `verified`, `expired`, `cancelled` |
| `expires_at` | DateTime(tz) | 5 days from creation |
| `created_at` | DateTime(tz) | |

**Table:** `student_recovery_codes` (linked to `recovery_requests`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer | PK |
| `recovery_request_id` | Integer | FK → `recovery_requests.id` |
| `student_id` | Integer | FK → `students.id` |
| `status` | String | `pending`, `verified` |
| `verified_at` | DateTime(tz) | |
| `verification_hash` | String | bcrypt of passphrase at verification time |

---

## 5. Cryptographic Summary

| Purpose | Algorithm | Key Material | Storage |
|---------|-----------|-------------|---------|
| PII at rest (names) | Fernet (AES-128-CBC + HMAC-SHA256) | `ENCRYPTION_KEY` env var | Base64 string in DB |
| TOTP secret at rest | Fernet | `ENCRYPTION_KEY` env var | Base64 string in DB |
| Username auth hash | HMAC-SHA256 | `PEPPER_KEY` + per-account `salt` | 64-char hex in DB |
| Username lookup hash | HMAC-SHA256 | `PEPPER_KEY` only (no salt) | 64-char hex in DB (indexed) |
| DOB sum hash | HMAC-SHA256 | Per-account `salt` | 64-char hex in DB |
| Claim credential hash | HMAC-SHA256 | Per-seat `salt` | 64-char hex in DB |
| Student PIN | bcrypt (Werkzeug) | 12+ rounds, random salt | bcrypt string in DB |
| Student passphrase | bcrypt (Werkzeug) | 12+ rounds, random salt | bcrypt string in DB |
| Hall pass verify token | `secrets.token_hex(32)` | N/A (random) | 64-char hex in DB |
| Teacher public ID | Word list selection | N/A (random) | Plaintext in DB |
| Join code | Random alphanumeric | N/A (random) | Plaintext in DB |

---

## 6. Known Debt & v2.0 Considerations

### Identity System Debt

1. **`students.teacher_id`** — Deprecated column still present. Legacy code paths may reference it. Should be dropped in v2.0.

2. **`students.block` as comma-separated string** — Multi-enrollment tracked as `"A,B,C"` in a single column. This is fragile, hard to query, and denormalized. The canonical source of truth is `teacher_blocks.is_claimed + student_id`, making this column redundant but still referenced.

3. **`students.join_code` / `students.join_code_id`** — Legacy single-class fields. Superseded by per-seat `teacher_blocks.join_code`. Should be dropped.

4. **`admins.username`** — Plaintext column kept for backward compatibility during migration. Should be dropped once all accounts are migrated.

5. **Dual hash system for usernames** — Both `username_hash` (salted) and `username_lookup_hash` (unsalted) exist. The salted hash is unused for lookup (can't compute without knowing which account to check). Consider whether both are needed.

6. **`StudentTeacher` uniqueness is per teacher, not per class** — A student enrolled in two blocks with the same teacher has ONE `student_teachers` row. This means the link doesn't capture *which* classes they share, only that they're linked. The actual enrollment data lives in `teacher_blocks`.

7. **`StudentBlock` lazy creation** — Not created during enrollment, which means it can be absent for students who haven't yet interacted with a period. Code must handle `None` checks everywhere. Consider eager creation during enrollment.

### Class Association Debt

8. **No explicit "Class" entity** — Classes exist implicitly as a `join_code` shared across `teacher_blocks` rows. There's no `classes` table with metadata (name, created_at, settings). Class-level settings (payroll, rent, banking) are stored in separate tables keyed by `teacher_id + block`, not by `join_code`.

9. **Block name vs join_code confusion** — Some settings tables use `block` (string name like "A"), others use `join_code`. This creates ambiguity when a teacher has multiple join_codes for the same block name (e.g., after deleting and recreating a class).

10. **PII lifecycle in TeacherBlock** — First name is encrypted but persists after claim. `dob_sum` and `last_name_hash` are correctly nulled, but the encrypted first name and last initial remain for display purposes. Consider whether claimed seats need PII at all.

11. **No audit trail for class membership changes** — When students are added/removed from classes, there's no `class_membership_history` table. Deletion is immediate and unrecoverable.

12. **Seat unclaiming on removal** — When a student is removed from a class, their seat reverts to unclaimed state but with `dob_sum=NULL` and `last_name_hash=NULL` (already cleaned up during original claim). This means the seat cannot be reclaimed by the original student without teacher re-uploading the roster.

---

*Last Updated: 2026-03-10*
*Covers codebase as of v1.4.0*

# Account Recovery Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-002     | 1.0     | 2026-04-22     | ARC-IDEN-002 v1.1 | Normative |

## I. Purpose

This document defines the v2 account recovery architecture for both student and teacher
principals.

Recovery restores credential access to an existing identity. It is not a password reset
that creates new records or alters economic history. It is an **identity rebinding
operation only**.

Supersedes `docs/ARCHITECTURE/IDENTITY/ARC-IDEN-002_Account_Recovery.md`.

## III. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

---

## II. Core Invariants (Non-Negotiable)

1. **No DOB.** No date of birth, DOB sum, or any birth-date-derived value is collected,
   stored, or used during recovery for any principal. This applies to both students and
   teachers.

2. **Ledger immutability.** Recovery must never modify, delete, merge, or rewrite
   historical economic records. No transactions, balances, item holdings, insurance
   records, or audit logs may be altered during recovery.

3. **Identity rebinding only.** Recovery replaces credential access on the same
   identity record. It does not create a new record, merge two records, or transfer
   economic state.

4. **Single active code.** Only one active reset code per identity at any time.

5. **Teacher-initiated for students.** Students cannot self-initiate recovery. A teacher
   must generate the reset code.

---

## IV. Scope

Applies to:
- Student credential recovery within a class economy boundary
- Teacher credential recovery (distinct flow — see §VII)

Does not apply to:
- System admin recovery (separate tier)
- Class deletion or archival flows

---

## V. Student Recovery

### IV.1 What Is Recoverable

Student recovery restores access to an existing `users` row (target model) or `students`
row (current runtime). All economic state remains attached to the same identity.

Credentials that are fully replaced during recovery:
- `username_hash` / `username_lookup_hash`
- `pin_hash`
- `passphrase_hash`

Credentials that are NOT touched during recovery:
- Economic records (`transaction`, `balance_cache`, etc.)
- Entitlement records (`student_items`, `student_insurance`, etc.)
- Attendance records (`tap_events`, `hall_pass_logs`)
- Obligation records (`rent_payments`, `insurance_claims`)

### IV.2 Recovery State

Recovery state lives on the identity record:

- `reset_code` — plaintext 8-character alphanumeric reset code; stored as plaintext
  because the teacher must be able to display it again after a page refresh until the
  code expires or recovery completes
- `reset_code_expires_at` — UTC timestamp; hard TTL of 10 minutes from generation
- `recovery_status` — `active` | `to_be_claimed`

Storage rationale: a reset code is a short-lived (10-minute), teacher-visible,
disposable code communicated in person. It is not a long-lived credential and does not
need to be hashed. Hashing it would make teacher redisplay impossible. Long-lived
credentials (PIN, passphrase, TOTP secret) are always hashed or encrypted; reset codes
are not.

### IV.3 Student Recovery Flow

**Step 1 — Teacher initiates**

Teacher initiates reset from student details view.

System must:
- Set `recovery_status → to_be_claimed`
- Invalidate any existing reset code
- Generate new 8-character random alphanumeric reset code
- Store the plaintext code in `reset_code`
- Set `reset_code_expires_at = now + 10 minutes`
- Log the reset event

The plaintext code is displayed to the teacher immediately and remains readable on
page refresh until the code expires or recovery completes. The teacher communicates
it verbally to the student in real time.

**Step 2 — Student submits join code + reset code**

Student navigates to the recovery entry point and submits:
- `join_code`
- reset code (plaintext)

Backend must validate:
- `reset_code` matches the submitted code (direct comparison)
- Code has not been used
- Code has not expired (`now < reset_code_expires_at`)
- `recovery_status == to_be_claimed`
- `join_code` matches the identity's class scope

If validation fails:
- Return a generic failure message
- Do not reveal whether a specific identity exists
- Do not alter economic or credential state

**Step 3 — Credential re-establishment**

If validation succeeds, student proceeds through the standard credential setup flow:
- Username
- PIN
- Passphrase

No identity verification fields (name, DOB, or any other PII) are re-entered.
The credential setup flow operates on the existing identity record.

Rules:
- All three credentials are fully replaced atomically.
- Old credentials become invalid immediately.
- No partial credential updates are permitted.
- If interrupted, `reset_code_hash` remains valid until expiration.

**Step 4 — Completion**

On successful credential setup:
- Clear `reset_code` (set to NULL)
- Clear `reset_code_expires_at`
- Set `recovery_status → active`
- Regenerate `current_session_nonce`
- Log successful reclaim event

### IV.4 State Machine

States: `active` | `to_be_claimed`

Allowed transitions:

| From | To | Trigger |
|------|----|---------|
| `active` | `to_be_claimed` | Teacher initiates reset |
| `to_be_claimed` | `active` | Successful reclaim |
| `to_be_claimed` | `active` | Reset code expiration (auto-clear) |

Forbidden transitions:

- Any transition that creates a new student record
- Any transition that merges two identity records
- `to_be_claimed → archived` without an explicit audit log entry

---

## VI. Teacher Recovery

Teacher recovery follows a different flow because teachers have a higher-security
authentication tier (TOTP required).

### V.1 What Is Recoverable

Teacher recovery restores access to an existing `users` row (target model) or `Admin`
row (current runtime).

Credentials that are fully replaced during recovery:
- `username_hash` / `username_lookup_hash`
- `totp_secret_encrypted` (new TOTP seed generated)
- Any enrolled passkey credentials are revoked

### V.2 Teacher Recovery Flow

Teacher recovery is system-admin–initiated. A teacher cannot self-initiate recovery
without sysadmin involvement.

**Step 1 — Sysadmin generates recovery token**

Sysadmin initiates recovery for the teacher account.

System must:
- Generate a time-bounded one-time recovery token (not a reset code — opaque URL token)
- Log the initiation event
- Deliver the token out-of-band (email or secure channel — implementation detail)

**Step 2 — Teacher uses recovery token**

Teacher submits the token via the recovery entry point.

Backend validates:
- Token exists and is unexpired
- Token is single-use

**Step 3 — Credential re-establishment**

If valid, teacher proceeds through standard teacher setup:
- New username
- New TOTP enrollment (mandatory)
- Optional passkey enrollment

All previously enrolled passkeys are invalidated.

**Step 4 — Completion**

On successful credential setup:
- Invalidate recovery token
- Regenerate `current_session_nonce`
- Log successful recovery event

---

## VII. Security Constraints (Both Roles)

- Reset codes and recovery tokens must be random and non-sequential.
- All codes/tokens are single-use — cleared on use or expiry.
- All codes/tokens have a hard TTL (student reset code: 10 minutes; teacher recovery
  token: implementation-defined, suggest 24 hours).
- **Reset codes are stored as plaintext** to support teacher redisplay after page
  refresh. This is intentional — reset codes are short-lived, disposable, and
  communicated in person. They are not long-lived credentials.
- Long-lived credentials (PIN, passphrase, TOTP secret) are always hashed or encrypted;
  this rule does not apply to reset codes.
- Rate-limit all recovery endpoints.
- Lock recovery flow after repeated failed attempts per identity.
- Never reveal whether a specific identity exists via recovery error messages.

---

## VIII. Hard Boundaries (Must Not Do)

The recovery system must NOT:

- Create a new identity record during recovery
- Merge two identity records automatically
- Transfer balances between accounts
- Copy, recreate, or void items or entitlements
- Issue refunds during recovery
- Modify transaction history
- Adjust economic balances
- Collect or verify DOB at any point
- Store DOB or any birth-date-derived value at any point

---

## IX. Target Model vs. Current Runtime

| Aspect | Target (Project 9) | Current Runtime |
|--------|-------------------|-----------------|
| Student identity record | `users` row | `students` row |
| Teacher identity record | `users` row | `Admin` row |
| Recovery state fields | On `users` | On `students` / `Admin` |
| Reset code storage | `reset_code` plaintext on `users` | `reset_code` plaintext on `students` — correct |

The current runtime `students.reset_code` plaintext storage is correct and intentional.
No change needed for Project 9 on this field — the field name and plaintext storage
model carry forward.

---

## X. Amendment

Revisions require version increment, effective-date update, and continued consistency
with `INV-CORE-000` and the identity architecture specs:

- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`

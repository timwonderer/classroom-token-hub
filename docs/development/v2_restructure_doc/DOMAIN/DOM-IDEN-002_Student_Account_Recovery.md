# DOM-IDEN-002 Student Account Recovery
| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-002     | 2.0     | 2026-04-22     | ARC-IDEN-002 v1.1 | Normative |

## I. Purpose

This document defines the v2 account recovery architecture for student principals.

Recovery restores credential access to an existing student identity. It is an **identity
rebinding operation only** — it never alters economic history or creates new records.

For teacher account recovery, see `DOM-IDEN-004_Teacher_Account_Recovery.md`.

Supersedes `docs/ARCHITECTURE/IDENTITY/ARC-IDEN-002_Account_Recovery.md`.

## II. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

---

## III. Core Invariants

1. **No DOB.** No date of birth, DOB sum, or any birth-date-derived value is collected,
   stored, or used at any point in student recovery.

2. **Ledger immutability.** Recovery must never modify, delete, merge, or rewrite
   historical economic records. No transactions, balances, item holdings, insurance
   records, or audit logs may be altered during recovery.

3. **Identity rebinding only.** Recovery replaces credential access on the same identity
   record. It does not create a new record, merge two records, or transfer economic state.

4. **Single active code.** Only one active reset code per student identity at any time.

5. **Teacher-initiated.** Students cannot self-initiate recovery. A teacher must generate
   the reset code.

---

## IV. Scope

Applies to:
- Student credential recovery within a class economy boundary

Does not apply to:
- Teacher recovery — see `DOM-IDEN-004_Teacher_Account_Recovery.md`
- System admin recovery (separate tier)
- Class deletion or archival flows

---

## V. What Is Recoverable

Student recovery restores access to an existing `users` row (target model) or `students`
row (current runtime). All economic state remains attached to the same identity.

Credentials that are fully replaced during recovery:
- `username_hash` / `username_lookup_hash`
- `pin_hash`
- `passphrase_hash`

Records that are NOT touched during recovery:
- Economic records (`transaction`, `balance_cache`, etc.)
- Entitlement records (`student_items`, `student_insurance`, etc.)
- Attendance records (`tap_events`, `hall_pass_logs`)
- Obligation records (`rent_payments`, `insurance_claims`)

---

## VI. Recovery State

Recovery state lives on the student identity record:

- `reset_code` — plaintext 8-character alphanumeric reset code
- `reset_code_expires_at` — UTC timestamp; hard TTL of 10 minutes from generation
- `recovery_status` — `active` | `to_be_claimed`

**Storage rationale:** Reset codes are short-lived (10-minute TTL), teacher-visible, and
communicated in person to the student. The plaintext code must be stored so the teacher
can redisplay it after a page refresh until it expires or recovery completes. This is
intentional — reset codes are not long-lived credentials. Long-lived credentials (PIN,
passphrase, TOTP secret) are always hashed or encrypted; reset codes are not.

---

## VII. Recovery Flow

**Step 1 — Teacher initiates**

Teacher initiates reset from the student details view.

System must:
- Set `recovery_status → to_be_claimed`
- Invalidate any existing reset code
- Generate new 8-character random alphanumeric reset code
- Store the plaintext code in `reset_code`
- Set `reset_code_expires_at = now + 10 minutes`
- Log the reset event

The code is displayed immediately to the teacher and remains readable on page refresh
until it expires or recovery completes. The teacher communicates it verbally to the
student in real time.

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

No identity verification fields (name, DOB, or any PII) are re-entered. The setup flow
operates on the existing identity record.

Rules:
- All three credentials are fully replaced atomically.
- Old credentials become invalid immediately.
- No partial credential updates are permitted.
- If interrupted, `reset_code` remains valid until expiration.

**Step 4 — Completion**

On successful credential setup:
- Clear `reset_code` (set to NULL)
- Clear `reset_code_expires_at`
- Set `recovery_status → active`
- Regenerate `current_session_nonce`
- Log successful reclaim event

---

## VIII. State Machine

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

## IX. Security Constraints

- Reset codes must be random and non-sequential.
- Reset codes are single-use — cleared on successful use or expiry.
- Hard TTL: 10 minutes.
- Reset codes are stored as plaintext (see §VI rationale).
- Rate-limit reset code generation and submission endpoints.
- Lock recovery flow after repeated failed submission attempts per identity.
- Never reveal whether a specific student identity exists via error messages.

---

## X. Hard Boundaries

The student recovery system must NOT:

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

## XI. Target Model vs. Current Runtime

| Aspect | Target (Project 9) | Current Runtime |
|--------|-------------------|-----------------|
| Identity record | `users` row | `students` row |
| Recovery state fields | On `users` | On `students` |
| Reset code storage | `reset_code` plaintext on `users` | `reset_code` plaintext on `students` — correct |

The current runtime `students.reset_code` plaintext storage is correct and intentional.
The field name and storage model carry forward directly into Project 9.

---

## XII. Amendment

Revisions require version increment, effective-date update, and continued consistency
with `INV-CORE-000` and:

- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

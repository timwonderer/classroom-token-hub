# Teacher Account Recovery Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-004     | 2.0     | 2026-04-22     | LOG-ARC-011 v1.1 | Normative |

## I. Purpose

This document defines the v2 account recovery architecture for teacher principals.

Teacher recovery is **self-serve and student-assisted**. The teacher proves identity
through their roster. No sysadmin involvement is required. No DOB or personal contact
information is used in the target model.

For student account recovery, see `DOM-IDEN-002_Student_Account_Recovery.md`.

Supersedes `docs/LOGS/AUDITS/LOG-ARC-011_Recovery_Evaluation.md` (informative).

## II. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`

---

## III. Core Invariants

1. **No DOB in target model.** No date of birth, DOB sum, or any birth-date-derived
   value is collected, stored, or used at any point in v2 teacher recovery. The current
   runtime still uses `dob_sum_hash` — this must be removed as part of Project 9.

2. **Self-serve.** Teacher recovery does not require system admin intervention.

3. **Identity rebinding only.** Recovery replaces credential access on the same
   identity record. It does not create new records or alter class or economic state.

4. **All classes must be represented.** One student per active class period must
   participate. Partial coverage is rejected.

5. **Distributed trust.** A single compromised student account cannot enable teacher
   account takeover. All represented class periods must verify.

6. **All-or-nothing code validation.** On any failed submission of recovery codes,
   all codes are invalidated immediately and students must regenerate. This prevents
   incremental probing of individual codes.

---

## IV. Scope

Applies to:
- Teacher credential recovery (self-serve, student-assisted)

Does not apply to:
- Student recovery — see `DOM-IDEN-002_Student_Account_Recovery.md`
- System admin recovery (separate tier)

---

## V. Data Model

Recovery state is tracked via two models:

### `RecoveryRequest`
- `teacher_id` — FK to teacher identity
- `status` — `pending` | `verified` | `expired`
- `expires_at` — UTC, 5-day TTL from creation
- `partial_codes` — DB-persisted list of codes entered so far (for cross-session resume)
- `resume_pin_hash` — hashed 6-digit PIN for resuming a saved session
- `resume_new_username` — saved new username for resume
- `dob_sum_hash` — **legacy field; present in current runtime; must be removed in Project 9**

### `StudentRecoveryCode`
- `recovery_request_id` — FK to `RecoveryRequest`
- `student_id` — FK to student who will verify
- `code_hash` — `HMAC(6-digit-code, b'')` — set when student completes verification;
  `NULL` means student has not yet generated their code
- `verified_at` — timestamp when student completed their verification

---

## VI. Recovery Flow

### Step 1 — Roster verification and request creation

Teacher navigates to `/recover` and submits:

**Target model (v2):**
- One `(join_code, username)` pair per active class period

Lookup rules (must be applied in this order):
1. Resolve `join_code → class_id`. Reject if unrecognized or not belonging to the
   teacher's account.
2. Within that resolved `class_id`, find the student by `username_lookup_hash`. Never
   search by username across the full table — always scope to the resolved `class_id`
   first.
3. Mark the pair verified if both the class resolves and the student is found within it.

**Current runtime (transitional):**
- Teacher submits student usernames (comma-separated) + DOB sum
- Backend finds students by `username_lookup_hash` (global, not class-scoped)
- Teacher identity is resolved via the common teacher across all submitted students
- DOB sum is verified against `Admin.dob_sum_hash`
- Block coverage is verified: submitted students must cover all active blocks

> [!WARNING]
> The current runtime uses DOB sum as a verification factor. This is explicitly
> prohibited in the target v2 model. `dob_sum_hash` on `Admin` must be removed
> before Project 9 cutover.

**Submission rules (both models):**
- One student per active class period is required; full coverage is enforced.
- All pairs/students validated atomically — partial success is not reported.
- Generic error on any failure; do not reveal which student or class failed.
- If an active recovery request already exists for this teacher, redirect to
  the recovery status page rather than creating a duplicate.

On success: a `RecoveryRequest` is created with `status = 'pending'` and
`expires_at = now + 5 days`. One `StudentRecoveryCode` row is created per selected
student with `code_hash = NULL`.

### Step 2 — Student verification and code generation

**Student side:**

Each selected student sees a persistent banner at the top of the app on their next
login (or immediately if already logged in). The banner prompts them to verify their
teacher's recovery request.

Student action sequence:
1. Student sees the banner and confirms.
2. Student enters their passphrase (financial-gate verification, same as any financial
   action).
3. On successful passphrase verification, the system generates a **6-digit numeric**
   recovery code and displays it to the student.
4. The code hash (`HMAC(code, b'')`) is stored in `StudentRecoveryCode.code_hash`.
5. Student communicates the plaintext code to their teacher in person.

Rules:
- Each student generates exactly one code per recovery request.
- The 6-digit code is generated by the system, not chosen by the student.
- Once generated, the code is not redisplayed. If the student loses it, the teacher
  must invalidate and restart (or wait for failure invalidation).
- Students cannot confirm outside an active `RecoveryRequest` with `status = 'pending'`.

**Teacher side — recovery status:**

Teacher monitors `/recovery-status` to see how many students have verified
(`code_hash IS NOT NULL`) vs. total required. The page shows a count only —
not individual student names or code values.

### Step 3 — Code entry and submission

Teacher navigates to `/reset-credentials` and enters all recovery codes collected
from students.

**Persistence across sessions:**

Entered codes and the new username are saved to `RecoveryRequest.partial_codes` and
`RecoveryRequest.resume_new_username` in the database when the teacher saves progress.
A 6-digit **resume PIN** is generated, hashed as `HMAC(pin, b'')`, and stored in
`RecoveryRequest.resume_pin_hash`. The teacher uses this PIN at `/resume-credentials`
to reload their saved state on any future browser session within the 5-day window.

Persistence rules:
- Entered codes are DB-persisted, not session-only.
- The teacher may enter codes gradually as students provide them.
- **Before submission, no indication is shown as to which entered codes are valid
  or invalid.** Codes are stored as entered without pre-validation feedback.

**Submission:**

When the teacher submits all entered codes:
- Backend verifies all students have generated codes (`code_hash IS NOT NULL` for all).
- Codes are validated as a set (order-independent): `set(HMAC(entered, b''))` must
  equal `set(stored code_hashes)`.
- **On any failure (wrong count, invalid format, hash mismatch): ALL `StudentRecoveryCode`
  rows are invalidated (`code_hash = NULL`, `verified_at = NULL`).** Students must
  regenerate their codes from the banner.
- **The failure message does not indicate which code failed or why.** A single generic
  error is shown.
- Teacher may attempt resubmission after students regenerate codes, within the 5-day
  window.

### Step 4 — Credential re-establishment

If all codes match:
- Teacher enters new username and scans a newly generated TOTP QR code.
- TOTP code from the new device is verified before credentials are written.
- All previously enrolled passkeys are revoked.
- New `username_hash`, `username_lookup_hash`, and `totp_secret` are written atomically.
- `RecoveryRequest.status` is set to `verified`.

### Step 5 — Completion

On successful credential setup:
- `RecoveryRequest.status = 'verified'`, `completed_at` set.
- Session recovery keys cleared.
- Teacher redirected to login with new credentials.
- Audit log: teacher identity + timestamp only; no student PII logged.

---

## VII. Session Expiry

The entire recovery session (Steps 1–5) expires 5 days after Step 1 completion.

On expiry:
- `RecoveryRequest.status` is set to `expired`.
- All `StudentRecoveryCode` rows become inert.
- Entered partial codes and resume PIN are inaccessible.
- Teacher must restart from Step 1.

---

## VIII. Security Properties

| Property | Mechanism |
|----------|-----------|
| Distributed trust | One student per class; all must verify |
| All-or-nothing code validation | Any wrong code wipes all codes — no incremental probing |
| No pre-submission feedback | Entered codes show no valid/invalid state before submit |
| Generic failure messages | No indication of which code or student caused failure |
| Cross-session persistence | Partial codes persisted in DB via resume PIN, not session |
| Resume PIN | 6-digit PIN, hashed — links browser back to DB-stored progress |
| Passphrase gate on students | Student must re-enter passphrase to generate their code |
| No contact PII | No email, phone used at any stage |
| No DOB (target) | DOB removed in Project 9 — current runtime still uses it |

---

## IX. Hard Boundaries

The teacher recovery system must NOT:

- Accept partial class coverage (all active classes must be represented)
- Pre-validate individual codes before the teacher submits all of them
- Reveal which code, student, or class caused a validation failure
- Preserve any `StudentRecoveryCode.code_hash` after a failed submission
- Collect or verify DOB at any point in the target v2 model
- Allow student-initiated confirmation outside an active `RecoveryRequest`
- Preserve enrolled passkeys across a recovery event
- Log student PII in recovery audit records

---

## X. Target Model vs. Current Runtime

| Aspect | Target (Project 9) | Current Runtime |
|--------|-------------------|-----------------|
| Teacher identity | `users` row | `Admin` row |
| Step 1 auth factor | `(join_code, username)` pairs, class-scoped | Student usernames + DOB sum |
| Username lookup | Scoped to `class_id` after `join_code` resolution | Global `username_lookup_hash` |
| DOB involvement | **None** | `dob_sum_hash` on `Admin` — must be removed |
| `RecoveryRequest` model | On `users` FK | On `Admin` FK — correct pattern, migrates as-is |
| `StudentRecoveryCode` model | Migrates as-is | Current implementation |
| Code format | 6-digit numeric | 6-digit numeric ✅ |
| Code invalidation on failure | All-or-nothing wipe | All-or-nothing wipe ✅ |
| Resume PIN | DB-persisted | DB-persisted ✅ |

---

## XI. Amendment

Revisions require version increment, effective-date update, and continued consistency
with `INV-CORE-000` and:

- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`

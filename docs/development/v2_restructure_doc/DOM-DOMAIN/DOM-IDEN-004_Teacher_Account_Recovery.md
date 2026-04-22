# Teacher Account Recovery Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-004     | 1.0     | 2026-04-22     | LOG-ARC-011 v1.1 | Normative |

## I. Purpose

This document defines the v2 account recovery architecture for teacher principals.

Teacher recovery is **self-serve and student-assisted**. The teacher proves identity
through their roster — specifically, by demonstrating knowledge of a student username
per each class they teach. No sysadmin involvement is required. No DOB or personal
contact information is used at any stage.

For student account recovery, see `DOM-IDEN-002_Student_Account_Recovery.md`.

Supersedes `docs/LOGS/AUDITS/LOG-ARC-011_Recovery_Evaluation.md` (informative).

## II. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`

---

## III. Core Invariants

1. **No DOB.** No date of birth, DOB sum, or any birth-date-derived value is collected,
   stored, or used at any point in teacher recovery.

2. **Self-serve.** Teacher recovery does not require system admin intervention. The
   teacher initiates and completes recovery through the application.

3. **Identity rebinding only.** Recovery replaces credential access on the same identity
   record. It does not create new records or alter class or economic state.

4. **All classes must be covered.** Recovery requires one verified student per active
   class. Partial coverage is rejected.

5. **Distributed trust.** A single compromised student account cannot unilaterally
   enable teacher account takeover. All classes must be represented.

---

## IV. Scope

Applies to:
- Teacher credential recovery (self-serve, student-assisted)

Does not apply to:
- Student recovery — see `DOM-IDEN-002_Student_Account_Recovery.md`
- System admin recovery (separate tier)
- Class deletion or archival flows

---

## V. What Is Recoverable

Teacher recovery restores access to an existing `users` row (target model) or `Admin`
row (current runtime).

Credentials that are fully replaced during recovery:
- `username_hash` / `username_lookup_hash`
- `totp_secret_encrypted` (new TOTP seed generated and enrolled)
- All enrolled passkey credentials are revoked at credential re-establishment

Records that are NOT touched during recovery:
- Class configurations
- Economic records
- Student rosters
- Audit logs (recovery event is appended, not modified)

---

## VI. Recovery Flow

### Step 1 — Roster pair verification

Teacher navigates to the recovery entry point and submits one `(join_code, username)`
pair for each class they currently teach.

**Lookup rules — must be applied in this exact order:**

1. Resolve `join_code → class_id`. If the `join_code` is unrecognized or does not
   belong to the claimed teacher account, reject the entire submission immediately.
2. Within that resolved `class_id`, find the student by `username_lookup_hash`. Never
   search by username across the full table — always scope to the resolved `class_id`
   first.
3. Mark the pair as verified if both the class resolves and the student is found within it.

**Submission rules:**

- One `(join_code, username)` pair is required per active class the teacher runs.
- The set of `join_codes` submitted must fully cover all of the teacher's active classes.
  No partial coverage is accepted.
- All pairs are validated atomically. A single failing pair rejects the entire
  submission. Partial success is never reported.
- On any failure: return a generic error. Do not reveal which pair failed, whether any
  individual class was recognized, or whether any student username exists.

If all pairs pass, a time-bounded recovery session is opened (TTL: 10 minutes).

### Step 2 — Student verification

Each student identified in Step 1 receives an in-app prompt asking them to confirm that
their teacher is physically present and requesting account recovery.

Rules:
- All identified students must confirm within the session TTL.
- If any student declines or the session expires, the entire recovery is invalidated.
  Teacher must restart from Step 1.
- Students cannot initiate, pre-approve, or confirm outside an active recovery session.
- Confirmation is reactive only — it is triggered by the teacher's Step 1 submission.

### Step 3 — Credential re-establishment

If all student confirmations are received within the session window:

Teacher proceeds through standard teacher credential setup:
- New username
- New TOTP enrollment (mandatory — recovery session does not complete without it)
- Optional passkey enrollment

All previously enrolled passkeys are invalidated at the start of this step, before
new credentials are written.

### Step 4 — Completion

On successful credential setup:
- Invalidate the recovery session
- Regenerate `current_session_nonce`
- Log the recovery event: teacher identity + timestamp only; no student PII is logged

---

## VII. Security Properties

| Property | Mechanism |
|----------|-----------|
| Distributed trust | One student per class; all must confirm |
| No stored PII | No email, phone, or DOB at any stage |
| Roster knowledge as auth factor | Only the legitimate teacher knows valid `(join_code, username)` pairs across all their classes |
| `class_id`-scoped lookup | Username search is always scoped to the resolved `class_id` first — prevents cross-class collision attacks |
| Atomic validation | No partial success signals that could aid enumeration |
| Session TTL | Recovery window expires if not completed promptly |
| Passkey revocation | All passkeys invalidated at credential re-establishment |

---

## VIII. Hard Boundaries

The teacher recovery system must NOT:

- Require sysadmin intervention to initiate or complete
- Accept partial class coverage (all active classes must be represented)
- Reveal which pair, class, or student failed validation
- Collect or verify DOB at any point
- Store DOB or any birth-date-derived value at any point
- Allow student pre-approval outside an active recovery session
- Preserve enrolled passkeys across a recovery event
- Log student PII as part of the recovery audit record

---

## IX. Target Model vs. Current Runtime

| Aspect | Target (Project 9) | Current Runtime |
|--------|-------------------|-----------------|
| Teacher identity record | `users` row | `Admin` row |
| Student lookup scope | `class_id` from `classes` | `class_id` from `class_economies` via `join_code` |
| Recovery session storage | On `users` | Implementation-defined (in-memory or DB session) |

The `join_code → class_id` resolution uses `class_economies` in the current runtime.
The lookup-order rule (resolve `class_id` first, then scope student search) applies
identically in both the current and target models.

---

## X. Amendment

Revisions require version increment, effective-date update, and continued consistency
with `INV-CORE-000` and:

- `DOM-IDEN-001_Identity_Class_Binding_Domain.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`

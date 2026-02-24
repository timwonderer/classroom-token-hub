# Student Account Recovery & Reclaim Specification

> **Verified against implementation.**
> Claims marked ~~strikethrough~~ reflect original design intent that was
> revised before or during implementation. Correction notes appear inline.
> See also: `teacher_account_recovery_spec.md` for teacher credential recovery.

---

## Purpose

This document defines the architecture, constraints, and invariants for the
Student Account Recovery & Reclaim feature.

The goal is to allow students to safely recover access to their existing
classroom economy account without:
- Deleting student records
- Recreating accounts
- Manually transferring balances
- Modifying historical transactions
- Altering economic history

This feature must preserve all existing economic data and adhere strictly to
ledger immutability principles.

---

## Core Invariant (Non‑Negotiable)

Account recovery must never modify, delete, merge, or rewrite historical
economic records.

Specifically:
- No transaction records may be altered.
- No balances may be edited manually.
- No items, insurance policies, or ownership records may be recreated.
- No historical logs may be rewritten.
- No migration files may be modified.

Account recovery is an identity rebinding operation only.

---

## Conceptual Model

Recovery is not a password reset.

Recovery is the process of re‑binding a human student to an existing participant
record within a specific `join_code` economy.

The economic record remains unchanged. Only credential access is restored.

There is a single recovery flow. All resets are teacher‑initiated and
time‑bounded.

---

## Data Model

### `students` table — recovery-relevant columns

| Column | Type | Notes |
|---|---|---|
| `reset_code` | String(8), nullable, **globally unique** | 8-character code from unambiguous alphabet |
| `reset_code_expires_at` | DateTime(tz), nullable | UTC; set to `now + 10 minutes` |
| `recovery_status` | String(20), default `'active'` | `active` / `to_be_claimed` / `archived` |

> **Correction:** The original spec named this column `status` and described it
> as a database enum. The actual column is named `recovery_status` and is a
> plain `String(20)` column with no enum constraint.

> **Correction:** The original spec stated the uniqueness constraint was scoped
> to `join_code`. The actual DB column has a global `UNIQUE` constraint across
> all students.

### Reset code alphabet

```
ABCDEFGHJKLMNPQRSTUVWXYZ23456789
```

Characters omitted to prevent visual confusion: `O`, `I`, `L`, `1`, `0`.

---

## Recovery Flow

### Step 1 — Teacher Initiates Reset (`POST /recovery/admin/generate-code/<student_id>`)

Teacher clicks **Reset Student Account** in Student Details.

System must:
- Verify teacher owns this student (`get_student_for_admin` scoping check).
- Overwrite any existing `reset_code` with a new 8-character code drawn from
  the unambiguous alphabet using `secrets.choice`.
- Set `reset_code_expires_at = utc_now() + 10 minutes`.
- Set `recovery_status = 'to_be_claimed'`.
- Log: `"Reset code generated for student {id} by admin {admin_id}"`.
- Flash the code and expiry to the teacher.
- Redirect to the student detail page.

Teacher provides reset_code to student immediately (in real time). The code is
displayed on the student detail page while the recovery is in progress.

---

### Step 2 — Student Enters Join Code + Reset Code (`POST /recovery/lookup`)

**Rate limit:** 10 per minute (production); 1000 per minute (test environment).

Student navigates to the login page and clicks "I can't log into my account",
then submits:
- `join_code` (uppercased on input)
- `reset_code` (uppercased on input)

**Backend validation sequence:**
1. Find a `TeacherBlock` row where `join_code` matches AND the linked student
   has `reset_code` matching the submitted code.
2. Load the student from `TeacherBlock.student_id`.
3. Check `reset_code_expires_at` is non-null and in the future.
4. Check `recovery_status == 'to_be_claimed'`.

All conditions are checked before any response is given. A single generic
message is shown on failure: `"Invalid or expired recovery code."`

**On success:**
- If `TeacherBlock.is_claimed` is True and `TeacherBlock.claimed_at` is None,
  set `claimed_at = utc_now()`.
- Clear all credentials:
  - `student.username_hash = None`
  - `student.username_lookup_hash = None`
  - `student.pin_hash = None`
  - `student.passphrase_hash = None`
  - `student.has_completed_setup = False`
- **`reset_code` and `recovery_status` are NOT cleared here.** They remain
  until credential setup completes.
- Set `session['claimed_student_id'] = student.id`.
- Log: `"Recovery lookup succeeded for student {id}; credentials cleared."`
- Redirect to `/student/create-username`.

---

### ~~Step 3 — Identity Re‑Registration~~ (Removed)

> **This step was removed from the implementation.**
> The original design required students to re-enter first name, last name, and
> date of birth. The `/recovery/verify-identity` route now redirects directly
> to `/recovery/lookup`.
>
> **Current behavior:** Identity (first name, last initial) is managed by the
> teacher and remains unchanged through recovery. No PII re-entry is required.

---

### Step 3 — Credential Re‑Establishment

Student proceeds through the normal credential setup flow:
- Username (via `/student/create-username`)
- PIN and passphrase (via `/student/setup-pin-passphrase`)

Rules:
- All four credential hashes are fully replaced.
- Old credentials become invalid immediately (cleared in Step 2).
- No partial credential updates allowed.
- If interrupted mid-flow, `reset_code` remains valid until expiration (it is
  not cleared until setup completes).

---

### Step 4 — Completion (`POST /student/setup-pin-passphrase`)

Upon successful credential setup:
- `student.reset_code = None`
- `student.reset_code_expires_at = None`
- `student.recovery_status = 'active'`
- `student.has_completed_setup = True`
- `session['claimed_student_id']` is cleared.
- PII cleanup: `student.dob_sum = None`, `student.last_name_hash_by_part = None`,
  `student.has_completed_profile_migration = True`.

---

## State Machine (Formal Definition)

### States

| State | Meaning |
|---|---|
| `active` | Student can log in normally |
| `to_be_claimed` | Recovery initiated; student must re-establish credentials |
| `archived` | Soft-deleted; cannot log in |

### Allowed Transitions

| # | From | To | Trigger |
|---|---|---|---|
| 1 | `active` | `to_be_claimed` | Teacher initiates reset |
| 2 | `to_be_claimed` | `active` | Student completes credential setup |
| 3 | `active` | `archived` | Teacher deletes student or class |

> **Implementation note:** Transition 3 from the original design (expired
> `reset_code` triggers automatic `to_be_claimed → active`) is **not
> implemented**. Status is only set back to `active` after successful credential
> setup. The expired code causes the lookup to fail, but the `recovery_status`
> is not automatically reverted.

### Forbidden Transitions

- `archived → active` (no explicit restore feature exists)
- `to_be_claimed → archived` without logging
- Any transition that creates a new student record automatically

---

## Security Constraints

| Constraint | Implementation |
|---|---|
| Reset code randomness | `secrets.choice` from unambiguous alphabet |
| Reset code length | 8 characters |
| Reset code uniqueness | Global unique constraint on `students.reset_code` |
| Reset code expiry | Hard TTL: 10 minutes |
| Reset code single-use | Code cleared after successful credential setup |
| Rate limit | 10 per minute (production) on `/recovery/lookup` |
| Generic error messages | No student existence revealed on failure |
| Credential clearing | All four credential hashes nulled atomically before redirecting |

---

## Hard Boundaries (Must Not Do)

The recovery system must NOT:
- Create a new student record during recovery.
- Merge two student records automatically.
- Transfer balances between accounts.
- Copy or recreate items.
- Issue refunds during recovery.
- Modify transaction history.
- Adjust economic balances.
- Alter migration history.

Recovery restores access. It does not alter economic reality.

---

## Acceptance & Safety Test Cases

*(Covered by `tests/test_flow_credential_reset.py` and `tests/test_student_recovery.py`.)*

### Identity Integrity Tests

- Recovering an account must not create a new student row.
- `student_id` must remain constant through recovery.
- `first_name` and `last_initial` must be unchanged after recovery.

### Economic Invariance Tests

- Balance before reset == balance after reset.
- Transaction count before reset == transaction count after reset.
- No new economic transactions are created during recovery.

### Reset Code Tests

- Reset code is 8 characters from the unambiguous alphabet.
- Generating a new reset code replaces any existing one.
- Reset code is cleared after successful credential setup.
- Expired code returns generic error; no state changes.

### Edge Case Tests

- Attempt lookup when `recovery_status != 'to_be_claimed'` → fail.
- Attempt lookup with expired `reset_code_expires_at` → fail.
- Interrupting after lookup (mid credential setup) leaves `recovery_status = 'to_be_claimed'`
  and `reset_code` intact until the code expires.

### Migration Discipline Tests

- No historical migration files are edited.
- No legacy economic data is rewritten.

---

## Summary Principle

Credentials are disposable.
Identity is reclaimable.
Economic history is immutable.
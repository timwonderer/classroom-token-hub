# Account Recovery & Reclaim Specification

## Purpose

This document defines the architecture, constraints, and invariants for the **Account Recovery & Reclaim** feature.

The goal is to allow students to safely recover access to their existing classroom economy account without:

- Deleting student records
- Recreating accounts
- Manually transferring balances
- Modifying historical transactions
- Altering economic history

This feature must preserve all existing economic data and adhere strictly to ledger immutability principles.

---

## Core Invariant (Non‑Negotiable)

**Account recovery must never modify, delete, merge, or rewrite historical economic records.**

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

Recovery is the process of re‑binding a human student to an existing participant record within a specific join_code economy.

The economic record remains unchanged. Only credential access is restored.

---

## Data Model Changes

### New / Updated Fields on Student

Add the following columns to the student table:

- `reset_code` (string, nullable)
- `reset_code_expires_at` (datetime, nullable)
- `status` (enum):
  - `active`
  - `to_be_claimed`
  - `archived` (existing or future use)

Constraints:

- `reset_code` must be unique within a join_code scope.
- `reset_code` must be one-time use.
- `reset_code` must be cleared upon successful claim.

---

## Recovery Modes

There are two recovery modes that share the same reclaim pipeline.

### Mode A — Student-Initiated Recovery Request

Used when a student forgets:

- Username
- PIN
- Passphrase
- Any combination of the above

Flow:

1. Student navigates to “Recover My Classroom Economy Account”.
2. Student submits:
   - join_code
   - first name
   - full last name
   - date of birth
3. Backend attempts to uniquely match a student record.

Rules:

- If zero matches: show generic failure message.
- If multiple matches: show generic failure message.
- If exactly one match:
  - Notify teacher of recovery request.
  - Do NOT display reset code to student.
  - Do NOT automatically log the student in.

Teacher must approve and generate reset code.

---

### Mode B — Teacher-Initiated Reset for Reclaim

Used when:

- Student account is stuck
- Migration limbo exists
- Teacher manually decides reset is required

Flow:

1. Teacher clicks “Reset for Reclaim”.
2. System:
   - Sets student status → `to_be_claimed`
   - Generates 8-character mixed alphanumeric reset_code
   - Sets expiration timestamp (recommended: 24–72 hours)
   - Logs reset event
3. Teacher provides reset_code to student.

---

## Reclaim Flow (Shared Pipeline)

1. Student enters reset_code on “Recover My Account with Reset Code” page.
2. Backend validates:
   - Code exists
   - Code unused
   - Code unexpired
   - Student status = `to_be_claimed`
3. Student is shown minimal context:
   - Class / block identifier
   - Teacher name (optional)

No financial data may be displayed at this stage.

4. Student must re-enter:
   - First name
   - Full last name
   - Date of birth

5. On success:
   - Credentials (username, PIN, passphrase) are re-established
   - `reset_code` is cleared
   - `reset_code_expires_at` cleared
   - Status set → `active`
   - Reclaim event logged

---

## Security Constraints

- Reset codes must be random, 8-character alphanumeric.
- Reset codes must be one-time use.
- Reset codes must expire.
- Rate limit reset code attempts.
- Lock reclaim flow after repeated failed attempts.
- Never reveal whether a specific student exists during Mode A.

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

If identity cannot be uniquely resolved, the system must fail safely and require teacher intervention.

---

## Logging Requirements

The following events must be logged:

- Recovery request initiated (student mode)
- Reset code generated
- Reset code claimed successfully
- Reset code expired
- Excessive failed attempts

Logs must not include plaintext reset codes.

---

## Failure Handling

If reclaim fails at any stage:

- Student remains in `to_be_claimed` state until expiration or manual reset.
- No economic state may change.
- No credentials may be partially updated.

Worst allowed outcome:

> Student must request a new reset code.

---

## Alignment with Economic Integrity

This feature must comply with:

- Monetary Reversals & Refunds Specification
- Ledger immutability principles
- Migration discipline (no rewriting history)

Account recovery restores access. It does not alter reality.

---

## State Machine (Formal Definition)

### States

- `active`
- `to_be_claimed`
- `archived`

### Allowed Transitions

1. `active` → `to_be_claimed`
   - Trigger: Teacher-initiated reset OR approved student recovery request
   - Action:
     - Generate reset_code
     - Set expiration timestamp
     - Log reset event

2. `to_be_claimed` → `active`
   - Trigger: Successful reset_code validation and credential re-establishment
   - Action:
     - Clear reset_code
     - Clear expiration timestamp
     - Log successful reclaim

3. `to_be_claimed` → `active` (expiration path)
   - Trigger: reset_code expires without claim
   - Action:
     - Clear reset_code
     - Clear expiration timestamp
     - Log expiration
     - Student must request new reset

4. `active` → `archived`
   - Trigger: Teacher deletes student or class
   - Action:
     - Preserve all economic history
     - Disable login permanently

### Forbidden Transitions

- `archived` → `active` (unless explicitly restored by future spec)
- `to_be_claimed` → `archived` without logging
- Any transition that creates a new student record automatically

---

## Acceptance & Safety Test Cases

The following conditions must be validated before feature completion.

### Identity Integrity Tests

- Recovering an account must not create a new student row.
- Recovering an account must not duplicate student IDs.
- Resetting must not modify student economic balances.
- Resetting must not alter items, insurance, or transaction history.

### Reset Code Behavior

- Reset code must be unique within join_code scope.
- Reset code must be invalid after first successful use.
- Reset code must be invalid after expiration.
- Entering an invalid code must not reveal student identity.
- Multiple failed attempts must trigger rate limiting.

### Economic Invariance Tests

- Balance before reset == balance after reset.
- Transaction count before reset == transaction count after reset.
- No new economic transactions are created during recovery.

### Edge Case Tests

- Multiple students with same name + DOB must fail safely.
- Attempting reclaim when status != `to_be_claimed` must fail.
- Expired reset code must not partially update credentials.
- Interrupting reclaim mid-flow must not corrupt state.

### Migration Compatibility Tests

- Existing legacy student records must support reset without schema modification.
- No historical migration files are edited.
- No data backfills rewrite transaction history.

---

## Summary Principle

Credentials are disposable.
Identity is reclaimable.
Economic history is immutable.


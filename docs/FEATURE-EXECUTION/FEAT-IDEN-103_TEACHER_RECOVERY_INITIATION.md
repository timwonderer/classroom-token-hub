# FEAT-IDEN-103: Teacher Recovery Initiation
**[Initiation scope reconciled with DOM-IDEN-003 §IX]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-103 | 1.1 | 2026-09-15 | 1.0 | Normative | ACTIVE |

---

## I. Purpose

This FEAT initiates a recovery request for a teacher who has lost access to their account (e.g., lost TOTP authenticator, forgotten passkey). Per DOM-IDEN-003 §IX:
> "One pair is required per active class."

The teacher submits one selected student per `class_id` under the teacher
`user_id`. Recovery creates one user-owned request with a five-day lifetime;
class names and period labels do not define the quorum. Here the domain's term
"active classes" means the existing owned class set; it does not introduce an
active/inactive lifecycle flag (INV-CORE-000 §III.6).

This FEAT creates a `recovery_request` record with status `pending`, allowing students to assist in teacher identity verification via FEAT-IDEN-104.

**Governing Authority:**
- DOM-IDEN-003 §IX (Teacher Recovery - Student-Verified Mechanism)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `pairs`: One (`join_code`, `student_username`) pair for every active class owned by the teacher. This is an unauthenticated identity challenge; the teacher User is resolved from the first join code, not trusted from client input.
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* Resolve the first `join_code` to `class_id` and its owning teacher `user_id`.
* Resolve the definitive set of that teacher's active classes from the backend.
* Resolve exactly one selected claimed student Seat within each submitted class.
* Require exact class-set coverage: no missing, extra, or duplicate class IDs.
* Verify that `User.user_role = 'teacher'` (requestor is a teacher).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Resolve the Teacher and Required Class Set
1. Resolve the first submitted join code to its ClassEconomy and teacher User.
2. Verify `user_role = 'teacher'`.
3. Retrieve all active classes owned by this User; identifiers, not labels, define scope.
4. Reject invalid identity/class submissions with a generic failure message.

#### Step 2: Verify Exact Class Coverage
1. Resolve each submitted join code within the teacher's definitive class set.
2. Require the submitted `class_id` set to equal the backend set exactly.
3. Reject missing, extra, or duplicate class submissions. Do not accept partial coverage.

#### Step 3: Resolve One Selected Student per Class
1. Within each resolved class, match the submitted username to a claimed student Seat.
2. Require exactly one selected student Seat for every required class.
3. An empty class or invalid selected student prevents initiation; it does not reduce quorum.
4. Validate all pairs before accepting any. Do not reveal which pair failed.

#### Step 4: Check Existing Recovery Requests
1. Query active, unexpired recovery requests by teacher `user_id`, not by class.
2. If one exists, present that request's status rather than creating a duplicate.
3. Multiple active requests for one User indicate an integrity error; do not choose a class-specific request.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Calculate Recovery Window

Perform time calculation outside the transaction:
1. `expires_at = NOW() + 5 DAYS` (per DOM-IDEN-003: 5-day TTL for teacher recovery).
2. `status = 'pending'` (recovery request created but not yet in progress).

#### Step 2: Create RecoveryRequest Record

Insert into `recovery_requests` table:
1. `user_id`: The teacher user.
2. `status`: "pending" (awaiting student code generation).
3. `expires_at`: Calculated 5-day expiration (NOW() + 5 DAYS).
4. `created_at`: ISO 8601 UTC timestamp (set by database default).

In the same transaction, provision one `StudentRecoveryCode` row per selected
student Seat, containing the request ID, `seat_id`, `class_id`, and NULL code hash.
The parent request is User-owned and has no single `class_id`. The selected
seat/class rows define the participants; the rest of each roster is not enrolled.

#### Step 3: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-103` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-103"
   - `user_id`: The teacher `user_id`
   - `recovery_request_id`: The created `recovery_requests.id`
   - `idempotency_key`: The provided key
   - `outcome`: `"RECOVERY_INITIATED"` (only possible outcome for new request)
   - `expires_at`: The 5-day expiration timestamp
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log any credentials or authentication details.

---

## IV. Invariants & Constraints

### 1. Student-Verified Recovery (MANDATORY)
Per DOM-IDEN-003 §IX:
> "All classes must be represented. One student per active class period must participate. Partial coverage is rejected."

This FEAT creates one request for the teacher and selects one student Seat per class. Every selected participant provides a code through FEAT-IDEN-104; every student on each roster is not required.

### 2. 5-Day TTL (MANDATORY)
Recovery requests expire after 5 days. After expiration, the recovery request is discarded and must be re-initiated.

### 3. Single Active Recovery Request (MANDATORY)
A teacher may have only ONE active (`pending` or `in_progress`) recovery request at a time. Initiating recovery while one is already in progress returns idempotent success (no duplicate).

### 4. Credential Restoration Only (MANDATORY)
Recovery restores access to the existing teacher User. Lost TOTP/passkey access does not authorize changes to participation, ownership, or economic state.

### 5. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 6. User-Owned Request, Class-Scoped Participants (MANDATORY)
One request covers all active classes under the teacher User. Each selected student is resolved within their own class. Do not create separate requests per class or resolve students through a global roster search.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `user_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `recovery_requests` row exists for `user_id` with `status IN ('pending', 'in_progress')`.
  - If true, return success with outcome `RECOVERY_IN_PROGRESS` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate recovery requests.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session or user context).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **NOT create a recovery request**.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Unable to verify identity. Please check your entries and try again." |
| No admin seat | `NO_ADMIN_SEAT` | 409 | "Unable to verify identity. Please check your entries and try again." |
| Recovery already in progress | `RECOVERY_IN_PROGRESS` | 200 | "Recovery is already in progress for this account." |
| Invalid class | `INVALID_CLASS_CONTEXT` | 400 | "Unable to verify identity. Please check your entries and try again." |
| No students | `NO_ELIGIBLE_STUDENTS` | 409 | "Unable to verify identity. Please check your entries and try again." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred during recovery initiation. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-103") |
| `user_id` | Integer | ✓ | The teacher user requesting recovery |
| `recovery_request_id` | Integer | ✓ | The created recovery request |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `RECOVERY_INITIATED` or `RECOVERY_IN_PROGRESS` |
| `expires_at` | ISO 8601 | ✓ | The 5-day expiration timestamp |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of initiation |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `RECOVERY_INITIATED`: Successful recovery request creation.
- `RECOVERY_IN_PROGRESS`: Idempotent return; recovery is already underway.

---

## VIII. Display Requirements

After successful recovery initiation, the route handler SHALL display to the teacher:

1. **Recovery Code Entry Form**: Instructions for students to provide recovery codes.
   - Display unique recovery request ID (for students to reference).
   - Display expiration timestamp.
   - Link/QR code to student-facing form for code generation (FEAT-IDEN-104).

2. **Countdown Timer**: Display remaining time until recovery request expires.
   - Refresh every 60 seconds or real-time if using WebSocket.
   - Show warning if < 1 hour remaining.

3. **Student Status**: Display number of students who have provided codes (updated as students participate).
   - Show "Awaiting codes from X students" or similar.
   - Refresh on completion.

4. **Next Steps**: Instructions for what happens after all selected students provide codes.
   - "Once one selected student from every class provides a code, your account will be restored."

---

## IX. Integration with FEAT-IDEN-104 & FEAT-IDEN-105

**Teacher recovery involves three coordinated FEATs:**

```
FEAT-IDEN-103: Teacher Initiates Recovery
├─ Teacher creates recovery_request
└─ Status: pending (awaiting student codes)

FEAT-IDEN-104: Students Generate Recovery Codes
├─ Students verify teacher identity through class roster
└─ Create student_recovery_code records (one per selected student Seat/class)

FEAT-IDEN-105: Teacher Validates Recovery & Restores Access
├─ Check that all selected students provided codes
├─ Verify codes are correct
└─ Update recovery_request.status to verified
└─ Reset TOTP secret (allow FEAT-IDEN-101 or FEAT-IDEN-106)
```

All three FEATs operate on the same `recovery_requests` record.

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] User role validation ensures only teachers can initiate recovery
- [ ] Exact class-set coverage with one selected student Seat per class
- [ ] Class context validation (verify class exists)
- [ ] Teacher affiliation verification (verify teacher has admin seat in class)
- [ ] Missing or ineligible selected students cause generic rejection
- [ ] Existing recovery request check (idempotent on active request)
- [ ] Expiration calculation is correct (NOW() + 5 DAYS)
- [ ] RecoveryRequest status is set to "pending"
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Credentials are NOT logged in audit
- [ ] Idempotency check prevents duplicate recovery requests
- [ ] Tests cover successful initiation and idempotent retry
- [ ] Tests cover missing, extra, duplicate, empty-class, and invalid-student submissions

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §IX.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-104 and FEAT-IDEN-105.

**Version 1.1 (2026-09-15): reconcile one user-owned request and one selected student per class with DOM-IDEN-003 §IX.**

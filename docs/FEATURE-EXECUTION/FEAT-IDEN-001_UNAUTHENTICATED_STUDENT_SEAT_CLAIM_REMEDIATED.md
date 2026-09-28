# FEAT-IDEN-001: Unauthenticated Student Seat Claim
**[v2 - Compliant with INV-ARC-019 and DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-001 | 3.0 | 2026-09-28 | 2.3 | Normative | ACTIVE |

---

## I. Purpose

This FEAT is the verification phase of the unauthenticated student claim. It resolves a teacher-provided join code and the student's roster name to exactly one unclaimed `Seat`, and hands that Seat to **FEAT-IDEN-002** (Student Credential Setup). FEAT-IDEN-002 then creates the student's `User`, activates its credentials and binds the Seat, all in one transaction.

This FEAT writes nothing. It provisions no `User`, binds no `Seat` and clears no claim artifact. Per DOM-IDEN-005 §VIII, binding associates an **authenticated** `User` with an unclaimed `Seat`. Per INV-ARC-019 §XII, "claim/setup later proves entitlement to the seat and creates/binds the authentication principal". A `User` is therefore never created before it has credentials.

> [!IMPORTANT]
>
> **Scope Clarification:** This FEAT handles **unauthenticated claim only**. It is for students claiming a classroom seat without prior authentication. For authenticated users joining a new classroom (reusing existing credentials), see **FEAT-IDEN-005** (Authenticated Class Binding).

**Governing Authority:**
- INV-ARC-019 §VII, §X and §XII (Operational Actor, claim artifacts, Roster Provisioning and Seat Claim)
- DOM-IDEN-005 §V, §VII and §VIII (Membership by Existence, Student Identity Lifecycle, Identity Binding)
- DOM-IDEN-002 §VIII (Roster Provisioning and Claim)
- SPEC-SEC-001 §V.2 (lookup normalization and HMAC encoding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `join_code`: Valid join code for the target class.
* `credentials`:
    * `first_name`: Student's first name (full or partial, as provided by teacher roster)
    * `last_name`: Student's last name (full or partial, as provided by teacher roster)
    * `dedupe_code`: (Optional) Short code provided by teacher to disambiguate duplicate names
* `idempotency_key`: Accepted or generated per FEAT-CORE-000 §III.3.

**Prohibited Inputs:** None of the following may be accepted:
- ❌ DOB or DOB derivatives (per DOM-IDEN-002 §XI)
- ❌ `existing_user_id` (unauthenticated claim cannot reference existing users)
- ❌ `identity_hash` (no cross-user identity inference)

### 2. Resolved Context (MANDATORY)

The FEAT MUST resolve the following before mutation:
* `class_id`: Resolved via `join_code` at the `ClassEconomy` boundary (the only use of `join_code`; every later step uses `class_id`)
* `roster_seat_id`: The unclaimed seat in that class matching the claim hashes
* `claim_generation`: The resolved Seat's current server-stored generation (DOM-IDEN-005 §VIII; DOM-IDEN-007)

---

## III. Orchestration Logic

### A. Verification (Read-Only)

This FEAT has only a read-only phase. It SHALL perform no database write.

#### Step 1: Resolve Class
1. Look up the `ClassEconomy` whose `join_code` matches the provided code.
2. Take `class_id` from it.
3. **Failure Behavior**: If no class is found, abort with `INVALID_JOIN_CODE`.

#### Step 2: Resolve Roster Seat
1. Select the unclaimed seats in the class: `class_id` matches, and `user_id IS NULL` (DOM-IDEN-002 §VIII, *Student Seat State*).
   - **Failure Behavior**: If there are none, abort with `NO_UNCLAIMED_SEATS`.
2. Compute the claim hashes:
   - `claim_first_name_hash = hash_claim_name(first_name, class_id=class_id, field="first")`
   - `claim_last_name_hash = hash_claim_name(last_name, class_id=class_id, field="last")`
   - Both use the normalization and purpose-separated HMAC encoding in SPEC-SEC-001 §V.2.
3. Select the seats whose two claim hashes both match.
4. **Deduplication**:
   - If exactly one seat matches, use it.
   - If several match and no `dedupe_code` was given, abort with `AMBIGUOUS_IDENTITY`.
   - If several match, keep those whose `dedupe_code` equals the given code. Exactly one must remain; otherwise abort with `INVALID_DEDUPE_CODE`.
   - If none match, abort with `INVALID_CREDENTIALS`.
5. Take `roster_seat_id` and its `claim_generation` from the resolved seat.
6. **Failure Behavior**: Abort at the first failing step. A failure reveals nothing about which seats or users exist.

#### Step 3: Identity Inference Prohibition
Per DOM-IDEN-005 §VII:
> "unauthenticated claim SHALL NOT search for or infer existing User identities outside the current claim transaction."

This FEAT **SHALL NOT**:
- ❌ Search for, read or compare any `User` record
- ❌ Compute or use an identity hash (DOB-based or otherwise)
- ❌ Reuse or link to any pre-existing `User`

**Rationale**: An unauthenticated context cannot prove that a returning student is the same person. Identity merging is therefore prohibited, and FEAT-IDEN-002 always creates a new `User` for an unauthenticated claim.

#### Step 4: Hand-off to FEAT-IDEN-002
1. Record the resolved Seat reference and its `claim_generation` in the signed onboarding session (see *Claim verification lifetime* below).
2. Record no `User` reference. None exists yet for this claim.

### B. What this FEAT does not do

The following belong to **FEAT-IDEN-002**, in one atomic transaction (DOM-IDEN-005 §VIII; INV-ARC-019 §X and §XII):
- creating the student `User` together with its credentials;
- binding the Seat (`user_id`, `claimed_at`) under a row lock, after rechecking that it is still unclaimed and that its `claim_generation` is the one recorded here;
- clearing `claim_first_name_hash`, `claim_last_name_hash`, `roster_fingerprint` and `dedupe_code`;
- initializing `last_active_class_id` and `last_active_seat_id` (DOM-IDEN-002 §VIII, *Claim Flow* step 9).

**Membership is not a record.** Per DOM-IDEN-005 §V and INV-ARC-013, participation in a class *is* the existence of the bound `Seat`. Neither this FEAT nor FEAT-IDEN-002 creates a separate membership row. The v1 `ClassMembership` table does not exist.

---

## IV. Invariants & Constraints

### 1. Read-Only (MANDATORY)
This FEAT SHALL NOT write to the database. A verified claim that is never completed leaves no `User`, no binding and no changed claim artifact.

### 2. No User Before Credentials (MANDATORY)
No `User` is provisioned by this FEAT. Per DOM-IDEN-005 §V and §VIII, a `User` exists only as an authenticated participant bound to a Seat.

### 3. Class Scope (MANDATORY)
Every seat query is scoped by the `class_id` resolved in Step 1. The claim hashes include `class_id`, so the same name matches no seat in any other class (SPEC-SEC-001 §V.2).

### 4. One Seat per User per Class
Per DOM-IDEN-001 §VII ("One `User` may own at most one `Seat` within a `Class`") and DOM-IDEN-005 §VIII ("One `User` SHALL own at most one `Seat` within the same `Class`"). This is enforced at binding by FEAT-IDEN-002 and by `UNIQUE(user_id, class_id)` on `seats`.

### 5. No Identity Inference (MANDATORY)
Per DOM-IDEN-005 §VII, as in Step 3. No DOB or DOB-derived data is accepted (DOM-IDEN-002 §XI).

---

## V. Idempotency

Per FEAT-CORE-000 §III.3, an `idempotency_key` is accepted or generated. Because this FEAT writes nothing, a replay has no effect to duplicate: the same inputs resolve to the same Seat, or to the same failure.

Replay safety for the claim itself belongs to FEAT-IDEN-002. The binding is conditional on `Seat.user_id IS NULL` and on the recorded `claim_generation`, so a replayed or stale verification cannot bind twice. An Unclaim invalidates every earlier verification by incrementing the generation.

---

## VI. Audit Requirements

Per FEAT-CORE-000 §III.4, the verification attempt **MUST** emit an audit record via DOM-OPS (`ACT-IDEN-001`):

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Always "FEAT-IDEN-001" |
| `class_id` | UUID | When resolved | The classroom context |
| `seat_id` | Integer | On success | The verified, still unclaimed seat |
| `correlation_id` | String | ✓ | Links this verification to the FEAT-IDEN-002 completion |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | `SEAT_VERIFIED`, or the failure code from §VII |
| `timestamp` | ISO 8601 | ✓ | UTC time of the attempt |
| `user_id` | UUID | ✗ | None exists; the actor is unauthenticated |
| `join_code` | String | ✗ | Not needed once `class_id` is resolved; keep it out of the record |
| `first_name`, `last_name`, `dedupe_code` | String | ✗ | DO NOT log (PII and claim material) |

**Explicitly prohibited outcomes:**
- ❌ `EXISTING_USER_LINKED`, `USER_REUSED`: identity inference is prohibited (DOM-IDEN-005 §VII).
- ❌ `NEW_USER_CLAIMED`: this FEAT provisions no User. The claim completes in FEAT-IDEN-002.

---

## VII. Failure Scenarios

A failure performs no write. It emits the audit record in §VI and returns an error. Messages SHALL NOT reveal whether a given name or seat exists.

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| Invalid join code | `INVALID_JOIN_CODE` | 400 | "Invalid join code or all seats already claimed. Check with your teacher." |
| No unclaimed seats in class | `NO_UNCLAIMED_SEATS` | 400 | "Invalid join code or all seats already claimed. Check with your teacher." |
| Names match no unclaimed seat | `INVALID_CREDENTIALS` | 400 | "No matching account found. Please check your join code and credentials." |
| Several matches, no dedupe code given | `AMBIGUOUS_IDENTITY` | 400 | "Multiple students in this class share that name. Enter your deduplication code from your teacher." |
| Dedupe code matches no single seat | `INVALID_DEDUPE_CODE` | 400 | "Invalid deduplication code. Check with your teacher." |
| Database failure | `INTERNAL_ERROR` | 500 | "An error occurred during account claim. Please try again or contact support." |

A seat claimed concurrently between verification and setup is refused by FEAT-IDEN-002 (`INVALID_SEAT_STATE`), not here.

---

## VIII. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-002_STUDENT_CREDENTIAL_SETUP.md`
- `docs/DOMAIN/DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`
- `docs/SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md`

---

## IX. Implementation Checklist

Before code review, verify:

- [ ] The verification performs no database write
- [ ] No `User` is read, searched for, created or reused
- [ ] No DOB or DOB-derived field is accepted or used
- [ ] Every seat query is scoped by the resolved `class_id`
- [ ] Claim hashes use `hash_claim_name` with `class_id` (SPEC-SEC-001 §V.2)
- [ ] The Seat reference and `claim_generation` are stored in the signed onboarding session
- [ ] Failure messages do not reveal whether a name or seat exists
- [ ] The `ACT-IDEN-001` audit record is emitted without PII
- [ ] No membership record is created (membership is the bound Seat)

---

## X. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Stay consistent with INV-ARC-019, DOM-IDEN-005 §V, §VII and §VIII, and DOM-IDEN-002 §VIII.
4. Stay consistent with FEAT-CORE-000 and FEAT-IDEN-002.

**Version 3.0 (2026-09-28):**
- FEAT-IDEN-001 is the read-only verification phase of the claim. User provisioning, seat binding,
  claim-artifact clearing and context initialization moved to FEAT-IDEN-002, which already
  performed them. Version 2.x put an uncredentialed `User` and the binding here. That
  contradicted DOM-IDEN-005 §VIII (binding associates an *authenticated* User) and INV-ARC-019
  §XII.
- Removed the step that created a `ClassMembership` "or equivalent" record. Membership is the bound Seat
  (DOM-IDEN-005 §V, INV-ARC-013), and `ClassMembership` does not exist in v2.
- Removed the `IdempotencyRecord` entity, because a read-only phase has nothing to replay. Idempotency is
  stated per FEAT-CORE-000 §III.3, and the binding's replay guard (`claim_generation`) is in FEAT-IDEN-002.
- The audit record now describes a verification attempt: it records no `user_id` and no `join_code`. Types now
  follow the schema (`users.id` has been a UUID since v2.0.1).
- Corrected citations: DOM-IDEN-001 §VII says "may", not "SHALL". Context initialization is DOM-IDEN-002 §VIII,
  *Claim Flow* step 9. Added INV-ARC-013, INV-ARC-019, SPEC-SEC-001 and FEAT-IDEN-002 as dependencies.

Version 1.0 (2026-04-23) was withdrawn for constitutional non-compliance.

## Claim verification lifetime

Successful verification captures the Seat’s server-stored `claim_generation` in the signed onboarding session alongside its Seat reference. FEAT-IDEN-002 must recheck this generation before binding; Unclaim invalidates all earlier verification sessions by incrementing it.

# DOM-IDEN-003: Teacher Identity Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-003 | 2.9 | 2026-09-24 | 2.8 | Constitutional |

---

## I. Purpose

This document defines how the canonical identity objects defined by DOM-IDEN-001 are specialized for teacher participation within Classroom Token Hub. It governs teacher-specific credential structure, authentication, step-up authentication, and account recovery.

This document is subordinate to **DOM-IDEN-001** (Canonical Identity Model) and **DOM-IDEN-005** (Identity Binding and Lifecycle). Those documents define the universal identity objects and lifecycle laws. This document specializes those definitions for the teacher role.

> [!IMPORTANT]
>
> This document defines the canonical v2 identity model. Legacy tables (`admins`/`teachers`, `teacher_blocks`, `student_teachers`, `class_memberships`) are migration artifacts and SHALL NOT be treated as identity authority.

---

## II. Scope

This document governs:

- Teacher credential structure on `users`
- Teacher seat structure
- Teacher authentication flow (TOTP and passkey)
- Teacher session semantics
- Teacher account recovery (self-serve, student-assisted)
- Passkey credential metadata
- Teacher class provisioning identity through `class_id` and `seat_id`

This document does **not** govern:

- The canonical identity objects themselves (DOM-IDEN-001)
- Identity binding and lifecycle rules (DOM-IDEN-005)
- Canonical context resolution (DOM-IDEN-006)
- Economic activity (Ledger domain)
- Student identity (DOM-IDEN-002)
- Class policy configuration
- Store ownership

---

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-008`, `DOM-IDEN-001`, and `DOM-IDEN-005`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`
- `DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## V. Schema Authority Declaration

### Owned Tables

This document is the sole schema and mutation authority over the following tables:

**`recovery_requests`**

Key fields: `id`, `user_id` (FK to `users` where `user_role = 'teacher'`), `status` (`pending` | `verified` | `expired`), `expires_at`, `created_at`, `completed_at`, `partial_codes` (JSON), `resume_pin_hash`, `resume_new_username`.

**`student_recovery_codes`**

Key fields: `id`, `recovery_request_id` (FK, CASCADE), `seat_id` (FK to `seats` where `role = 'student'`), `code_hash` (NULL until student generates their code), `verified_at`, `notified_at`, `dismissed`.

**`passkey_credentials`**

Teacher passkey credential metadata. Owned by `users.id` (per INV-ARC-019 §XI). This unified table is the canonical passkey store for teacher and sysadmin principals.

**`teacher_signup_attempts`**

The encrypted, expiring staging record for initial teacher provisioning (§VII Account Provisioning; FEAT-IDEN-101 executes it). Key fields: `nonce_hash` (primary key; purpose-separated SHA-256 verifier of the browser's random signup nonce), `payload_encrypted` (pending class/display metadata, username and pending credential; INV-ARC-018 temporary signup inventory), `expires_at`.

### Schema Contract

Teacher-specific fields on `users`: `totp_secret_encrypted`.

### Constraints

- `recovery_requests`: At most one `status = 'pending'` row per user at any time. `expires_at` is a hard TTL (5 days). Rows past `expires_at` are inert regardless of status. `partial_codes` and `resume_new_username` must be cleared when `status` transitions to `verified` or `expired`.
- `student_recovery_codes`: One row per selected student seat per recovery request. `code_hash` is `HMAC(6-digit-code, b'')`. Plaintext code is never stored. `code_hash` is set to NULL and `verified_at` is cleared on any failed submission (all-or-nothing invalidation per §IX invariant 6). Rows become inert when the parent `recovery_request.expires_at` passes.
- `passkey_credentials`: Passwordless external IDs use `user_<User.id>`. Legacy external IDs such as `admin_<id>` are invalid v2 principals. Passkey metadata does not authorize class access, seat access, recovery, or economic actions.
- `teacher_signup_attempts`: Temporary state only. It references no `users`, `classes` or `seats` row and grants no identity, lookup or classroom authority. The plaintext nonce is never stored. A row past `expires_at` is inert and is removed by cleanup; a restart deletes the previous attempt; successful provisioning deletes the attempt in the same transaction that creates the `User`, `Class`, `Seat` and `IdentityProfile`, so a replay cannot provision a second account.

### Derived / Cross-Domain Rules

The `user_recovery_tokens` table is a shared recovery capability table owned by `users` (per INV-ARC-019 §XI). This document governs the teacher-specific recovery workflow that produces and consumes those tokens.

---

## VI. Teacher Identity Layers

Teacher identity follows the universal three-layer model defined by DOM-IDEN-001:

- **`User`**: authentication principal — owns credentials, recovery, and global security state
- **`Seat`**: class-local actor — the canonical operator record inside a class
- **`Class`**: economic universe boundary

Economic and operational authority is never inferred from `user_id` alone. Scoped actions require a resolved teacher `seat_id` bound to the active `class_id`.

### Teacher `User` Fields

A teacher `User` is a `users` row with `user_role = 'teacher'`. Common `users` fields are defined by DOM-IDEN-001. This section defines only the teacher-specific delta.

Teacher-specific fields:

- `totp_secret_encrypted` — base64-encoded encrypted TOTP seed

> [!IMPORTANT]
>
> Teacher users may optionally enable passkey for authentication. Passkey-related metadata is stored on the unified `passkey_credentials` table with the following fields: `id`, `user_id` (FK to `users.id`), `credential_id`, `authenticator_name`, `created_at`, `last_used`. Actual field requirements should consult Bitwarden Passwordless SDK requirements.

Student-specific fields (`pin_hash`, `passphrase_hash`, `money_action_cooldown_until`) SHALL be `NULL` for teacher rows.

Teacher-specific rules:

- Teacher maximum session length is 60 minutes.
- A missing or invalid `last_active_class_id` must not be treated as authority failure by itself; the login boundary may surface explicit class selection when valid seats exist, and only fail closed after verifying that no valid class/seat options remain.

### Teacher `Seat` Fields

A teacher seat is a `seats` row with `role = 'teacher'`. Base seat fields and participation rules are defined by DOM-IDEN-001. This section defines only the teacher-specific delta.

Teacher-specific rules:

- A teacher seat is provisioned when the teacher sets up a class.
- Teacher seats do not use `roster_fingerprint` or `dedupe_code`; those fields are `NULL` for teacher seats.
- `teacher_notes_encrypted` is accessible only to the seat's teacher and system admins.
- A class has exactly one authoritative teacher seat owner for teacher-scoped mutation surfaces.
- Teacher-scoped writes must be attributable to a teacher `seat_id`.

### Teacher `IdentityProfile`

Defined by DOM-IDEN-001. No teacher-specific delta. Teacher display names are stored here, not on a separate teacher table.

---

## VII. Teacher Authentication

### Login Flow

```text
1. Teacher submits username.
2. Backend computes username_lookup_hash and finds the users row.
3. Backend verifies user_role == 'teacher'.
4. If passkey is enrolled and the client supports it → passkey challenge (preferred).
5. Otherwise → TOTP challenge using totp_secret_encrypted.
6. On success: write current_session_started_at, current_session_expires_at,
   current_session_nonce.
```

TOTP is required for all teacher accounts. Passkey is an optional second authentication method — when enrolled, it replaces the TOTP step for that device.

Active seat and class context restoration follows DOM-IDEN-006. Sysadmin authentication may share the same login surface but is not governed by this document.

### Account Provisioning

Teacher account provisioning follows DOM-IDEN-005 §VI. The constitutional provisioning sequence is:

1. Provision a canonical `User` (with `user_role = 'teacher'`).
2. Provision an initial `Class`.
3. Provision one administrative `Seat`.
4. Bind the administrative `Seat` to the newly provisioned `User`.
5. Initialize the active class and seat pointers (per DOM-IDEN-006 §XIII).
6. Permit runtime participation through DOM-IDEN-006.

Teacher-specific credential setup (TOTP enrollment, optional passkey enrollment) occurs within this sequence. TOTP setup is required before `has_completed_setup = true`.

Per DOM-IDEN-005 §VI, the initial Class and administrative Seat MUST be provisioned atomically with the User. Failure to provision the initial Class SHALL invalidate the entire teacher provisioning transaction.

Initial provisioning stages submitted metadata and the pending credential in an
encrypted, expiring server record per INV-ARC-018 and FEAT-IDEN-101. The browser
holds only a random nonce. Staging grants no identity or classroom authority;
successful atomic provisioning consumes it.

### Session Establishment

- `current_session_started_at` is written at sign-in.
- `current_session_expires_at` is written once at sign-in (fixed 60-minute window, does not slide forward on activity).
- `current_session_nonce` is regenerated at sign-in and binds requests to one specific login session.
- All three session fields are replaced on the next successful sign-in.

Request-time session validation is governed by DOM-IDEN-006.

### Financial Action Gate

Teachers administering financial actions (adjustments, payroll, approvals) are authenticated by the existing session. There is no additional passphrase gate for teachers — the TOTP at login is the authentication signal.

### Step-Up Authentication

Certain privileged identity mutations SHALL require step-up authentication beyond the existing session. Step-up authentication is a fresh re-authentication challenge issued at the time of the privileged action, not a replay or reuse of the login-time credential.

The following actions SHALL require step-up authentication:

- Final classroom deletion (destruction of the teacher's last class, which triggers identity destruction per DOM-IDEN-005 §VI)
- Disabling or replacing the enrolled TOTP secret
- Registering or removing passkey credentials
- Initiating student account recovery (issuing a reset code for another actor)

Step-up authentication is a constitutional requirement. The specific mechanism, validity window, and binding rules are defined by the governing FEAT contract.

---

## VIII. Authority Rules

1. **Authentication authority:** `user_id` proves who is logged in.
2. **Scoped authority:** `seat_id` proves class-local actor authority. `class_id` proves universe boundary.
3. **Request contract:** Global teacher routes may use authenticated `user_id` only. Any class-scoped teacher operation must resolve and validate `seat_id + class_id` ownership.
4. **Membership by existence:** If a teacher seat exists for (`user_id`, `class_id`), membership exists. No implied membership from other tables or duplicated denormalized markers.

Domains SHALL NOT accept teacher authority from `join_code` or `user_id` without seat-ownership validation.

---

## IX. Teacher Account Recovery

Recovery replaces credentials on the existing teacher User. It never changes Seat
bindings, class ownership or economic state. No DOB, contact information or
administrator intervention is required.

### Authority and class boundaries

The attempt is User-owned under INV-ARC-019's credential-recovery authority. Its
manifest contains the required owned class IDs; its coordinator combines deposited
proofs, not student/roster data. Recipient selection, student issuance and code
submission are independent commands with one explicit class_id each; the browser
makes separate class-scoped requests for them.

The initial knowledge proof is the one exception. It is an ingress check that
authorizes creating the attempt, not part of the attempt, and it runs as a single
precheck command: it resolves each join code to class_id and each username within
that class, and it holds resolved student identities only in memory for that command.
Submitted usernames and resolved students are never persisted, logged or carried
into the attempt; the attempt stores only the per-class proof result.

### Initial proof and fixed selection

1. Teacher submits join-code/student-username pairs for every owned class in one
   request. All join codes must resolve to classes owned by one teacher User, and
   the submitted classes must equal that User's owned class set.
   Resolve each join code to class_id before checking the usernames against that
   class's claimed student Seats. The number of distinct claimed students each
   class must prove depends on how many classes the teacher owns:

   | Owned classes | Usernames per class |
   |---|---|
   | 1 | 6 |
   | 2 | 3 |
   | 3 | 2 |
   | 4 or more | 1 |

   **Security posture:** every owned class must have at least three claimed student
   Seats. Step 2 randomly picks two recipients per class, and with fewer than three
   eligible Seats that pick is predictable to anyone who knows the class, so a class
   below three fails the proof closed and student-assisted recovery is unavailable
   for the whole account. Teacher-facing recovery, setup and roster surfaces SHALL
   state this requirement and its reason. A class with at least three but fewer
   claimed students than its requirement must prove every claimed student. Each resolved student User may
   back only one pair of a submission, even when that student holds Seats in several
   of the teacher's classes; uniqueness is checked on resolved user_id, not on the
   typed text. Any failure creates nothing. These inputs prove account structure;
   they do not nominate recovery recipients. Do not reveal individual proof validity.
2. Only after the complete nonempty class proof set is present may selection begin.
   Within each class, cryptographically randomly sample exactly two distinct eligible
   claimed student Seats. Fewer than three eligible Seats fails closed.
   Recipients SHALL be selected independently within each class. Selection MUST NOT
   exclude, prefer or otherwise alter the eligibility of a Seat based on the existence
   or selection of Seats belonging to the same users.id in another class. The two
   stages differ deliberately: claimant-chosen evidence (step 1) requires distinct
   principals to prevent concentration, while system-randomized recipients stay
   ignorant of cross-class identity (INV-ARC-008). One student may therefore be
   selected in several classes; that follows from membership and chance, not from
   claimant control, and is accepted.
3. Notify both selected recipients immediately through their authenticated class
   sessions. There is no primary/backup role. Hide identities and per-recipient
   state from the teacher. Class names are display labels only, never scope keys.
4. Freeze the selected seat IDs for the five-day attempt. Duplicate requests,
   code expiration, failed submission and regeneration cannot reroll or add seats.
   Only one selected attempt per teacher may exist within its lifetime. An attempt
   exists only after a complete proof, so unproven input cannot reserve that slot. Losing a selected Seat removes that recipient;
   the remaining recipient may still help. Never replace a removed recipient.

### Lifetimes and student issuance

| Object | Lifetime |
|---|---|
| Recovery attempt | Five days from creation |
| Random recipient selection | Fixed for the attempt |
| Student confirmation code | Thirty minutes from issuance, capped by attempt expiry |
| Accepted class confirmation | Remainder of attempt, unless the full-set submission fails |

A selected student authenticates in that class, re-enters their passphrase, and
obtains a fresh six-digit numeric code. Issuing it replaces only that student's
prior code. Regeneration is student-controlled, through the same selected Seat;
teachers cannot target students or request replacement recipients. Store only a
request/class-bound verifier and issuance/expiry metadata. Explain that the code
is given in person only if the teacher is currently with the class.

### Private class confirmations and aggregate-only feedback

Code entry takes place within one class_id. Return the exact same receipt for a
correct, incorrect, malformed, expired or already-used code. Teacher status may
show that an entry was received, never whether it was valid, which recipient
responded, or whether a class is privately satisfied.

Accept either selected recipient's live code as the class proof. Atomically record
satisfied_at for that class and invalidate both outstanding codes in that class.
That private confirmation can persist from Monday to Tuesday while another class
has yet to meet; a thirty-minute code expiry does not expire the accepted proof.

After all codes have been collected, the teacher explicitly submits the full set.
Return only a generic success or failure. Every required current class must have a
valid private confirmation. On failure, increment the attempt's submission round:
all previous-round codes and private confirmations become unusable, requiring
fresh codes for every class. The selected recipients do not change. A round marker
invalidates proofs without a cross-class mutation sweep. No individual feedback or
partial validity results are returned, including after a failed full submission.

### Resume and credential completion

The attempt has a random server-verified access nonce; knowing its ID or reentering
roster pairs does not grant access to another browser's selected attempt. A teacher
can obtain a six-digit resume PIN, stored only as a separate-purpose verifier.
Resuming rotates the attempt access nonce, clears prior setup authorization, and
retains fixed selections and private class confirmations. Ambiguous PIN matches
fail closed. No plaintext student codes are saved for later replay.

Successful full-set verification grants one server-bound setup nonce. Store its
verifier, encrypted pending TOTP seed and encrypted pending username on the attempt;
the signed cookie holds only nonces and references. Verify the new TOTP against
server-held state, pending status, original expiry and complete current proof set.
Atomically replace canonical username/TOTP credentials, revoke passkeys and login
sessions, mark verified/completed_at, and erase temporary authorization/resume data.
Recovery completion never changes participation or class state. Require fresh login.


## IX.A. Account Retention and Automatic Destruction

`User.last_signed_in_at` records successful teacher authentication (TOTP or passkey),
not requests, class activity, recovery initiation, or session refresh. If present,
eligibility begins at that instant plus 180 days; if absent, eligibility begins
at `User.created_at` plus 30 days. An hourly lifecycle sweep rechecks eligibility
under a User row lock and executes FEAT-IDEN-007, with the same lock used when
recording a successful sign-in. Candidate discovery alone is not authorization.

The scheduled lifecycle authority names the teacher principal directly after this
policy check. It is not a sysadmin session, impersonation, or inferred class
activity. Account destruction composes the same domain command as manual deletion
and removes every owned class, seat, support artifact, and orphaned student User.
A failed account transaction rolls back; a later sweep can retry.


## X. Credential Summary

| Credential | Teacher |
|------------|---------|
| Username | `username_hash` / `username_lookup_hash` |
| Primary auth factor | TOTP (`totp_secret_encrypted`) |
| Secondary / optional factor | Passkey metadata owned by `users.id` |
| Passphrase | N/A |
| DOB | **Not stored** |
| Recovery | Student-assisted distributed trust |
| Session | Nonce + 60-minute fixed-window expiry |

For student credential structure, see DOM-IDEN-002.

---

## XI. Forbidden Patterns

- Separate `teachers` / `admins` table as identity authority (legacy migration artifact)
- DOB or DOB-derived hashes for any purpose
- Plaintext username column (only `username_hash` and `username_lookup_hash`)
- `teacher_public_id` as a separate field (display identity lives in `identity_profiles`)
- Passkeys owned by role-specific principal IDs (legacy `admin_<id>` format)
- Treating `join_code` as backend authority boundary
- Implicitly deriving active scope from unrelated session residue
- Writing class-scoped state when no teacher seat is resolved
- Using legacy `teacher_id` alone to scope student data instead of resolved `class_id` and `seat_id`

---

## XII. Amendment

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-001 and DOM-IDEN-005.
4. Maintain consistency with INV-CORE-000.

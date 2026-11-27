# FEAT-IDEN-102: Teacher Passkey Enrollment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-102 | 1.4 | 2026-11-27 | 1.3 | Normative |

## I. Purpose

Enroll a required passkey, preserving unrelated credentials. A principal always holds at least one activated passkey: a passkey is changed by enrolling a new one and then revoking the old one (FEAT-IDEN-107), never by an in-place replacement.

## II. Scope

Teacher or sysadmin principal initial/additional enrollment. Principal credential-maintenance scope; no classroom/Seat prerequisite.

## III. Authority Level

Execution-level contract subordinate to INV-CORE-000/001, INV-ARC-001/003/006/007/019,
and DOM-IDEN-003/005. No implementation behavior overrides that authority.

## IV. Dependencies

- [DOM-IDEN-003 — Teacher Identity Architecture](../DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md), §VII.A and §IX.
- [DOM-IDEN-005 — Identity Binding and Lifecycle](../DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md).
- [FEAT-CORE-000](FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md), declared execution scopes and workflows.
- [SPEC-IDEN-002 — Credential Lifecycle Protocol](../SPEC/SPEC-IDEN-002_CREDENTIAL_LIFECYCLE_PROTOCOL.md), incorporated by DOM-IDEN-003.
- [SPEC-SEC-001](../SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md).
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md), §2.5 outcome envelope.

## V. Authorization and registration

Resolve the authenticated teacher or sysadmin principal at the request boundary. TOTP must already
be activated. Every principal proves fresh TOTP bound to the requested operation for
initial or additional enrollment and revocation. A login session alone is
insufficient.

In a short transaction, validate current generation/session/expiry and reserve one
operation with database-enforced uniqueness. Persist pending registration before
issuing a provider token, so reconciliation protects unknown-ID registrations. Perform
provider calls outside database transactions/row locks. Verify registration server-side:
successful registration type, expected principal, exact unique credential ID, intended
challenge/purpose, expiry, origin and RP ID. Provider ceremony verification does not
substitute for local ownership/activation. Do not import metadata from inventory.

Preserve the existing ceremony-integrity obligations through the provider adapter;
prove challenge/origin/RP binding in that integration, not by trusting browser fields.
No raw assertion/token, public-key archive, hardware identifier or device-separation
policy is introduced. Credential IDs are unique; multiple credentials and credentials
from the same physical/synchronized authenticator are permitted. Escape display labels;
labels are never authority or audit fields.

## VI. Completion workflows

For enrollment, durably record the verified credential as pending, invoke the canonical
principal reconciliation commands with that pending credential protected, then revalidate
current authority in a local transaction. Activate once, consume the operation, advance
generation, invalidate sessions/challenges/management grants and emit ACT-IDEN-102.

Each local step is one FEAT transaction through Identity commands. A later autonomous
continuation uses FEAT-IDEN-108, never a nested FEAT call. Generation/stage checks refuse
stale responses and SATAR/destruction-superseded activation. Authorization expiry before
retirement intent prevents completion; after intent only the fixed operation may finish.

## VII. Failure, idempotency and presentation

Cancellation/expiry before activation preserves every existing credential and makes
abandoned remote registration cleanup-only. Enrollment has no retirement step; the
recoverable remote-first retirement workflow belongs to revocation (FEAT-IDEN-107).

Use a random operation identity and unique local transition/receipt, not an audit
identity archive or read-then-act existence check. A duplicate completion never activates
a second credential, emits a second mutation outcome or invalidates a later session.
After bounded receipt expiry, old requests fail closed rather than reconstructing work.

Success requires fresh sign-in. Signup completion says credential setup is complete and sign-in is required. Use only
DOM-OPS-002 §2.5 outcome fields; never log credential labels or identity-derived hashes.

## VIII. Required validation

Cover all SPEC-IDEN-002 scenarios, including wrong principal/type/challenge, pending
assertions, multiple passkeys A/B/C with a fourth enrolled and then only B revoked, unknown-ID pending
protection, failed inventory, provider response loss, commit failure after deletion,
expiry, supersession, duplicate completion, session invalidation, no active classroom,
CSRF/rate limits, accessible manual/error flows and GHSA credential-ownership guards.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. The 2026-11-27 revision (v1.4; Owner ruling 2026-11-27: passkey replacement removed; replacement is enrollment followed by revocation) removes selected-passkey replacement: the replacement operation, its purpose and its stages are gone, and the rule that a principal must always hold at least one activated passkey is unchanged (revoking the last one is refused, FEAT-IDEN-107). The earlier 2026-11-27 revision (owner authorization 2026-11-27) removes the signup-derived enrollment capability: fresh TOTP authorizes every enrollment, and enrollment is no longer authorized by the signup ceremony; cancellation, expiry and stale-operation protections are unchanged. The 2026-11-26 revision makes the enrolled passkey required (DOM-IDEN-003 §VII.A) and widens scope to sysadmin principals. The 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.

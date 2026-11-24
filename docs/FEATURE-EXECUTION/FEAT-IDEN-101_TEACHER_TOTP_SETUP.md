# FEAT-IDEN-101: Teacher TOTP Setup

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-101 | 1.4 | 2026-11-23 | 1.3 | Normative |

## I. Purpose

Provision a teacher and activate verified initial TOTP atomically, optionally issuing one explicit signup-derived passkey enrollment authorization.

## II. Scope

Initial teacher signup only. Existing-user TOTP replacement and SATAR completion use FEAT-IDEN-106; this FEAT cannot reconfigure a credential.

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

## V. Execution context and staging

Declare the FEAT-CORE-000 identity-establishment scope. Follow DOM-IDEN-005's lawful
provisioning sequence; do not require an existing teacher, Seat or active classroom.
Stage class metadata and teacher display metadata first, then username and pending
TOTP, in the encrypted server signup record authorized by INV-ARC-018. The browser
holds only a random 256-bit capability; its purpose-separated SHA-256 verifier keys
the record. Its fixed lifetime is 30 minutes, never extended by retries.

Username changes replace the pending seed. Invalid codes may redisplay the same
pending secret within the original deadline. Restart deletes the previous attempt;
hourly signup cleanup deletes expired rows. No plaintext staging enters cookies,
logs, URLs, telemetry or audit. This flow issues no backup codes or recovery request.

## VI. Atomic provisioning and optional enrollment

Before submitting signup TOTP verification, the teacher may explicitly elect optional
passkey enrollment. Verify the submitted code against server-held pending material.
Lock/revalidate the signup attempt; atomically create User, initial ClassEconomy,
administrative Seat and IdentityProfile, activate verified TOTP, initialize credential
generation, consume staging and emit the required non-identifying outcome. Failure
rolls back provisioning and consumption; a retry cannot provision another account.

If explicitly elected, the same successful verification also establishes one five-minute
initial-passkey capability bound to the new principal, generation and signup session/browser.
It starts no general management session and cannot replace a credential. FEAT-IDEN-102
consumes it into one enrollment operation, never renews it, and never reconstructs it
from an authenticated session. A later request executes that FEAT; no nested FEAT call.

Establish the post-provisioning session through the normal session command. Offer
optional passkey enrollment or skip. Skip retains that session. Optional failure does
not undo signup. Successful passkey activation invalidates the signup session and
requires fresh sign-in under the same rule as other credential mutations.

## VII. Failure, display and audit

No identity is durable before valid TOTP verification. Display accessible QR and manual
entry for the pending authenticator; do not require physical device separation or
restrict synchronized credentials. Explain that passkeys are optional and SATAR is
independent recovery. Do not reveal an activated seed again.
Audit uses ACT-IDEN-101 and DOM-OPS-002 §2.5, without identifiers or secret material.

## VIII. Required validation

Cover atomic provisioning/rollback, staging expiry/restart, wrong/new username,
invalid TOTP, duplicate completion, secret non-retention, explicit enrollment election,
skip/session preservation, failed optional enrollment, capability expiry/consumption,
replay/renewal/repurposing denial and fresh sign-in after initial passkey activation.
Preserve the existing signup security and accessibility tests.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. This 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.

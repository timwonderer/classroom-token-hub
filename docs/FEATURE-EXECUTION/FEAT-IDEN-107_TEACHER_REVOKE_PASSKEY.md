# FEAT-IDEN-107: Teacher Revoke Passkey

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-107 | 1.3 | 2026-11-23 | 1.2 | Normative |

## I. Purpose

Remove exactly one owned passkey after fresh TOTP proof, with remote-first retirement and atomic local completion.

## II. Scope

Principal-scoped teacher passkey removal. Multiple passkeys are independent; TOTP remains activated. Account destruction is a separate FEAT and failure policy.

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

## V. Authorization and intent

Resolve the authenticated teacher principal, current generation/session and fresh
purpose-bound TOTP proof. Verify the exact selected local credential belongs to that
principal and is activated, and TOTP remains available. Require no active class or Seat.
Commit an immutable retirement intent bound to the operation and consume interactive
authorization before calling the provider. A mere existence read is not an idempotency lock.

## VI. Remote retirement and local completion

Delete the exact credential remotely outside database transactions/row locks. Resolve
uncertain outcomes with fresh inventory and invoke principal reconciliation. On confirmed
retirement, lock/revalidate current principal, generation, operation stage and supersession;
hard-delete only the selected local binding, advance generation, invalidate sessions and
outstanding challenges/grants, consume completion and emit ACT-IDEN-107 atomically.

Provider failure leaves ordinary removal incomplete; do not use account destruction's
provider-failure exception. After remote retirement, database failure is recoverable
coordination, not restoration of the old passkey. Session expiry cannot grant discretion,
but FEAT-IDEN-108 can finish the exact recorded obligation. Supersession permits cleanup
only and cannot invalidate a newer session again.

## VII. Idempotency, audit and presentation

SPEC-IDEN-002's unique operation/transition receipt replaces the former audit-event
identity-key mechanism. Do not retain credential-derived idempotency keys or principal
references in audit. Duplicate completion returns the stored bounded outcome without
repeating generation/session/audit effects. Expired receipts cannot recreate an operation.
No revoked-credential archive or inactive fallback binding is retained.

Report pending versus completed removal accurately. Completion requires fresh sign-in;
remaining passkeys and TOTP remain usable. Audit follows DOM-OPS-002 §2.5, with no
credential label, credential hash or principal attribution fabricated from a classroom.

## VIII. Required validation

Cover fresh TOTP gate, foreign/missing credential, pending-credential denial, no active
classroom, multiple-passkey preservation, remote failure, lost response, local failure,
concurrent and repeated completion, supersession, session expiry and later-session
preservation. Retain GHSA remote-before-local and local-binding regression coverage.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. This 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.

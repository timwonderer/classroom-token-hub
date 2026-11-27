# FEAT-IDEN-107: Teacher Revoke Passkey

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-107 | 1.5 | 2026-11-27 | 1.4 | Normative |

## I. Purpose

Remove exactly one owned passkey after fresh TOTP proof, with remote-first retirement and atomic local completion.

## II. Scope

Principal-scoped teacher or sysadmin passkey removal. Multiple passkeys are independent; TOTP remains activated. Account destruction is a separate FEAT and failure policy.

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

Resolve the authenticated teacher or sysadmin principal, current generation/session and fresh
purpose-bound TOTP proof. Verify the exact selected local credential belongs to that
principal and is activated, and TOTP remains available. Require no active class or Seat.
Commit an immutable retirement intent bound to the operation and consume interactive
authorization before calling the provider. A mere existence read is not an idempotency lock.

Revocation of the only activated passkey is refused; the lawful path is to enroll a new passkey
(FEAT-IDEN-102) and then revoke the old one.

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
preservation, refusal to revoke the only passkey. Retain GHSA remote-before-local and local-binding regression coverage.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. The 2026-11-26 revision widens scope to sysadmin principals and refuses revocation of the only activated passkey (DOM-IDEN-003 §VII.A). The 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.

### Revision History

> [!IMPORTANT]
> **v1.2 (2026-10-14), review correction.** v1.1's restated replay-safety mechanism was a read-then-act check, not a lock: two requests carrying the same `idempotency_key` can both pass Step 3's existence lookup before either audit event is written, since `audit_events` carries no uniqueness on `(feat_id, idempotency_key)` (`app/models.py` `AuditEvent.__table_args__`). §V now requires a unique constraint on that pair as part of this FEAT's schema contract, and Step 3's failure behavior is restated to rely on that constraint rather than on the lookup alone.
>
> **v1.1 (2026-10-14), documentation modernization.** Removed the former Mutation Phase Step 1, which inserted into an `IdempotencyRecord` entity that does not exist anywhere in the codebase (same removal already made in `FEAT-IDEN-001`/`FEAT-IDEN-002`). Replay safety is restated through the mechanism §V already described: a missing `passkey_credentials` row plus a matching `idempotency_key` in the `ACT-IDEN-107` audit event (Step 2, Mutation Phase) resolves to `ALREADY_REVOKED` rather than `CREDENTIAL_NOT_FOUND`. Renumbered the remaining Mutation Phase steps; no behavior change.

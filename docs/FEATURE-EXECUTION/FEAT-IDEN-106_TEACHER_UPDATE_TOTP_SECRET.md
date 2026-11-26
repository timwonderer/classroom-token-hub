# FEAT-IDEN-106: Teacher Update TOTP Secret

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-IDEN-106 | 1.3 | 2026-11-26 | 1.2 | Normative |

## I. Purpose

Atomically activate a verified replacement TOTP for a teacher or sysadmin principal's routine maintenance, or complete independently authorized (teacher-only) SATAR recovery.

## II. Scope

Principal-scoped teacher or sysadmin TOTP replacement and teacher recovery completion (SATAR is teacher-only). These have distinct authorization paths; neither requires an active classroom.

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

## V. Routine TOTP replacement

Require an authenticated eligible teacher or sysadmin principal with activated TOTP and a fresh, purpose-bound
assertion from that teacher's activated passkey. Apply INV-ARC-019 local validation;
provider proof alone is insufficient. Stage only an encrypted new secret (generated per SPEC-SEC-001 §V seed-length requirement) on the current
operation and expose QR/manual-entry material to its authorized browser.

Until final verification/commit, the existing TOTP remains unchanged. Verify a submitted
new code against the server-held pending seed, not a browser-supplied secret. In one
local transaction, lock/recheck principal, operation, generation, session, expiry and
passkey authority; overwrite the TOTP seed, consume authorization, erase pending secret,
advance generation, revoke sessions/challenges/grants and emit ACT-IDEN-106.
Failure rolls back all activation effects. Do not retain an old seed or fallback code.

## VI. SATAR completion

Declare the teacher-recovery identity-establishment scope of FEAT-CORE-000, including
DOM-IDEN-005's unauthenticated establishment boundary. Resolve the target exclusively
from the server recovery attempt; accept no class/Seat selector as credential authority.
FEAT-IDEN-105's successful aggregate proof has already advanced generation and superseded
routine maintenance. Verify the live setup nonce, pending status, original five-day
expiry, current proof coverage, expected generation and the new authenticator code.

After that proof, commit exact recovery completion intent and perform remote retirement
of prior passkeys and principal reconciliation outside database transactions/row locks.
Recovery is not the account-destruction provider-failure exception: unavailable provider
work leaves recovery completion pending. Preserve only the material needed for recovery
within its original deadline. Expired/superseded recovery cannot activate; remaining
remote effects become cleanup-only under FEAT-IDEN-108.

Revalidate all completion conditions in the final local transaction. Update username
through the canonical builder, activate the new TOTP, remove superseded passkey bindings,
advance generation, invalidate sessions/challenges/management grants, mark the recovery
verified/completed_at, erase setup/resume material and emit the audit outcome. Username
conflict or local failure rolls back local activation; it cannot undo prior provider
retirement. Recovery never changes Seats, class ownership or economic records. Completion leaves the
principal with the new TOTP and no passkey; the credential compliance gate (DOM-IDEN-003
§VII.A) directs passkey enrollment at the next sign-in, authorized by the fresh recovery TOTP.

## VII. Idempotency, audit and presentation

Use operation transitions and unique receipts as specified in SPEC-IDEN-002. Replays
cannot overwrite a newer generation or repeat session invalidation. Routine cancellation,
expiry or incorrect new code preserves existing TOTP. SATAR and routine rotation are
not interchangeable grants, and neither issues backup codes.

Audit is the non-identifying DOM-OPS-002 §2.5 envelope. Pending seed and setup material
never enter cookies/logs/URLs. Display the pending secret only within the live setup
operation; after activation it is never revealed again. Require fresh sign-in after
completion. Explain atomic local TOTP replacement separately from recovery's external
passkey-retirement work; do not claim that provider work rolls back atomically.

## VIII. Required validation

Cover abort-before-verification, wrong code, local rollback, expiry, proof replay,
old-secret invalidation, post-replacement challenge/session invalidation, stale response,
SATAR supersession before/after retirement intent, lost provider responses, generation
races, username uniqueness rollback, secret erasure and no-class maintenance. Preserve
all SATAR selection, class-confirmation and independent-recovery tests.

## IX. Amendment

Increment version and effective date, preserve the INV → DOM → FEAT hierarchy,
and update SOP-DOC-001 and dependent references. The 2026-11-26 revision widens routine replacement to sysadmin principals, requires seed-length-compliant generation and records the post-SATAR gate (DOM-IDEN-003 §VII.A). The 2026-11-23 revision records
the approved lifecycle contract; it does not claim implemented or deployed behavior.

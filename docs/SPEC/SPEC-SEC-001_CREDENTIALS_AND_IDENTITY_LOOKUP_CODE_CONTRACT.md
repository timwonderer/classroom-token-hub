# SPEC-SEC-001: Credentials and Identity Lookup Code Contract

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-SEC-001 | 1.1 | 2026-09-05 | 1.0 | Technical Specification |

## I. Purpose

This specification defines the code-level security contract for credential handling, authentication, recovery-capability handling, and class-scoped identity lookup. It translates the governing `INV-*` requirements into testable technical behavior without making the security namespace a domain or an independent authority tier.

## II. Scope

This specification applies to every route, domain, feature executor, background job, migration, serializer, logger, cache, and test fixture that handles credentials, authentication identifiers, recovery capabilities, or identity lookup. It governs code behavior only. Infrastructure ownership, secret administration, rotation, monitoring, incident response, and release workflow are governed by `SOP-SEC-001`.

This document does not create users, seats, classes, roles, or capabilities. Those remain owned by the applicable `DOM-*` and `FEAT-*` contracts.

## III. Authority and Incorporation

Technical Specification. `SPEC-SEC-001` is not an independent level of runtime authority and cannot promote itself through metadata. Its requirements are binding only where incorporated by a governing `INV-*`, `DOM-*`, or `FEAT-*` contract, and it remains subordinate to every applicable `INV-*` requirement. The `SEC` label identifies a cross-cutting subject, not a runtime authority namespace.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## V. Normative Code Contract

### V.1 Credential material

1. Code MUST pass passphrases through one canonical password-hashing primitive exposed by the owning identity contract.
2. The canonical password KDF is scrypt with the encoded profile `scrypt:32768:8:1`. Each password hash MUST contain its own randomly generated salt in the standard encoded verifier format.
3. Password hashing MUST NOT use `PEPPER_KEY`, `SECRET_KEY`, `ENCRYPTION_KEY`, or any other application secret as an input. Those keys have separate ownership and rotation semantics.
4. Code MUST store only the resulting verifier; it MUST NOT store plaintext passphrases, reversible passphrase encryption, or a recoverable copy in logs, events, sessions, URLs, caches, test output, or error objects.
5. Verification MUST use the stored verifier and MUST return only a boolean/typed success result to its caller. Algorithm and parameters MUST be centralized in the canonical primitive, not duplicated in FEAT documents or route code.
6. Malformed, missing, expired, or otherwise unusable verifiers MUST fail closed and MUST not disclose which condition occurred.

### V.1a Required runtime environment

The application MUST refuse to start in any non-test environment when a required variable is absent, blank, malformed, or uses a development/default value.

| Variable | Code purpose | Required handling |
|---|---|---|
| `SECRET_KEY` | Session and application signing | High-entropy, environment-specific secret; never reused as a password pepper or PII-encryption key. |
| `ENCRYPTION_KEY` | Symmetric encryption of recoverable display PII | Valid key for the approved encryption facility; production key must be stored outside the repository and retained only under controlled key custody. |
| `PEPPER_KEY` | HMAC key for deterministic lookup/matching digests | High-entropy, environment-specific key; never used for password hashing. |
| `AUDIT_HMAC_KEY` | Integrity protection for security/audit lineage where required by its owning contract | High-entropy, environment-specific key; never logged or exposed to application responses. |
| `DATABASE_URL` | Canonical persistence boundary | Must identify the explicitly selected environment; implicit local/default database selection is prohibited for production. |
| `FLASK_ENV` | Explicit environment selection | Must be set explicitly; production must not run under development/test settings. |

`PEPPER_KEY` rotation is a lookup-digest migration and access-control event. `SECRET_KEY` rotation is a session-signing event. `ENCRYPTION_KEY` rotation is a protected-PII re-encryption event. `AUDIT_HMAC_KEY` rotation is an audit-lineage verification event. They MUST be planned and executed independently; no code may silently fall back from one variable to another.

### V.2 Lookup and PII representation

1. A lookup MUST resolve the canonical `class_id` before evaluating class-local identity or claim authority.
2. Name or other PII lookup values MUST be normalized by one canonical, documented function, then compared using HMAC-SHA-256 under `PEPPER_KEY` with a field/domain separation label. The digest MUST not permit recovery of the original value.
3. Recoverable display PII MUST use the application’s approved symmetric encryption facility. Hash and encrypted display representations MUST be separate fields when both purposes exist.
4. `users.id`, `seats.id`, and `class_id` MUST retain their distinct meanings. `public_id` MUST be resolved under canonical class scope and MUST never grant authority.
5. Lookup responses MUST return the minimum result needed by the owning contract. They MUST NOT expose credential material, lookup digests, encryption keys, internal identifiers, or unrelated class membership.

### V.3 Authentication, capability, and context

1. Authentication establishes `users.id`; it does not by itself establish `seat_id` or `class_id`.
2. Any class-scoped action MUST construct explicit request context containing the required principal, actor, boundary, request, and time values. Missing or contradictory context MUST fail immediately.
3. Authorization MUST be evaluated at request time through the owning domain capability contract. Route-local role checks, global cached authorization, inferred scope, and helper-based scope repair are prohibited.
4. Mutations MUST execute through the owning FEAT command boundary. Reads MUST be pure and MUST NOT commit state, rotate credentials, create recovery artifacts, or alter session identity as an incidental effect.

### V.4 Recovery and capability artifacts

1. Recovery and claim artifacts MUST be opaque, single-purpose, class-constrained where applicable, time-bounded when their owning contract requires it, and stored only in a non-reversible verification form unless recoverability is explicitly required by the governing contract.
2. Code MUST bind artifact use to its owner and canonical scope before consuming it.
3. Successful consumption MUST be atomic with the state change it authorizes; replay, mismatch, expired use, and cross-class use MUST fail closed.
4. Responses for failed authentication, lookup, claim, and recovery attempts MUST be generic enough not to reveal account existence, roster membership, credential validity, or class membership.

### V.5 Observability and retention

Security events MAY record a request identifier, owning FEAT identifier, outcome class, and non-sensitive technical metadata. They MUST NOT contain PII, passphrases, tokens, raw lookup inputs, digests, encryption keys, or detailed failure material. Records MUST follow the owning identity and class deletion semantics; no security artifact may preserve deleted identity data without an explicitly authorized, separately scoped requirement.

## VI. Required Verification

Implementations MUST have focused tests proving: plaintext and secret non-retention; normalization and keyed lookup behavior; class-scoped resolution; principal/seat/class separation; fail-closed malformed and replay paths; generic failure responses; pure reads; atomic authorized mutations; and deletion of security material with its owning identity. Source inspection alone is insufficient evidence for rendered or runtime behavior.

## VII. Non-Goals and Prohibitions

Implementations MUST NOT select or substitute cryptographic algorithms or parameters outside those explicitly governed by this specification. This specification does not create a `SEC` domain, authorize cross-class administration, or provide compatibility bridges for legacy credential or identity schemes. Any algorithm or parameter change must be recorded as a revision to this specification and operationalized by `SOP-SEC-001` before release.

## VIII. Amendment

Revisions require a version increment, updated effective date, explicit derivation from the dependencies in Section IV, reconciliation with affected `DOM-*` and `FEAT-*` contracts, and focused verification of every changed invariant boundary.

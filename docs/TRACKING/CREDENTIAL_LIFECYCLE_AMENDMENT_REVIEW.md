# Credential Lifecycle Amendment Review

Review date: 2026-11-23. Status: documentation changes submitted for review; application implementation is not authorized by this change. This record is descriptive. Authority remains INV → DOM → FEAT, with incorporated technical specifications.

The provider verifies cryptographic proof. CTH establishes authentication authority. Reconciliation maintains consistency between the two.

## Coordinated amendments

| Governing documents | Review result |
|---|---|
| INV-ARC-001/002/003/008/019, DOM-IDEN-006, FEAT-CORE-000 | Explicit principal and system credential scopes; no inferred classroom, Seat prerequisite or classroom authority. INV-ARC-002's formerly universal class requirement is narrowed alongside the other scope clauses. |
| INV-ARC-019, DOM-IDEN-003, SPEC-SEC-001, SPEC-OPS-004 | CTH-owned activation and generation; pure teacher/sysadmin assertion validation across every authentication surface. |
| DOM-IDEN-003, FEAT-IDEN-101/102/105/106/107 | Atomic local TOTP replacement; durable selected-passkey replacement; signup-derived single-use authorization; SATAR supersession after aggregate proof; consistent session/challenge invalidation. |
| DOM-IDEN-003/005, FEAT-IDEN-007/108, SPEC-IDEN-002 | Unified reconciliation, remote-first ordinary retirement, bounded provider work followed by lawful local destruction even when external cleanup is unverified. |
| INV-ARC-018/019, DOM-OPS-001/002, SPEC-IDEN-002 | Minimal operation inventory, separate secret/operational lifetimes, non-identifying outcome evidence and no post-destruction ownership archive. |
| SOP-DOC-001 | New contracts registered and dependent versions recorded. |

[SPEC-IDEN-002](../SPEC/SPEC-IDEN-002_CREDENTIAL_LIFECYCLE_PROTOCOL.md) contains the field-level ownership, representation, retention and validation matrix. [FEAT-IDEN-108](../FEATURE-EXECUTION/FEAT-IDEN-108_CREDENTIAL_RECONCILIATION.md) supplies the dedicated reconciliation authority. The 15-second total provider budget and maximum three transient attempts are operational requirements, not foundational invariants.

## Implementation proposal for subsequent review

1. Add Identity-owned generation and bounded operation state under the exact inventory in SPEC-IDEN-002. Use database-enforced uniqueness and short transaction boundaries. Keep pending credentials outside the activated registry; no compatibility fallback or provider-to-local import.
2. Split shared passkey evaluation from explicit challenge consumption, session creation, audit and usage bookkeeping. The current `verify_sign_in` in `app/services/passkey_service.py` updates `last_used`; replacing that update with a pure ownership/activation query is required before the new contract is implemented.
3. Route signup enrollment, fresh-TOTP enrollment/replacement/removal and passkey-authorized TOTP replacement through the declared FEATs. Bind purpose, generation and session at execution, not only when proof is first collected.
4. Implement one Identity inventory classifier and explicit retirement commands. Reuse the provider integration in `scripts/passkey_tenant_audit.py`, which currently detects orphaned provider principals; extend it to per-credential discrepancies and lawful pending registrations. Replace its independent destructive path with the authorized reconciliation command. Do not carry its identifier-printing behavior into retained observability.
5. Use durable reservations and short, serialized local transitions across workers; never hold a database transaction or row lock over provider I/O. The concrete coordination design must demonstrate that activation cannot adopt a target while retirement is in flight, including absent-principal reconciliation. Process-local locks are insufficient. This mechanism remains an implementation design decision, not authority to add tombstones or identity history.
6. Invoke principal reconciliation at every declared lifecycle boundary and provide a scheduled residual sweep. An hourly sweep is a proposed starting cadence, subject to measured tenant size and rate limits; it is not an approved availability guarantee. Pending-secret cleanup targets one minute, reports failures and retries at the earliest lawful execution.
7. Preserve local destruction atomicity and truthful completion outcomes. Commit initial authority revocation separately, perform bounded provider work outside database transactions, then revalidate local authority and destroy through the existing lifecycle command. No provider outage can justify retaining a principal after lawful local destruction.
8. Implement the full targeted acceptance matrix in SPEC-IDEN-002 before application review. Preserve GHSA-5v6c-mw3v-fmf2 regression coverage, accessibility, CSRF and rate limits. Do not equate these documentation checks with behavior tests.

## Provider evidence and enablement gate

The [Passwordless API reference](https://docs.passwordless.dev/guide/api) documents credential inventory by user and exact credential deletion. The installed Passwordless Python SDK 2.0.0 exposes tenant user listing, per-user credential listing, credential deletion and user deletion. The existing tenant audit script uses tenant listing and user deletion. These establish an integration path; they do not establish complete hosted-tenant enumeration or production readiness.

Before enabling destructive scheduled reconciliation, verify tenant-wide completeness, pagination/truncation behavior, tenant permissions/isolation, exact deletion and already-absent responses, deadline enforcement, and ambiguous/lost provider responses against the actual integration contract and an authorized isolated tenant. Record provider contract evidence separately from mocked failure tests. No production inventory or cleanup was authorized or performed for this amendment.

Provider registration fencing is not a destruction prerequisite. A late provider registration has no local authority and can be discovered from current provider inventory without retaining a deleted principal. A successful inventory comparison is evidence of consistency at that execution, not a guarantee against later external arrivals.

## Review disposition and remaining gates

No additional destruction-outage policy is proposed: the owner's bounded-failure exception governs, while local authorization, database and mandatory audit failures still prevent successful completion. Ordinary credential replacement/removal and SATAR completion retain remote-first retirement.

The scope conflict in INV-ARC-002 is addressed by an explicit normative amendment, not an implementation exception. The proposed coordination mechanism and scheduler cadence still need implementation review. Provider completeness and deletion semantics remain an enablement gate; any inability to meet them must return for adjudication rather than silently broadening authority or retention.

Review the actual coordinated diff before authorizing application work. This change does not implement, merge, deploy or run credential cleanup.

## Documentation validation

The documentation index and archive/citation checks pass: 887 tests using `pytest --noconftest` against the two documentation test modules. These checks establish index/link integrity, not credential lifecycle correctness or provider readiness.

The generated documentation build and integrity check also pass with zero failures. Existing source-heading warnings remain in other sections, including DOM-IDEN-005; this amendment does not alter those headings.

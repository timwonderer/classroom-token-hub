# SOP-SEC-001: Credentials and Identity Lookup Operations

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-SEC-001 | 1.0 | 2026-09-05 | N/A | Normative procedure (Tier 2) |

## I. Purpose

This procedure defines the human and infrastructure controls that keep the code contract in `SPEC-SEC-001` operating safely over its lifecycle. It covers secret custody, configuration, maintenance, deployment, incident response, and evidence production outside application code.

## II. Scope

This SOP applies to maintainers, operators, release managers, database administrators, CI owners, and anyone who can access production configuration, credential-hashing parameters, encryption keys, recovery infrastructure, logs, backups, or identity data. It does not define application behavior or domain ownership.

## III. Authority Level

Normative human procedure (Tier 2), subordinate to `INV-CORE-*` and `INV-ARC-*`, and implementing `SPEC-SEC-001`. Under `SOP-CORE-000`, this SOP binds people and operational systems; it cannot establish runtime authority or override an `INV-*`, `DOM-*`, or `FEAT-*` contract.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md`
- `docs/SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-CORE-000_Sop_Foundation.md`

## V. Operating Controls

### V.1 Secret custody

- Store encryption keys, lookup secrets, and signing material only in the approved secret manager or protected runtime configuration. Password hashing has no application-secret input.
- Grant least-privilege access to named operators and services; review access at every release and at least once per operating cycle.
- Never place secrets in Git, tickets, chat, shell history, CI output, screenshots, backups intended for broad access, or copied test fixtures.
- Maintain separate secrets and access paths for development, test, staging, and production.

### V.2 Change and rotation

1. Propose changes to cryptographic algorithms, parameters, secret sources, normalization rules, retention, or recovery behavior as a versioned `SPEC-SEC-001` change.
2. Before deployment, record affected data, migration/reverification strategy, rollback safety, owner, approvers, and focused evidence.
3. Rotate secrets through a controlled change window with dual review, preflight validation, and an explicitly tested failure mode. Do not silently substitute a fallback secret or storage mechanism.
4. If rotation would make existing protected data unverifiable or unrecoverable, stop and escalate; do not invent a compatibility bridge.

### V.2a Environment provisioning

Provision these variables independently for each environment: `SECRET_KEY`, `ENCRYPTION_KEY`, `PEPPER_KEY`, `AUDIT_HMAC_KEY`, `DATABASE_URL`, and `FLASK_ENV`. Generate secrets with a cryptographically secure generator, place them in the approved secret manager, and inject them at process startup. Do not commit values, copy production values into development/test, or rely on `.env` files for production custody.

Before release, verify that all six variables are present, non-default, environment-specific, and readable by the intended service identity only. A missing or invalid variable is a deployment failure. Do not substitute `SECRET_KEY` for `PEPPER_KEY`, `ENCRYPTION_KEY`, or `AUDIT_HMAC_KEY`, and do not add an in-memory or default fallback.

Password verification uses the SPEC-defined scrypt profile and does not depend on `PEPPER_KEY`. A pepper rotation therefore does not require resetting passwords. It does require a separately approved, per-field migration or re-establishment strategy for every lookup digest: an old HMAC digest cannot be transformed into a new-key digest without the original lookup value. Re-materialization is permitted only where that value is lawfully available at rotation time; otherwise the affected lookup artifact may become unusable and the owning identity/feature contract must define the fail-closed recovery or re-establishment path before rotation. An encryption-key rotation requires a controlled re-encryption operation and verification before the old key is retired.

### V.3 Deployment and maintenance

- Verify production configuration is present, non-default, environment-specific, and readable only by the intended service identity.
- Run focused security, identity, migration, and deletion tests for the changed boundary. Report unavailable infrastructure separately from application failures.
- Review logs and metrics for secret exposure, repeated failed authentication, cross-class lookup attempts, replay attempts, and unexpected scope failures without exporting sensitive payloads.
- Keep backups and replicas subject to the same access controls and deletion policy as the source data. Backups MUST NOT be used to restore deleted accounts or deleted class-scoped identity data.

### V.4 Incident response

On suspected exposure, compromise, cross-class access, or loss of key material:

1. Restrict the affected secret, service, or operator access without deleting evidence.
2. Preserve a minimal, access-controlled incident record containing time, request identifiers, affected scope, actions, and approvers; exclude PII and secret values.
3. Rotate or revoke affected material using the approved change procedure.
4. Determine whether identity, class, or recovery data was exposed and apply the governing deletion/revocation action.
5. Require a documented review of `SPEC-SEC-001`, affected domain/feature contracts, tests, and deployment controls before restoring normal operation.

## VI. Required Evidence and Handoff

Every security change handoff MUST include the governing `INV-*` references, changed SPEC/SOP versions, environment and secret-change record, focused test results, migration or rotation evidence, unresolved risks, and explicit `NOT_EVALUATED` or `BLOCKED` items. A clean source diff does not prove that infrastructure, secrets, backups, or live configuration are correct.

## VII. Prohibited Operations

Operators MUST NOT use production backups to restore accounts, disable scope checks to troubleshoot, print protected values for diagnosis, share secrets between environments, rely on default or in-memory security stores, or approve a change whose authority chain is unresolved.

## VIII. Amendment

Revisions require a version increment, updated effective date, review against the Section IV dependencies, and evidence that the revised workflow still preserves the `INV-*` requirements and `SPEC-SEC-001` code contract.

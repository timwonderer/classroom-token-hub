# FEAT-IDEN-008 — Operator Sysadmin Bootstrap

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| --- | --- | --- | --- | --- |
| FEAT-IDEN-008 | 1.0 | 2026-11-15 | — | Normative FEAT |

## I. Purpose

Establish a system authentication principal for an independently operated deployment.

## II. Scope

This contract covers the external operator command and the initial TOTP enrollment.

## III. Authority Level

Tier 2 normative execution contract subordinate to INV-CORE-000, INV-ARC-006,
INV-ARC-019, DOM-CORE-002 and DOM-IDEN-001.

## IV. Dependencies

FEAT-CORE-000 governs the transaction. SPEC-OPS-004 defines the console
surface. SOP-SEC-001 governs handling of credentials and lookup data.

## V. Authority and entry

The infrastructure operator invokes `flask create-sysadmin` in the deployment
environment. SPEC-OPS-004 §V assigns account provisioning to this out-of-band
surface. DOM-CORE-002 §V.1 locates system authority on the authentication
principal. INV-CORE-000 §III.4 and INV-ARC-019 separate this principal from
classroom actors. This command grants no application capability to initiate
bootstrap. HTTP requests must be refused.

## VI. Mutation and replay

The CLI accepts a nonempty normalized login. The FEAT calls the Identity-owned creation command. A single transaction creates
one `User` with role `SYSADMIN`, salted username hash, keyed lookup hash and
encrypted TOTP secret. It creates no economy, seat, membership or economic
state. An empty input fails validation. A duplicate login, including a login
owned by another role or a concurrent invocation, leaves the existing principal
and credentials intact. Failed transactions roll back. The CLI reveals enrollment
material only after successful creation and only to the initiating operator.

## VII. Execution evidence

Blast radius is **HIGH**. Use FEAT-CORE-000 transaction ownership and log the
FEAT identifier with an opaque correlation and invocation key. Login inputs,
lookup digests, enrollment URIs and TOTP material must stay out of operational
evidence (SOP-SEC-001). This operation has no seat, class, or classroom audit
event. The subject receives only the console privileges defined in SPEC-OPS-004.

## VIII. Amendment

Changes require a version increment, review against the governing contracts,
and a corresponding entry in the documentation index and changelog.

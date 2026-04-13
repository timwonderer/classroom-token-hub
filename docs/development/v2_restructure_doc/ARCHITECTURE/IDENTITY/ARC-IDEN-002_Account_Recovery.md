# ARC-IDEN-002: Account Recovery

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-002     | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the architectural rules for student account recovery inside the
realigned v2 model.

Its purpose is to ensure recovery remains a tenant-scoped identity rebinding flow rather
than a data-repair or economic-rewrite mechanism.

## II. Scope

This document applies to:

- teacher-initiated student recovery
- reset-code or reclaim-token style recovery flows
- recovery-time credential rebinding
- tenant-scoped recovery validation

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-012_Datetime_Handling_Specification.md`

## V. Core Recovery Rule

Recovery is an identity rebinding action within one tenant boundary.

Recovery must restore access without rewriting economic history, duplicating actors, or
creating a second account for the same tenant-scoped participant.

## VI. Tenant Scope Rule

Recovery must be explicitly tied to one tenant boundary.

Architectural requirements:

- recovery initiation must identify the target tenant explicitly
- recovery validation must confirm the actor belongs to that tenant context
- recovery must not fan out across classes or infer scope from teacher-global ownership

## VII. Identity Rebinding Rule

Recovery rebinds access credentials or identity linkage to an existing participant path.

Architectural consequences:

- recovery must not create a new economic identity path as part of the same action
- recovery must not merge multiple participant histories implicitly
- recovery must preserve the existing tenant-scoped economic history

## VIII. Teacher-Initiated Boundary

Recovery is a controlled teacher-side initiation flow, not an unrestricted public
account-discovery mechanism.

Architectural requirements:

- recovery initiation must come from an authorized teacher actor inside the relevant
  tenant boundary
- recovery issuance must be explicit and auditable
- recovery entry by the student must reveal as little as possible before successful
  validation

## IX. Recovery Token Rule

Recovery tokens or reset codes are temporary recovery artifacts only.

Architectural requirements:

- recovery artifacts must be time-bounded
- recovery artifacts must be single-use
- recovery artifacts must not become durable identity credentials
- expiration and invalidation behavior must be explicit

## X. Monetary And Historical Integrity Rule

Recovery must not alter economic reality.

The following are forbidden during recovery:

- editing ledger history
- manually changing balances
- recreating items or claims as part of access restoration
- transferring history to a newly created replacement record

Recovery changes access state, not tenant-scoped history.

## XI. Request And Command Rule

Recovery must obey the same ARC model as other actions.

Architectural requirements:

- validation steps must be side-effect free until the recovery command path executes
- recovery mutation must occur through explicit command handling
- completion must be atomic with respect to credential rebinding and token invalidation

## XII. Failure Rule

Failed recovery attempts must fail without leaking unnecessary identity information and
without mutating tenant-scoped economic state.

Architectural consequences:

- generic failure is acceptable where identity disclosure would be unsafe
- repeated failures may be rate-limited or locked down
- failure handling must remain separate from economic or class-scoped mutation

## XIII. Prohibited Patterns

The following are forbidden:

- recovery that creates a replacement student record as part of the same flow
- recovery that merges or transfers financial history implicitly
- recovery that bypasses tenant validation
- public recovery flows that reveal whether a participant exists before valid proof
- partial recovery paths that leave multiple valid identity states active

## XIV. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- FEAT recovery flows must remain tenant-scoped and identity-focused
- DOM or service-layer recovery commands must preserve economic immutability
- schema and implementation work may contain recovery artifacts, but those artifacts do
  not redefine tenant or economic authority

## XV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

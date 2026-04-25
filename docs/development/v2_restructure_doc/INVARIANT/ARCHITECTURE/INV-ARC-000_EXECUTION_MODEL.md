# INV-ARC-000 — Execution Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-000      | 1.1     | 2026-04-13     | 1.0        | Foundational    |

## I. Purpose

This document defines the canonical execution model for Classroom Token Hub.

It is the umbrella `INV-ARC` document that governs how request-time decisions are made
and executed across the system.

## II. Scope

This specification applies to:

- HTTP request handling
- capability evaluation
- domain command execution
- cross-domain interaction
- logging and observability

It is binding on all `DOM` and `FEAT` specifications.

## III. Authority Level

Foundational within the `INV-ARC` namespace. It derives from:

- `INV-CORE-000_Core_Invariants.md`
- `INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`

## V. Core Execution Model

Every request MUST follow this sequence:

1. construct request context
2. evaluate capabilities
3. resolve allow or deny
4. execute a single domain command if allowed
5. return response

No deviation from this sequence is permitted.

## VI. Registered INV-ARC Rules

This execution model is elaborated by the following `INV-ARC` documents:

- `INV-ARC-001_Scoped_Request_Context.md`
- `INV-ARC-002_No_Implicit_Global_Access.md`
- `INV-ARC-003_Scoped_Capability_Evaluation.md`
- `INV-ARC-004_Cross_Tenant_Isolation.md`
- `INV-ARC-005_No_PII_Leakage_in_Execution_Layer.md`
- `INV-ARC-006_Command_Boundary_for_Mutation.md`
- `INV-ARC-007_GET_Must_Be_Pure.md`
- `INV-ARC-009_Domain_Authority_for_State.md`
- `INV-ARC-010_Explicit_Context_Switching.md`
- `INV-ARC-011_No_Phantom_Scope_Access.md`
- `INV-ARC-012_Hard_Deletion_Enforcement.md`
- `INV-ARC-013_Membership_by_Existence.md`
- `INV-ARC-014_No_Label_Based_Logic.md`
- `INV-ARC-015_Temporal_Model_and_Boundary_Enforcement.md`

## VII. Rebuild Intent

This execution model exists to force the v2 rebuild away from the failure modes already
identified in the architecture audit:

- write-on-read behavior
- unscoped capability decisions
- route-local authorization logic
- recomputed state in features
- cross-domain mutation shortcuts

The rebuild intent is not merely cleaner wording. It is to make those patterns
architecturally invalid so `DOM` and `FEAT` cannot normalize them again.

## VIII. Execution Constraints

### VIII.1 Capability Evaluation

- capability checks must be side-effect free
- capability checks must use explicit context only
- capability checks must be evaluated at request time

### VIII.2 Command Execution

- exactly one command path must execute per request
- commands must be idempotent where applicable
- commands must own all mutation logic

### VIII.3 Cross-Domain Interaction

- domains must not directly mutate other domains
- cross-domain effects must be expressed through approved domain contracts

## IX. Downstream Consequence

`DOM` specifications must expose truth, capability checks, and commands in a way that
fits this request model.

`FEAT` specifications must describe action flow only as orchestration of this model, not
as exceptions to it.

## X. Observability Requirements

All decisions MUST be logged with:

- `request_id`
- `action`
- `capability`
- `domain`
- `allowed`
- `reason` when denied
- `join_code`
- `actor_id`

## XI. Enforcement

The following MUST be enforced through CI and runtime guards:

- no database commits in `GET` routes
- no use of unscoped balance properties in execution paths
- capability checks precede command execution
- no cross-domain mutation

## XII. Final Statement

> Domains declare truth. Invariants govern interaction. Capabilities evaluate authority.
> Features execute decisions.

## XIII. Amendment

Revisions to this document must:

1. increment the version number
2. update the Effective Date
3. maintain alignment with all `INV-CORE` specifications
4. preserve the registered `INV-ARC` rule set

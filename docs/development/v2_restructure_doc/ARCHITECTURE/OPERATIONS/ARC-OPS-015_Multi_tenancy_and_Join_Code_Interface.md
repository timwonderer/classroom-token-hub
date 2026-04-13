# ARC-OPS-015: Multi-tenancy and Join-Code Interface

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-015      | 2.0     | 2026-04-12     | 1.0        | Constitutional  |

## I. Purpose

This document defines the architectural boundary for tenant isolation in Classroom
Token Hub.

It establishes how `join_code`, `class_id`, membership existence, and request context
work together so that every request is constrained to exactly one tenant boundary.

## II. Scope

This document applies to:

- tenant identification
- request scoping
- class membership enforcement
- student join and claim entry points
- tenant deletion and tenant non-existence behavior
- all cross-domain reads and writes that depend on class scope

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_EXECUTION_MODEL.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## V. Core Tenant Rule

All runtime access and mutation MUST be constrained to a single tenant boundary.

That boundary is represented publicly by `join_code` and architecturally by
request-scoped tenant context anchored to the same class instance.

A request that cannot prove its tenant boundary is invalid.

## VI. Tenant Identity Model

### Public Tenant Pointer: `join_code`

`join_code` is the public tenant locator.

It may be used to:

- locate a class during join or claim flows
- anchor a request context
- route requests into the correct tenant boundary

It must not be used as an excuse for partially scoped access. If a request references a
`join_code`, the rest of the request must remain inside that same tenant boundary.

### Canonical Class Anchor: `class_id`

`class_id` is the canonical class identity anchor inside the system.

Architectural rules:

- `class_id` either exists or does not exist
- `class_id` is not lifecycle-based
- all internal class-scoped state must resolve to the same class instance represented by
  the active `join_code`

`class_id` and `join_code` are not competing scope systems. They are two identifiers for
the same tenant boundary at different interfaces.

## VII. Membership by Existence

Membership in a tenant is determined only by existence of a valid class association.

Architectural consequences:

- access exists if the actor has a valid class association
- access does not exist if that association does not exist
- membership must not be inferred from labels, status flags, prior session state, or
  teacher ownership shorthand

No lifecycle label may replace membership existence as the basis for access decisions.

## VIII. Request Scope Requirements

Every class-scoped request MUST construct explicit tenant context containing:

- `class_id`
- `join_code`
- `actor_id`
- `actor_type`
- `request_id`
- `timestamp`

Additional domain identifiers may be included as needed, but no class-scoped action is
valid without the tenant anchor.

### Scope Resolution Rule

Tenant resolution must follow this sequence:

1. resolve the target tenant from explicit request input or explicit session context
2. validate that the tenant exists
3. validate that the actor is permitted inside that tenant boundary
4. execute all subsequent capability checks and command paths within that same tenant

If any step fails, the request must fail immediately.

## IX. Cross-Tenant Isolation Rules

A single request MUST NOT:

- read across multiple `join_code` boundaries
- write across multiple `join_code` boundaries
- authorize against one tenant and mutate another
- combine teacher-global data with class-scoped execution truth

Teacher ownership does not authorize tenant fan-out inside a request. If a teacher can
access multiple classes, each request must still be anchored to one class boundary.

## X. Phantom Scope And Non-Existence

Requests referencing a non-existent tenant must fail.

The system MUST NOT:

- fall back to another tenant
- infer replacement scope from prior session state
- silently recover from missing tenant context
- preserve access to deleted tenants

Non-existence is definitive.

## XI. Join And Claim Flows

Join and claim flows are the public entry path into tenant-scoped behavior.

Architectural requirements:

- `join_code` may be used to locate the target tenant during entry
- claim logic must bind the actor to that specific tenant only
- successful claim must result in explicit tenant membership existence
- claim must not create cross-tenant authority or shared-scope side effects

These flows are entry mechanisms, not exceptions to the tenant model.

## XII. Deletion Semantics

Tenant deletion is hard deletion of the tenant boundary.

Architectural consequences:

- deleted tenant scope must not be referenced by later requests
- deleted tenant scope must not survive through background jobs
- deleted tenant scope must not remain reachable through logs, support paths, or
  fallback queries inside the application domain

Membership deletion is also existence-based:

- removal from a class erases the actor from that class context
- if no remaining class associations exist for that actor, the actor is removed from the
  system according to invariant-defined deletion semantics

## XIII. Prohibited Patterns

The following are forbidden:

- `teacher_id`-only scoping where class scope is required
- label-based scope resolution
- mixing class-scoped and teacher-global reads into one execution truth
- scope fallback based on prior request state
- access paths that succeed without explicit tenant context
- tenant-preserving soft deletion within the runtime model

## XIV. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- ARC documents must assume one tenant boundary per request
- DOM documents must define domain truth inside that tenant boundary
- FEAT documents must describe actions that enter, validate, and execute within that
  boundary without exceptions

If later documents require multi-tenant execution in one request, those documents are
wrong.

## XV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and execution-model authority named
above.

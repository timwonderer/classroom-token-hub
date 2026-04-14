# INV-CORE-001 — Capability-Based Architecture and Authority Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-CORE-001     | 1.1     | 2026-04-13     | 1.0        | Foundational    |

## I. Purpose

This document defines the authority model for Classroom Token Hub v2 and establishes how
the invariant layer governs all downstream design and implementation.

Its central rule is:

> All actions are governed by capability checks evaluated at request time, under a
> strict authority hierarchy.

## II. Foundational Principle

CTH does not grant actions by default.

> An action is permitted only if the required capability is proven in context.

## III. Normative Hierarchy

The normative hierarchy for CTH v2 is:

1. `INV`
2. `DOM`
3. `FEAT`

All other document families are informative or not applicable to normative runtime
authority unless explicitly promoted by a later governing invariant.

### III.1 INV Namespace

`INV` is the highest authority namespace and contains two sub-namespaces:

- `INV-CORE`: the laws of the system
- `INV-ARC`: how those laws are applied across the application

Conflict resolution inside `INV` is:

- `INV-CORE` overrides all other specifications
- `INV-ARC` must derive directly from `INV-CORE`
- `DOM` must conform to all `INV` specifications
- `FEAT` must conform to all `INV` and `DOM` specifications

Standalone `ARC` as an independent layer is deprecated.

## IV. INV-CORE Specifications

`INV-CORE` specifications define the non-negotiable laws in which all logic and design
must operate.

Reference documents:

- `INV-CORE-000_Core_Invariants.md`
- `INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`

## V. INV-ARC Specifications

`INV-ARC` specifications define how `INV-CORE` laws are applied within Classroom Token
Hub.

An `INV-ARC` specification:

- must be generalized and not feature-bound
- must directly derive from one or more `INV-CORE` laws
- must govern cross-domain behavior or interactions between domains
- must not contradict any `INV-CORE` rule

Core architectural rules:

- all actions must pass capability checks
- no domain may directly enforce behavior in another domain
- state must be evaluated at request time

Registered `INV-ARC` documents at this level are:

- `INV-ARC-000_EXECUTION_MODEL.md`
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

## VI. DOM Specifications

Domains own truth and expose capability checks.

Domains:

- define authoritative bounded state
- expose capability evaluation based on that state
- must not directly modify another domain's state
- must not assume global state

## VII. FEAT Specifications

Features execute user-facing actions.

FEAT responsibilities:

- orchestrate capability checks
- enforce allow or deny decisions
- compose cross-domain behavior only through capability evaluation and approved domain
  contracts
- avoid introducing independent business logic outside that orchestration

## VIII. Capability Contract

Capability checks must follow this structure:

```text
allowed, reason = can_<action>(actor, context)
```

Requirements:

- deterministic
- context-scoped
- explainable when denied

### VIII.1 Capability Composition

Multiple capability checks may be composed at the `FEAT` layer.

Rules:

- checks are evaluated sequentially
- the first failing check determines denial
- the associated reason is returned to the caller

### VIII.2 Capability Ownership And Constraints

Capability checks are authoritative evaluations, not convenience helpers.

Requirements:

- capability checks must live in the domain that owns the evaluated truth
- capability checks must be side-effect free
- capability checks must use explicit request-scoped context only
- capability checks must not rely on global state, cached authorization state, or prior
  request outcomes

Context requirements:

- context must be self-contained
- context must include the class scope anchor when class-scoped behavior is evaluated
- context must include any additional identifiers needed to evaluate the action at
  request time

## IX. Prohibited Patterns

The following are forbidden:

- cross-domain mutation
- implicit side effects across domains
- recomputed state without domain authority
- capability decisions made outside request context
- capability checks with side effects

## X. Success Criteria

- every action can be traced to a capability decision
- no domain owns behavior outside its boundary
- no hidden coupling exists between domains

## XI. Amendment

Revisions to this document must:

1. increment the version number
2. update the Effective Date
3. preserve the `INV-CORE` versus `INV-ARC` distinction inside the `INV` namespace
4. maintain compatibility with `INV-CORE-000`

# ARC-CORE-000: Architecture Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-CORE-000     | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the constitutional execution model for the Classroom Token Hub
application and the governing boundary between architecture, domains, and features.

Its purpose is not to describe the current codebase loosely. Its purpose is to define
the structural rules that all runtime behavior and all lower-tier documents must obey.

## II. Scope

This document applies to:

- all HTTP request handling
- all capability evaluation
- all domain commands and domain queries
- all route, service, and background execution paths
- all ARC, DOM, and FEAT documents that define runtime behavior

## III. Authority Level

Constitutional (ARC Tier). Subordinate only to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`

No ARC, DOM, FEAT, SOP, or implementation artifact may override this document.

## IV. Dependencies

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/INV-CORE-001_Capability_Based_Architecture_and_Authority_Model.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_EXECUTION_MODEL.md`

## V. Core Architectural Principle

Classroom Token Hub executes actions through a capability-governed request model.

No action is allowed by default.

An action may execute only when:

1. a valid request context is constructed
2. the relevant capabilities are evaluated at request time
3. the request is allowed under current authoritative state
4. a permitted command path executes inside the owning domain

This sequence is mandatory.

## VI. Runtime Execution Model

Every runtime action MUST follow this sequence:

1. Construct request context
2. Evaluate capabilities
3. Resolve allow or deny
4. Execute at most one mutation command path if allowed
5. Return response

The feature layer may orchestrate this sequence, but it may not skip or reorder it.

### Request Context Requirements

Every request-scoped action MUST operate from explicit context.

The minimum architectural context is:

- `class_id`
- `join_code`
- `actor_id`
- `actor_type`
- `request_id`
- `timestamp`

If required scope is missing, the request MUST fail immediately.

### Decision Timing

Capability decisions MUST be evaluated against current authoritative state at request
time.

Capability decisions MUST NOT be:

- reused across requests without revalidation
- inferred from prior UI state
- inferred from cached authorization state
- replaced with inline route conditionals

### Mutation Boundary

All state mutation MUST occur inside an explicit domain command.

Mutation during:

- capability evaluation
- query evaluation
- GET request rendering
- template preparation

is forbidden.

## VII. Layer Responsibilities

### ARC: Allowed Interactions

ARC defines what kinds of interactions are allowed across the system.

ARC is responsible for:

- the request execution sequence
- request context requirements
- capability evaluation rules
- command and query boundaries
- cross-domain interaction constraints
- observability requirements tied to action execution
- global prohibitions such as write-on-read, implicit scope reuse, and cross-tenant access

ARC does not define feature-specific behavior and does not own domain truth.

### DOM: Owned Truth

DOM defines bounded modules and the truth each module owns.

Each domain:

- owns its authoritative state
- defines domain queries for reading that state
- defines capability checks for actions governed by that state
- defines domain commands for permitted mutations

Domains MUST NOT:

- mutate another domain directly
- assume global or unscoped state
- delegate their truth to the feature layer

### FEAT: Action Orchestration

FEAT defines how a specific user-facing action is carried out.

FEAT is responsible for:

- constructing the user-facing action flow
- invoking capability checks in sequence
- stopping at the first failed check
- invoking the allowed domain command path
- returning the resulting response

FEAT MUST NOT:

- invent new business rules outside domain capability and command contracts
- recompute domain-owned truth independently
- perform direct mutation outside the owning domain command
- bypass ARC sequencing rules for convenience

## VIII. Allowed Interaction Rules

The following interaction model is mandatory:

1. FEAT constructs or receives request context under ARC rules.
2. FEAT invokes one or more DOM-owned capability checks.
3. Capability checks evaluate only explicit request-scoped context.
4. FEAT resolves the first deny result or proceeds if all required checks pass.
5. FEAT invokes the single allowed DOM command path.
6. DOM performs owned mutation only within its own boundary.
7. FEAT returns the response.

Cross-domain behavior is allowed only through evaluation and orchestration, never
through direct mutation by one domain into another.

## IX. Prohibited Structural Patterns

The following patterns are forbidden:

- GET handlers that commit, flush, or trigger domain mutation
- route handlers that embed authorization as ad hoc inline conditionals
- feature code that recomputes domain-owned state as execution truth
- unscoped or teacher-global decisions where class scope is required
- domain code that mutates another domain's state directly
- request handling that reads or writes across multiple tenant boundaries
- implicit reuse of prior request context
- capability checks with side effects
- architecture documents that preserve invalid boundaries for backward compatibility

## X. Architectural Consequences For The Repo

The application must be organized and evaluated as follows:

- ARC documents define the legal execution and interaction model.
- DOM documents define the bounded modules and the state each one owns.
- FEAT documents define concrete user actions by composing ARC-compliant capability
  evaluation with DOM-owned commands.

If code or lower-tier documents blur these roles, the code or documents are wrong, not
the architecture.

Current repository shape may inform rewrite sequencing, but it does not authorize mixed
responsibility patterns to remain part of the target design.

## XI. Subdivisions

The `ARCHITECTURE` namespace remains the cross-domain namespace for runtime interaction
rules.

Its current subdivisions are:

- `OPERATIONS/` for execution, runtime, data, and operational architecture
- `IDENTITY/` for actor identity and authority-boundary architecture
- `SYSADMIN/` for platform-level administrative architecture

These subdivisions must remain subordinate to the execution model and layer boundaries
defined in this document.

## XII. Success Criteria

The architecture layer is coherent only when all of the following are true:

- every action can be explained as request context plus capability evaluation plus
  command execution
- ARC documents define interaction rules without owning domain truth
- DOM documents define owned truth without bypassing ARC
- FEAT documents define specific actions without becoming the source of authority
- the architecture can drive a structural rebuild of the application without relying on
  backward-compatibility exceptions

## XIII. Amendment

Revisions to this document require explicit architectural deliberation, a version
increment, an updated Effective Date, and continued consistency with the locked INV
authority and execution model documents named above.

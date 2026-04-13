# ARC-CORE-000 — Execution Model

| Reference Number | Version|Effective Date | Supersedes|Authority Level |
|------|------|-----|-----|----|
| ARC-CORE-000 | 1.0|2026-4-12 |N/A |Constitutional |


---

## I. Purpose

This document defines the canonical execution model for Classroom Token Hub (CTH).

Architecture (ARC) governs **how decisions are made and executed**, not **what decisions are correct**.

All architectural rules in this document are **direct descendants of invariants** and exist to enforce invariant compliance at runtime.

---

## II. Scope

This specification applies to all runtime execution paths including:

- HTTP request handling
- Capability evaluation
- Domain command execution
- Cross-domain interaction
- Logging and observability

This specification is binding for:
- FEAT (Feature Layer)
- DOM (Domain Layer)

---

## III. Core Execution Model

Every request MUST follow this sequence:

1. Construct RequestContext (ARC)
2. Evaluate capabilities (ARC + DOM)
3. Resolve allow/deny decision (ARC)
4. Execute a single domain command if allowed (DOM)
5. Return response (FEAT)

No deviation from this sequence is permitted.

---

## IV. Derived Architectural Rules

### ARC-001 — Scoped Request Context
**Derived from:** INV-CORE-000 (join_code isolation)

All requests MUST construct a RequestContext that includes:
- class_id
- join_code
- actor_id
- actor_type
- request_id
- timestamp

Requests missing required scope MUST fail immediately.

---

### ARC-002 — No Implicit Global Access
**Derived from:** INV-CORE-000

No domain or feature logic may access global or unscoped data.

All data access MUST be explicitly scoped using join_code or class_id.

---

### ARC-003 — Scoped Capability Evaluation
**Derived from:** INV-CORE-000

All capability checks MUST accept explicit context.

Capability evaluation without join_code is invalid.

---

### ARC-004 — Cross-Tenant Isolation
**Derived from:** INV-CORE-000

A single request MUST NOT:
- read across multiple join_codes
- write across multiple join_codes

All execution is constrained to a single tenant boundary.

---

### ARC-005 — No PII Leakage in Execution Layer
**Derived from:** INV-CORE-000 (Minimal PII)

RequestContext and logs MUST NOT contain sensitive personal information beyond allowed invariant-defined fields.

---

### ARC-006 — Command Boundary for Mutation
**Derived from:** INV-CORE-000 (Deterministic financial logic)

All state mutation MUST occur inside explicit domain commands.

Mutation during:
- capability evaluation
- query execution
- request rendering

is strictly forbidden.

---

### ARC-007 — GET Must Be Pure
**Derived from:** INV-CORE-000 (Determinism)

GET requests MUST be side-effect free.

GET requests MUST NOT:
- commit
- flush
- trigger domain mutations

---

### ARC-008 — Domain Authority for State
**Derived from:** INV-CORE-000

Only domain queries may define authoritative state.

Feature layer MUST NOT recompute domain values.

---

### ARC-009 — Capability-Based Authorization
**Derived from:** INV-CORE-001 (Authority Model)

No action may execute without capability evaluation.

Authorization MUST be expressed as:

can_<action>(actor, context)

Inline conditional authorization is forbidden.

---

### ARC-010 — Explicit Context Switching
**Derived from:** INV-CORE-001

All context changes MUST be explicit.

Implicit reuse of prior request state is forbidden.

---

### ARC-011 — No Phantom Scope Access
**Derived from:** INV-CORE-000 (Tenant lifecycle)

Requests referencing non-existent join_code MUST fail.

No fallback or recovery logic is permitted.

---

### ARC-012 — Hard Deletion Enforcement
**Derived from:** INV-CORE-000

Deleted scope MUST NOT be referenced by:
- requests
- background jobs
- domain operations

---

### ARC-013 — Membership by Existence
**Derived from:** INV-CORE-000

Membership MUST be determined by existence of valid seat association.

State-based membership flags are forbidden.

---

### ARC-014 — No Label-Based Logic
**Derived from:** INV-CORE-000

Execution MUST NOT depend on:
- labels
- sections
- periods

Only canonical identifiers (class_id, join_code) may be used.

---

## V. Execution Constraints

### V.1 Capability Evaluation

- Capability checks MUST be side-effect free
- Capability checks MUST use explicit context only
- Capability checks MUST be evaluated at request time

### V.2 Command Execution

- Only one command path per request is allowed
- Commands MUST be idempotent where applicable
- Commands MUST own all mutation logic

### V.3 Cross-Domain Interaction

- Domains MUST NOT directly mutate other domains
- Cross-domain effects MUST be expressed via commands

---

## VI. Observability Requirements

All decisions MUST be logged with:

- request_id
- action
- capability
- domain
- allowed (true/false)
- reason (if denied)
- join_code
- actor_id

---

## VII. Enforcement

The following MUST be enforced via CI and runtime guards:

- No database commits in GET routes
- No usage of unscoped balance properties
- Capability checks precede command execution
- No cross-domain mutation

---

## VIII. Final Statement

> Architecture defines how decisions are made, not what decisions are correct.
> 
> Domains declare truth. Architecture governs interaction. Capabilities evaluate authority. Features execute decisions.

---
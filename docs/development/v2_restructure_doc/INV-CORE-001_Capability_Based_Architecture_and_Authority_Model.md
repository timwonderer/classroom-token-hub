# INV-CORE-001 — Capability-Based Architecture and Authority Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-CORE-001     | 1.0     | 2026-04-12     | N/A| Foundational    |

---

## 1. Purpose

This document is the sole authority defining the core architectural invariant for CTH v2:

> All actions are governed by capability checks evaluated at request time, under a strict authority hierarchy.

This invariant establishes how all domains interact and how system behavior is enforced.

---

## 2. Foundational Principle

CTH does not grant actions by default.

> An action is permitted only if the required capability is proven in context.

---

## 3. Authority Hierarchy

### 3.0 Authority Governance Model

CTH defines explicit authority levels for all documents and rules:

- **Foundational (INV)** — Highest authority. Non-negotiable system truths.
- **Constitutional (ARC)** — Governs how systems interact and enforce invariants.
- **Domain (DOM)** — Defines rules within a bounded system.
- **Implementation (FEAT)** — Executes behavior via routes, UI, and endpoints.

Conflict Resolution:
- INV overrides all levels
- ARC must not violate INV
- DOM must conform to ARC and INV
- FEAT must conform to all above levels

This hierarchy is absolute and must be preserved in all system design and implementation.

### 3.1 INVARIANT (INV) SPECIFICATIONS

INV-level specifications MUST be interpreted as absolute and final because they define the fundamental invariants that Classroom Token Hub is built on.

All other authority levels MUST derive their respective authorities from INV-level specifications and MUST NOT contradict or constrain INV-level requirements.

Reference Documents:

- [INV-CORE-000 CORE INVARIANTS OF CLASSROOM TOKEN HUB](/docs/INV-CORE-000_Core_Invariants.md)
- [INV-CORE-002 CAPABILITIES BASED ARCHITECTURE AND AUTHORITY MODEL](/docs/INV-CORE-002_Capability_Based_Architecture_and_Authority_Model.md)

---

### 3.2 ARCHITECTURE (ARC) SPECIFICATIONS

ARC-level specifications define how INV-level specifications are implemented within Classroom Token Hub. Each ARC-level specification MUST be a direct descendant of a specific invariant and govern a generalized behavior within the application that affects either cross-domain behavior or interactions between domains.

ARC-level specification MUST meet the following criteria:
- Must be a generalized (abstracted) behavior not bound to a specific feature
- Must be directly connected to an invariant
- Must directly impact behaviors across multiple domains
- Must not contradict INV-level specifications

Core rule:
- All actions must pass capability checks
- No domain may directly enforce behavior in another domain
- State must be evaluated at request time

---

### 3.3 DOM — Domain Authorities

Domains own truth and expose capability checks.

Examples:
- Rent → obligation state
- Banking → balance state
- Store → inventory state

Domains:
- MUST NOT directly modify the state of another domain under any circumstance
- MUST NOT assume global state

---

### 3.4 FEAT — Execution Layer

Implements user-facing actions.

Responsibilities:
- orchestrate capability checks
- enforce allow/deny decisions
- compose cross-domain decisions only through capability evaluation
- MUST NOT introduce independent business logic outside capability orchestration

---

## 4. Capability Contract

All capability checks must follow the structure:

```
allowed, reason = can_<action>(student_id, context)
```

Requirements:
- Deterministic
- Context-scoped
- Explainable (must return reason when denied)

### 4.1 Capability Composition

Multiple capability checks MAY be composed at the FEAT layer.

Rules:
- Checks are evaluated sequentially
- The first failing check SHALL determine denial
- The associated reason SHALL be returned to the caller

### 4.2 Capability Ownership and Constraints

Capability checks are authoritative evaluations, not convenience helpers.

Requirements:
- Capability checks MUST be defined within the domain that owns the underlying state being evaluated
- Capability checks MUST be side-effect free
- Capability checks MUST evaluate only context that is explicit and request-scoped
- Capability checks MUST NOT rely on implicit global state, cached authorization state, or prior request outcomes

Context Requirements:
- Context MUST be self-contained
- Context MUST include the class scope anchor (`class_id` and/or `join_code`) when class-scoped behavior is evaluated
- Context MUST include any temporal or domain identifiers required to evaluate the action correctly at request time

Revalidation Rule:
- Capability decisions MUST be evaluated at request time against current authoritative state
- No capability decision may be reused across requests unless it is explicitly revalidated against current domain state

---

## 5. Execution Model

```
Action (FEAT)
    ↓
Capability Checks (ARC)
    ↓
Domain Responses (DOM)
    ↓
Allow / Deny (must not violate INV)
```

---

## 6. Prohibited Patterns

The following are strictly forbidden:

- Cross-domain mutation (e.g., Rent directly modifying Store)
- Implicit side effects across domains
- Recomputed state without domain authority
- Capability decisions made outside request context
- Capability checks with side effects

---

## 7. System Implications

- All behavior must be explainable through capability checks
- All cross-domain interactions must occur through queries, not commands
- System correctness is enforced at action time, not precomputed

---

## 8. Success Criteria

- Every action can be traced to a capability decision
- No domain owns behavior outside its boundary
- No hidden coupling exists between domains

---

## 9. Governance Model

- INV / ARC / DOM / FEAT define and legislate system behavior
- The application executes actions by evaluating capability checks at request time
- CI pipeline and tests act as judicial enforcement, ensuring invariants are upheld and violations are rejected

---

## 10. Final Statement

> Domains declare truth. Architecture governs interaction. Capabilities evaluate authority. Features execute decisions.

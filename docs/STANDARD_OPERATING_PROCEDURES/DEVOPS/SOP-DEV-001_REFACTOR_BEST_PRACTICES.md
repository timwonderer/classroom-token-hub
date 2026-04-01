# SOP-DEV-001: Refactor Best Practices

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEV-001      | 1.0     | 2026-03-31     | N/A        | Normative       |

---

## I. Purpose

Define the required execution order for system-wide refactors to prevent inconsistent intermediate states, duplicated logic, and invalid system configurations.

---

## II. Scope

This SOP applies to:

- All system-wide refactors
- All architectural restructuring efforts
- All cross-domain changes affecting identity, scoping, enforcement, or interfaces

This SOP governs development sequencing and does not define system invariants or architecture.

---

## III. Authority Level

Normative. Subordinate to:

- INV-CORE-000 (Foundational Invariants)
- INV-CORE-001 (Authority Model)
- SOP-DOC-000 (Documentation Standard)

---

## IV. Dependencies

- INV-CORE-000_Core_Invariants.md  
- INV-CORE-001_Authority_Model.md  
- SOP-DOC-000_Writing_Specification.md  

---

## V. Refactor Execution Order

All major refactors MUST follow this order:

### 1. Identity

- Authoritative identifiers MUST be explicitly defined
- Entity lifecycle MUST be deterministic and enforceable
- Identity MUST NOT be nullable unless explicitly required
- Identity MUST NOT be inferred implicitly

---

### 2. Scope

- All data access and operations MUST use a single authoritative scoping model
- Mixed scoping strategies are prohibited
- Implicit or fallback scoping is prohibited
- Scope MUST NOT be derived indirectly from unrelated entities

---

### 3. Enforcement

- Constraints MUST be enforced at the system level (e.g., database constraints, schema rules)
- Invalid states MUST NOT be representable
- Access control MUST rely on guarantees, not conditional assumptions
- Application-only enforcement without structural backing is prohibited

---

### 4. Interface

- Routes, APIs, and UI logic MUST reflect system design
- Interfaces MUST NOT compensate for missing invariants
- Business rules MUST NOT be duplicated across interface layers

---

## VI. Stage Gate Requirements

Progression to the next stage is prohibited if any condition below is true:

### 1. Identity Stage Incomplete

- Identity remains nullable where not explicitly required
- Identity is inferred instead of required
- Entity lifecycle is ambiguous or inconsistently enforced

---

### 2. Scope Stage Incomplete

- Multiple scoping strategies coexist
- Scope is derived indirectly
- Fallback or implicit scoping logic exists

---

### 3. Enforcement Stage Incomplete

- Constraints exist only at the application layer
- Invalid states remain representable
- Access control depends on conditional logic

---

### 4. Interface Stage Premature

- Interfaces contain compensating logic for missing guarantees
- Interfaces attempt to correct underlying system design issues
- Business logic is duplicated across interface layers

---

## VII. Prohibited Patterns

The following are prohibited:

- Refactoring interfaces to resolve underlying system design issues
- Implementing enforcement prior to identity and scope stabilization
- Maintaining inferred or fallback identity paths
- Retaining temporary compatibility logic without defined removal
- Mixing multiple scoping models within a single domain
- Implementing logic dependent on assumptions instead of enforced guarantees

---

## VIII. Guiding Principle

The following order is mandatory:

Identity → Scope → Enforcement → Interface

---

## IX. Amendment

Revisions to this document MUST:

1. Increment the version number per SOP-DOC-000
2. Update the Effective Date
3. Update the Supersedes field
4. Maintain consistency with INV-CORE-000 and INV-CORE-001
# Division Definitions of Classroom Token Hub

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|------------------|
| SOP-DOC-003     | 1.0     | 2026-03-01     | N/A        | Normative        |

---

## I. Purpose

This document defines the structural boundaries and intended scope of each documentation division within Classroom Token Hub.

It governs how documents are classified and where they reside within the repository.

This document does not define system identity or architectural invariants. All authority derives from INV-CORE-000 (Foundational Invariants) and INV-CORE-001 (Authority Model).

---

## II. Scope

This division model applies to:

- All documentation artifacts
- All future document creation
- All document refactoring efforts
- All namespace placement decisions

---

## III. Division Definitions

### 1. ARCHITECTURE (ARC)

#### Purpose
Defines structural mechanisms that enforce Foundational invariants across the entire system.

#### Contains
- Cross-cutting system design
- Identity model
- Authorization architecture
- Ledger structure
- Isolation model (e.g., `join_code` scoping)
- System-wide lifecycle constraints
- Data model constraints spanning domains

#### Does Not Contain
- Operational procedures
- Feature walkthroughs
- Historical reports
- UI descriptions

#### Authority Level
Constitutional (Derived)

#### Boundary Rule
If altering this document would affect multiple domains simultaneously or compromise enforcement of a Foundational invariant, it belongs in ARC.

ARC defines system physics.

---

### 2. DOMAIN (DOM)

#### Purpose
Defines bounded business contexts and their internal rules.

#### Contains
- Domain vocabulary
- Domain entities
- State transitions
- Domain-local constraints
- Logical grouping of related behaviors

Examples include: RENT, BANK, PAY, INSURANCE, STORE, STUDENT.

#### Does Not Contain
- Cross-cutting enforcement logic
- Operational procedures
- Historical notes

#### Authority Level
Constitutional (Derived)

#### Boundary Rule
If it applies only within a specific business context and does not constrain the entire system, it belongs in DOM.

DOM defines ecosystems inside system physics.

---

### 3. FEATURE (FEAT)

#### Purpose
Defines user-experienced workflows and concrete implementations of domain capabilities.

#### Contains
- Route groupings
- Interaction flows
- State machine implementations
- Acceptance criteria
- UX-visible behaviors
- Automation tied to domain events

#### Does Not Contain
- Core identity principles
- Domain vocabulary definitions
- Operational procedures

#### Authority Level
Normative (Scoped Implementation)

#### Boundary Rule
If it describes how a user or system actor interacts with a domain rule, it belongs in FEAT.

FEAT implements domain capability.

---

### 4. STANDARD OPERATING PROCEDURE (SOP)

#### Purpose
Defines required operational and governance behavior for maintaining the system.

#### Contains
- Deployment procedures
- Rollback procedures
- Migration workflows
- Backup policy
- CI/CD process
- Versioning policy
- Documentation governance

#### Does Not Contain
- System identity
- Structural invariants
- Domain logic definitions
- Historical reports

#### Authority Level
Normative (Operational Governance)

#### Boundary Rule
If it prescribes required actions for maintainers or operators, it belongs in SOP.

SOP governs how the system is operated.

---

### 5. SECURITY (SEC)

#### Purpose
Defines protection mechanisms and audit records ensuring compliance with Foundational invariants.

#### Contains

**Security Architecture (Constitutional, Derived)**
- Threat models
- Authorization enforcement
- Isolation verification
- PII handling enforcement

**Security Records (Informative)**
- Audit reports
- Incident reports
- Risk assessments
- Remediation summaries

#### Does Not Contain
- Domain feature descriptions
- Operational deployment steps

#### Authority Level
Mixed:
- Security Architecture → Constitutional (Derived)
- Security Records → Informative

#### Boundary Rule
If the document defines how invariants are protected, it belongs here. If it records a past security event, it also belongs here.

SEC protects and verifies.

---

### 6. LOGS (LOG)

#### Purpose
Preserves institutional memory and system history.

#### Contains
- Release notes
- Milestones
- Postmortems
- Historical change logs
- Archived summaries

#### Does Not Contain
- Policy
- Enforcement rules
- Operational instructions

#### Authority Level
Informative

#### Boundary Rule
If it describes what happened rather than what must happen, it belongs in LOG.

LOG preserves institutional memory.

---

## IV. Division Relationship Model

Authority flows downward as defined in INV-CORE-001:

Foundational (INV-CORE)
↓
Constitutional (ARC / DOM / SEC-Architecture)
↓
Normative (FEAT / SOP)
↓
Informative (LOG / SEC-Records)

Higher authority levels constrain all lower levels. Lower levels may not redefine or override higher levels.


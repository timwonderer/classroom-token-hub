# Documentation Taxonomy and Namespace

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-001      | 1.0     | 2026-02-28 | N/A        | Constitutional            |

---

## I. Purpose

This document defines the official top-level documentation divisions and their functional sub-divisions for the Classroom Token Hub repository.

---

## II. Top-Level Divisions

The repository documentation is organized into the following top-level namespaces:

- **SOP** — Standard Operating Procedures (human operational discipline)
- **ARC** — Application Architecture (system-level structural design)
- **DOM** — Domain Architecture (business-domain structure)
- **FEAT** — Feature Specifications (scoped functionality)
- **SEC** — Security Audit and Incident Documentation
- **LOG** — Milestone and Historical Records

Each document must belong to exactly one top-level namespace.

---

## III. Sub-Divisions by Namespace

### 1. SOP — Standard Operating Procedures
Defines human procedures outside of application runtime behavior.

Approved functional areas include:
- **DOC** — Documentation governance
- **REL** — Release procedures
- **DEP** — Deployment workflow
- **DB** — Backup and disaster recovery
- **CI** — CI/CD enforcement procedures
- **GIT** — Repository and branching discipline
- **MIG** — Migration execution procedures

---

### 2. ARC — Application Architecture
Defines cross-domain architectural principles and global system structure.

Approved functional areas include:
- **INV** — Core invariants (constitutional layer)
- **OPS** — Application-level operational constraints
- **ROLE** — Role and authority architecture
- **LIFE** — Tenant lifecycle architecture
- **APP** — Core application structure
- **SEC** — Application security architecture

---

### 3. DOM — Domain Architecture
Defines structural boundaries and core models within specific business domains.

Approved functional areas include:
- **BASE** — Foundational architecture and rules
- **PAY** — Payroll and attendance economics
- **BANK** — Banking and ledger system
- **RENT** — Rent system
- **INS** — Insurance system
- **STORE** — Store and redemption system
- **ATT** — Attendance logic
- **HALL** — Hall pass system
- **TIX** — Support and ticketing system
- **ANA** — Analytics

---

### 4. FEAT — Feature Specifications
Defines scoped functionality within a specific domain.

Feature documents must mirror existing DOM functional areas, plus BASE for foundations.

Example:
- FEAT-BANK-001 — Savings Interest Calculation
- FEAT-RENT-002 — Rent Waiver Flow

---

### 5. SEC — Security Documentation
Defines security audits, threat models, vulnerability assessments, and incident reports.

Approved functional areas include:
- **AUD** — Security audit framework
- **INC** — Incident reports
- **VUL** — Vulnerability assessments
- **THR** — Threat modeling
- **CONT** — Control and mitigation standards

SEC documents may mandate remediation actions but must not redefine architectural invariants.

---

### 6. LOG — Milestone and Historical Records
Defines descriptive, time-bound documentation.

Approved functional areas include:
- **BASE** — Foundational records strategy
- **REL** — Release logs
- **INC** — Incident timelines
- **MILE** — Milestone reports

LOG documents are descriptive only and hold no normative authority.

---

## IV. Naming Convention

All document identifiers must follow the format:

[Namespace]-[Functional Area]-[Numeric Identifier]

Rules:
- `000` is reserved for foundational or normative definition documents within a namespace.
- Subsequent numbers (`001`, `002`, etc.) represent derived or scoped documents.
- LOG documents may include dates in addition to numeric identifiers.
- Naming must reflect functional clarity and must not include informal descriptors.

---

## V. Authority Hierarchy

1. ARC-INV documents define constitutional-level constraints.
2. ARC and DOM documents define authoritative application structure.
3. FEAT documents must conform to ARC and DOM documents.
4. SOP documents govern human procedures and must not conflict with ARC or DOM documents.
5. SEC documents may mandate remediation actions but must remain consistent with ARC-INV-000.
6. LOG documents are descriptive and hold no normative authority.

In the event of conflict, ARC documents take precedence.
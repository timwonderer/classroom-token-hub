# Classroom Token Hub Documentation Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-000      | 2.0     | 2026-03-01     | N/A        | Constitutional  |

---

## I. Purpose

This document defines the taxonomy, structure, authority levels, and authoring standards for all documentation within the Classroom Token Hub repository.

---

## II. Scope

This specification applies to all normative and procedural documents maintained within the repository, including but not limited to:

- SOP (Standard Operating Procedure) documents
- ARC (Application Architecture) documents
- DOM (Domain Architecture) documents
- FEAT (Feature Specification) documents
- LOG (Milestone, Archive, or Historical Log) documents
- SEC (Security Audit and Incident) documents

---

## III. Documentation Taxonomy

The highest-level documentation divisions are as follows:

### Document Naming Convention

All document identifiers must follow the format:

[Purpose/Category] - [Functionality / Area of Concern] - [Specific Topic]

The numerical suffix must follow these rules:
- ###-000 is reserved for foundational, constitutional, or normative definition documents.
- Subsequent numbers (001, 002, etc.) represent derived or scoped documents within the same category.

Naming must reflect functional clarity and must not include narrative, dates (except for LOG documents), or informal descriptors.

### 1. SOP — Standard Operating Procedures
Defines human operational discipline and governance outside of application runtime behavior.
Examples include:
- Documentation standards
- Release procedures
- Deployment workflow
- Backup and disaster recovery

### 2. ARC — Application Architecture
Defines system-level invariants and core structural design of the application.
- ARC-INV-###: Core invariants (constitutional layer)
- ARC-OPS-###: Application-level operational constraints

### 3. DOM — Domain Architecture
Defines structural boundaries and core models within a specific domain of the application.
- Must derive from ARC documents
- Must not redefine invariants

### 4. FEAT — Feature Specifications
Defines scoped functionality within a domain.
- Must reference applicable ARC and DOM documents
- Must not redefine invariants or domain boundaries

### 5. LOG — Milestone and Historical Records
Descriptive and time-bound documentation including:
- Milestone reports
- Release notes
- Architectural evolution summaries
- Incident timelines

LOG documents are not normative and must not define rules.

### 6. SEC — Security Audit and Incident Documentation
Defines security audits, vulnerability assessments, and incident response documentation.
- May contain analysis and findings
- May define required remediation steps
- Must not redefine architectural invariants

---

## IV. Authoring Standards

All normative documents (ARC, DOM, FEAT, SOP) must include:

1. Purpose
2. Scope
3. Authority Level (if applicable)
4. Dependencies or Referenced Documents

Normative documents must:
- Avoid historical narrative or design storytelling
- Avoid duplication of invariant language
- Use precise and enforceable language ("must", "shall", "prohibited")
- Follow the established document naming convention defined in Section III.

Historical documents may include narrative but must not define rules.

---

## V. Authority Hierarchy

All documents must specify one of three Authority Levels in their metadata header:

1. **Constitutional**: Represents the highest level of authority. Other levels cannot violate Constitutional rules. Lower-level documents must reference the relevant Constitutional document when implementing logic. Includes Core Invariants and foundational rulebooks.
2. **Normative**: Represents the second level of authority. Defines rules, expectations, standards, and conventions. Must reference Constitutional documentation but cannot define constitutional-level behaviors. Includes Domain, Feature, Security, and SOP documents.
3. **Informative**: The lowest level of authority. Describes, presents, and records events, guides, and other information that does not define how the application operates. Includes Milestone, Archive, and Historical Log documents.

**Resolution of Conflict**:
1. Constitutional documents supersede Normative documents.
2. ARC and DOM documents define authoritative application structure.
3. FEAT documents must conform to ARC and DOM documents.
4. SOP documents govern human procedures and must not conflict with ARC or DOM documents.
5. SEC documents may mandate remediation actions but must remain consistent with ARC-INV-000.
6. Informative LOG documents hold no normative authority.

---

## VI. Versioning

- Major version increments indicate structural change.
- Minor version increments indicate clarification or non-breaking updates.
- Effective Date must be updated upon approval of revisions.

---

## VII. Amendment

Revisions to this document must:
- Increment version number
- Document summary of changes
- Maintain consistency with ARC-INV-000
# SOP-DOC-000: Documentation Standard

| Reference Number | Version | Effective Date | Supersedes                        | Authoritative |
|------------------|---------|----------------|-----------------------------------|---------------|
| SOP-DOC-000      | 2.0     | 2026-03-02     | SOP-DOC-000 v1.0, SOP-DOC-001 v1.0 | YES           |

---

## I. Purpose

This document defines the complete documentation standard for the Classroom Token Hub repository, encompassing document tier classification, namespace taxonomy, sub-division structure, naming conventions, authoring standards, authority hierarchy, versioning, and amendment procedures.

---

## II. Scope

This standard applies to all documents maintained within the repository, including:

- Constitutional, architectural, domain, and feature specification documents
- Standard operating procedure documents
- Security audit, control, and incident documents
- Historical and milestone log documents
- User-facing guides
- AI agent operational rules (`.claude/rules/`)
- Root-level contributor files

---

## III. Authority Level

Normative (SOP Tier). Subordinate to ARC-INV-000.

---

## IV. Dependencies

- ARC-INV-000: Core Invariants

---

## V. Document Tier Classification

All repository documents are classified into one of three tiers based on their normative authority.

### Tier 1 — Constitutional

**Definition:** Inviolable system invariants. No other document may contradict or override a Constitutional document. Changes require explicit architectural deliberation.

**Language:** Must use "shall" and "prohibited" exclusively for constraints.

**Applies to:**
- `ARC-INV-*`

---

### Tier 2 — Normative

**Definition:** Binding rules that must be followed. All implementations and procedures must conform. Must not conflict with Constitutional documents.

**Language:** Must use "must", "shall", "required", "prohibited".

**Applies to:**
- `ARC-OPS-*`, `ARC-ROLE-*`, `ARC-LIFE-*`, `ARC-APP-*`, `ARC-SEC-*` — structural architecture
- `DOM-*` — domain architecture
- `FEAT-*` — feature specifications
- `SOP-*` — standard operating procedures
- `.claude/rules/*` — AI agent operational rules
- `SEC-CONT-*` — security control standards

---

### Tier 3 — Informative

**Definition:** Descriptive or reference content. Must not define new rules or restate invariants. Informative documents describe, explain, instruct, or record.

**Language:** May use advisory language ("should", "recommended"). Must not use binding language.

**Applies to:**
- `LOG-*` — historical records and milestone reports
- `SEC-AUD-*`, `SEC-INC-*`, `SEC-VUL-*`, `SEC-THR-*` — audit findings, incidents, vulnerability reports
- `docs/user-guides/*` — user-facing instructional content
- Root-level files: `README.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, `PROJECT_HISTORY.md`, `CONTRIBUTING.md`

---

### Conflict Resolution

In the event of conflict between documents:

1. Constitutional (Tier 1) takes precedence over all.
2. Normative (Tier 2) takes precedence over Informative (Tier 3).
3. Within Tier 2: ARC supersedes DOM, DOM supersedes FEAT, FEAT supersedes SOP.

---

## VI. Documentation Namespaces

The repository documentation is organized into the following top-level namespaces. Each document must belong to exactly one namespace.

| Namespace        | Tier                              | Purpose                                           |
|------------------|-----------------------------------|---------------------------------------------------|
| ARC              | Constitutional (INV) / Normative  | Cross-domain architectural principles and invariants |
| DOM              | Normative                         | Domain boundaries and core business models        |
| FEAT             | Normative                         | Scoped functionality within a domain              |
| SOP              | Normative                         | Human operational procedures and governance       |
| SEC              | Normative (CONT) / Informative    | Security audits, controls, and incident records   |
| LOG              | Informative                       | Historical records, milestones, release logs      |

Non-namespace locations:

| Location          | Tier        | Purpose                                      |
|-------------------|-------------|----------------------------------------------|
| `.claude/rules/`  | Normative   | AI agent operational rules                   |
| `docs/user-guides/` | Informative | User-facing instructional content            |
| Root files        | Informative | Project orientation and contributor reference |

---

## VII. Namespace Sub-Divisions

### ARC — Application Architecture

Defines cross-domain architectural principles and global system structure.

Approved functional areas:

- **INV** — Core invariants (Constitutional tier)
- **OPS** — Application-level operational constraints
- **ROLE** — Role and authority architecture
- **LIFE** — Tenant lifecycle architecture
- **APP** — Core application structure
- **SEC** — Application security architecture

---

### DOM — Domain Architecture

Defines structural boundaries and core models within specific business domains. Must derive from ARC documents and must not redefine invariants.

Approved functional areas:

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

### FEAT — Feature Specifications

Defines scoped functionality within a specific domain. Must reference applicable ARC and DOM documents and must not redefine invariants or domain boundaries.

Feature documents must mirror existing DOM functional areas, plus BASE for foundations.

Examples:
- `FEAT-BANK-001` — Savings Interest Calculation
- `FEAT-RENT-002` — Rent Waiver Flow

---

### SOP — Standard Operating Procedures

Defines human procedures outside of application runtime behavior. Must not conflict with ARC or DOM documents.

Approved functional areas:

- **DOC** — Documentation governance
- **REL** — Release procedures
- **DEP** — Deployment workflow
- **DB** — Database and migration procedures
- **CI** — CI/CD enforcement procedures
- **GIT** — Repository and branching discipline
- **MIG** — Migration execution procedures

---

### SEC — Security Documentation

Defines security audits, threat models, vulnerability assessments, incident reports, and control standards.

Approved functional areas:

| Sub-Division | Tier        | Purpose                            |
|--------------|-------------|------------------------------------|
| **AUD**      | Informative | Security audit framework and reports |
| **INC**      | Informative | Incident reports and timelines     |
| **VUL**      | Informative | Vulnerability assessments          |
| **THR**      | Informative | Threat modeling                    |
| **CONT**     | Normative   | Control and mitigation standards   |

`SEC-CONT` documents are Normative and may mandate remediation actions. All other SEC sub-divisions are Informative and must not redefine architectural invariants.

---

### LOG — Milestone and Historical Records

Descriptive and time-bound documentation. LOG documents are Informative and must not define rules.

Approved functional areas:

- **BASE** — Foundational records strategy
- **REL** — Release logs
- **INC** — Incident timelines
- **MILE** — Milestone reports

---

## VIII. Naming Convention

All document identifiers must follow the format:

```
[NAMESPACE]-[FUNCTIONAL-AREA]-[NUMERIC-IDENTIFIER]_[Descriptive_Title].md
```

Rules:

- `000` is reserved for foundational or normative definition documents within a namespace-area.
- Subsequent numbers (`001`, `002`, ...) represent derived or scoped documents.
- LOG documents may include dates in addition to numeric identifiers.
- Naming must reflect functional clarity and must not include informal descriptors, narrative, or dates (except LOG documents).

---

## IX. Authoring Standards

### Frontmatter Table

All formally tracked documents must include a frontmatter table immediately after the document title:

```markdown
| Reference Number | Version | Effective Date | Supersedes       | Authoritative |
|------------------|---------|----------------|------------------|---------------|
| [REF]            | [X.Y]   | [YYYY-MM-DD]   | [N/A or prev ref] | YES / NO     |
```

The `Authoritative` field must reflect the document's tier:
- `YES` = Constitutional or Normative
- `NO` = Informative

### Required Sections for Normative Documents

All normative documents (ARC, DOM, FEAT, SOP, SEC-CONT) must include the following sections in this order:

1. **I. Purpose** — Single paragraph statement of the document's purpose
2. **II. Scope** — What this document governs and where it applies
3. **III. Authority Level** — Tier classification and what this document is subordinate to
4. **IV. Dependencies** — Documents this document directly derives from or requires
5. **[V+] Content Sections** — Document-specific normative content
6. **[Last] Amendment** — Procedure for revising this document

Informative documents (LOG, SEC-AUD/INC/VUL/THR, user-guides, root files) do not require this structure.

### Section Numbering

All formal sections must use Roman numerals at the top level (I, II, III...). Subsections use Arabic numerals (1, 2, 3...) or letters.

### Language Standards

Normative documents must:

- Use precise and enforceable language: "must", "shall", "required", "prohibited"
- Avoid narrative, historical storytelling, or design rationale
- Avoid duplicating invariant language from ARC-INV-000
- Avoid redundancy with other normative documents

Informative documents:

- May use advisory language: "should", "recommended", "typically"
- May include narrative and contextual explanation
- Must not define binding rules or restate Constitutional constraints

---

## X. Authority Hierarchy

The following precedence order applies in the event of conflict:

1. **Constitutional** — ARC-INV documents define inviolable constraints.
2. **Normative (Structural)** — ARC and DOM documents define authoritative application structure.
3. **Normative (Feature)** — FEAT documents must conform to ARC and DOM documents.
4. **Normative (Procedural)** — SOP and `.claude/rules/` documents govern human and agent procedures; must not conflict with ARC or DOM documents.
5. **Normative (Security Controls)** — SEC-CONT documents may mandate remediation actions; must remain consistent with ARC-INV-000.
6. **Informative** — LOG, SEC audit/incident/vulnerability, user-guides, and root files are descriptive only and hold no normative authority.

---

## XI. Versioning

- Major version increments indicate structural changes to purpose, scope, tier classification, or authority.
- Minor version increments indicate clarification or non-breaking additions.
- Effective Date must be updated upon approval of all revisions.
- Supersedes field must reference the prior version or any superseded documents by reference number and version.

---

## XII. Amendment

Revisions to this document must:

1. Increment the version number per Section XI.
2. Update the Effective Date.
3. Populate the Supersedes field with the replaced version or document references.
4. Maintain consistency with ARC-INV-000.
5. Update SOP-DOC-002 to reflect any structural changes to the namespace or sub-division definitions.

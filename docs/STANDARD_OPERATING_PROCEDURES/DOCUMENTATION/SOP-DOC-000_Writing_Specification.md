# SOP-DOC-000: Documentation Standard

| Reference Number | Version | Effective Date | Supersedes | Authority Level  |
|------------------|---------|----------------|------------|------------------|
| SOP-DOC-000      | 2.0     | 2026-03-01     | N/A        | Constitutional   |

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

Foundational (Tier 0). This document establishes the rules by which all governance must abide, deriving its authority explicitly from INV-CORE-001 (Authority Model).

---

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `INV-CORE-001_Authority_Model.md`

---

## V. Document Tier Classification

All repository documents are classified into one of four tiers based on their normative authority, as defined by `INV-CORE-001`.

### Tier 0 — Foundational

**Definition:** Defines the identity, philosophy, and non-negotiable existence principles of the system. No lower authority document may override or redefine a Foundational invariant.
**Language:** Establishes core invariants. Cannot derive authority from lower levels.
**Applies to:**
- `INV-CORE-000`, `INV-CORE-001`, `SOP-DOC-000`

### Tier 1 — Constitutional

**Definition:** Defines structural enforcement mechanisms and cross-cutting constraints that operationalize Foundational invariants.
**Language:** Must use "shall" and "prohibited" exclusively for constraints. MUST cite relevant Foundational invariants.
**Applies to:**
- `ARCHITECTURE/` (ARC-*)
- `DOMAINS/` (DOM-*)
- `SECURITY/` (SEC-CONT, Security Architecture)

---

### Tier 2 — Normative

**Definition:** Defines required operational procedures and behavioral governance necessary to maintain compliance. Must not conflict with Constitutional documents.
**Language:** Must use "must", "shall", "required", "prohibited".
**Applies to:**
- `FEATURES/` (FEAT-*)
- `STANDARD_OPERATING_PROCEDURES/` (SOP-*)
- `.claude/rules/*` — AI agent operational rules

---

### Tier 3 — Informative

**Definition:** Records historical events, reports, audits, releases, and descriptive system information. Must not define new rules.
**Language:** May use advisory language ("should", "recommended"). Must not use binding language.
**Applies to:**
- `LOGS/` (LOG-*) — historical records and milestone reports
- `SECURITY/` (SEC-AUD/INC/VUL/THR) — audit findings, incidents, vulnerability reports
- `docs/user-guides/*` — user-facing instructional content
- Root-level files: `README.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, `PROJECT_HISTORY.md`, `CONTRIBUTING.md`

---

### Conflict Resolution

In the event of conflict between documents, `INV-CORE-001` Section V is the sole authority:
1. Foundational authority SHALL prevail.
2. Constitutional authority SHALL prevail over Normative and Informative.
3. Normative authority SHALL prevail over Informative.

---

## VI. Documentation Namespaces

The repository documentation is organized into six functional Divisions. For a complete definition of each Division, its purpose, its boundary rules, and what it may/may not contain, refer to `SOP-DOC-003_Division_Definition.md`.

| Division      | Tier Classification                 |
|---------------|-------------------------------------|
| ARCHITECTURE  | Constitutional (ARC)               |
| DOMAINS       | Constitutional (DOM)               |
| FEATURES      | Normative (FEAT)                   |
| SOP           | Normative (SOP)                    |
| SECURITY      | Mixed (Constitutional/Informative) |
| LOGS          | Informative                        |

Non-namespace locations:

| Location          | Tier        | Purpose                                      |
|-------------------|-------------|----------------------------------------------|
| `.claude/rules/`  | Normative   | AI agent operational rules                   |
| `docs/user-guides/` | Informative | User-facing instructional content            |
| Root files        | Informative | Project orientation and contributor reference |

---

## VII. Namespace Sub-Divisions

Subdivisions (e.g., `docs/ARCHITECTURE/OPERATIONS/`, `docs/DOMAINS/BANKING/`) are governed individually by the `CORE-000` document located at the root of their respective namespaces (e.g., `ARC-CORE-000`, `DOM-CORE-000`). Refer to the respective `CORE-000` documents for up-to-date subdivision structures.

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
| Reference Number | Version | Effective Date | Supersedes       | Authority Level                      |
|------------------|---------|----------------|------------------|--------------------------------------|
| [REF]            | [X.Y]   | [YYYY-MM-DD]   | [N/A or prev ref] | Foundational/Constitutional/Normative/Informative |
```

The `Authority Level` field must strictly match the assigned Tier of the document (Foundational, Constitutional, Normative, or Informative).

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

The following precedence order applies in the event of conflict, per `INV-CORE-001`:

1. `INV-CORE` and `SOP-DOC-000` define Foundational truth.
2. `ARC`, `DOM`, and Security Architecture define authoritative Constitutional rules.
3. `FEAT` and `SOP` define Normative implementation details and operational procedures.
4. `LOG` and `SEC` records are Informative descriptions.

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

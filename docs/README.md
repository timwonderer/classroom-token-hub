# Classroom Token Hub Documentation Index

This directory contains the canonical documentation for the Classroom Token Hub, organized by namespace per [SOP-DOC-000](development/v2_restructure_doc/SOP-DOC-000_DOCUMENTATION_STANDARD.md).

---

## Document Tier Classification

All documents are classified into one of three tiers. See [SOP-DOC-000 Section V](development/v2_restructure_doc/SOP-DOC-000_DOCUMENTATION_STANDARD.md) for full definitions.

| Tier               | Authority                              | Namespaces / Locations                        |
|--------------------|----------------------------------------|-----------------------------------------------|
| **Constitutional** | Inviolable — cannot be overridden      | `ARC-INV-*`                                   |
| **Normative**      | Binding — must be followed             | `ARC`, `DOM`, `FEAT`, `SOP`, `.claude/rules/`, `SEC-CONT-*` |
| **Informative**    | Descriptive — no normative authority   | `LOG`, `SEC-AUD/INC/VUL/THR-*`, `user-guides/`, root files |

---

## Documentation Namespaces

| Namespace | Tier | Purpose |
|-----------|------|---------|
| **[ARC](ARCHITECTURE/)** | Constitutional / Normative | Foundational invariants and operational constraints |
| **[SOP](STANDARD_OPERATING_PROCEDURES/)** | Normative | Standard operating procedures (documentation, releases, deployments, deployments, databases) |
| **[SEC](SECURITY/)** | Normative (CONT) / Informative | Security architecture, audits, controls, and incident records |
| **[DOM](DOMAINS/)** | Normative | Domain specifications *(pending user-guide migration)* |
| **[FEAT](FEATURES/)** | Normative | Feature specifications *(pending user-guide migration)* |
| **[LOG](LOGS/)** | Informative | Historical archives and release logs |
| **[user-guides/](user-guides/)** | Informative | User-facing documentation for teachers and students |

Non-namespace locations:

| Location | Tier | Purpose |
|----------|------|---------|
| `.claude/rules/` | Normative | AI agent operational rules |
| Root files | Informative | Project orientation and contributor reference |

---

## Quick Links

- **[Core Invariants](INV-CORE-000_CORE_INVARIANTS.md)** — Constitutional constraints (Tier 1)
- **[Schema Ownership Index](ARCHITECTURE/OPERATIONS/ARC-OPS-016_Schema_Ownership_Index.md)** — Thin table-to-domain ownership map
- **[Cross-Domain Data Relationships](ARCHITECTURE/OPERATIONS/ARC-OPS-017_Cross_Domain_Data_Relationships.md)** — Meaning of shared reference fields across domains
- **[Documentation Standard](development/v2_restructure_doc/SOP-DOC-000_DOCUMENTATION_STANDARD.md)** — Tier classification, taxonomy, naming, authoring rules
- **[Documentation Index](development/v2_restructure_doc/SOP-DOC-002_DOCUMENTATION_INDEX.md)** — Complete list of tracked documents
- **[Teacher Manual](user-guides/teacher_manual.md)** — User-facing teacher guide
- **[Student Guide](user-guides/student_guide.md)** — User-facing student guide

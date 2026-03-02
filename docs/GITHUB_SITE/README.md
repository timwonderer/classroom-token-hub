# Classroom Token Hub Documentation Index

This directory contains the canonical documentation for the Classroom Token Hub, organized by namespace per [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-000_Writing_Specification.md).

---

## Document Tier Classification

All documents are classified into one of three tiers. See [SOP-DOC-000 Section V](../STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-000_Writing_Specification.md) for full definitions.

| Tier               | Authority                              | Namespaces / Locations                        |
|--------------------|----------------------------------------|-----------------------------------------------|
| **Constitutional** | Inviolable — cannot be overridden      | `ARC-INV-*`                                   |
| **Normative**      | Binding — must be followed             | `ARC`, `DOM`, `FEAT`, `SOP`, `.claude/rules/`, `SEC-CONT-*` |
| **Informative**    | Descriptive — no normative authority   | `LOG`, `SEC-AUD/INC/VUL/THR-*`, `user-guides/`, root files |

---

## Documentation Namespaces

| Namespace | Tier | Purpose |
|-----------|------|---------|
| **[ARC](arc/)** | Constitutional / Normative | Foundational invariants and operational constraints |
| **[SOP](sop/)** | Normative | Standard operating procedures (documentation, releases, deployments, databases) |
| **[SEC](sec/)** | Normative (CONT) / Informative | Security architecture, audits, controls, and incident records |
| **[DOM](dom/)** | Normative | Domain specifications *(pending user-guide migration)* |
| **[FEAT](feat/)** | Normative | Feature specifications *(pending user-guide migration)* |
| **[LOG](log/)** | Informative | Historical archives and release logs |
| **[user-guides/](user-guides/)** | Informative | User-facing documentation for teachers and students |

Non-namespace locations:

| Location | Tier | Purpose |
|----------|------|---------|
| `.claude/rules/` | Normative | AI agent operational rules |
| Root files | Informative | Project orientation and contributor reference |

---

## Quick Links

- **[Core Invariants](../INV-CORE-000_Core_Invariants.md)** — Constitutional constraints (Tier 1)
- **[Documentation Standard](../STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-000_Writing_Specification.md)** — Tier classification, taxonomy, naming, authoring rules
- **[Documentation Index](../STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-002_Documentation_Index.md)** — Complete list of tracked documents
- **[Teacher Manual](../user-guides/teacher_manual.md)** — User-facing teacher guide
- **[Student Guide](../user-guides/student_guide.md)** — User-facing student guide

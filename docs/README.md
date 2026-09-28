# Classroom Token Hub — Documentation Index

This directory contains the canonical v2 documentation for the Classroom Token Hub, organized by namespace per [SOP-DOC-000](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md).

---

## Document Tier Classification

Every document belongs to one of four tiers. This table summarises
[SOP-DOC-000 §V](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md), which is
the authority; where they differ, SOP-DOC-000 wins.

| Tier | Authority | Namespaces / Locations |
|------|-----------|------------------------|
| **0 — Foundational** | Non-negotiable laws of the system | `INV-CORE-*` (`INVARIANT/CORE/`) |
| **1 — Constitutional** | Enforcement mechanisms and bounded domain rules | `INV-ARC-*` (`INVARIANT/ARCHITECTURE/`), `DOM-*` (`DOMAIN/`) |
| **2 — Normative** | Implementation flows, transactions, procedures | `FEAT-*`, `SOP-*`, `SPEC-*` (binding when incorporated by an INV, DOM or FEAT contract) |
| **3 — Informative** | Memory, rationale, plans, guides; defines no runtime rule | `MAP-*`, `PRN-*`, `user-guides/`, `archive/`, root files |

`REFERENCE/`, `TRACKING/`, `ops/` and `self-hosting/` are not assigned a tier by SOP-DOC-000.
They are descriptive: they summarise and can drift, and they are never cited as authority.

---

## Documentation Namespaces

### Governing (Tiers 0–2)

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[INVARIANT/](INVARIANT/)** | 0 and 1 | Core invariants (`INV-CORE`) and architecture invariants (`INV-ARC`) |
| **[DOMAIN/](DOMAIN/)** | 1 | Per-domain authority specs and contracts |
| **[FEATURE-EXECUTION/](FEATURE-EXECUTION/)** | 2 | FEAT contracts for all state mutations |
| **[SPEC/](SPEC/)** | 2 | Technical contracts |
| **[STANDARD_OPERATING_PROCEDURES/](STANDARD_OPERATING_PROCEDURES/)** | 2 | SOPs for database, deployment, devops, operations, security, testing, documentation |

### Informative and descriptive

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[MAP/](MAP/)** | 3 | Domain-to-FEAT capability maps and UI wiring maps |
| **[PRINCIPLES/](PRINCIPLES/)** | 3 | Why a design was chosen (security, privacy, SSO, project philosophy) |
| **[REFERENCE/](REFERENCE/)** | descriptive | Vocabulary and interface references (`REF-TERM-*`, `REF-API-001`, `REF-DES-001`) |
| **[user-guides/](user-guides/)** | 3 | Teacher and student help served by the in-app `/docs` site |
| **[self-hosting/](self-hosting/README.md)** | descriptive | Running your own instance |
| **[TRACKING/](TRACKING/)** | descriptive | The post-launch tracker and open decision packages |
| **[ops/](ops/)** | descriptive | Production host notes and dated release and audit records (`ops/audits/`) |
| **[archive/](archive/)** | 3 | Superseded material, kept for history only (see below) |

### Outside `docs/`

| Location | Purpose |
|----------|---------|
| Root files (`README.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `SECURITY.md`) | Project orientation, chronology, roadmap, contributor and security policy |
| `.claude/` | Operational guidance for AI agents. Never authoritative |
| `docs-site/` | Docusaurus workspace that publishes the developer tree to classroomtokenhub.com/docs |

---

## Quick Links

- **[Core Invariants](INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** — Canonical v2 core invariants
- **[Authority Model](INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** — Canonical capability-based authority hierarchy
- **[Domain Authority Summary](DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md)** — Per-domain authority overview
- **[Identity Reference Models](DOMAIN/DOM-IDEN-007_Identity_Models_and_References.md)** — Canonical identity reference ownership and lookup rules
- **[FEAT Constitutional Directive](FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md)** — FEAT execution rules
- **[Canonical Monetary Resolution](FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md)** — intended plan / resolved plan workflow before posting
- **[Canonical Temporal Resolver](SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md)** — normative build spec for SLE/CLE temporal authority, primitives, elapsed-duration evaluation, and browser display timezone
- **[Display Metadata Resolver](SPEC/SPEC-DISPLAY-001_DISPLAY_IDENTITY_METADATA_RESOLVER.md)** — normative build spec for display-only identity, class, and page-context metadata derived from canonical context
- **[Canonical Schema Definition](DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md)** — Runtime schema, table ownership, and structural constraints
- **[Canonical Domain Reconstruction Workflow](STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md)** — Repeatable truth-to-interface workflow for rebuilding domains and rewiring surfaces
- **[Template to FEAT Wiring Map](MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md)** — Template audit findings mapped to route, context, FEAT, domain, persistence, and read-model obligations
- **[Request Context and View Model Pipeline](MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md)** — Four-question request pipeline for authority, time, display metadata, and page view models
- **[Documentation Standard](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)** — Tier classification, taxonomy, naming, authoring rules
- **[Documentation Index](STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md)** — Complete list of tracked documents

---

## Archive

`archive/` holds superseded material. None of it is authority. Cite it only with a label that
says it is archived (SOP-DOC-000 §V, *Citing archived material*).

| Directory | Contents |
|-----------|----------|
| `archive/v1-architecture/` | Early v1 identity and core architectural specs |
| `archive/v1-development/` | v1→v2 migration planning and legacy schema analysis |
| `archive/v1-docs/` | v1 security audits, deployment SOPs, ARC-* specs, FEATURES/*, DOMAINS/* (~55 files) |
| `archive/PHASE_PLANNING/` | Phase 3–5 roadmaps, store domain implementation tracking, demolition and migration plans |
| `archive/STANDARD_OPERATING_PROCEDURES/` | Retired SOPs, at their original namespace paths |
| `archive/MAP/` | Retired maps (`MAP-CLASS-002`, archived 2026-09-28: its `class_id`-first target is now the current model) |
| `archive/v2-tracking-2026/` | v2 migration and launch tracking, including the pre-launch ship tracker (archived 2026-09-28); its README says why each file was archived |
| `archive/github-pages/` | Historical GitHub Pages landing site assets |

> [!NOTE]
> 
> Some of the documentation you are looking for may have been relocated. v1 namespace directories (`ARCHITECTURE/`, `FEATURES/`, `DOMAINS/`) archived — their content is covered by v2 namespaces (`INVARIANT/ARCHITECTURE/`, `FEATURE-EXECUTION/`, `DOMAIN/`). v2 docs previously misplaced in the archive were restored to canonical namespaces. Historic Phase 3-5 planning and store domain implementation logs (completed work) have been consolidated in `archive/PHASE_PLANNING/`.


> [!IMPORTANT] 
> 
> Cross-domain reference semantics (formerly ARC-OPS-017) is now covered by `INV-ARC-021`. Sysadmin interface does not require a standalone spec — it follows from DOM authority and FEAT contracts like other interfaces.

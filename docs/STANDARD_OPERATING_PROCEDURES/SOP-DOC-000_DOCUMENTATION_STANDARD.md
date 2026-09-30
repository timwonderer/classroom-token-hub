# SOP-DOC-000: Documentation Standard

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-000      | 3.4     | 2026-09-28     | SOP-DOC-000 v3.3 | Foundational |

---

## I. Purpose

This document defines the documentation standard for the Classroom Token Hub repository: the tier classification, the directory taxonomy, naming, authoring rules, the serving model, and link integrity. It covers the v2 documentation tree, current from the v2.0.0 release (2026-09-26).

---

## II. Scope

This standard governs all documentation in the repository, including core invariants, architectural specifications, domain definitions, feature execution files, standard operating procedures, user guides, and root repository files.

---

## III. Authority Level

Foundational (Tier 0). Subordinate only to `INV-CORE-000` and `INV-CORE-001`.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md`: the index of every registered document, maintained under this standard

---

## V. Document Tier Classification

All documents are classified into four tiers representing their normative authority:

### Tier 0 — Foundational
- **Definition**: Defines non-negotiable laws and identity of the system.
- **Location**: `docs/INVARIANT/CORE/`
- **Prefix**: `INV-CORE-*`

### Tier 1 — Constitutional
- **Definition**: Structural enforcement mechanisms and bounded domain rules that operationalize Tier 0 laws.
- **Location**: 
  - `docs/INVARIANT/ARCHITECTURE/` (Prefix: `INV-ARC-*`)
  - `docs/DOMAIN/` (Prefix: `DOM-*`)

### Tier 2 — Normative
- **Definition**: Governs concrete implementation flows, transactions, and operational standard procedures.
- **Location**: 
  - `docs/SPEC/` (Technical specifications)
  - `docs/FEATURE-EXECUTION/` (Prefix: `FEAT-*`)
  - `docs/STANDARD_OPERATING_PROCEDURES/` (Prefix: `SOP-*`)
  - `docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md` — the developer vocabulary. Specifications, code review and internal documentation MUST use its terms as defined

`SPEC` documents are technical contracts, not an independent runtime authority
namespace. Their requirements bind implementation only when incorporated by the
applicable `INV-*`, `DOM-*`, or `FEAT-*` contract. This classification does not
alter the `INV → DOM → FEAT` runtime hierarchy established by `INV-CORE-001`.

### Tier 3 — Informative
- **Definition**: Preserves institutional memory, timelines, target plans, releases, and user guides. Must not define runtime rules.
- **Location**:
  - `docs/MAP/` (Prefix: `MAP-*`)
  - `docs/PRINCIPLES/` (Prefix: `PRN-*`) — rationale documents explaining *why* a design was chosen
  - `docs/REFERENCE/` (Prefix: `REF-*`), except `REF-TERM-001`. `REF-TERM-002` (user-facing vocabulary) is highly recommended for standardization. Accessibility takes precedence over it: where a term would create an unnecessary barrier, INV-CORE-000 §III.7 and INV-ARC-020 govern the wording. `REF-API-001` and `REF-DES-001` are descriptive references
  - `docs/user-guides/` (User guides)
  - `docs/self-hosting/` — guidance for running an instance
  - `docs/TRACKING/` — the live tracker and open decision packages (working state)
  - `docs/ops/` — production host notes and dated release and audit records (`docs/ops/audits/`)
  - `docs/archive/` — superseded material, retained for history only: the v1 documentation (`v1-*`), v2 migration and launch tracking retired after release (`v2-tracking-2026/`, `PHASE_PLANNING/`), and retired numbered documents kept at their namespace paths (`STANDARD_OPERATING_PROCEDURES/`, `MAP/`)
  - Root directory files (`README.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `SECURITY.md`)

Agent guidance under `.claude/` is outside the tier system. It is never authoritative, and where it
conflicts with a document above, the `.claude/` text is corrected.

The `LOG-*` prefix and the `docs/LOGS/` tree were **removed on 2026-09-05**. Do not reintroduce
either; institutional memory belongs in `docs/PRINCIPLES/` (rationale) or `CHANGELOG.md`
(chronology).

### Citing archived material

A document under `docs/archive/` is superseded by definition. A live document MUST NOT cite one in a
**Dependencies** section, or link to one without labelling it as archived — an unlabelled link to
archived material is indistinguishable from a citation of current authority, which is the exact
confusion the archive exists to prevent. Where an archived document must be referenced, mark it
inline (e.g. *"(archived)"*) and state what supersedes it.

`CHANGELOG.md` is maintained for developers. It is **not** published to the in-app documentation
site and must not be mirrored into `docs/`; a mirrored copy drifts from the original silently.

---

## VI. Directory Taxonomy

The structure under `docs/` is:

1. **`INVARIANT/CORE/`**: Foundational invariants and system properties (Tier 0).
2. **`INVARIANT/ARCHITECTURE/`**: Architectural invariants, cross-domain safety boundaries, and gating rules (Tier 1).
3. **`DOMAIN/`**: Authoritative domain specifications defining vocabulary, schema authority, owned database tables, and capability checks (Tier 1).
4. **`FEATURE-EXECUTION/`**: Specs defining user interactions, FEAT orchestration, and transaction safety (Tier 2).
5. **`SPEC/`**: Technical contracts, binding when incorporated (Tier 2).
6. **`STANDARD_OPERATING_PROCEDURES/`**: Procedures by area: `DATABASE/`, `DEPLOYMENT/`, `DEVOPS/`, `OPERATIONS/`, `SECURITY/`, `TESTING/`, plus the documentation SOPs at its root (Tier 2).
7. **`MAP/`**: Capability and wiring maps (Tier 3).
8. **`PRINCIPLES/`**: Rationale documents (Tier 3).
9. **`REFERENCE/`**: Vocabulary and interface references. `REF-TERM-001` is Tier 2; the others are Tier 3 (see §V).
10. **`user-guides/`**: The in-app help centre (Tier 3; see §X).
11. **`self-hosting/`**: Instance setup guidance (Tier 3).
12. **`TRACKING/`**: The live tracker and open decision packages (Tier 3). A document that stops describing live work moves to `archive/v2-tracking-2026/`, with its reason recorded in that directory's README.
13. **`ops/`**: Production host notes; `ops/audits/` holds one dated record per release or audit (Tier 3).
14. **`assets/`**: Images used by the documents.
15. **`archive/`**: Superseded material (Tier 3; see §V, *Citing archived material*).

---

## VII. Naming Convention

All formal document identifiers must follow the format:

```
[NAMESPACE]-[FUNCTIONAL-AREA]-[NUMERIC-IDENTIFIER]_[Descriptive_Title].md
```

- `000` is reserved for namespace-area definitions or foundations (e.g. `DOM-CORE-000`).
- Subsequent numbers represent derived documents.
- Title must use snake_case or descriptive words separated by underscores.

---

## VIII. Authoring Guidelines

### Required Sections for Normative and Constitutional Documents

Formal specifications (INV, DOM, FEAT, SOP) must include the following sections in this exact order:

1. **I. Purpose** — Single paragraph explaining the document's goal.
2. **II. Scope** — Details on what is governed and where constraints apply.
3. **III. Authority Level** — Tier classification and subordination mappings.
4. **IV. Dependencies** — References to preceding documents or models.
5. **[V+] Content Sections** — Document-specific rules (e.g., capability definitions).
6. **[Last] Amendment** — Standard revision procedure.

### Crucial Architectural Rules to Document

- **Class Isolation Scoping**: Documents must scope student/seat queries by `class_id` (canonical boundary) rather than teacher ownership or label.
- **Identity Context**: Roster and activity anchors must be bound to `seat_id`.
- **Pure Reads**: Read pathways (GET) must not trigger state modification or session commits.
- **PII Encryption**: Specifications must ensure PII is encrypted at rest using standard hash/encryption helpers.

---

## IX. Codebase Organization Playbook

### Clean Separation Rules
- **No Documentation in `/app/`**: Runtime directories must contain only execution code, tests, and configuration.
- **No Runtime Code in `/docs/`**: The documentation tree must not contain executable modules or active scripts.
- **User-Facing Separation**: Public guides belong in `docs/user-guides/` and must focus on high-level guarantees and walkthroughs. No internal implementation details, ORM schemas, or system keys may be published in user-facing guides.

### File Operations Workflow
1. **Use Git Move**: Always run `git mv` to relocate files to preserve commit history.
2. **Verify References**: After moving, use `rg` to locate and update all inbound markdown links and reference pointers.
3. **Audit heads**: Ensure Alembic migration heads and Git HEAD remain clean and unified.

---

## X. Serving Model

Documentation is published from two places, and each file belongs to exactly one
of them.

### The application serves the help centre

`docs/user-guides` is rendered by the application's docs blueprint at `/docs`
and is the in-app help centre for teachers and students. It ships with the
application, is versioned with it, and is the only documentation tree the
application serves or indexes in its search.

### The technical site serves everything else

The technical site is built from `docs-site/` (Docusaurus) and published at
`classroomtokenhub.com/docs/`. It includes `docs/INVARIANT`, `docs/DOMAIN`,
`docs/FEATURE-EXECUTION`, `docs/SPEC`, `docs/STANDARD_OPERATING_PROCEDURES`,
`docs/MAP`, `docs/PRINCIPLES`, `docs/REFERENCE`, `docs/self-hosting`, and two
durable files from `docs/TRACKING`: the documentation roadmap and the domain plan
template. It excludes `docs/user-guides` (owned by the application),
`docs/archive`, `docs/assets`, `docs/ops`, and the rest of `docs/TRACKING`, which
is working state. The exclude list in `docs-site/docusaurus.config.js` is the
layer that governs this, and `tests/test_docs_site_publishes_no_working_state.py`
fails closed on a new TRACKING or ops file that is neither excluded nor
deliberately published.

The application does not render these documents. A request for one is forwarded
to the technical site when its base URL is configured; otherwise the path is absent.

The public site (`github-pages/`: the landing page, `learnmore.html`,
`timeline.html`, `district.html`, `privacy.html` and `terms.html`) is static and
is **outside** the technical site's generator. `.github/workflows/github-pages.yml`
assembles both into one GitHub Pages artifact from `main`: `github-pages/` at the
site root and the technical site's build at `/docs/`. Neither is served by the
application host.

### Where the boundary is decided

In `app/utils/helpers.py`: `USER_GUIDES_DIR`, `is_user_guide_doc_path()` and
`APP_OWNED_DOCS_ROUTES`, used by both the docs blueprint and the URL builders so
a link and the route it points at cannot disagree. `tests/dom/docs/test_docs_platform_split.py`
pins it.

The boundary is **not** read from `docs-site/route-map.json`. That map lists
`user-guides` as migrated, and honouring it sent the working in-app help centre
— and its index — off the application as soon as an external docs base URL was
configured. A migration map may rename a destination; it does not decide
ownership.

This split is about which renderer owns a file, not about who may read it. The
repository is public and so is its documentation.

## XI. Link Integrity Verification Procedure

Every file relocation or renaming must be immediately verified with:

```bash
# Search for occurrences of the old filename or path across the repository
rg "old_filename_or_path" docs/
```

All references must be updated in the same commit to guarantee a zero-broken-link state.

The following checks enforce this; run them before merging a relocation:

- `lychee --offline .` (the `local-doc-links` job of `.github/workflows/docs-links.yml`): relative links across the repository
- `md-dead-link-check --config pyproject.toml`: Markdown links, including web links on `main`
- `tests/test_docs_archive_citations.py`: live relative links resolve, and every citation of archived material is labelled
- `tests/dom/docs/test_documentation_index_complete.py`: SOP-DOC-001 lists every registered document and no missing one
- `npm run build` in `docs-site/`: the technical site fails on a broken link or anchor

---

## XII. Change Notes

**Version 3.4 (2026-09-28):**
- Assigned `docs/REFERENCE/` by operator ruling: `REF-TERM-001` (developer vocabulary) is Tier 2
  Normative, and the rest are Tier 3. `REF-TERM-002` (user-facing vocabulary) is Informative but highly
  recommended for standardization, subject to INV-CORE-000 §III.7 and INV-ARC-020.

**Version 3.3 (2026-09-28):**
- §V: `docs/archive/` holds superseded v1 **and** v2 material: retired v2 tracking and retired
  numbered documents, not only v1. Assigned `self-hosting/`, `TRACKING/` and `ops/` to Tier 3;
  version 3.2 left them without a tier. `REFERENCE/` stays unassigned, because two `REF-TERM` documents
  declare themselves Normative; §V says how that is handled until an amendment decides. Stated that `.claude/` is outside the tier system.
- §VI: the taxonomy now lists every directory under `docs/`. Tracking belongs in `TRACKING/`, not `MAP/`.
- §X: the technical site's scope matches its exclude list: `ops/` and most of `TRACKING/` are not
  published, and `self-hosting/` is. There is no separate Pages branch; one artifact is built from
  `main`. The public site has six pages.
- §XI: listed the automated link checks.
- §IV: dependencies are given as full paths, and SOP-DOC-001 is added.

---

## XIII. Amendment

Revisions to this standard require:
1. Incrementing the version number.
2. Updating the Effective Date.
3. Updating the Supersedes list.
4. Ensuring compatibility with core invariants in `INV-CORE-000`.

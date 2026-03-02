# SOP-DOC-003: Codebase Organization and Documentation Hygiene Playbook

| Reference Number | Version | Effective Date | Supersedes       | Authority Level |
|------------------|---------|----------------|------------------|-----------------|
| SOP-DOC-003      | 2.0     | 2026-03-02     | SOP-DOC-003 v1.0 | Normative       |

**Status:** Authoritative

**Primary Goal:** Create a clean, navigable, low-entropy repository by eliminating misplaced, duplicated, and outdated files **without introducing regressions or broken references**.

**Secondary Goal:** Clearly separate **user-facing documentation** from **developer/internal documentation** to improve readability, reduce duplication, and prevent accidental information disclosure.

---

## I. Purpose

This document defines the canonical procedure for organizing the repository, eliminating documentation entropy, and maintaining clean separation between user-facing and internal documentation — without introducing regressions or broken references.

---

## II. Scope

This procedure applies to all non-runtime files in the repository, including documentation, configuration, and scripts. It governs file placement, naming, deduplication, archival, and deletion decisions.

---

## III. Authority Level

Normative (SOP Tier). Subordinate to ARC-INV-000 and SOP-DOC-000.

---

## IV. Dependencies

- ARC-INV-000: Core Invariants
- SOP-DOC-000: Documentation Standard (tier classification and naming conventions)

---

## V. Non-Negotiable Constraints

The following rules must be honored before any file operation:

1. **No semantic changes during cleanup.**
   - File moves, renames, and deletions only.
   - No logic refactors mixed into organization work.

2. **All moves must preserve history.**
   - Use `git mv` exclusively.
   - No copy-paste-delete workflows.

3. **No broken references are allowed.**
   - Python imports
   - Markdown links
   - CI references
   - Navigation links

4. **Every directory must have a single responsibility.**
   - If a directory cannot be described in one sentence, it is incorrectly scoped.

---

## VI. Canonical Repository Structure

### Repository Root — Entry Points and Contracts

Root-level files answer: *What is this project and how do contributors work on it safely?*

Permitted at root:

```
README.md
DEVELOPMENT.md
CONTRIBUTING.md
PROJECT_HISTORY.md
CHANGELOG.md
LICENSE
.env.example
docker-compose.yml
```

Prohibited at root:

- Feature documentation
- Design drafts
- Legacy notes

Root must contain fewer than 15 files.

---

### `/docs/` — Canonical Knowledge (No Runtime Code)

```
docs/
├── README.md              ← documentation map
├── arc/                   ← architecture and invariants
├── sop/                   ← standard operating procedures
├── sec/                   ← security audits and controls
├── dom/                   ← domain specifications
├── feat/                  ← feature specifications
├── log/                   ← historical records and milestones
└── user-guides/           ← user-facing documentation
```

Rules:

- No `misc/`, `old/`, or `notes/` folders.
- Outdated but historically useful content → `docs/log/`.
- Outdated and useless content → delete.

---

### `/app/` — Runtime Code Only

- No documentation files.
- No experimental scripts.
- No commented-out legacy modules.
- Subfolders reflect runtime responsibility, not developer convenience.

---

## VII. Documentation Audience Classification

Documentation is an interface. Different audiences require different interfaces. The three tiers defined in SOP-DOC-000 map directly to audience:

| Tier            | Audience                     | Location                  |
|-----------------|------------------------------|---------------------------|
| Constitutional  | Architects and maintainers   | `docs/arc/ARC-INV-*`     |
| Normative       | Contributors and AI agents   | `docs/arc/`, `docs/sop/`, `docs/dom/`, `docs/feat/`, `.claude/rules/` |
| Informative     | End users, public            | `docs/user-guides/`, root files, `docs/log/` |

Each document must answer: *Who is this written for?* That answer determines where it lives and whether it may appear on the public documentation site.

---

## VIII. Canonical Source of Truth

### Repository

The repository contains the complete, authoritative documentation:

- Policies
- Enforcement rules
- Architecture details
- Failure modes
- Operational runbooks

No external site or mirror is considered canonical.

---

### Documentation Site

The documentation site is a curated projection of user-facing content, not a mirror of the repository.

It must be:

- Shorter
- Outcome-focused
- Free of enforcement mechanisms and internal operational details

**Golden Rule:** Users get guarantees, not mechanisms.

Permitted source for the documentation site: `docs/user-guides/` only.

Prohibited patterns:

- Copy-pasting full normative docs and "simplifying" them.
- Maintaining two parallel canonical versions of the same content.
- Linking from the documentation site to internal normative GitHub docs.

---

## IX. Approved Layering Pattern

For topics that span both normative and user-facing audiences:

**Normative version (canonical, in repository):**

```
docs/sop/SOP-DOC-XXX_[Topic].md
```

- Full details
- Enforcement language
- Incident references

**User-facing summary (documentation site):**

Derived from the normative version, containing:

- High-level intent only
- User-visible guarantees
- No implementation details or enforcement mechanics

The user-facing version must never explain how something is enforced.

---

## X. Cleanup Procedure

### Phase 1: Inventory (Read-Only)

1. Generate repository tree:

   ```bash
   tree -L 4 > repo_tree.txt
   ```

2. Classify all non-code files as one of:
   - Canonical
   - Duplicate
   - Outdated but historical
   - Outdated and useless
   - Orphaned (unreferenced)

   No file operations during this phase.

---

### Phase 2: Canonical Location Assignment

For every topic, define exactly one canonical home per SOP-DOC-000 namespace rules.

If two files compete for the same topic:

- Keep the newer or more complete version.
- Archive or delete the other.

---

### Phase 3: Execute File Operations

Rules:

- Use `git mv` for all moves.
- One logical group per commit.
- Commit message format:
  ```
  docs: move [topic] to canonical location
  ```

---

## XI. Broken Reference Verification

After any file operation:

### Application Code

```bash
pytest -q
flask routes
```

### Markdown Links

For each moved document:

```bash
rg "old_path|old_filename" docs/
```

Fix all inbound links before committing.

---

## XII. Duplicate, Archive, and Delete Policy

### Decision Tree

- Same topic, different content → merge, archive duplicate.
- Same topic, one obsolete → archive obsolete version.
- Same topic, both obsolete → archive one, delete the other.

### Archived Documents

- Archived documents are read-only.
- No new links may point to archived documents.
- Archived content belongs in `docs/log/`.

### Deletion Criteria

A file may be deleted only if all of the following are true:

- It is not referenced by any active document, CI configuration, or navigation file.
- It contains no content that is not fully superseded by an active document.
- It has been confirmed orphaned via reference search (Section XI).

Commit message format:

```
docs: remove obsolete [topic] documentation
```

---

## XIII. Entropy Prevention

### Mandatory Guardrails

1. `docs/README.md` must explain the purpose of each namespace folder.
2. No new root-level files without explicit justification documented in a commit message.
3. The public documentation site may only source content from `docs/user-guides/`.

---

## XIV. Completion Criteria

A cleanup pass is complete when:

- No duplicate documentation exists.
- Every document has a canonical home per SOP-DOC-000.
- Repository root contains fewer than 15 files.
- No broken links exist.
- Tests and CI pass.

> If nothing was deleted, nothing was cleaned. Archiving is mercy. Deletion is hygiene.

---

## XV. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with ARC-INV-000 and SOP-DOC-000.

# Codebase Organization & Documentation Hygiene Playbook

**Status:** Authoritative

**Primary Goal:** Create a clean, navigable, low-entropy repository by eliminating misplaced, duplicated, and outdated files **without introducing regressions or broken references**.

**Secondary Goal:** Clearly separate **user-facing documentation** from **developer/internal documentation** to improve readability, reduce duplication, and prevent accidental information disclosure.

---

## 1. Non‑Negotiable Constraints

Before touching any files, the following rules MUST be honored:

1. **No semantic changes during cleanup**

   - File moves, renames, and deletions only
   - No logic refactors mixed into organization work

2. **All moves must preserve history**

   - Use `git mv` exclusively
   - No copy‑paste‑delete workflows

3. **No broken references are allowed**

   - Python imports
   - Markdown links
   - CI references
   - Doc‑site navigation links

4. **Every directory must have a single responsibility**

   - If a directory cannot be described in one sentence, it is incorrectly scoped

---

## 2. Canonical Mental Model

### Repository Root = Entry Points & Contracts

Root‑level files answer:

> *What is this project and how do contributors work on it safely?*

Allowed at root:

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

❌ No feature documentation\
❌ No design drafts\
❌ No legacy notes

---

### `/docs/` = Canonical Knowledge (No Runtime Code)

```
docs/
├── README.md                 ← documentation map
├── development/              ← policies, gates, internal rules
├── technical-reference/      ← system internals & architecture
├── operations/               ← production & maintenance
├── security/                 ← audits & threat models
├── user-guides/              ← full user‑facing documentation
└── archive/                  ← frozen historical docs
```

Rules:

- No `misc/`, `old/`, or `notes/` folders
- Outdated but historically useful → `archive/`
- Outdated and useless → delete

---

### `/app/` = Runtime Code Only

Rules:

- No documentation files
- No experimental scripts
- No commented‑out legacy modules
- Subfolders reflect runtime responsibility, not developer convenience

---

## 3. Documentation Audience Separation (Critical)

Documentation is an **interface**, and different audiences require different interfaces.

### Three Documentation Classes

1. **User‑Facing (Public, Low‑Trust)**
2. **Developer‑Facing (Medium‑Trust)**
3. **Internal / Operational (High‑Trust)**

Each document MUST answer the question:

> *Who is this written for?*

That answer determines **where it lives** and **whether it may appear on the doc site**.

---

## 4. Canonical Source of Truth Rules

### GitHub Repository

The repository contains the **complete, authoritative documentation**:

- Policies
- Enforcement rules
- Architecture details
- Failure modes
- Operational runbooks

Nothing in the doc site is considered canonical.

---

### Documentation Site

The documentation site is a **curated projection**, not a mirror.

It must be:

- Shorter
- Safer
- Outcome‑focused
- Free of enforcement and internal mechanics

**Golden Rule:**

> *Users get guarantees, not mechanisms.*

---

## 5. Handling the Same Topic for Different Audiences

### ❌ Forbidden Patterns

- Copy‑pasting full docs and “simplifying” them
- Maintaining two parallel canonical versions
- Linking from doc site → internal GitHub docs

---

### ✅ Approved Pattern: Layered Documentation

**Canonical (GitHub):**

```
docs/development/SCHEMA_CONTRACTION_POLICY.md
```

- Full details
- Enforcement language
- CI rules
- Incident references

**Doc Site Summary:**

```
docs-site/concepts/schema-changes.md
```

- High‑level intent only
- User‑visible guarantees
- No implementation details

Doc‑site versions must never explain *how* something is enforced.

---

## 6. Cleanup Procedure (Safe Order)

### Phase 1: Inventory (Read‑Only)

1. Generate repository tree:

   ```bash
   tree -L 4 > repo_tree.txt
   ```

2. Classify all non‑code files as:

   - Canonical
   - Duplicate
   - Outdated but historical
   - Outdated and useless
   - Orphaned (unreferenced)

No moves during this phase.

---

### Phase 2: Canonical Location Assignment

For every topic, define **exactly one home**.

If two files compete:

- Keep the newer or more complete
- Archive or delete the rest

---

### Phase 3: Move Files

Rules:

- Use `git mv`
- One logical group per commit
- Commit message format:
  ```
  docs: move <topic> docs to canonical location
  ```

---

## 7. Broken Reference Detection

### 7.1 Application Code

After code‑related moves:

```bash
pytest -q
flask routes
```

---

### 7.2 Markdown Links

For each moved doc:

```bash
rg "old_path|old_filename" docs/
```

Fix **all inbound links**.

---

### 7.3 Doc Site Integrity

If using a static doc site:

- Update nav/sidebars
- Run local doc build
- Cleanup fails if site build fails

---

## 8. Duplicate, Archive, and Delete Policy

### Decision Tree

- Same topic, different content → merge, archive duplicate
- Same topic, one obsolete → archive obsolete
- Same topic, both obsolete → archive one, delete one

Archived docs:

- Read‑only
- No new links allowed

---

## 9. Deletion Checklist

A file may be deleted only if:

-

Commit message:

```
docs: remove obsolete <topic> documentation
```

---

## 10. Preventing Future Entropy

### Mandatory Guardrails

1. `docs/README.md` explaining folder purpose
2. No new root‑level files without explicit justification
3. Doc‑site build may only read from:
   - `docs/user-guides/`
   - `docs-site/`

Attempting to ingest internal docs MUST fail the build.

---

## 11. Completion Criteria

Cleanup is complete when:

- No duplicate documentation exists
- Every doc has a clear home
- Root directory contains < 15 files
- No broken links
- Tests and CI pass

---

## 12. Final Rule

> **If nothing was deleted, nothing was cleaned.**

Archiving is mercy. Deletion is hygiene.


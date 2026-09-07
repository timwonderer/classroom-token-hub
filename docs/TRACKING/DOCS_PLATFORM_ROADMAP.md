# Documentation Platform Roadmap

**Status:** Partially superseded — see note below
**Created:** 2026-06-14
**Last Reconciled:** 2026-09-06
**Branch:** `CTH_v2.0` (this document was authored on `docs/cleanup-and-organization`)

---

## Context

The v2 documentation reorganization (completed 2026-06-14) promoted all v2 canonical docs to
top-level directories under `docs/` and archived v1 content to `docs/archive/`. This roadmap covers
the remaining documentation work.

> [!IMPORTANT]
> Two of this roadmap's premises no longer hold, and its remaining phases must be read against
> current state rather than the state described here.
>
> - **`docs/LOGS/` no longer exists.** The `LOG-*` namespace was removed on 2026-09-05. Rationale
>   belongs in `docs/PRINCIPLES/`, chronology in root `CHANGELOG.md`. Any step below that proposes
>   promoting content *into* `docs/LOGS/` is void.
> - **`docs/archive/v1-user-guides/` no longer exists.** Its 100 files were promoted to
>   `docs/user-guides/` — see `docs/TRACKING/USER_GUIDE_INVENTORY_2026-09.md`. Phase 2's premise
>   that the guides are still archived is stale; the open work is content quality, not relocation.
>
> References to `docs/archive/` below are deliberate and point at genuinely superseded v1 material.

---

## Phase 1: Port v1 Docs to v2 Standard

**Goal:** Review archived v1 documentation and migrate still-relevant content into the v2 namespace system.

### Scope
- Review `docs/archive/v1-development/` (archived) for content that remains relevant to v2
- Migrate relevant content using live v2 namespace prefixes (`INV`, `DOM`, `FEAT`, `SPEC`, `SOP`,
  `MAP`, `PRN`). Do **not** use `ARC`, `SEC`, or `LOG` — those namespaces are retired.
- Content that is purely historical stays in `docs/archive/`

### Acceptance Criteria
- [ ] Every file in `docs/archive/v1-development/` has been triaged (keep in archive, promote, or delete)
- [ ] Promoted content follows the SOP-DOC-000 documentation standard
- [ ] No orphan references to archived content from active docs

---

## Phase 2: Upgrade v1 User Guides to v2

**Goal:** Rewrite user-facing documentation for the v2 architecture, UX, and terminology.

### Scope
- Review the guides now live at `docs/user-guides/` (promoted out of the archive; the former
  `docs/archive/v1-user-guides/` path no longer exists)
- Rewrite for v2:
  - **Teacher Manual** — updated for seat-based identity, class_id scoping, FEAT execution model
  - **Student Guide** — updated for v2 student portal UX
  - **Economy Guide** — aligned with DOM-ECON domain specs
  - **Sysadmin Manual** — updated for v2 admin capabilities
- Align terminology with v2 domain model (seat, class_id, join_code as alias, FEAT-driven mutations)

### Acceptance Criteria
- [ ] All four core guides rewritten for v2
- [ ] Terminology consistent with v2 domain specs (authority language only from the canonical identity model)
- [ ] Guides placed in canonical location (may be Docusaurus source, see Phase 3)

---

## Phase 3: Rebuild Documentation Sites

Two separate platforms, each serving a different audience and use case.

### A. Docusaurus Public Site

**Purpose:** External-facing documentation for users, developers, and educators.
**URL:** `classroomtokenhub.com/docs` or `docs.classroomtokenhub.com`

Four content areas:

1. **Main Documentation**
   - Project overview and getting started
   - Architecture and design decisions
   - Installation and self-hosting

2. **In-Depth Guide**
   - Detailed feature documentation for teachers and students
   - Economy design and configuration
   - Best practices for classroom economy management

3. **Feature Guide**
   - Per-feature reference pages (attendance, payroll, rent, store, hall pass, insurance, etc.)
   - Configuration options and examples
   - Screenshots and workflows

4. **Developer Blog**
   - Release notes and version history
   - Technical decision records
   - Migration guides and upgrade paths
   - v2 architecture deep dives

#### Acceptance Criteria
- [ ] Docusaurus site scaffolded and deployable
- [ ] All four content areas populated with initial content
- [ ] Deployed to production URL
- [ ] CI pipeline for docs builds

### B. In-App Custom Doc Site

**Purpose:** Context-sensitive, role-specific help served from within the Flask application.
**Route:** `/docs/` (existing route in `app/routes/docs.py`)

Features:

1. **Role-Specific Content**
   - Teacher help pages tailored to teacher workflows
   - Student help pages tailored to student workflows
   - Sysadmin help pages tailored to admin operations

2. **Context-Sensitive Help**
   - Contextual help for the page the user is currently viewing
   - Quick-reference tooltips and inline guidance

3. **Diagnostics Interface**
   - Troubleshooting guides organized by problem category
   - Based on the diagnostics content ported to `docs/user-guides/`
   - Interactive diagnostic flows where applicable

#### Acceptance Criteria
- [ ] In-app docs route serves role-appropriate content
- [ ] Diagnostics guides ported from v1 and updated for v2 UX
- [ ] Context-sensitive help available on key pages
- [ ] Content loads without external dependencies (fully self-contained)

---

## Dependencies

- Phase 1 is independent and can start immediately
- Phase 2 depends on Phase 1 (need to know what v1 content is worth porting)
- Phase 3A (Docusaurus) can start in parallel with Phase 2
- Phase 3B (in-app docs) depends on Phase 2 completion (needs the rewritten guides)

# Documentation Standards

> **Not authoritative.** This file is operational guidance for agents. Normative authority lives only under `docs/INVARIANT/`, `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/SPEC/`, and `docs/STANDARD_OPERATING_PROCEDURES/`. Where this file conflicts with one of those, the normative document wins and this file is what gets corrected.

**CRITICAL:** Documentation must be updated whenever features are added, changed, or removed. Outdated documentation is worse than no documentation.

---

## The Golden Rules

1. **ALWAYS update CHANGELOG.md for every change**
2. **ALWAYS update relevant user guides for user-facing changes**
3. **ALWAYS update technical docs for architecture changes**
4. **NEVER leave TODO comments without tracking in DEVELOPMENT.md**
5. **ALWAYS keep documentation in sync with code**

---

## Documentation Structure

```
/
├── CHANGELOG.md              # All changes (required for every PR)
├── DEVELOPMENT.md            # Roadmap and planned features
├── README.md                 # Project overview and quick start
├── CONTRIBUTING.md           # Contribution guidelines
├── SECURITY.md               # Vulnerability reporting policy
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md  # The PR template
├── .claude/                  # Agent guidance (non-authoritative)
│   ├── CLAUDE.md             # Guide for AI assistants (this guide's parent)
│   ├── AGENTS.md             # AI agent workflow guidelines
│   └── rules/                # Detailed rule files
├── docs/
│   ├── README.md             # Documentation index
│   ├── INVARIANT/            # Core and architecture invariants (Tier 0/1)
│   ├── DOMAIN/               # Per-domain authority specs (Tier 1)
│   ├── FEATURE-EXECUTION/    # FEAT contracts (Tier 2)
│   ├── SPEC/                 # Technical contracts (Tier 2, binding only when incorporated)
│   ├── STANDARD_OPERATING_PROCEDURES/  # SOPs (Tier 2)
│   ├── MAP/                  # Domain-to-FEAT capability maps (Tier 3)
│   ├── PRINCIPLES/           # PRN-* rationale: why a design was chosen (Tier 3)
│   ├── REFERENCE/            # REF-* interface references
│   ├── TRACKING/             # Launch readiness and status
│   ├── user-guides/          # User-facing help served by the in-app /docs site
│   ├── self-hosting/         # Self-hosting guide
│   ├── ops/                  # Operational notes
│   │   └── audits/           # Dated deploy/release records (DEPLOY_*.md) and audits
│   ├── assets/               # Documentation images and assets
│   └── archive/              # Superseded material — history only, never authority
│       ├── v1-architecture/, v1-development/, v1-docs/  # Archived v1 material
│       ├── v2-tracking-2026/ # Archived v2 migration/launch tracking (2026-07 → 2026-09)
│       ├── PHASE_PLANNING/   # Archived v2 phase plans and audits
│       ├── STANDARD_OPERATING_PROCEDURES/  # Retired SOPs (e.g. SOP-DB-009, SOP-DB-010)
│       └── github-pages/     # Archived GitHub Pages assets
```

**Two rules the tree does not show:**

- `docs/LOGS/` (`LOG-*`) was removed on 2026-09-05 and must not be reintroduced. Rationale goes in
  `docs/PRINCIPLES/`, chronology in `CHANGELOG.md`.
- `CHANGELOG.md` is developer-facing. Do not mirror it into `docs/` and do not link it from the
  in-app docs site — a mirror drifts from the original without announcing it.

---

## When to Update Which Docs

### For EVERY Change

**CHANGELOG.md** - Update for ALL changes, no exceptions

```markdown
## [Unreleased]

### Added
- Teacher account recovery via student-verified codes (#609)
- System admin 2FA reset functionality (#608)

### Changed
- Updated privacy page UX and clarity (#610)
- Improved Terms of Service readability (#610)

### Fixed
- Auto-tap-out bug with missing join_code (#607)
- Hall pass timestamp updates (#606)

### Security
- Hardened recovery code handling with scrypt hashing via `hash_password()`
```

**Format:** Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- Group by: Added, Changed, Deprecated, Removed, Fixed, Security
- Include PR/issue numbers
- Use present tense
- Be specific and concise

---

### For New Features

#### 1. User-Facing Features

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Added
- Hall pass system with time tracking and automatic status updates (#XXX)
```

**README.md** (if it's a major feature)
```markdown
### Core Features
- **Hall Pass System** — Time-limited passes with automatic tracking
```

**User Guide** (`docs/user-guides/teacher_manual.md` or `student_guide.md`)
```markdown
## Hall Passes

Students can request hall passes from their dashboard...

### Creating a Hall Pass

1. Click "Request Hall Pass"
2. Select duration...
```

**DEVELOPMENT.md** (update "Current State" when it ships or priorities change)
```markdown
### In production
- **v2.x.y** (`<sha>`, YYYY-MM-DD) adds the hall pass system (`docs/user-guides/student_guide.md`).
```

#### 2. Internal/Technical Features

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Added
- RecoveryRequest and StudentRecoveryCode models for account recovery (#609)
```

**The governing normative document** (if it changes architecture or domain behavior) —
the `INV-*`, `DOM-*`, `FEAT-*` or `SPEC-*` document that owns the area, amended per
`SOP-DOC-000`. Code that departs from its governing document is a defect in one or the other.

**`docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`** (for new tables or models) —
it defines the only valid set of runtime tables:
```markdown
### recovery_requests

Teacher account recovery requests.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | UUID | FK to users.id |
...
```

#### 3. API Changes

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Added
- `/admin/recovery-status` endpoint for live recovery tracking (#609)
```

**API reference:** `docs/REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE.md`

---

### For Bug Fixes

#### 1. Critical/Security Fixes

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Security
- Fixed multi-period data leak for students with same teacher (#P0)
- Resolved join_code scoping issue in transaction queries
```

**Security documentation**
- Incident record per `SOP-SEC-001` §V.4 (minimal, access-controlled, no PII or secret values)
- `SECURITY.md` if the reporting policy changes

**README.md** (if affects installation/setup)

**Release record** (if it ships): a dated `docs/ops/audits/DEPLOY_<date>_<sha>.md`

#### 2. Regular Bug Fixes

Update **MINIMUM**:

**CHANGELOG.md**
```markdown
### Fixed
- Auto-tap-out bug where missing join_code prevented token accumulation (#607)
- Hall pass verification timestamp not updating (#606)
```

Optionally update:
- Relevant user guide (if bug affected user workflow)
- Technical docs (if bug revealed architecture issues)

---

### For Breaking Changes

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Changed (BREAKING)
- Renamed `motto` to `tagline` on `classes` (#XXX)
  **Migration Required:** Run `flask db upgrade`
  **Code Impact:** Update any direct SQL queries using old column name
```

**DEVELOPMENT.md** (if affects future work)

**Deployment SOP** (upgrade instructions): `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md`

**Migration guide** (create if major version change)

---

## Documentation Quality Standards

### Writing Style

✅ **DO:**
- Use clear, concise language
- Write in active voice
- Use present tense for features ("The system validates...")
- Include code examples where helpful
- Link to related documentation
- Use proper markdown formatting

❌ **DON'T:**
- Use jargon without explanation
- Write vague descriptions ("improves performance")
- Leave broken links
- Include outdated screenshots
- Use passive voice excessively
- Assume prior knowledge

### Code Examples

Always include:
- Working, tested code
- Necessary imports
- Context (what file, what scenario)
- Expected output or behavior

```python
# ✅ GOOD EXAMPLE
# In app/routes/admin.py

from app.models import Seat

# Get student seats for the teacher's active class
class_id = g.canonical_context.class_id
seats = Seat.query.filter_by(class_id=class_id, role="student").all()

# Returns: List of Seat objects scoped to class_id
```

```python
# ❌ BAD EXAMPLE
# Get students
students = query_students()
```

### Markdown Formatting

Use proper markdown:

```markdown
# H1 - Document Title (once per document)
## H2 - Major Sections
### H3 - Subsections
#### H4 - Minor Subsections

**Bold** for emphasis
*Italic* for references
`code` for inline code
```code blocks``` for multi-line code

- Unordered lists
1. Ordered lists

> Blockquotes for important notes

[Links](../../README.md) to related docs
```

---

## Specific File Guidelines

### CHANGELOG.md

**Structure:**
```markdown
# Changelog

## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [2.0.1] - 2026-09-28 — Security release

(Release notes)
```

**Entry Format:**
```markdown
- Clear description of what changed (#PR-number)
```

**When to Update:**
- EVERY commit that changes functionality
- Update "Unreleased" section
- On release, move to versioned section

---

### DEVELOPMENT.md

**Purpose:** Roadmap and development priorities

**Structure:**
```markdown
# Classroom Token Hub - Development Priorities

## Quick Links
## Branch and Database Truth
## Git Hooks

## Current State (YYYY-MM-DD)
### In production
- Released versions, with commit and date
### Next
- Priority-ordered work (the post-launch tracker is the working list)

## v2 Technical Direction
## Working Agreements
```

**When to Update:**
- When a release ships (update "In production")
- When priorities change (update "Next")
- When deferring features

---

### README.md

**Purpose:** Project overview and quick start

**Update When:**
- Major new features added
- Installation process changes
- Prerequisites change
- Quick start steps change

**Don't Update For:**
- Minor bug fixes
- Internal refactoring
- Small feature additions (document elsewhere)

---

### User Guides

**Location:** `docs/user-guides/`

**Files:**
- `teacher_manual.md` - Complete teacher guide
- `student_guide.md` - Complete student guide

**Update When:**
- New user-facing features
- UI changes
- Workflow changes
- Bug fixes that change behavior

**Include:**
- Step-by-step instructions
- Screenshots (if helpful)
- Common issues and solutions
- Links to related features

---

### Technical Reference

There is no separate technical-reference tree; the normative documents are the reference.

**Locations:**
- `docs/INVARIANT/ARCHITECTURE/` - System architecture (`INV-ARC-*`)
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` - Database structure
- `docs/SPEC/` - Financial and other technical contracts (e.g. `SPEC-ECON-*`, `SPEC-LED-*`)
- `docs/REFERENCE/` - Interface and vocabulary references (`REF-*`, descriptive)

**Update When:**
- New models added
- Architecture changes
- New routes/blueprints
- Major refactoring

---

### Security Documentation

**Locations:**
- `SECURITY.md` - Vulnerability reporting policy
- `docs/STANDARD_OPERATING_PROCEDURES/SECURITY/` - Security operations (`SOP-SEC-001`, incl. incident response §V.4)
- `docs/SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md` - Credential/lookup code contract
- `docs/ops/audits/` - Dated audit and release records

**Update When:**
- Security vulnerabilities found
- Security features added
- Security audits completed
- Critical fixes deployed

**Format:** Create dated, immutable reports

---

## Documentation Checklist

### For Every PR

- [ ] CHANGELOG.md updated
- [ ] Relevant docs in `docs/` updated
- [ ] Links work (no broken references)
- [ ] Code examples tested
- [ ] README.md updated (if major change)
- [ ] DEVELOPMENT.md updated (if roadmap affected)

### For New Features

- [ ] Feature documented in user guide
- [ ] Technical details in technical reference
- [ ] API endpoints documented (if applicable)
- [ ] Examples provided
- [ ] Common issues addressed

### For Bug Fixes

- [ ] Root cause documented (if complex)
- [ ] User-facing fixes in user guide
- [ ] Known limitations updated

### For Releases

- [ ] CHANGELOG.md finalized
- [ ] `docs/ops/audits/DEPLOY_<date>_<sha>.md` release record created
- [ ] All docs reviewed for accuracy
- [ ] Deprecated features marked
- [ ] Upgrade instructions provided

---

## Common Documentation Mistakes

### ❌ MISTAKE 1: Not updating CHANGELOG.md

**Problem:** Users can't track what changed between versions

**Solution:** Update CHANGELOG.md in EVERY PR

### ❌ MISTAKE 2: Outdated code examples

**Problem:** Documentation shows code that no longer works

**Solution:** Test all code examples before committing docs

### ❌ MISTAKE 3: Broken links

**Problem:** Links to moved/renamed files return 404

**Solution:** Check all links when reorganizing docs

### ❌ MISTAKE 4: Vague descriptions

**Bad:**
```markdown
### Changed
- Improved performance
- Fixed bugs
- Updated UI
```

**Good:**
```markdown
### Changed
- Reduced payroll calculation time by 40% using cached queries (#XXX)

### Fixed
- Auto-tap-out bug where missing join_code prevented token accumulation (#607)

### Changed
- Updated student dashboard with modern card-based layout (#XXX)
```

### ❌ MISTAKE 5: Missing upgrade instructions

**Problem:** Breaking changes without migration guide

**Solution:** Always include upgrade steps for breaking changes

---

## Documentation Tools

### Link Checker

Before committing:

```bash
# Check for broken internal links
grep -r "](/" docs/
grep -rn "](.*\.md)" .
```

### Markdown Linter

Use a markdown linter:

```bash
# Install markdownlint
npm install -g markdownlint-cli

# Run linter
markdownlint docs/**/*.md
```

---

## Review Checklist

Before marking docs as complete:

- [ ] All facts accurate
- [ ] All links work
- [ ] All code examples tested
- [ ] Proper markdown formatting
- [ ] No spelling errors
- [ ] Consistent terminology
- [ ] Clear and concise
- [ ] Appropriate detail level
- [ ] Cross-references where needed
- [ ] Updated file dates

---

## Quick Reference

| Change Type | Required Docs | Optional Docs |
|-------------|---------------|---------------|
| New Feature | CHANGELOG, User Guide, Technical Ref | README, DEVELOPMENT |
| Bug Fix | CHANGELOG | User Guide (if workflow changed) |
| Security Fix | CHANGELOG, Security Docs | User Guide |
| Breaking Change | CHANGELOG, Migration Guide | All affected docs |
| Refactor | CHANGELOG | Technical Ref |
| Documentation | CHANGELOG | - |

---

**Last Updated:** 2026-09-28
**Total Documentation Files:** 441 Markdown files under `docs/` (271 outside `docs/archive/`)
**Documentation Coverage:** Comprehensive (user guides, normative INV/DOM/FEAT/SPEC/SOP, operations, security)

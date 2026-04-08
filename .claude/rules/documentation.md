# Documentation Standards

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
├── PROJECT_HISTORY.md        # Project evolution and philosophy
├── CLAUDE.md                 # Guide for AI assistants (this guide's parent)
├── CONTRIBUTING.md           # Contribution guidelines
├── .claude/                  # Claude-specific rules and settings
│   ├── AGENTS.md             # AI agent workflow guidelines
│   └── rules/                # Detailed rule files
├── docs/
│   ├── README.md             # Documentation index
│   ├── user-guides/          # For end users
│   │   ├── README.md
│   │   ├── teacher_manual.md
│   │   ├── student_guide.md
│   │   ├── economy_guide.md
│   │   ├── diagnostics/
│   │   ├── features/
│   │   └── legal/
│   ├── technical-reference/  # For developers
│   │   ├── architecture.md
│   │   ├── database_schema.md
│   │   ├── api_reference.md
│   │   ├── analytics-specification.md
│   │   └── economy-specification.md
│   ├── operations/           # Deployment and maintenance
│   │   ├── README.md
│   │   ├── Deployment_Guide.md
│   │   ├── README_GITHUB_PAGES.md
│   │   ├── GITHUB_PAGES_SETUP.md
│   │   ├── CLEANUP_DUPLICATES.md
│   │   ├── DEMO_SESSIONS.md
│   │   ├── DIGITALOCEAN_CLOUDFLARE_SETUP.md
│   │   ├── MULTI_TENANCY_FIX_DEPLOYMENT.md
│   │   ├── PII_AUDIT.md
│   │   ├── SECURITY_AUDIT_2025.md
│   │   ├── SECURITY_IMPROVEMENTS_IMPLEMENTATION.md
│   │   └── PULSETIC_SETUP.md
│   ├── security/             # Security audits and reports
│   │   ├── CRITICAL_SAME_TEACHER_LEAK.md
│   │   └── MULTI_TENANCY_AUDIT.md
│   ├── development/          # Development guides
│   │   ├── codebase_organization_documentation_hygiene_playbook.md
│   │   ├── SCHEMA_CHANGE_MD.md
│   │   ├── migration-specifications.md
│   │   ├── TESTING_SUMMARY.md
│   │   └── SEEDING_INSTRUCTIONS.md
│   └── archive/              # Historical documents
│       ├── releases/         # Old release notes
│       │   ├── RELEASE_NOTES_v1.0.md
│       │   ├── RELEASE_NOTES_v1.1.0.md
│       │   ├── RELEASE_NOTES_v1.1.1.md
│       │   └── RELEASE_NOTES_v1.2.0.md
│       ├── RECOVERY_EVALUATION.md
│       ├── migration_check_report.md
│       ├── pr-reports/
│       └── FIXES_SUMMARY.md
```

---

## When to Update Which Docs

### For EVERY Change

**CHANGELOG.md** - Update for ALL changes, no exceptions

```markdown
## [Unreleased] - Version 1.x

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
- Hardened recovery code handling with bcrypt hashing
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

**DEVELOPMENT.md** (mark as completed or update roadmap)
```markdown
## Completed Features

### Hall Pass System ✅
**Status:** Completed in v1.0
**Documentation:** `docs/user-guides/student_guide.md`
```

#### 2. Internal/Technical Features

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Added
- RecoveryRequest and StudentRecoveryCode models for account recovery (#609)
```

**docs/technical-reference/architecture.md** (if changes architecture)
```markdown
## Account Recovery

The system implements a student-verified account recovery mechanism...
```

**docs/technical-reference/database_schema.md** (for new models)
```markdown
### RecoveryRequest

Stores teacher account recovery requests.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| teacher_id | Integer | FK to Admin |
...
```

#### 3. API Changes

Update **ALL** of these:

**CHANGELOG.md**
```markdown
### Added
- `/admin/recovery-status` endpoint for live recovery tracking (#609)
```

**API documentation** (if separate API docs exist, or in technical reference)

**Postman collection** (if maintained)

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

**Security documentation** (`docs/security/`)
- Create incident report if critical
- Update existing audit documents

**README.md** (if affects installation/setup)

**RELEASE_NOTES** (if affects current version)

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
- Renamed `student_id` to `user_id` in Transaction model (#XXX)
  **Migration Required:** Run `flask db upgrade`
  **Code Impact:** Update any direct SQL queries using old column name
```

**DEVELOPMENT.md** (if affects future work)

**docs/operations/DEPLOYMENT.md** (upgrade instructions)

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
# In app/routes/student.py

from app.auth import get_admin_student_query
from app.models import ClassMembership, Student

# Get students for current class period
students = (
    get_admin_student_query()
    .join(ClassMembership, ClassMembership.student_id == Student.id)
    .filter(ClassMembership.join_code == current_join_code)
    .all()
)

# Returns: List of Student objects scoped to join_code
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

[Links](url) to related docs
```

---

## Specific File Guidelines

### CHANGELOG.md

**Structure:**
```markdown
# Changelog

## [Unreleased] - Version X.Y

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [1.0.0] - 2025-12-XX

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
# Development Priorities

## Current Work (v1.1)
- Features being actively developed

## Planned Features
### v1.1 - Analytics
- Specific features planned

### v1.2 - Mobile
- Mobile-focused features

## Deferred Features
- Features considered but not prioritized

## Completed Features
- Features done, with links to docs
```

**When to Update:**
- When planning new features
- When completing features (move to "Completed")
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

**Location:** `docs/technical-reference/`

**Files:**
- `architecture.md` - System architecture
- `database_schema.md` - Database structure
- `economy-specification.md` - Financial system spec

**Update When:**
- New models added
- Architecture changes
- New routes/blueprints
- Major refactoring

---

### Security Documentation

**Location:** `docs/security/`

**Files:**
- Audit reports
- Incident reports
- Security guidelines

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
- [ ] RELEASE_NOTES_vX.Y.md created/updated
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
grep -r "\[.*\](.*\.md)" .
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

**Last Updated:** 2025-12-13
**Total Documentation Files:** 30+
**Documentation Coverage:** Comprehensive (user guides, technical ref, operations, security)

# SOP-DOC-006: User Guide Authoring Standard

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-006 | 1.0 | 2026-03-08 | N/A | Normative |

## I. Purpose

This document defines how user-facing guides in `docs/user-guides/` must be written, structured, and maintained so they remain readable for end users while staying aligned with the canonical repository documentation.

## II. Scope

This standard governs all content inside `docs/user-guides/`, including:

- role manuals and quick-start indexes
- feature guides
- diagnostics and troubleshooting guides
- legal and policy-facing user documentation
- user-facing reference guides such as the classroom economy guide

This document does not govern ARC, DOM, FEAT, SOP, SEC, or LOG documents outside `docs/user-guides/`.

## III. Authority Level

Normative. Subordinate to `SOP-DOC-000`, `SOP-DOC-003`, and `SOP-DOC-005`.

## IV. Dependencies

- `SOP-DOC-000_Writing_Specification.md`
- `SOP-DOC-003_Division_Definition.md`
- `SOP-DOC-005_Codebase_Organization_Playbook.md`

## V. Audience and Content Rules

- User guides must be written for teachers, students, or system administrators, not for maintainers.
- User guides must explain user-visible behavior, expected outcomes, and next actions.
- User guides must not define or override product policy, security controls, or architectural rules.
- User guides must not expose internal implementation mechanics unless the user must interact with them directly.
- User guides must not include internal branch names, migration notes, ORM details, or operator-only procedures.

## VI. Guide Families

The `docs/user-guides/` tree currently contains four primary guide families plus role entry points.

### 1. Role Manuals

Examples:
- `teacher_manual.md`
- `student_guide.md`
- `sysadmin_manual.md`

Rules:
- A role manual must act as an entry point, not a full duplicate manual.
- It must direct the reader to the correct diagnostics and feature guides.
- It should prioritize common tasks and common failure cases.

### 2. Feature Guides

Location:
- `docs/user-guides/features/`

Purpose:
- Explain how to complete a task or use a feature.

Rules:
- A feature guide must be task-oriented.
- It should describe prerequisites, the main steps, and the expected result.
- It should link to related diagnostics when a common failure mode exists.

### 3. Diagnostics

Location:
- `docs/user-guides/diagnostics/`

Purpose:
- Help a user quickly identify and resolve a problem.

Rules:
- A diagnostic guide must be symptom-oriented.
- It should start from what the user sees, not from the underlying implementation.
- It should prefer short decision paths, checks, and next actions.
- If escalation is required, it must state who to contact or what support path to use.

### 4. Legal

Location:
- `docs/user-guides/legal/`

Purpose:
- Present user-facing legal, license, attribution, and commercial-use information.

Rules:
- Legal pages must remain plain-language where possible.
- They must not rewrite or weaken the governing legal text.
- Cross-links between related legal pages should be explicit.

### 5. User-Facing Reference Guides

Examples:
- `economy_guide.md`

Purpose:
- Provide explanatory ranges, examples, and reference material for end users.

Rules:
- Reference guides may summarize or interpret normative behavior for users.
- They must not become the canonical source for enforcement rules.
- When a canonical normative document exists, the user guide should summarize user-visible outcomes and link to the canonical document only when appropriate for developers or advanced readers.

## VII. Metadata Rules

- User guides may use lightweight YAML frontmatter.
- Frontmatter is recommended when it improves navigation, search, role filtering, or related-link rendering.
- Frontmatter must remain minimal and user-safe.

Allowed metadata fields include:
- `title`
- `category`
- `description`
- `roles`
- `related`

- User guides do not require the formal numbered-document metadata table used by tracked ARC/SOP/FEAT documents.
- Frontmatter must never be used to store internal-only notes or maintainer instructions.

## VIII. Writing Style

- Use plain language and active voice.
- Prefer direct instructions and concrete outcomes.
- Use the terms users see in the interface.
- Keep paragraphs short and scannable.
- Prefer examples that match realistic classroom use.

User-guide prose must:
- answer "what do I do?"
- answer "what should I expect?"
- answer "what should I try next if this fails?"

User-guide prose must not:
- explain database structure
- explain internal access-control mechanics
- include code unless the page is explicitly for technical users and the code is directly actionable
- copy normative enforcement language unless the user truly needs the exact restriction

## IX. Structure Patterns

### Feature guide pattern

A feature guide should usually contain:

1. What the feature is for
2. What the user needs before starting
3. Step-by-step usage
4. What happens next
5. Related guides

### Diagnostic guide pattern

A diagnostic guide should usually contain:

1. The symptom
2. The most likely causes
3. Checks the user can perform
4. Recovery or workaround steps
5. Escalation path when self-service fails

### Role manual pattern

A role manual should usually contain:

1. Start-here links
2. Common questions
3. Links into feature and diagnostic sections

## X. Source-of-Truth Rules

- User guides are informative and user-facing.
- Normative repository documents remain the canonical source for architecture, policy, and operational governance.
- A user guide may summarize a normative rule only in terms of user-visible behavior.
- A user guide must not restate internal guarantees in a way that creates a competing source of truth.

Per `SOP-DOC-005`, the documentation site may source content from `docs/user-guides/` only.

## XI. Maintenance Rules

- When a user-facing workflow changes, the corresponding user guide must be reviewed in the same change.
- When a diagnostic path changes, the affected troubleshooting guides must be updated.
- New user-facing features should be added to the appropriate feature guide tree and linked from the relevant role manual when appropriate.
- Obsolete user guides should be removed or replaced rather than left as contradictory paths.

## XII. Amendment

Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.

# Historical Records Foundation

| Reference Number | Version | Effective Date | Supersedes | Authoritative |
|------------------|---------|----------------|------------|---------------|
| LOG-ARC-000      | 1.0     | 2026-03-01     | N/A        | NO            |

## I. Purpose
To classify, categorize, and define the storage of historical project notes, milestone completions, and version changelogs across the application's infrastructure.

## II. Scope
All descriptive and historical texts documenting past events rather than enforcing programmatic architectural behaviors. Examples include the `CHANGELOG.md` hierarchy and explicit release notes originally mapped under `SOP-REL` or major post-mortem incidents. 

## III. Authority Level
Non-normative. Reference only.

## IV. Archival Rules

### 1. The Immutable Record Principle
Release notes (e.g., `SOP-REL-015_RELEASE_NOTES_v1.8.0.md`) and global `CHANGELOG.md` entries are chronological ledgers. Once marked published against a specific `v*.*.*` git tag, these documents constitute a sealed history and must not be retroactively edited to describe new features. Subsequent changes require sequential subsequent entries.

### 2. Post-Mortem Documentation
Resolution of any P0 incidents (e.g., the legacy `CRITICAL_SAME_TEACHER_LEAK` data bleed) MUST generate a trailing descriptive document. These documents detail timelines, exploit conditions, and resolutions, and remain immutable after publication.

### 3. PII Prohibitions in Historical Records
Historical documents, debugging dumps, and milestone reports MUST NEVER contain any un-hashed raw production PII parameters. User IDs should substitute for usernames matching `.claude/rules/security.md` masking mandates.

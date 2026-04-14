# INV-ARC-002 — No Implicit Global Access

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-002      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Prevent global or unscoped data access from becoming execution truth.

## II. Scope

Applies to all domain and feature logic.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

No domain or feature logic may access global or unscoped data.

All data access MUST be explicitly scoped using `join_code` or `class_id`.

## VI. Amendment

Revisions must preserve explicit scoping requirements.

# INV-ARC-014 — No Label-Based Logic

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-014      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Prevent labels from becoming identity or scope authority.

## II. Scope

Applies to all runtime execution paths.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-009_Domain_Authority_for_State.md`

## V. Core Rule

Execution MUST NOT depend on:

- labels
- sections
- periods

Only canonical identifiers such as `class_id` and `join_code` may be used.

## VI. Amendment

Revisions must preserve canonical-identifier-only execution.

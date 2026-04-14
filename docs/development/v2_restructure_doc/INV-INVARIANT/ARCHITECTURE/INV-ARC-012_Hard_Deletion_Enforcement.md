# INV-ARC-012 — Hard Deletion Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-012      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the runtime consequences of hard deletion.

## II. Scope

Applies to deleted tenant or deleted scope references.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-011_No_Phantom_Scope_Access.md`

## V. Core Rule

Deleted scope MUST NOT be referenced by:

- requests
- background jobs
- domain operations

## VI. Amendment

Revisions must preserve hard deletion semantics.

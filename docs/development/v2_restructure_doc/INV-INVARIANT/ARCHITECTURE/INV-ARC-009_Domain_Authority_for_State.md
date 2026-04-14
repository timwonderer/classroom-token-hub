# INV-ARC-009 — Domain Authority for State

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-009      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define who is allowed to establish execution truth for state.

## II. Scope

Applies to all state evaluation used by runtime decisions.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-002_No_Implicit_Global_Access.md`

## V. Core Rule

Only domain queries may define authoritative state.

Feature logic MUST NOT recompute domain values as execution truth.

## VI. Amendment

Revisions must preserve domain-owned state authority.

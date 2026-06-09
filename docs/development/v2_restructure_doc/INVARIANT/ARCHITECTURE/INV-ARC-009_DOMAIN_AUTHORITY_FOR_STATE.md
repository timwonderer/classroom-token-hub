# INV-ARC-009: Domain Authority for State

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

- `INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`

## V. Core Rule

Only domain queries may define authoritative state.

Feature logic MUST NOT recompute domain values as execution truth.

## VI. Rebuild Intent

This rule exists to stop the rebuild from preserving route-level recalculation of
balances, status, or eligibility when the underlying truth belongs to a domain.

## VII. Downstream Consequence

`DOM` must expose authoritative reads, and `FEAT` must consume them rather than
rebuilding execution truth ad hoc.

## VIII. Amendment

Revisions must preserve domain-owned state authority.

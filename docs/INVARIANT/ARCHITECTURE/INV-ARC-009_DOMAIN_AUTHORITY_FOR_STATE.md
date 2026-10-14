# INV-ARC-009: Domain Authority for State

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-009      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Define who is allowed to establish execution truth for state.

## II. Scope

Applies to all state evaluation used by runtime decisions.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
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

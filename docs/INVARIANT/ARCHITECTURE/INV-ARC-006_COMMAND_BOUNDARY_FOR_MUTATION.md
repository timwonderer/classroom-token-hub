# INV-ARC-006: Command Boundary for Mutation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-006      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Define the mutation boundary for all runtime behavior.

## II. Scope

Applies to all state mutation.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md`

## V. Core Rule

All state mutation MUST occur inside explicit domain commands.

Mutation during:

- capability evaluation
- query execution
- request rendering

is forbidden.

## VI. Rebuild Intent

This rule exists to eliminate hidden writes in reads, feature-layer mutation shortcuts,
and cross-domain side effects disguised as helper behavior.

## VII. Downstream Consequence

`DOM` must own explicit mutation commands, and `FEAT` must never mutate state outside
those commands.

## VIII. Amendment

Revisions must preserve explicit command-only mutation.

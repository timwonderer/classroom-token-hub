# INV-ARC-012: Hard Deletion Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-012      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Define the runtime consequences of hard deletion.

## II. Scope

Applies to deleted tenant or deleted scope references.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.5, `Definite Class Lifecycle`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`

## V. Core Rule

Deleted scope MUST NOT be referenced by:

- requests
- background jobs
- domain operations

## VI. Rebuild Intent

This rule exists so deletion in the rebuilt app is real at runtime, not merely hidden
behind soft lifecycle semantics or leftover access paths.

## VII. Downstream Consequence

`DOM` and `FEAT` must not preserve deleted scope through convenience reads, jobs,
support flows, or cache-based survivorship.

## VIII. Amendment

Revisions must preserve hard deletion semantics.

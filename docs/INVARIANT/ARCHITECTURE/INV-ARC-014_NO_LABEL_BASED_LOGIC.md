# INV-ARC-014: No Label Based Logic

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-014      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Prevent labels from becoming identity or scope authority.

## II. Scope

Applies to all runtime execution paths.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.6, `Class Identity and Membership Model (Existence-Based)`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## V. Core Rule

Execution MUST NOT depend on:

- labels
- sections
- periods

Only canonical identifiers such as `class_id` may be used for runtime authority.
`join_code` may only be used as a boundary-ingress alias that resolves to
`class_id` before execution-time logic begins.

## VI. Rebuild Intent

This rule exists to prevent labels, sections, periods, and similar metadata from
re-entering the rebuilt app as identity, grouping, or authority shortcuts.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat labels as metadata only, never as canonical routing,
ownership, lifecycle, or execution keys.

## VIII. Amendment

Revisions must preserve canonical-identifier-only execution.

# INV-ARC-002: No Implicit Global Access

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-002      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Prevent global or unscoped data access from becoming execution truth.

## II. Scope

Applies to all domain and feature logic.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

No domain or feature logic may access global or unscoped data.

All data access MUST be explicitly scoped using `class_id`, or by a
`join_code` that has already been resolved to `class_id` at the boundary ingress.

## VI. Rebuild Intent

This rule exists to eliminate teacher-global shortcuts, unscoped balance use, and other
mixed-scope execution paths identified in the v2 rebuild audit.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat any unscoped read used for runtime truth as invalid, even if
the underlying field or helper still exists in the repository.

## VIII. Amendment

Revisions must preserve explicit scoping requirements.

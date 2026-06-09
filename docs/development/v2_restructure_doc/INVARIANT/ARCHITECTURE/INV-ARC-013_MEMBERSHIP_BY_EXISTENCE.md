# INV-ARC-013 — Membership by Existence

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-013      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the membership rule that governs runtime access.

## II. Scope

Applies to all membership and class-access decisions.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

Membership MUST be determined by existence of valid class association.

State-based membership flags are forbidden as runtime authority.

## VI. Rebuild Intent

This rule exists to eliminate lifecycle-state membership logic and to force access
control to rest on actual surviving class association.

## VII. Downstream Consequence

`DOM` and `FEAT` must not branch on active/inactive-style membership flags as authority.

## VIII. Amendment

Revisions must preserve existence-based membership.

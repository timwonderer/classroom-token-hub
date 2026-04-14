# INV-ARC-010 — Explicit Context Switching

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-010      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Ensure context changes are explicit and observable.

## II. Scope

Applies to all request or actor context switching.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-001` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

All context changes MUST be explicit.

Implicit reuse of prior request state is forbidden.

## VI. Amendment

Revisions must preserve explicit context switching.

# INV-ARC-011 — No Phantom Scope Access

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-011      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Prevent requests from succeeding against non-existent scope.

## II. Scope

Applies to all requests referencing tenant scope.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-004_Cross_Tenant_Isolation.md`

## V. Core Rule

Requests referencing non-existent `join_code` MUST fail.

No fallback or recovery logic is permitted.

## VI. Rebuild Intent

This rule exists to prevent the rebuild from papering over missing or deleted tenant
state with fallback lookups, alternate scope, or “best effort” recovery logic.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat non-existent scope as terminal for that request path.

## VIII. Amendment

Revisions must preserve hard failure for phantom scope.

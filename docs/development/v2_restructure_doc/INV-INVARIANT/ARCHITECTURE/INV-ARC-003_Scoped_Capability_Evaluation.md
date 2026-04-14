# INV-ARC-003 — Scoped Capability Evaluation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-003      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define how capability checks must evaluate scope.

## II. Scope

Applies to all capability checks.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

All capability checks MUST accept explicit context.

Capability evaluation without explicit class scope is invalid.

## VI. Requirements

- capability checks are side-effect free
- capability checks use explicit request-scoped context only
- capability checks are evaluated at request time

## VII. Amendment

Revisions must preserve request-scoped capability evaluation.

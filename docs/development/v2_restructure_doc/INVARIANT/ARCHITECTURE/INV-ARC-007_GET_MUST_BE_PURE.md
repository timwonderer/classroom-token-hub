# INV-ARC-007: GET Must Be Pure

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-007      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Preserve read purity in HTTP GET execution.

## II. Scope

Applies to all GET requests.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`

## V. Core Rule

GET requests MUST be side-effect free.

GET requests MUST NOT:

- commit
- flush
- trigger domain mutations

## VI. Rebuild Intent

This rule exists to remove the specific class of bugs where viewing a page changes
financial state, expires goals, settles balances, or repairs runtime data.

## VII. Downstream Consequence

Any rebuild design that requires mutation during `GET` is invalid and must be moved to a
command or job path instead.

## VIII. Amendment

Revisions must preserve read purity.

# INV-ARC-004 — Cross-Tenant Isolation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-004      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the one-tenant-per-request rule.

## II. Scope

Applies to all runtime requests and background execution paths.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

A single request MUST NOT:

- read across multiple `join_code` boundaries
- write across multiple `join_code` boundaries

All execution is constrained to a single tenant boundary.

## VI. Amendment

Revisions must preserve one-tenant-per-request execution.

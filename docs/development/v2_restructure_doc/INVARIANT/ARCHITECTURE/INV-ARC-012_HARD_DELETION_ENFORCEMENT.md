# INV-ARC-012: Hard Deletion Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-012      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the runtime consequences of hard deletion.

## II. Scope

Applies to deleted tenant or deleted scope references.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

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

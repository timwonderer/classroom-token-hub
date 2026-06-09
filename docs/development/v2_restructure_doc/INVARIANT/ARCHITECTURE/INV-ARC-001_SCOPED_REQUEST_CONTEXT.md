# INV-ARC-001: Scoped Request Context

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-001      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the required request context for all request-time decision making.

## II. Scope

Applies to all runtime actions that evaluate capability or execute domain commands.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-ARC-000_EXECUTION_MODEL.md`

## V. Core Rule

All requests MUST construct explicit request context containing:

- `class_id`
- `join_code`
- `actor_id`
- `actor_type`
- `request_id`
- `timestamp`

Requests missing required scope MUST fail immediately.

## VI. Rebuild Intent

This rule exists to prevent the rebuild from falling back to route-local assumptions,
implicit session carryover, or actor-only access patterns that bypass tenant scope.

## VII. Downstream Consequence

`DOM` and `FEAT` must assume that missing request context is a hard failure, not a cue to
infer or repair scope implicitly.

## VIII. Amendment

Revisions must preserve explicit scope requirements and alignment with `INV-ARC-000`.

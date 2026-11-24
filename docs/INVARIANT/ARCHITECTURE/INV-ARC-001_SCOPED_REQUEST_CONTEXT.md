# INV-ARC-001: Scoped Request Context

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-001 | 1.2 | 2026-11-23 | 1.1 | Constitutional |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Define the required request context for all request-time decision making.

## II. Scope

Applies to all runtime actions that evaluate capability or execute domain commands.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-000_EXECUTION_MODEL.md`

## V. Core Rule

Class-scoped requests MUST construct explicit request context containing:

- `user_id`
- `class_id`
- `seat_id`
- `actor_type`
- `request_id`
- `timestamp`

> [!IMPORTANT]
>
> Although `user_id` is included in every context construction, `user_id` should only be used for the following cases:
> 1. `seat_id` look up within the `class_id` boundary provided
> 2. Verifying session validity 
> 3. principal-scoped authentication, credential maintenance and recovery
> 4. account deletion

Requests missing required scope MUST fail immediately.

### Principal and system execution scopes

Authentication and principal-owned credential maintenance SHALL construct explicit
principal context: authenticated `user_id`, principal role, request identifier,
canonical time, and the session/challenge/generation evidence required by Identity.
They SHALL NOT require, infer, select or fabricate `class_id` or `seat_id`.
This context is not a class-scoped `canonicalContext` and grants no classroom access.
Missing active class selection does not prevent otherwise eligible maintenance.

Credential reconciliation has explicit principal-operation or system execution
context under INV-ARC-019 and FEAT-IDEN-108. System authority is restricted to the
provider registry and Identity's minimal credential/operation state; it grants no
classroom reads or mutations and does not impersonate a teacher or sysadmin.
Every execution re-evaluates current domain authority. Missing required scope for
its declared operation fails closed; this is not a generic missing-context bypass.

## VI. Rebuild Intent

This rule exists to prevent the rebuild from falling back to route-local assumptions,
implicit session carryover, or actor-only access patterns that bypass tenant scope.

## VII. Downstream Consequence

`DOM` and `FEAT` must assume that missing request context is a hard failure, not a cue to
infer or repair scope implicitly.

## VIII. Amendment

Revisions must preserve explicit scope requirements and alignment with `INV-ARC-000`.

**2026-11-23 amendment:** Records the owner-approved credential lifecycle scope, activation, reconciliation and retention boundaries. Class isolation and foundational lifecycle requirements remain unchanged.

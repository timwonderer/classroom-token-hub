# SPEC-DISPLAY-001: Display Metadata Resolver

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-DISPLAY-001 | 1.1 | 2026-10-12 | SPEC-DISPLAY-001 v1.0 | Normative |

---

## I. Purpose

This document is the normative build specification for the Display Metadata Resolver.

The resolver creates a per-request display object from canonical identity and class references so templates and route view builders can render names, class labels, join codes, teacher notes, class timezone, section labels, and other display-only artifacts without each page independently re-querying for them. Per section VII, the object is request-scoped only and must never be persisted to the session or any other cross-request store.

This resolver does not establish authority. It does not answer whether an actor may do something. Authorization, scope, and actor identity remain the responsibility of Canonical Context resolution and capability evaluation.

---

## II. Authority

This specification is subordinate to:

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `docs/DOMAIN/DOM-IDEN-007_Identity_Models_and_References.md`

If this document conflicts with a higher-level invariant or domain document, the higher-level document prevails.

---

## III. Core Principle

The Display Metadata Resolver answers one question:

> How should this canonical actor and class be presented here?

It must not answer:

- What makes this actor authorized?
- Which class or seat is authoritative?
- Whether a route, FEAT, or domain operation may execute?
- Whether a user should be treated as a teacher, student, or system actor?

Those questions belong to `CanonicalContext` and capability evaluation.

Display metadata is a presentation contract, not an authority contract.

---

## IV. Canonical Inputs

The resolver accepts only:

```python
CanonicalContext | None
```

For class-scoped display metadata, `CanonicalContext` must contain:

| Field | Requirement |
|---|---|
| `class_id` | Required |
| `seat_id` | Required when actor-specific display metadata is needed |
| `user_id` | Required for context identity (`context_key`) |
| `actor_role` | Required for actor-role display selection |

The resolver may return `None` when no class-scoped canonical context exists.

Callers must not pass legacy identifiers such as `student_id`, `teacher_id`, `join_code`, `block`, or `admin_id` as resolver authority.

---

## V. Authoritative Sources

The resolver may read display metadata from these canonical owners only:

| Source | Owned Display Facts |
|---|---|
| `ClassEconomy` | `class_id`, `join_code`, class display name, class timezone, section label, teacher owner user reference |
| `Seat` | classroom-local operational identity reference used to locate display profile |
| `IdentityProfile` | first name, last name, teacher notes, user-facing display metadata |

The resolver must not use helper tools that derive or reinterpret class identity outside `ClassEconomy`.

Specifically:

- Join code must be read from `ClassEconomy.join_code`.
- Display names must be read from `IdentityProfile`.
- Teacher display metadata must resolve through the teacher's canonical `Seat` and `IdentityProfile`.
- Class display metadata must resolve through `ClassEconomy`.

---

## VI. Return Object

The resolver must return a `DisplayMetadata` object.

Minimum fields:

| Field | Meaning |
|---|---|
| `context_key` | Stable identity string derived from canonical context (`user_id`/`seat_id`/`class_id`/`actor_role`); used for equality checks, not caching |
| `user_id` | Display copy of canonical user id |
| `seat_id` | Display copy of canonical seat id |
| `class_id` | Display copy of canonical class id |
| `actor_role` | Display copy of canonical actor role |
| `join_code` | Display join code from `ClassEconomy` |
| `class_display_name` | User-facing class label |
| `class_identifier` | Template-compatible class label |
| `class_timezone` | Class timezone for display/page context |
| `section` | Class section label from `ClassEconomy` |
| `actor_first_name` | Actor first name from `IdentityProfile` |
| `actor_last_name` | Actor last name from `IdentityProfile` |
| `actor_full_name` | Actor display full name |
| `student_first_name` | Student display first name when actor is student |
| `student_last_name` | Student display last name when actor is student |
| `student_full_name` | Student display full name when actor is student |
| `teacher_first_name` | Teacher display first name |
| `teacher_last_name` | Teacher display last name |
| `teacher_display_name` | Teacher display full name |
| `teacher_note` | Display note from actor `IdentityProfile` |

The return object must not expose `block`, `block_display`, `period`, or any block-shaped alias. Those names are not valid v2 template contract fields. Templates that still require them must be rewired to `section`, `class_display_name`, or a page-specific view-model field documented by the relevant template audit row.

---

## VII. Cache Contract

`DisplayMetadata` must not be cached in the Flask session, or in any other
store that persists across requests on the client. It carries decrypted PII
(`actor_first_name` and its siblings) by design (section VI); the Flask
session is a signed but unencrypted cookie, so writing `DisplayMetadata`
there puts that PII at rest in plaintext on the client, in conflict with
`INV-CORE-000` section 2 and `INV-ARC-018` section VII.1.

v1.0 of this document allowed exactly that caching (audit finding S10).
Operator ruling (Tim, 2026-10-12): resolving `DisplayMetadata` fresh from the
database on every request is cheap, so there was no real tradeoff being made
by caching it, and no reason to accept the PII-at-rest exposure for it. This
revision removes the allowance rather than narrow it.

The resolver must therefore recompute `DisplayMetadata` on every call.
Implementations may hold it only for the lifetime of the single request that
resolved it (for example, an in-memory variable or a `flask.g` attribute
scoped to that request) — never across requests, and never anywhere that is
serialized back to the client.

Because there is no cross-request cache, there is nothing to invalidate on
class/seat switch, name change, note change, or logout: every one of those
requests already recomputes `DisplayMetadata` from current canonical context.

---

## VIII. Required Public API

The implementation must live at:

```text
app/utils/display_metadata.py
```

The public names exported by this module must include:

```python
DisplayMetadata
resolve_display_metadata
get_or_resolve_display_metadata
```

Per section VII, `get_or_resolve_display_metadata` must not read or write any
cross-request cache; it exists only because callers already use that name.

Route handlers and context processors may call `get_or_resolve_display_metadata(ctx)` after canonical context has been resolved.

Domain services, FEAT implementations, and authorization code must not depend on `DisplayMetadata`.

---

## IX. Prohibited Patterns

The following are prohibited:

- Using display metadata as an authorization source.
- Resolving display metadata from `student_id`, `teacher_id`, `admin_id`, or legacy model identity.
- Using join code as canonical class scope.
- Calling a join-code helper instead of reading `ClassEconomy.join_code`.
- Duplicating display names onto unrelated domain tables.
- Querying `IdentityProfile` by `IdentityProfile.id` as an application identifier.
- Exposing `block`, `block_display`, `period`, or block-shaped display aliases from the resolver.
- Using `block`, `block_display`, or `period` as scope, route authority, capability input, query authority, or template contract.
- Letting templates independently query display metadata.
- Letting Jinja call database-backed helpers for display identity.

---

## X. Template and View Model Contract

Templates should receive display metadata through a stable display object or through page view models built from that object.

Page view models that consume display metadata should remain domain-owned or page-owned presentation contracts. A page may compose multiple display-safe objects, but it should not collapse them into a generic shared builder that re-exposes raw business primitives.

Templates may render:

- actor display name;
- student display name;
- teacher display name;
- class display name;
- section;
- join code;
- teacher note;
- class timezone/display metadata.

Templates must not use those values to decide scope, ownership, authorization, mutation authority, or domain eligibility.

Route handlers must continue to use `CanonicalContext` and registered FEAT/domain boundaries for those decisions.

---

## XI. Test Requirements

Targeted tests should prove:

1. Resolver returns `None` without class-scoped canonical context.
2. Resolver reads join code from `ClassEconomy.join_code`.
3. Resolver reads actor display names from `IdentityProfile`.
4. Resolver reads teacher display names through teacher `Seat` plus `IdentityProfile`.
5. Resolver does not use join code as class authority.
6. Resolver output does not expose `block`, `block_display`, `period`, or block-shaped aliases.
7. `DisplayMetadata` is never written to the Flask session (audit S10 regression guard).
8. Two calls to `resolve_display_metadata` with the same canonical context return independently-resolved, equal results — proving no cross-request cache is in play.

Recommended test file:

```text
tests/dom/identity/test_SPEC_DISPLAY_001__display_identity_metadata_resolver.py
```

---

## XII. Definition of Done

`SPEC-DISPLAY-001` is implemented when:

- `app/utils/display_metadata.py` exports the required public names;
- class metadata resolves from `ClassEconomy`;
- display names and notes resolve from `IdentityProfile`;
- teacher display metadata resolves through canonical teacher seat/profile references;
- `DisplayMetadata` is recomputed on every request and never persisted to the session or any other cross-request store (section VII);
- route/template display contracts use the resolver or page view models derived from it;
- no FEAT, domain service, or authorization path uses display metadata as authority;
- no display resolver path calls legacy join-code helpers or legacy identity identifiers.
- no resolver output includes `block`, `block_display`, `period`, or block-shaped aliases.

---

## XIII. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the effective date.
3. Remain subordinate to `DOM-IDEN-007`.
4. Preserve the separation between operational authority and display metadata.
5. Distinguish display aliases from canonical scope.

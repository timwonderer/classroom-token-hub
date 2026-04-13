# ARC-OPS-005: API Reference

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-005      | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the architectural contract for HTTP and API-facing execution in
Classroom Token Hub.

It does not aim to list every route exhaustively. It defines the request-model rules
that API surfaces and route-backed action endpoints must obey.

## II. Scope

This document applies to:

- JSON APIs
- action-oriented HTTP endpoints
- route families with runtime significance
- authentication class boundaries at the API layer

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-013_Money_Handling.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/SYSADMIN/ARC-SYS-001_Sysadmin_Interface.md`

## V. Core API Rule

Every API-facing action must obey the same execution sequence:

1. construct explicit request context
2. validate actor class and tenant boundary where applicable
3. evaluate required capabilities
4. execute at most one allowed mutation command path
5. return response

APIs do not get a weaker contract than HTML-backed routes.

## VI. Authentication Classes

The API layer recognizes four architectural actor classes:

- public
- student
- teacher admin
- system admin

Actor class determines entry eligibility only. It does not replace capability
evaluation.

## VII. Tenant-Scoped API Rule

Any student-facing or teacher-facing class-scoped API must be explicitly tied to one
tenant boundary.

Architectural requirements:

- the request must identify or derive one tenant boundary
- out-of-scope tenant access must fail
- teacher-global or student-global shortcuts must not replace tenant validation
- APIs must not read or write across multiple tenant boundaries in one request

## VIII. Read And Write Boundary

API read endpoints must remain pure reads.

API write endpoints must:

- execute only after capability evaluation
- mutate state only through explicit domain commands
- remain tenant-scoped when class behavior is involved

The API layer must not hide mutation inside convenience reads.

## IX. Public API Rule

Public APIs may exist only for explicitly public routing or verification flows.

Architectural requirements:

- public identity references may be used where architecture permits
- public endpoints must not expose tenant-scoped actor data beyond their declared public
  contract
- public requests must not backdoor into privileged execution

## X. Student API Rule

Student APIs must execute only within the student's active and authorized tenant
context.

Architectural requirements:

- student actions must validate tenant membership
- student capability checks must be request-time and side-effect free
- student APIs must not rely on unscoped financial or identity state

## XI. Teacher Admin API Rule

Teacher-admin APIs must execute only within the teacher's authorized tenant boundary.

Architectural requirements:

- selected class context must be explicit
- teacher identity alone does not authorize class mutation
- class-scoped admin actions must validate membership or equivalent tenant authorization
  before mutation

## XII. Sysadmin API Rule

Sysadmin APIs are platform APIs, not tenant-scoped teacher substitutes.

Architectural requirements:

- sysadmin routes must remain platform-level
- sysadmin APIs must not expose tenant-scoped student data directly
- sysadmin APIs must not trigger tenant-scoped mutation unless a separate constitutional
  document explicitly authorizes it

## XIII. Response Contract Rule

API responses must reflect the request-time decision model clearly.

Architectural requirements:

- deny results should be explainable
- scope failures must fail explicitly
- actor-class mismatch must fail explicitly
- APIs must not silently downgrade or reinterpret scope

## XIV. Route Family Guidance

The repository contains route families such as:

- public verification and session utility endpoints
- student action endpoints
- teacher-admin action endpoints
- sysadmin platform endpoints

This document governs those families by contract, not by exhaustive inventory.

Detailed FEAT documents may later define specific endpoint behavior, but they must
derive from this API contract rather than redefining it.

## XV. Prohibited Patterns

The following are forbidden:

- GET endpoints that mutate application state
- class-scoped APIs that authorize via `teacher_id` alone
- unscoped financial checks in student or teacher APIs
- public endpoints that expose privileged or tenant-invasive behavior
- sysadmin endpoints that serve as hidden tenant-management tools

## XVI. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

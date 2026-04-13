# ARC-SYS-001: Sysadmin Interface

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-SYS-001      | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the architectural boundary of the sysadmin interface.

It governs what kind of platform-level interaction the sysadmin layer may perform and,
equally importantly, what it may never do inside tenant-scoped application behavior.

## II. Scope

This document applies to:

- sysadmin authentication and actor boundary
- platform monitoring surfaces
- platform support surfaces
- platform-wide teacher-account administration
- non-tenant-invasive observability and control functions

This document does not define teacher workflows and does not grant class-scoped runtime
authority.

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`

## V. Core Boundary Rule

The sysadmin interface is a platform boundary, not a tenant-management shortcut.

A sysadmin actor may manage the platform and teacher accounts, but may not enter
tenant-scoped runtime authority merely by virtue of being a sysadmin.

## VI. Allowed Sysadmin Interaction Categories

The sysadmin layer may perform only platform-level interaction categories such as:

- platform observability
- platform health review
- platform support triage
- teacher-account administration
- platform-wide communication where explicitly authorized
- security and access-control administration at the platform layer

These are platform actions, not teacher or student actions.

## VII. Tenant Isolation Constraints

The sysadmin layer must remain outside tenant-scoped execution.

Sysadmin actors must not:

- access tenant-scoped student data directly
- act as a substitute teacher inside a class boundary
- mutate tenant-scoped state
- cross tenant boundaries under a single support action
- use platform privileges to bypass tenant capability evaluation

The architecture must make this impossible by design, not merely discouraged by policy.

## VIII. Observability Rules

Sysadmin observability must be aggregate, explainable, and non-tenant-invasive.

Allowed observability principles:

- platform health metrics may be exposed
- tenant-derived aggregates may be exposed when they do not reveal tenant-scoped
  student data
- alerts may reference internal routing anchors only when needed to preserve
  determinism and support workflow

Disallowed observability patterns:

- direct student record browsing through sysadmin surfaces
- transaction-history drill-down for tenant-scoped actors
- support tooling that becomes a hidden backdoor into class runtime behavior

## IX. Support And Escalation Boundary

Sysadmin support functions are coordination functions.

They may:

- triage issues
- review platform-level signals
- manage teacher-facing escalation workflows
- coordinate remediation at the platform level

They may not:

- operate tenant workflows on behalf of teachers
- inspect tenant-scoped runtime data beyond the aggregate and non-invasive limits
  defined by architecture
- resolve application behavior by bypassing tenant boundaries

## X. Teacher Administration Boundary

The sysadmin layer may administer teacher accounts and teacher access mechanisms because
those are platform-level concerns.

This authority does not extend to:

- class-scoped data ownership
- student-scoped operations
- teacher action impersonation inside a class

Teacher-account administration and class authority are separate concerns.

## XI. Platform Communication Boundary

Sysadmin communication surfaces may broadcast platform-level information only where the
architecture explicitly defines them as platform-wide.

Platform communication must not become a side channel for tenant-scoped mutation or
tenant-specific enforcement.

## XII. Prohibited Patterns

The following are forbidden:

- sysadmin impersonation of teacher or student actors
- tenant-scoped data access through support tooling
- administrative convenience paths that bypass capability evaluation
- platform-level routes that trigger tenant-scoped mutation
- observability tools that expose more than aggregate or non-invasive information

## XIII. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- ARC docs must treat sysadmin as a separate platform actor class
- DOM docs must not expose tenant mutation paths to sysadmin actors unless a later
  constitutional document explicitly authorizes them
- FEAT docs for `/sysadmin` must remain platform-level and must not collapse into
  teacher-admin or student behavior

## XIV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

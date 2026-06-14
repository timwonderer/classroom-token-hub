# INV-CORE-000: Core Invariants
| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|INV-CORE-000| 2.0 | 2026-06-13 | 1.1 |Foundational|

## I. Purpose
This document defines the core invariants, or underlying principles, that drives the design of this application. Any future development of this application must stay within the boundaries of these invariants. This document serves as top level authority in which all other levels of authority derives from.

For documentation writing standards, please see SOP-DOC-000 and SOP-DOC-001

## II. Scope
The invariants in this document applies to:

- All services
- All routes
- All migrations
- All background jobs
- All domains, features, and visual elements

## III. Core Invariants
The following invariants shall be interpreted as hard boundaries that must be observed at all time. Invariants in this section are cumulative and non-negotiable. A valid implementation must satisfy all invariants simultaneously.

### 1. `class_id` Centric Isolation

#### Statement
All data access and mutation operations must be scoped to a single `class_id`. `class_id` defines the boundary in which actors operate. `join_code` is a human-facing alias for `class_id` and MUST resolve to `class_id` before any authority-sensitive operation. Within a class, `seat_id` anchors all actor-scoped state.

#### Constraints
- No actor may access a `class_id` boundary they are not bound to.
- No financial operation may be performed without explicit `class_id` scope.
- All domain services must accept `class_id` as an explicit parameter. Services may accept `join_code` for convenience but must resolve it to `class_id` before any authority-sensitive operation.
- No global settings, attributes, logs, or ledgers are allowed within the application.
- Scoped data associated with a `class_id` must not survive its deletion unless explicitly re-scoped under a separate `class_id` context.

#### Prohibited Action
- Any operation that accesses or mutates data across `class_id` boundaries not assigned to the actor explicitly.

- Any role or privilege that allows for cross-class action.

---
### 2. Minimal Use and Storage of PII

#### Statement
The system stores only the minimum personally identifiable information required for functional identity binding. Any stored PII must be one-way hashed unless recovery of original content is required (e.g. display name for greeting).

#### Constraints
- No raw DOB storage of any kind
- No full name storage beyond initial claim
- PII must be nullified or deleted immediately after fulfillment of its identity-binding purpose unless explicitly required by invariant-defined functionality.
- No contact method of any kind can be stored, processed, or requested.

#### Prohibited Action
- Retention of PII beyond its defined functional purpose.
- PII stored as plaintext.

---
### 3. Deterministic and Traceable Financial Logic

#### Statement
All finance-related actions must be immutably logged and traceable. Financial outcomes must be deterministically reproducible from ledger state and configuration at time of execution.

#### Constraints
- Any edits of finance-related log entry must be visible to all actors within the class.
- Reversal action creates new counter-entry, not removal of previous action.
- Full financial history within the `class_id` scope must be fully traceable.
- Changes to financial configuration shall not retroactively alter prior ledger outcomes.

#### Prohibited Action
- Deletion or silent mutation of financial ledger entries.

---
### 4. Principal and Actor Authority

#### Statement
Authority is strictly scoped to defined principals and actors. The system distinguishes between the authentication principal (`users.id`), the operational actor (`seats.id`), and the isolation boundary (`classes.class_id`). No principal or actor may exercise cross-class or cross-domain privileges beyond its invariant-defined scope.

#### Constraints
- Teacher principals must only access `class_id` boundaries they own.
- Role transition must require explicit context change and re-authentication where applicable.
- System administrator must not be able to access or alter any `class_id` scoped instances.
- A demo seat must behave identically to a regular seat.

#### Prohibited Action
- Any mechanism that enables privilege escalation or hidden impersonation within the application domain.

---
### 5. Definite Class Lifecycle

#### Statement
`class_id` defines the boundary in which ledger entries, attendance records, and analytics reside. Destruction of a class must also destroy all data linked to that `class_id`.

#### Constraints
- No cross-class global ledger or historical archive retaining deleted class data is permitted within the application domain.
- Deletion of a class must also delete all linked data entries.
- Database backup and restoration must not be used to restore accounts.
- When a seat is deleted with its class, if the owning user has no remaining seats in any class, the user MUST be deleted from the system entirely.
- Stale classes and their associated seats must be automatically deleted and their data purged.

#### Prohibited Action
- Storage of `class_id` linked data or accounts after a deletion action has been completed.
- Retention of recoverable financial history after class deletion.

---
### 6. Class Identity and Membership Model (Existence-Based)

#### Statement
Class and membership are existence-based, not lifecycle-based. A `class_id` either exists or does not exist. Membership represents existence within a class, not a state.

#### Constraints
- `class_id` is the sole authority for class identity and boundary.
- A class MUST NOT have lifecycle states such as "active", "inactive", or "archived".
- Membership MUST NOT use lifecycle labels (e.g., `status`, `is_active`). Membership exists if and only if a seat record exists for a given `class_id`.
- Seat state within a class is limited to:
  - `unclaimed` (teacher-provisioned placeholder)
  - `claimed` (identity established via user binding)
- Labels such as `block`, `period`, `section`, or display names are metadata only and MUST NOT be used for identity, scoping, grouping, or lifecycle decisions.
- All settings, aggregates, and operations MUST be scoped by `class_id` (or its public alias `join_code`), not by labels.

#### Deletion Semantics
- Removing a seat from a class erases that seat from that class context entirely, as if they never existed in that class.
- If a user has no remaining seat associations in any class, the user MUST be deleted from the system entirely.
- Deletion logic MUST be driven by surviving seat associations under `class_id` only.

#### Prohibited Action
- Branching logic on class or membership lifecycle labels (e.g., `if status == "active"`).
- Using labels (`block`, `period`, `section`) as identifiers or join/filter keys for ownership or lifecycle.
- Retaining seat or user records after their last `class_id` association is removed.
- Any cleanup or preservation rule based on labels or legacy identifiers instead of `class_id`.

---
### 7. No Unnecessary Barriers to Supported Use

#### Statement
All supported functions within the system shall be accessible to intended users through readily available assistive technologies. Supported use must remain perceivable, understandable, navigable, and operable across the product's interface, wording, theming, and support surfaces.

#### Constraints
- User-facing flows must prioritize functional clarity over local stylistic preference.
- Accessibility is part of the supported-function contract, not an optional enhancement.
- Visual design choices, theming, component styling, and interaction patterns must not introduce avoidable obstacles to reading, navigation, comprehension, focus, or task completion.
- Wording, labels, instructions, and documentation must be standardized enough to reduce avoidable ambiguity for intended users.
- Help, support, and operational guidance that the product depends on must not omit or obscure information required to perform supported functions.
- User-facing standardization may vary by audience or context only when the variation removes confusion rather than introducing it.

#### Prohibited Action
- Introducing interface, wording, documentation, or design decisions that create avoidable friction for intended users when the underlying function is supported.
- Treating accessibility, clarity, or support discoverability as optional polish rather than functional requirements.
- Using local visual or copy conventions that materially reduce usability, comprehension, or operability without an invariant-defined reason.

---
## IV. Identity Model Reference

The canonical identity and ownership model is defined in
`INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`. The settled identity chain is:

- `users.id` — authentication principal
- `seats.id` — operational actor
- `classes.class_id` — isolation boundary
- `seats.public_id` — canonical deidentified public actor identity
- `identity_profiles` — display-only identity

Identity resolution and seat-scope enforcement rules are defined in
`INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`.

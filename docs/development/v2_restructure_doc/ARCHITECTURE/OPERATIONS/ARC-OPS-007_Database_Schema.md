# ARC-OPS-007: Database Schema

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-007      | 2.0     | 2026-04-12     | 1.3        | Constitutional  |

## I. Purpose

This document defines the architectural database contract that supports the realigned
v2 runtime model.

It is not a dump of every model field. It identifies the runtime-significant schema
structures, the canonical keys they expose, and the coexistence rules needed where the
repository currently contains overlapping or transitional representations.

## II. Scope

This document applies to:

- tenant identity and membership structures
- actor identity structures
- ledger and balance structures
- analytics and observability structures
- runtime-significant class-scoped tables
- schema coexistence rules for overlapping model generations

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-013_Money_Handling.md`

## V. Schema Reading Rule

The repository currently contains more than one generation of data structures in some
areas.

This document therefore distinguishes between:

- canonical runtime authority structures
- supporting runtime structures
- transitional or overlapping structures that still exist in the repo

Presence in the schema does not automatically mean architectural authority.

## VI. Canonical Tenant Structures

### `class_economies`

`class_economies` is the canonical class anchor table.

Architectural role:

- `join_code` is the public tenant locator
- `class_id` is the canonical internal class anchor
- row existence defines class existence

This table is the root of the tenant boundary.

### `class_memberships`

`class_memberships` is the canonical membership authority table.

Architectural role:

- membership existence determines class access
- membership is scoped by tenant boundary
- teacher and student class access must derive from membership existence, not labels or
  teacher-global shortcuts

### `seats`

`seats` is a runtime-significant class association structure linking class scope and
student participation.

Architectural role:

- binds class-specific participation to the tenant anchor
- supports dual identification through `join_code` and `class_id`
- must remain subordinate to the canonical tenant boundary rather than replacing it with
  a second independent scope system

## VII. Canonical Actor Identity Structures

### `teachers`

`teachers` is the runtime authority table for teacher actors.

Architectural role:

- stores admin-side actor identity
- exposes stable public teacher identity
- supports non-plaintext authentication identity

### `system_admins`

`system_admins` is the runtime authority table for system-admin actors.

Architectural role:

- represents platform actors
- must remain separate from tenant-scoped teacher or student actors

### `students`

`students` is the runtime student actor container, but not by itself the authority for
class membership.

Architectural role:

- stores actor identity and credential-related state
- participates in class scope through tenant-bound structures, not standalone
  student-global authority

### Supporting Identity Structures

The repository also contains identity-supporting structures such as:

- `users`
- `identity_profiles`
- onboarding and invite tables

These may be active supporting structures, but they do not override the tenant and
actor-boundary rules above.

## VIII. Canonical Monetary Structures

### `transactions`

`transactions` is the canonical ledger table for monetary history.

Architectural role:

- append-only record of monetary movement
- tenant-scoped financial truth
- source of reproducible financial outcomes

### `balance_cache`

`balance_cache` is a tenant-scoped performance structure for ledger-derived balances.

Architectural role:

- supports efficient balance reads
- remains subordinate to ledger authority
- must not become an independent money source of truth

### Related Monetary Structures

Other runtime-significant monetary tables include:

- `payroll_cache`
- `student_items`
- `student_insurance`
- `insurance_claims`
- `rent_payments`
- `rent_waivers`

These structures may hold domain-specific state, but monetary truth still derives from
tenant-scoped ledger behavior.

## IX. Canonical Analytics And Observability Structures

### `analytics_snapshots`

Stores deterministic aggregate artifacts derived from tenant-scoped runtime state.

### `analytics_alerts`

Stores platform-facing alert artifacts derived from analytics snapshots or equivalent
deterministic aggregate inputs.

### Observability And Support Structures

Runtime-significant support and observability structures include, where present:

- issues and issue lifecycle tables
- request trace or correlation tables
- error logging tables
- support intake tables

These structures may reference tenant anchors or actor anchors, but must not become
alternate tenant-authority systems.

## X. Runtime-Significant Class-Scoped Tables

The repository contains multiple class-scoped tables that participate in runtime
behavior, including examples such as:

- `tap_events`
- `student_blocks`
- `hall_pass_logs`
- `announcements`
- feature or policy setting tables
- other class-scoped domain tables carrying `join_code`, `class_id`, or both

Architectural rule:

- when these tables participate in class-scoped runtime behavior, they must resolve to
  the canonical tenant boundary
- auxiliary fields such as `teacher_id`, labels, or legacy ownership hints do not become
  class-boundary authority merely because they exist in the same row

## XI. Coexistence Rules For Overlapping Schema Generations

Because the repository contains overlapping generations of schema design, the following
rules apply:

- canonical architectural authority is determined by the ARC layer, not by age of table
  or field
- overlapping fields may coexist temporarily in the repo without sharing equal runtime
  authority
- transitional aliases, compatibility fields, and dual-write bridges must not be treated
  as target architecture

Examples of coexistence patterns that require care:

- `join_code` and `class_id` appearing together on runtime tables
- student-global actor records coexisting with class-scoped participation structures
- compatibility synonyms or lookup aliases remaining present while no longer defining new
  behavior
- analytics and support tables referencing tenant anchors for routing while not becoming
  tenant execution surfaces

## XII. Canonical Key Rules

The architectural key rules are:

- tenant boundary authority is anchored by `class_economies` and `class_memberships`
- public tenant routing uses `join_code`
- internal class anchoring uses `class_id`
- teacher public routing uses stable public teacher identity
- monetary truth is tenant-scoped through ledger structures

Any schema interpretation that elevates teacher-global keys, labels, or compatibility
aliases above these canonical anchors is invalid.

## XIII. Prohibited Schema Interpretations

The following are forbidden:

- treating every extant field as equal authority
- using compatibility aliases as the basis for new runtime contracts
- assuming a table is canonical merely because it is older or more widely referenced
- treating teacher ownership tables as class-boundary authority
- treating caches, snapshots, or support tables as domain truth

## XIV. Architectural Consequences For Later Layers

This document constrains later layers as follows:

- API and feature docs must reference canonical schema authority, not incidental fields
- domain docs must identify owned truth structures without inventing new authority
  hierarchies
- implementation planning must distinguish between canonical structures and transitional
  coexistence

## XV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

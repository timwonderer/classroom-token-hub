# ARC-SYS-002: Deterministic Analytics Alerting Pipeline

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-SYS-002      | 2.0     | 2026-04-12     | 1.0        | Constitutional  |

## I. Purpose

This document defines the architectural rules for deterministic analytics snapshots and
sysadmin alerting.

Its purpose is to allow platform health monitoring without turning analytics or support
flows into hidden tenant-access channels.

## II. Scope

This document applies to:

- analytics snapshots
- analytics alert generation
- sysadmin alert review surfaces
- aggregate monitoring derived from tenant-scoped application behavior

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/SYSADMIN/ARC-SYS-001_Sysadmin_Interface.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-013_Money_Handling.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-015_Multi_tenancy_and_Join_Code_Interface.md`

## V. Core Analytics Rule

Analytics and alerting may observe tenant-derived system behavior only through
deterministic aggregate artifacts.

Analytics must not become a backdoor into tenant-scoped runtime inspection.

## VI. Snapshot Architecture

The system may create immutable analytics snapshots for a single tenant boundary at a
specific time.

Snapshot rules:

- each snapshot is tenant-scoped
- each snapshot is time-scoped
- each snapshot is aggregate, not actor-invasive
- each snapshot is derived from authoritative domain state

Snapshots are read models for observability, not alternate domain truth.

## VII. Determinism Rule

Analytics outputs and alert decisions must be deterministic for a given snapshot input
and threshold configuration.

Architectural requirements:

- the same tenant state and threshold set must produce the same alert result
- alert reasoning must be explainable from stored aggregate inputs
- alert generation must not depend on hidden operator judgment or manual intervention

## VIII. Isolation Rule

Analytics processing must preserve tenant isolation.

Requirements:

- snapshot generation must not merge tenant execution truth across class boundaries
- alert generation must not require student-level inspection inside sysadmin surfaces
- internal routing identifiers may be retained only to support deterministic platform
  handling, not to expose tenant data

Tenant-derived aggregates are allowed. Tenant-invasive observability is not.

## IX. Mutation Boundary

Analytics and alerting must not mutate application runtime behavior as a side effect of
observation.

The following are forbidden:

- alert generation that mutates tenant-scoped economic state
- snapshot generation that repairs tenant data implicitly
- sysadmin review flows that trigger tenant-scoped commands

Observation and intervention are separate architectural concerns.

## X. Alert Model

Alerts may exist only as deterministic interpretations of aggregate state.

Architectural requirements:

- alert identity must be tied to a deterministic condition
- alert severity must derive from declared rules
- alert lifecycle may track platform handling state such as active, acknowledged, or
  resolved
- alert context must remain aggregate and non-invasive

## XI. Sysadmin Review Boundary

Sysadmin actors may review alerts only at the platform layer.

They may:

- inspect aggregate alert context
- acknowledge or resolve alert lifecycle state
- coordinate teacher-facing follow-up

They may not:

- drill from alert context into tenant-scoped student records
- use alert tooling to perform tenant-scoped mutation
- bypass tenant isolation by claiming observability need

## XII. Data Minimization For Alerts

Alert context must contain only what is necessary to explain why the alert exists.

Allowed context:

- aggregate metrics
- threshold comparisons
- deterministic reason descriptors
- internal tenant anchors required for platform routing

Disallowed context:

- direct student identities
- raw transaction histories
- sensitive tenant-level details not required for the alert decision

## XIII. Prohibited Patterns

The following are forbidden:

- analytics as hidden tenant inspection tooling
- non-deterministic alert generation
- alert-triggered tenant mutation
- student-level drill-down through sysadmin alert interfaces
- cross-tenant aggregation used as request-time execution truth for tenant behavior

## XIV. Architectural Consequences For Later Layers

This document constrains the rest of the system as follows:

- analytics domain work must produce aggregate, deterministic artifacts
- sysadmin features must consume those artifacts without crossing into tenant behavior
- later FEAT docs for alert dashboards must remain observational and platform-scoped

## XV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

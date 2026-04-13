# ARC-OPS-000: Operational Constraints

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-000      | 2.0     | 2026-04-12     | 1.0        | Constitutional  |

## I. Purpose

This document defines the operational constraints that the application runtime must obey
so the architectural model remains enforceable in practice.

These constraints exist to preserve deterministic execution, tenant isolation, and
observability integrity across environments.

## II. Scope

This document applies to:

- runtime environments
- background execution
- dependency and infrastructure assumptions
- operational observability
- retention and lifecycle enforcement

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-012_Datetime_Handling_Specification.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/SYSADMIN/ARC-SYS-002_Deterministic_Analytics_Alerting_Pipeline.md`

## V. Core Operational Rule

Operations must preserve the architectural contract.

No deployment mode, support habit, or runtime shortcut may bypass:

- tenant isolation
- request-time capability evaluation
- explicit command boundaries
- deterministic financial and observability behavior

## VI. Environment Rule

All environments must preserve the same core execution assumptions, even when feature
flags, sample data, or support tooling differ.

Environment differences must not create:

- alternate authority models
- relaxed tenant isolation
- hidden mutation paths that do not exist elsewhere

## VII. Background Execution Rule

Background jobs are subject to the same architectural rules as request-driven actions.

Architectural requirements:

- jobs must operate with explicit scope
- jobs must not cross tenant boundaries implicitly
- jobs that mutate state must do so through explicit command paths
- observational jobs must remain observational

## VIII. Dependency Rule

Operational dependencies must support deterministic runtime behavior.

Architectural requirements:

- dependency changes that affect data handling, time handling, auth handling, or
  persistence semantics require architectural review
- infrastructure must not force the app into unscoped fallback behavior

## IX. Performance Rule

Performance goals exist to support architectural correctness, not to justify breaking
it.

Architectural consequences:

- caching must not replace domain truth
- performance shortcuts must not skip capability evaluation
- operational pressure must not justify write-on-read patterns

## X. Observability Rule

Operational observability must remain compatible with tenant isolation and platform
boundaries.

Requirements:

- request and job traces may capture routing and decision metadata
- observability must not become tenant-invasive debugging by default
- operational logging must support diagnosis without breaking actor or tenant boundaries

## XI. Retention And Lifecycle Rule

Operational retention must remain subordinate to invariant-defined deletion and data
lifecycle semantics.

Architectural requirements:

- stale or deleted tenant data must not persist inside active application behavior
- operational artifacts inside the application domain must respect deletion boundaries
- backups and external operational systems do not redefine in-app architectural truth

## XII. Prohibited Patterns

The following are forbidden:

- operational shortcuts that bypass tenant validation
- background mutation without explicit scope
- environment-specific authority behavior
- performance fixes that convert reads into hidden writes
- observability surfaces that expose tenant-scoped student data to platform actors

## XIII. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

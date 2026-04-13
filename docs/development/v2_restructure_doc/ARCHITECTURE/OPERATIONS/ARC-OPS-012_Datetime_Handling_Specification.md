# ARC-OPS-012: Datetime Handling Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-012      | 2.0     | 2026-04-12     | 1.1        | Constitutional  |

## I. Purpose

This document defines the architectural rules for datetime creation, persistence,
comparison, transmission, and display in Classroom Token Hub.

Its purpose is to preserve deterministic behavior across request handling, jobs,
deadlines, and observability.

## II. Scope

This document applies to:

- persisted datetimes
- request-time datetime use
- deadline and expiration logic
- API datetime transmission
- client-side datetime rendering

## III. Authority Level

Constitutional (ARC Tier). Subordinate to:

- `docs/development/v2_restructure_doc/INV-CORE-000_Core_Invariants.md`
- `docs/development/v2_restructure_doc/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

## IV. Dependencies

- `docs/development/v2_restructure_doc/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md`

## V. Core Datetime Rule

Persisted datetimes must be UTC-aware and comparable without ambiguity.

Localization is a presentation concern except where a business rule is explicitly based
on a local calendar interpretation before conversion to UTC.

## VI. Creation Rule

Current-time generation must be centralized and explicit.

Architectural requirements:

- request and job code must use a shared UTC-aware time source
- direct ad hoc time creation that risks naive datetimes is forbidden

## VII. Persistence Rule

Persisted datetimes must be stored as UTC-aware values.

Architectural requirements:

- stored datetime values must be UTC-aware
- persistence defaults must preserve that rule
- schema and model definitions must not normalize naive storage as acceptable

## VIII. Comparison Rule

All datetime comparisons used for execution truth must occur between normalized
UTC-aware values.

Architectural consequences:

- expiry, due-date, and scheduling logic must not compare mixed naive and aware values
- normalization must occur at system boundaries before comparison

## IX. Local Calendar Rule

Some business rules may originate from teacher-local calendar meaning.

Architectural requirements:

- local-calendar interpretation must occur explicitly
- the resulting execution instant must be converted to UTC before persistence or
  comparison
- client-local browser time must not redefine server-side deadline semantics

## X. API Rule

API datetime transmission must remain unambiguous.

Architectural requirements:

- API payloads must carry UTC-aware datetime representations
- transmitted datetimes must include timezone information
- APIs must not transmit browser-localized execution truth

## XI. Client Rule

The client may localize timestamps for display only.

Architectural consequences:

- client rendering may transform UTC display values for presentation
- client rendering must not become the source of deadline or authorization logic
- client-localization utilities must remain presentation helpers

## XII. Observability Rule

Request traces, logs, alerts, and support artifacts must use consistent datetime
semantics.

Architectural requirements:

- observability timestamps must be comparable across requests and jobs
- ambiguous or mixed datetime semantics are architectural defects

## XIII. Prohibited Patterns

The following are forbidden:

- persisting naive datetimes intentionally
- comparing naive and aware datetimes in execution paths
- API payloads without timezone-qualified execution timestamps
- client-side timezone logic redefining server-side business rules

## XIV. Amendment

Revisions to this document require a version increment, an updated Effective Date, and
continued consistency with the locked invariant and foundation documents named above.

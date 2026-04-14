# INV-ARC-005 — No PII Leakage in Execution Layer

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-005      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Restrict PII exposure in execution-time context and observability artifacts.

## II. Scope

Applies to request context, logs, and execution-layer telemetry.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` and `INV-ARC-000`.

## IV. Dependencies

- `INV-ARC-001_Scoped_Request_Context.md`

## V. Core Rule

Request context and logs MUST NOT contain sensitive personal information beyond allowed
invariant-defined fields.

## VI. Rebuild Intent

This rule exists so the rebuild does not solve observability or support gaps by pushing
more PII into request context, logs, or platform tooling.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat execution-layer observability as compatibility with minimal
PII, not an excuse to widen data exposure.

## VIII. Amendment

Revisions must preserve minimal PII exposure in execution paths.

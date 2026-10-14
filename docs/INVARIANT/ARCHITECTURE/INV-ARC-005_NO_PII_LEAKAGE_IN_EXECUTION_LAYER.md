# INV-ARC-005: No PII Leakage in Execution Layer

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-005      | 1.1     | 2026-10-14     | 1.0        | Constitutional   |

> [!IMPORTANT]
> **v1.1 (2026-10-14), developer-documentation modernization pass.** Corrected a mislabeled Authority Level: this is a Tier 1 (`INV-ARC`) document and must read **Constitutional**, not Foundational -- "Foundational" is reserved for `INV-CORE` (Tier 0). No substantive rule in this document changed.

## I. Purpose

Restrict PII exposure in execution-time context and observability artifacts.

## II. Scope

Applies to request context, logs, and execution-layer telemetry.

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.2, `Minimal Use and Storage of PII`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

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

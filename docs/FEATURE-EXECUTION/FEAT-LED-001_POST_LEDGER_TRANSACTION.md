# FEAT-LED-001: Post Ledger Transaction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-001 | 1.5 | 2026-10-03 | 1.4 | Normative |

## I. Purpose

Define the canonical Ledger posting domain-command contract for resolved monetary plans, composed by each originating business FEAT inside its single atomic execution context.

## II. Scope

All class-scoped monetary movements, including payroll, purchases, fines, corrections and internal transfers. Posting does not decide business eligibility or transform intended monetary plans.

Independent monetary verification incorporates [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md) §III–V, including explicit account reconciliation boundaries for both reconstruction surfaces and unavailable outcomes for missing proof inputs. This read contract does not authorize settlement during a proof query.

## III. Authority Level

Normative; subordinate to `INV-CORE-000` §III.1,3–6, `INV-CORE-001` §III, VIII, `INV-ARC-006` §V, `INV-ARC-009` §V, `INV-ARC-016` §V, and `INV-ARC-021` §V, VII. `FEAT-CORE-000` §II–V requires one atomic FEAT context. This contract incorporates `SPEC-LED-002` §§III–VIII through `DOM-LED-001` §VII.1–1A.

## IV. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md`

## V. Execution Context and Inputs

The initiating FEAT invokes the Ledger posting command, never executes a second FEAT. It supplies canonical `class_id`, actor/target seat context, `mechanism`, initiating `feat_code`, `idempotency_key`, `correlation_id`, and a resolved Ledger plan with signed integer-cent effects, account targets, type, policy references where applicable, and immutable lineage. An internal transfer has exactly two equal-and-opposite legs with one transfer correlation identity. A single credit/debit is not modeled as an invented source/destination account transfer.

The required command reservation identity is `(class_id, feat_code, idempotency_key)`. Ledger defines the canonical immutable command representation, replay fingerprint and `fingerprint_version`; callers cannot supply arbitrary serialized fingerprint material. Compensation effects additionally carry the Ledger-owned original public locator, attributable compensation cents and opaque correction-intent locator under `DOM-LED-001` §VII.1A, VIII.1. The proposed `payroll_correction` type is authorized for a later implementation; no runtime enum or migration is asserted here.

## VI. Verification and Atomic Posting

1. Resolve or create the permanent command reservation within the originating FEAT transaction. On a reservation conflict, compare the fingerprint and version. An exact replay returns the accepted command outcome and its effects; a mismatch returns `REPLAY_MISMATCH` with no new effect. A read-only preview cannot reserve a command.
2. Validate account targets, shared anchors and all effects within `class_id`. Balance-dependent commands hold the seat lock, then ClassEconomy, then any compensation-origin lock, then pending rows/snapshots in the existing deterministic order through commit. Payroll settlement uses the same seat lock when eligibility and compensation can race.
3. Require the resolved plan to remain valid under current domain authority. Revalidate bounded recovery under the original-transaction lock; sum attributable compensation across exact reversals and partial/residual corrections, excluding funding-transfer legs and fees. Do not reinterpret owning-domain interval evidence.
4. Allocate each effect's immutable class-scoped posting sequence through the Ledger effect-creation command before INSERT. Freeze reservation linkage, command key, initiating FEAT and all protected inputs; append the effects for the single creation audit in step 5. The lawful Ledger settlement command reconciles account snapshots/cursors and may initialize the informational UTC `posted_at` receipt; it never patches signed transaction fields or persisted status. All required effects and settlement changes commit or roll back together. Pending/posted state remains reconciliation-derived; do not mutate original transaction lifecycle fields.
5. Invoke the Operations audit command in the same FEAT context and transaction. No direct Ledger-to-Operations domain invocation is permitted.

## VII. Constraints and Replay

- Only a plan resolved through the domain-command workflow described by `FEAT-LED-000` may post. Posting does not insert fees or protection transfers itself.
- Checking may become negative for a lawful charge/deduction after the shared full-shortfall funding rule; the former transaction-type-based checking nonnegativity rule is superseded. Own-account transfers retain sufficient-funds requirements, no protection and no fees.
- Internal transfers conserve cents; compensation cannot exceed the original credit. Full reversal is eligible only while the original credit is uncompensated.
- The reservation identity stays occupied permanently, including after reversal or correction. One reservation may own multiple effects. A transaction-row unique key or a bare “get or create by key” cannot substitute for command identity and fingerprint comparison.
- Different keys cannot authorize a second recovery for the same correction intent. Duplicate intent and exhausted recovery are owning-domain outcomes, not fresh monetary authority.

## VIII. Audit Requirements

Operations records class/actor/target seat anchors, initiating FEAT, reservation identity and fingerprint version, correlation, resolved signed effects and account targets, compensation-origin/intent locators where applicable, attributable recovery, and success or denial reason. No PII or unrestricted personal notes are introduced. Failed atomic posting leaves no durable partial business or monetary result.

## IX. Change Notes

**1.3 (2026-10-03)** supersedes 1.2's transaction-row key lookup, global key uniqueness, FEAT-to-FEAT execution language, two-account-only input shape and transaction-type-based checking nonnegativity. Establishes permanent command reservations and bounded compensation posting under the higher-authority Ledger contracts. This is a documentation change; existing callers and runtime behavior are not certified by it.

**1.4 (2026-10-03)** supersedes step VI.4's ambiguous settlement-time sequence assignment. Creation allocates the immutable sequence before signing; settlement advances account-scoped reconciliation projections only. Historical signatures remain unchanged.

## X. Amendment

Increment the version and effective date, identify superseded rules, and preserve the governing INV and DOM hierarchy. Runtime implementation requires separate code and migration work.

### Version 1.5: immutable accepted command replay (2026-10-03)

Explicitly incorporates SPEC-LED-002 v1.2: version-4 effect-plan fingerprints bind the complete immutable vector and FEAT-established business intent, while the transfer family retains its exact two-leg serializer. Stored versions 1–3 remain interpreted under their original payload contracts. Replay resolves accepted effects before current prices, balances, fees, or protection and fails closed for changed canonical intent; no accepted history is re-signed or rewritten.

# FEAT-PROD-003: Record Payroll Event

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-003 | 1.4 | 2026-10-03 | 1.3 | Normative |

## I. Purpose

Record append-only payroll business events and compose their monetary effects through owning domain commands inside one atomic FEAT context, preserving original payroll and attendance facts.

## II. Scope

Covers attendance-based payroll credits, manual credits, exact whole-event reversal, and residual recovery after prior compensation. Interval invalidation is coordinated by FEAT-PROD-005; both FEATs may invoke PROD's `record_payroll_event` command. Class-level settlement under FEAT-PROD-004 likewise composes that domain command and the monetary/audit commands inside its own transaction and command namespace, consuming this contract without executing this FEAT. This document does not authorize direct persistence writes or nested FEAT execution.

## III. Authority Level

Normative; subordinate to INV-CORE-000 §III.1–6, INV-CORE-001 §III, VIII, DOM-PROD-001 §VII–XI, XV, and DOM-LED-001. INV-ARC-006 §V–VII and INV-ARC-009 §V–VII require owning domain commands and authoritative queries. INV-ARC-021 §V, VII and FEAT-CORE-000 §II–V require one FEAT context and transaction, with no direct domain-to-domain calls.

## IV. Dependencies

- [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §VIII.3–6, XI.3–4, XIII, XV — payroll business authority and lawful writers.
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) — monetary amounts, balances, compensation linkage, and aggregate recovery cap.
- [DOM-IDEN-006](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md) §VII–XI — canonical context and scoped actor/target resolution.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md) §VII, X and [DOM-CLASS-002](../DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md) §V, VII — authoritative configuration and funding applicability.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5 — protected mutation lineage.
- [DOM-ITR-001](../DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md) §VIII–IX — preserve completed observations; no Interpretation command is executed by a correction.
- [FEAT-CORE-000](FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md) §II–V — single orchestration and transaction.
- [FEAT-LED-000](FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md) §VII, XI and [FEAT-LED-001](FEAT-LED-001_POST_LEDGER_TRANSACTION.md) — incorporated domain-command resolution and posting contracts, never second FEAT execution.
- [FEAT-LED-002](FEAT-LED-002_VOID_REVERSE_TRANSACTION.md) — exact full reversal contract; partial/residual corrections are separately authorized here.
- [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) — incorporated settlement membership, pricing provenance, and correction interaction contract.
- [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md) §III–V and [SPEC-LED-002](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) §III–VIII — incorporated monetary proof, reservation, replay, and concurrency requirements.
- [SPEC-ECON-003](../SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md) §4.5.1.1 — incorporated funding rule; payroll corrections incur no NSF fee.
- [SPEC-OPS-001](../SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md) §II (2.3), III, X — artifact-specific correction, not generic undo.
- [INV-ARC-008](../INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md), [INV-ARC-015](../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md) §VI–VII, [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, IX–XI — seat, UTC/class-local time, and audit authority.
- [SPEC-TIME-001](../SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md) — incorporated temporal primitives.

## V. Inputs and Pure Preview

Required inputs: `ctx` (`CanonicalContext`), `target_seat_id`, `idempotency_key`, `mechanism` (`TEACHER` or `SYSTEM`), `payroll_run_type` (`payroll`, `manual_credit`, `reversal`, or `correction`), `correlation_id`, and structured business intent. `reference_time_utc` may supply a deterministic evaluation timestamp.

For manual credit, the caller may supply the explicit lawful credit intent. A teacher-entered manual credit requires no payroll policy; another domain's policy-priced credit retains that calculation's provenance. For attendance payroll, the caller cannot select a pricing policy: PROD establishes original policy inputs for each canonical interval. A class with no payroll settings cannot price payroll, but its earlier attendance remains eligible unless separately invalidated.

Recovery additionally requires `original_payroll_event_id` and `expected_preview_identity`; `correction` here means `RESIDUAL_RECOVERY`. The caller supplies no recovery amount. Pure preview composes PROD business authority, Ledger's original credit/attributable compensation and resulting balance queries, and Class Configuration's protection settings. It returns the original settlement, previous recovery, proposed remaining recovery, protection transfer, projected balances, and an opaque identity covering those authoritative facts. It performs no writes, flush, reservation, or commit (INV-ARC-007 §V).

## VI. Canonical Execution

1. Resolve current canonical actor/class context and target seat through Identity. For recovery, require the class-bound teacher and domain-owned capability checks. No target identity or cached preview grants authority.
2. Resolve accepted command replay before fresh pricing, balance reads, or temporal evaluation. Command identity is `(class_id, originating_feat_code, idempotency_key)`. Exact immutable intent returns the original business and Ledger result; mismatched intent fails closed. Monetary commands use Ledger reservations under SPEC-LED-002, not transaction-level uniqueness. Original result locators resolve through owning domain queries.
3. For a new command, serialize with payroll, interval invalidation, and all recovery on `(class_id, target_seat_id)`. Lock target seat first, then ClassEconomy, original credit, then pending/snapshot monetary sources under the common Ledger order. Multi-seat runs lock target seats in stable identifier order. Requery authority after serialization.
4. Resolve canonical time once. For payroll, PROD establishes eligible, completed, not previously settled intervals, original settings, exact seconds, and allocation-version 1 inputs. Preserve per-setting aggregate quantization once; retain interval IDs, credited seconds, original rates, and policy identifiers in `summary_json` under SPEC-PROD-001. Persist no monetary totals or earnings cache in PROD.
5. For recovery, establish original business permission through PROD and obtain Ledger's proven original amount and compensation total. Revalidate preview identity against current authoritative facts. A changed preview denies before any business or monetary effect.
6. Compose intended, resolved, and applied monetary plans through Ledger domain commands. Append the PROD payroll event through `record_payroll_event` (and its specialized recovery commands). All business records, reservations, protection legs, monetary effects, protected audit evidence, and correlation bindings commit together exactly once. Any failure rolls back every effect.

### Exact reversal

`record_payroll_reversal` appends `payroll_event_type = reversal`, reuses the original `correlation_id` and original policy/cycle lineage, and posts the exact negative of the original credit through the whole-entry reversal contract. It is lawful only if Ledger proves zero previous attributable compensation. It never mutates the original row or attendance.

### Residual correction

`record_payroll_correction` appends `payroll_event_type = correction` with `original_payroll_event_id` and `correction_intent = RESIDUAL_RECOVERY` in `summary_json`, retaining policy/cycle provenance and opaque Ledger locators. It uses a new correction correlation and a Ledger-owned payroll-correction effect, not a partial `REVERSAL` or `VOID`.

Ledger determines remaining recovery as original credited cents minus prior attributable compensation cents and enforces the aggregate cap. Protection transfer legs carry no attributable compensation. If remaining recovery is zero, deny `ALREADY_RECOVERED` without a new correction or debit; exact replay of a prior successful command still returns its original result. Partial interval corrections followed by residual correction recover exactly the original credit, never more.

### Funding

For a charge/deduction leaving checking negative, protection enabled plus sufficient savings transfers the entire shortfall atomically. Insufficient savings remains untouched; the full deduction posts and checking may become negative. Disabled protection transfers nothing. Own-account transfers retain their sufficient-funds rule. Payroll corrections incur no NSF fee and create no obligation or deferred deduction.

## VII. Temporal and History Rules

Timestamps persist UTC and display/evaluate in canonical class time. Only `payroll` events advance payroll windows and automatic scheduled occurrences. `manual_credit`, `reversal`, and `correction` are non-boundary events. Corrections retain historical pricing and never advance or reopen an economic cycle, rewrite completed Interpretation, or turn reversed/corrected work into unpaid work. Class-level completion remains governed by FEAT-PROD-004.

## VIII. Denials and Acceptance

Deny unauthorized context/scope, missing target/original event, unavailable original settlement or compensation proof, preview changes, replay mismatch, absent pricing settings for payroll, unlawful policy provenance, exact reversal after partial compensation, already-complete recovery, and integrity failure. Report unavailable historical evidence explicitly; do not fabricate linkage or use current rates as a substitute. A failure never commits partial business or monetary state.

Targeted contract scenarios: positive payroll retains exact allocation inputs; teacher manual credit needs no policy; $45 payment with $15 attributable interval recovery permits only $30 residual recovery; full reversal before invalidation leaves later eligibility invalidation with no debit; same-key replay returns original recovery and different-key recovery cannot exceed the cap; concurrent payroll/invalidation serializes; cross-class and unprovable-history commands fail closed. Verify funding examples through SPEC-PROD-001 and preserve lifecycle destruction under DOM-PROD-001 §VII.1.a.

## IX. Amendment

Version 1.4 (2026-10-03) supersedes v1.3's exclusive payroll writer, whole-event-only recovery, and pre-command-reservation execution wording. This amendment authorizes domain-command writes coordinated by FEAT-PROD-003 and FEAT-PROD-005, exact uncompensated reversal, and residual correction. Runtime implementation is not included. Revisions must increment version/date, identify superseded rules, and preserve governing INV and DOM contracts.

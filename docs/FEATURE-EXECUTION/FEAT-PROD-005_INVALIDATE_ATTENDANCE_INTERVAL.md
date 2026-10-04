# FEAT-PROD-005: Invalidate Attendance Interval

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-005 | 1.3 | 2026-10-03 | 1.2 | Normative |

## I. Purpose

Authorize a teacher to invalidate one completed work interval and atomically compensate any attributable original payment while preserving original attendance, payroll, monetary, and completed Interpretation facts.

## II. Scope

Completed canonical opening/closing attendance pairs for one student seat in one class. Invalidation is terminal: no restore, re-eligibility, freeform notes, attendance mutation, or generic undo. This contract authorizes documentation scope; runtime implementation is not included.

## III. Authority Level

Normative, subordinate to INV-CORE-000 §III.1–6 (isolation, minimal PII, financial traceability, actor and lifecycle), INV-CORE-001 §III, VIII (hierarchy/capabilities), and DOM-PROD-001 §VII–XI, XIII, XV. SPEC requirements are incorporated below through owning DOM/FEAT authority, not independently executable.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6; [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V–VII; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V–VII — commands, pure reads, and domain-owned conclusions.
- [INV-ARC-008](../INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md) §V; [INV-ARC-015](../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md) §VI–VII; [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, IX–XI — seat resolution, time, and protected lineage.
- [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII; [FEAT-CORE-000](FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md) §II–V — one FEAT transaction and no nested FEAT/domain-to-domain execution.
- [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §VII–XI, XIII, XV — canonical pair, terminal eligibility, settlement membership, lawful invalidation/correction writers, and preserved boundaries.
- [DOM-IDEN-006](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md) §VII–XI — current actor and target scope.
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md); [FEAT-LED-000](FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md) §VII, XI; [FEAT-LED-001](FEAT-LED-001_POST_LEDGER_TRANSACTION.md); [FEAT-LED-002](FEAT-LED-002_VOID_REVERSE_TRANSACTION.md) — Ledger-owned monetary resolution, compensation cap, and distinct exact reversal.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md) §VII, X; [DOM-CLASS-002](../DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md) §V, VII — configuration and protection applicability.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5 — registered immutable protected fields and audit commands.
- [DOM-ITR-001](../DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md) §VIII–IX — completed records remain immutable; this FEAT writes no Interpretation record.
- [FEAT-PROD-001](FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md), [FEAT-PROD-003](FEAT-PROD-003_RECORD_PAYROLL_EVENT.md), [FEAT-PROD-004](FEAT-PROD-004_COMPLETE_PAYROLL_CYCLE.md) — preserved attendance, full/residual recovery, and cycle-completion contracts; none is executed by this FEAT.
- [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) — incorporated interval identity, original allocation/provenance, historical evidence, terminal eligibility, and serialization contract.
- [SPEC-TIME-001](../SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md); [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md) §III–V; [SPEC-LED-002](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) §III–VIII — incorporated time, monetary proof, and reservations/replay.
- [SPEC-ECON-003](../SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md) §4.5.1.1; [SPEC-OPS-001](../SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md) §II (2.3), III, X — incorporated shared protection rule and artifact-specific correction limits.

These are declared FEAT-level cross-domain dependencies. PROD never calls another domain or holds an internal cross-domain FK. Ledger and audit references are opaque locators.

## V. Inputs and Pure Preview

Command inputs: canonical teacher `ctx`, `target_seat_id`, `opening_event_id`, `closing_event_id`, `reason_code`, `idempotency_key`, and `expected_preview_identity`. Reasons are exactly `INVALID_ATTENDANCE`, `NON_WORK_ACTIVITY`, and `DUPLICATE_PARTICIPATION`. No monetary amount or unrestricted personal note is accepted. The FEAT generates the correction correlation, normalizes recorded time to UTC, and propagates its command identity and sanitized intent to domain commands.

A pure read composes Identity actor/target resolution; PROD completed-pair, eligibility, settlement-membership, and business permission queries; Ledger original credit, compensation proof, and balance queries; and Class Configuration protection queries. It returns original scans and credited duration, eligibility separately from settlement state, original settlement evidence, proposed recovery, savings transfer, resulting balances, and opaque expected-preview identity. For an unpaid interval, preview requires canonical closed-work and eligibility evidence only: proposed compensation is zero, protection transfer is absent, and no payment, pricing, or funding/balance permission is required. Work recorded before any payroll setting remains invalidatable under DOM-PROD-001 §XV.6. Preview neither reserves nor writes/flushes/commits. The identity covers pair/source evidence, invalidation state, protected lineage, and settlement disposition; for paid work it additionally covers original allocation inputs/version, original credit and compensation state, and any applicable protection configuration/balance inputs; a client cannot grant authority with it.

## VI. Atomic Command

1. Resolve current canonical context and class-bound teacher capability; prove target seat belongs to that class. Fail closed without authority before returning scoped records.
2. Resolve command replay by `(class_id, FEAT-PROD-005, idempotency_key)` before fresh temporal, eligibility, pricing, or balance evaluation. Compare versioned canonical intent digest including class, actor, target, pair, reason, and expected preview identity. Exact replay returns the accepted original receipt and resolves its original monetary result through Ledger, without recalculation or a second audit/business effect. Mismatch denies `REPLAY_MISMATCH`.
3. For new intent, acquire shared serialization in target-seat → ClassEconomy → original-credit → pending/snapshot-source order. Payroll, invalidation, exact reversal, and residual recovery use the same order; multi-seat payroll locks seats by stable identifier. Query canonical pair and eligibility again after serialization. A different key for an already-invalidated pair denies `ALREADY_INVALIDATED`.
4. PROD establishes whether the canonical closed interval is unpaid or belongs to an original settlement. Unpaid work needs no payroll setting, original payment, pricing, compensation, or funding proof. Only for the paid branch, PROD establishes original membership/pricing provenance and the FEAT obtains all Ledger source/candidate proof requirements, invokes Operations' pure typed creation-evidence query for each required record, and passes the complete scoped evidence into Ledger. Ledger matches this evidence to its current locked source records, verifies original payment and compensation facts and derives allocated attributable recovery under SPEC-PROD-001. Historical paid membership, rates, allocation, or totals that cannot be proven deny the entire paid action. Preserve original per-setting cent quantization and largest-remainder allocation; never reprice with current rates.
5. Recompute pure preview through the same domain authorities and compare expected identity under serialization. Changed inputs deny `PREVIEW_CHANGED`, with no eligibility or monetary mutation. Resolve canonical timestamp once for acceptance.
6. If unpaid, append only `attendance_interval_invalidation` through PROD's domain command, plus its immutable receipt and lawful protected audit evidence. If previously fully recovered, do the same with zero new monetary effect. A paid zero-cent allocated interval likewise needs no debit or correction event. Previously settled work remains settled.
7. If paid with positive unrecovered allocation, compose Ledger `build_intended_ledger_plan`, `resolve_intended_ledger_plan`, and `apply_resolved_ledger_plan` domain commands. Append invalidation and a `correction` payroll event through PROD domain commands; `summary_json` records `original_payroll_event_id`, `correction_intent = INTERVAL_INVALIDATION`, invalidation ID, original policy/cycle provenance, and opaque Ledger result locators. Store no monetary amount in PROD.
8. Commit once with invalidation, receipt, correction event where applicable, Ledger reservation/effects and protection legs, compensation linkage, and protected audit evidence. Any failure rolls back all business and monetary effects. No nested FEAT, deferred recovery, obligation, or Interpretation recomputation is authorized.

The invalidation creation command freezes its eleven protected business fields at INSERT, including the complete receipt. Operations emits once after row identity exists and initializes `lineage_event_id`, `lineage_token`, and `lineage_version` together within the same creating transaction; linkage is opaque and excluded from its own payload. Deferred database structural and application payload guards reject missing, partial, replaced or late linkage. Commit is the permanent immutability boundary for linkage and never a permission to change business fields.

The immutable protected `receipt_json` on the invalidation record contains `expected_preview_identity`, `fingerprint_version`, `canonical_intent_digest`, `original_settlement_disposition`, and `opaque_outcome_locators` (no amounts or balances). It preserves unpaid/previously recovered/zero-cent outcomes even when no Ledger reservation exists. Monetary effects use Ledger's command reservation; all protection legs belong to that same command. Ledger owns `compensation_origin_locator`, nonnegative attributable recovery, and correction intent linkage; transfer legs contribute zero to recovery. The sum of exact reversal, interval corrections, and residual recovery cannot exceed the original credit.

### VI.1 Historical business-proof integration gate

SPEC-PROD-001 §VI.1 is incorporated only as the conditional original-business evidence standard for a later integration. DOM-PROD-001 §XV.9 and FEAT-PROD-006 §VI.1 define the separate future pure historical evaluation. This FEAT does not execute another FEAT, substitute diagnostic replay for original membership, or enable a historical fallback through this amendment. Any later approved integration must compose the owning PROD, Policies, Ledger and Operations interfaces inside this FEAT and declare its full implementation dependencies before activation.

Original source-set completeness/visibility, per-event writer and original setting/quantization must independently satisfy the conditional contract. A positive business mapping or newly derived historical attribution does not establish original lawful monetary creation/posting or complete compensation. Existing §VI.4 paid evidence requirements remain cumulative; v1 gaps, unsigned reversal linkage and unknown compensation still deny the entire paid command without eligibility-only commit. The current 153 priced candidates remain diagnostic, and no new writer, proof adoption, preview fallback, API or runtime enablement is authorized here.

### VI.2 Historical graph integration remains separately gated

SPEC-PROD-001 §VI.2 is incorporated as the separate conditional multi-payment evidence/allocation standard only. DOM-PROD-001 §XV.10, DOM-LED-001 §IX.4 and FEAT-PROD-006 §VI.2 define future pure graph evaluation; this FEAT executes none of them as another FEAT. The later integration must compose PROD, Policies, Ledger, Operations, Identity and Class Configuration interfaces directly within one FEAT context and declare implemented dependencies before activation. No current preview, receipt/writer schema or recovery path is expanded by this amendment.

All original fragment/remainder/top-up credits require independently proven graph membership, original source visibility/writer/settings, exact allocation and lawful monetary creation/posting and complete compensation. Positive top-up credit is additional original money; do not count it as prior recovery or omit its legitimate allocation. Ambiguous prior partial recovery attribution denies the whole paid action. A fully recovered or zero-cent graph still requires complete proof before eligibility-only invalidation. Future atomic recovery locks every origin in stable Ledger locator order after target seat and ClassEconomy and before monetary sources, revalidates complete preview/compensation, and uses one reservation for all recovery/funding legs. Each origin preserves its individual cap and recovery-intent uniqueness. Any missing origin or failure leaves no eligibility, correction, reservation, audit or partial funding result. Original receipts must bind the complete graph/attribution and all opaque outcome locators under a separately reviewed schema/protocol extension; do not silently fit a graph into the current single-original-event receipt. This documentation authorizes no such persistence extension or activation.

## VII. Funding, History, and Lifecycle

Enabled protection transfers the entire checking shortfall from savings only if savings can fund it entirely; otherwise savings is untouched and checking takes the full deduction below zero. Disabled protection transfers nothing. Own-account transfers retain sufficient-funds rules. Payroll corrections incur no NSF fee, obligation, or deferred deduction.

Eligibility invalidation does not alter scans, attendance duration, hall-pass consumption, payroll windows, scheduled occurrences, original payroll entries, completed cycles, or completed Interpretation records. Reversed or corrected work never re-enters unpaid eligibility. Target-seat or class destruction removes the new PROD business records atomically under DOM-PROD-001 §VII.1.a; deletion of the acting seat alone does not license destroying a surviving target's evidence.

## VIII. Denials and Verification

Stable outcomes: `UNAUTHORIZED_SCOPE`, `INCOMPLETE_INTERVAL`, `INVALID_REASON`, `ALREADY_INVALIDATED`, `PREVIEW_CHANGED`, `PROVENANCE_UNAVAILABLE`, `REPLAY_MISMATCH`, and `INTEGRITY_FAILURE`. Missing/foreign endpoints are denied without exposing another class's records. Malformed/noncanonical pairs are incomplete/invalid intervals, not an invitation to infer endpoints. Unverified, invalid, or degraded evidence is distinguished under INV-ARC-016 §VI; none supplies the missing proof required for correction.

Verify SPEC-PROD-001 worked examples: unpaid exclusion with intact scans; exact-cent paid recovery; multi-interval conservation; partial then residual recovery; prior full recovery with no new debit; same-key/different-key duplicates; concurrent payroll; insufficient/sufficient/disabled protection; cross-class denial; unavailable historical evidence; whole-transaction rollback; lifecycle destruction. Targeted checks only; no full test suite belongs to this documentation step.

## IX. Amendment

1.3 (2026-10-03) incorporates a separately gated historical graph standard (§VI.2) only; current single-origin receipts, writers, runtime and monetary proof remain unchanged. Supersedes no atomic execution or signature rule.


1.2 (2026-10-03) records the conditional historical business standard and explicit later integration gate; it supersedes no current paid-proof or atomic command rule.

1.1 (2026-10-03) incorporates the complete invalidation creation-linkage contract and guarded one-time initialization; business decisions remain terminal.

Initial 1.0 (2026-10-03) authorizes terminal interval eligibility and its atomic paid compensation. Revisions must increment version/date, identify superseded rules, and preserve higher INV/DOM authority. This document is authorization, not evidence of runtime implementation or production certification.

# SPEC-PROD-001: Attendance Interval Eligibility and Payroll Correction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-PROD-001 | 1.2 | 2026-10-03 | 1.1 | Normative technical contract; incorporated authority only |

## I. Purpose

Define reproducible interval eligibility, original-settlement provenance, and bounded compensation without rewriting attendance or financial history.

## II. Scope

Completed attendance intervals within one class and target seat; payroll settlement, interval invalidation, and residual correction. This documentation authorizes a future implementation. It introduces no runtime code, migration, historical backfill, or compatibility bridge.

## III. Authority Level

This technical contract binds only through explicit incorporation by `DOM-PROD-001` and `FEAT-PROD-003` / `FEAT-PROD-005`. It does not independently authorize mutations. `INV → DOM → FEAT` governs; higher-level conflicts stop implementation. Cross-domain composition belongs solely to the FEAT contracts; the owning domains neither import nor invoke one another.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6: class isolation, minimum PII, immutable financial history, principal/actor authority, and destruction.
- [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII: hierarchy and request-scoped capabilities.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V–VII; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V: commands, pure previews, and domain-owned conclusions.
- [INV-ARC-008](../INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md) §V; [INV-ARC-019](../INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md) §V: canonical teacher/target seat resolution.
- [INV-ARC-015](../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md) §VI–IX; [SPEC-TIME-001](SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md) §IX.9: UTC source timestamps, class-day boundaries and canonical elapsed duration.
- [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, IX; [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5.4, §6: protected records and lawful emission.
- [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII; [FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md) §II–V: domain isolation and one atomic FEAT context.
- [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §VII–XI, XIII–XV; [FEAT-PROD-001](../FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md); [FEAT-PROD-003](../FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md); [FEAT-PROD-004](../FEATURE-EXECUTION/FEAT-PROD-004_COMPLETE_PAYROLL_CYCLE.md); [FEAT-PROD-005](../FEATURE-EXECUTION/FEAT-PROD-005_INVALIDATE_ATTENDANCE_INTERVAL.md): evidence, eligibility, pricing, and execution ownership.
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §VI–VII; [FEAT-LED-000](../FEATURE-EXECUTION/FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md); [FEAT-LED-001](../FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md); [FEAT-LED-002](../FEATURE-EXECUTION/FEAT-LED-002_VOID_REVERSE_TRANSACTION.md): money and compensation authority. These FEAT contracts are interface contracts, never nested executors.
- [SPEC-LED-001](SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md); [SPEC-LED-002](SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) §III–VIII: proof, command reservations, exact replay, and serialization.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md); [DOM-CLASS-002](../DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md); [SPEC-ECON-003](SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md) §4.5.1.1: protection funding and independent fee applicability.
- [DOM-ITR-001](../DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md) §VIII–IX; [SPEC-OPS-001](SPEC-OPS-001_REVERSAL_AND_VOID.md) §III–IV: completed observations remain immutable; corrections are distinct from exact reversal and void.
- [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) §V, VIII; [SOP-DOC-001](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md) §V: classification and registration.

## V. Interval Identity and Terminal Eligibility

PROD pairs one opening `active` event with its corresponding closing `inactive` event in its canonical ordered timeline. Identity is `(class_id, target_seat_id, opening_event_id, closing_event_id)`. Both rows belong to that class and target, form the completed pair selected by PROD, and satisfy canonical class-day boundaries. An arbitrary pair, an open interval, or an end preceding its start is ineligible for this operation. A legitimate zero-duration completed pair is allowed.

PROD derives credited seconds through canonical elapsed duration; invalidation changes only compensation eligibility. Original scans, credited duration evidence, and current attendance state are preserved and remain inspectable. Invalidation is terminal: it cannot be edited, reversed, deleted while its target exists, or converted into a new payable interval. Paid work remains historically settled, including after correction or reversal; it never re-enters unpaid work.

`attendance_interval_invalidation` is the append-only PROD-owned decision record. Required fields are `id`, `class_id`, `actor_seat_id`, `target_seat_id`, `opening_event_id`, `closing_event_id`, `recorded_at` (UTC), `reason_code`, `idempotency_key`, `correlation_id`, `receipt_json`, `lineage_event_id`, `lineage_token` (64 characters), and `lineage_version`. Business fields are frozen at INSERT. Audit linkage is opaque and excluded from the protected payload; all three fields initialize together exactly once in the creating transaction, whose commit requires matching complete creation evidence. Late attachment, replacement, partial linkage and missing evidence fail closed under DOM-PROD-001 §XI.4 and the Operations creation protocol. Reasons are exactly `INVALID_ATTENDANCE`, `NON_WORK_ACTIVITY`, or `DUPLICATE_PARTICIPATION`; no unrestricted notes are accepted or persisted. Unique interval identity prevents a second invalidation under any key. Command identity is `(class_id, FEAT-PROD-005, idempotency_key)`.

Source-event references are within PROD. `class_id` and seat references are shared anchors; other-domain internal rows are referenced only through opaque locators. The protected-row audit pointer is the narrowly mandated linkage of `INV-ARC-016`, not a general permission for cross-domain foreign keys.

## VI. Original Settlement Provenance and Cent Allocation

Each new payroll settlement freezes its complete interval membership in `payroll_event.summary_json`: opening/closing event IDs, credited seconds, governing `policy_uuid`, original per-minute `pay_rate`, and `allocation_version = 1` (including the version-1 quantization convention). Existing setting-share and scheduled-occurrence provenance remains present. References are scoped to the event's class and target. Policy UUID is an opaque non-FK locator; no subsequent rate lookup may reprice settled work.

Persist source inputs, not allocated amounts: no earnings cache, payroll amount column, or monetary amount in PROD summary JSON is introduced. PROD owns frozen participation, original pricing facts, settlement membership, and eligibility conclusions. FEAT supplies those proven inputs to Ledger; Ledger performs monetary allocation/correction arithmetic and validates it against its original posted credit. Ledger must never discover or reinterpret attendance intervals, select payroll policies, or resolve business eligibility itself.

For each governing setting, retain the original pricing rule: total credited seconds × original per-minute rate ÷ 60, quantized once to cents using exact decimal/rational arithmetic, nearest cent with ties to even (`ROUND_HALF_EVEN`) for allocation version 1. Do not round interval durations or separately quantize interval earnings. Historical reproduction must establish the original quantization contract rather than infer it from today's default.

Let a setting's quantized share be integer cents C and its interval seconds be s_i, summing to S. Allocate floor(C × s_i / S) cents to each interval, then distribute the remaining cents one each in descending order of fractional remainder. Resolve equal remainders by ascending closing-event UTC timestamp, then ascending opening-event ID, then ascending closing-event ID. This ordering is canonical, not query order. Exact rational arithmetic prevents floating-point ties. If S = 0, C must be zero and every allocation is zero; nonzero C with S = 0 is an integrity failure. Negative credited seconds or a negative original payroll credit fail integrity validation.

Allocation sums must equal each original setting share, and setting shares must sum to the original posted payroll credit. Corrections reuse the full original allocation, never reallocate cents among surviving intervals. A zero-cent interval may be invalidated with no Ledger effect or correction payroll row.

Historical payment correction is allowed only when PROD can prove exact original membership and frozen pricing inputs, and Ledger can prove the original credit, quantization, allocations, and compensation history. Existing lawful immutable evidence may establish these facts; proximity in time, matching totals, or current rates cannot. Missing provenance denies the whole paid invalidation action without committing eligibility alone. No historical row is rewritten, no command reservation or lineage is fabricated, and no compatibility bridge is authorized.

### VI.1 Conditional historical business membership, priced complete pairs only

DOM-PROD-001 §XV.9 incorporates SPEC-PROD-002 §VI.1 for a future pure historical membership evaluation. Its positive business result requires independently established original source completeness and visibility, original rule/writer assignment, original setting selection and lawful protected business evidence. Equal seconds or cents do not meet those conditions. The dated 153 priced closed-event cohort is only an initial candidate population, never an allowlist or proof criterion. Unpriced events, clipped remainders, open-at-settlement fragments, manual credits and top-ups are outside this contract.

For proven original whole-pair setting shares, Ledger may derive **historical attribution version 1** as a present-day pure calculation; it is not an allocation recorded by the original writer and is distinct from prospective settlement `allocation_version = 1`. Retain each share's independently established original quantized cents, produced by its proven original arithmetic descriptor. In particular, the ad957 descriptor divides the rate by 60 at decimal precision 28 with ROUND_HALF_EVEN, then multiplies by integer seconds and quantizes once; the modern multiply-first expression must not replace it. Using those original share cents, apply the exact rational largest-remainder allocation and ascending closing UTC/opening ID/closing ID tie order above. Require exact conservation per share and for the uniquely identified original credit. No correction causes reallocation.

Business membership is not lawful Ledger creation, original posting or compensation proof. No historical attribution output, new audit event, teacher confirmation or diagnostic envelope supplies those missing facts. This amendment enables no recovery fallback, writer, schema, migration, signing, adoption or current preview integration. Independent existing Ledger/Operations gates remain mandatory and must be satisfied separately before any later implementation is authorized.

## VII. Compensation, Replay, and Concurrency

An unpaid interval produces only its invalidation and audit record. A paid interval produces its invalidation, a `correction` payroll business event when money is recovered, Ledger compensation effects/reservation, and audit lineage atomically. Correction summary carries same-domain `original_payroll_event_id`, `correction_intent = INTERVAL_INVALIDATION`, invalidation ID, source-event IDs, and opaque `correction_intent_locator` and Ledger origin locator; no financial amount is stored there.

Ledger owns immutable `compensation_origin_locator`, nonnegative `compensation_amount_cents`, and `correction_intent_locator` on its monetary effects. Only actual recovery is attributable compensation; savings/checking transfer legs contribute zero. For each original credit, full reversal plus interval and residual compensation must not exceed that credit. Ledger validates and serializes the aggregate cap. PROD must not infer remaining recoverable money by adding payroll rows.

Exact full reversal is allowed only while the original credit is uncompensated. After partial compensation, `FEAT-PROD-003` uses a distinct residual `correction`: original credit minus all attributable prior compensation. Its summary has `correction_intent = RESIDUAL_RECOVERY` and original-event/intent provenance. It is neither a partial `REVERSAL` nor a `VOID`. Already fully recovered payments permit later eligibility invalidation with zero additional monetary recovery. Missing or inconsistent recovery history fails closed.

Corrections and reversals do not advance payroll windows, scheduled occurrences, payroll-cycle completion, or economic-cycle boundaries. Neither invalidation nor recovery rewrites completed Interpretation materializations.

Preview is a pure domain-query composition: interval eligibility, settlement evidence, authoritative proposed compensation, protection transfer, and resulting balances. Its identity covers every fact affecting confirmation. For a new command, serialize and revalidate the preview before mutation; any changed relevant fact returns `PREVIEW_CHANGED` without writes. Successful exact replay resolves the existing command and compares the original supplied request fingerprint before current-preview evaluation; it returns the original result even though the action itself changed eligibility or balances. Same key with changed actor, target, pair, reason, or preview identity returns `REPLAY_MISMATCH`. A different key for an already-invalidated pair returns `ALREADY_INVALIDATED` without recovery.

The immutable protected `receipt_json` stores `expected_preview_identity`, `fingerprint_version`, `canonical_intent_digest`, `original_settlement_disposition`, and `opaque_outcome_locators`. It contains no monetary amounts, personal notes, or cached earnings. It permits reconstruction of the original accepted result through owning-domain queries without evaluating today's eligibility or balances. New unpaid/zero-value commands use the invalidation record and receipt as the durable PROD result; monetary commands also follow Ledger reservation identity `(class_id, feat_code, idempotency_key)` under SPEC-LED-002. Do not expand that namespace by target, account, amount, or effect type.

Payroll settlement and invalidation share serialization for `(class_id, target_seat_id)` before eligibility selection. If invalidation commits first, payroll excludes the interval; if payroll commits first, invalidation observes paid membership and requires a refreshed paid preview before compensation. Reversal and all corrections also serialize against the original Ledger credit and current account settlement. Every required business row, monetary effect, reservation, and audit emission commits together or rolls back together.

## VIII. Funding and Lifecycle

For a correction debit, Ledger resolves the shared protection rule using Class Configuration's supplied current banking directive: when checking would be negative, transfer the entire shortfall from savings only if protection is enabled and savings can cover it completely. Otherwise savings remains untouched and checking takes the full debit, including below zero. Own-account transfers retain their separate sufficient-funds rule. Corrections incur no NSF fee, obligation, or deferred deduction.

Target-seat destruction removes its invalidations and source business records under existing lifecycle authority; class destruction removes all class-scoped records. Removing a provenance actor does not authorize removal of another surviving target's records. Lifecycle destruction is the sole deletion exception, not an invalidation operation. Audit handling follows its existing immutable-chain and lawful-destruction contracts; do not invent a retained business archive or new audit deletion path.

## IX. Worked Acceptance Examples

| Scenario | Required result |
|---|---|
| Unpaid A is invalidated before payroll | Append decision; preserve both scans; A is excluded from future settlement. |
| A=$10, B=$15, C=$20 settle as +$45; invalidate B | Preserve +$45; append −$15 with B/original-payment lineage; net +$30. |
| Then invalidate A | Append −$10; total recovery $25, remaining original contribution $20; B cannot recover again. |
| Then request whole-payment recovery | Distinct residual correction −$20; total recovery exactly $45; no partial reversal. |
| Payment was already fully reversed or residually recovered | Later interval invalidation records eligibility; zero additional recovery. |
| Three 20-second intervals at $0.05/minute | Quantized setting share is 5 cents; equal remainders allocate 2,2,1 cents using canonical tie order; invalidating the last recovers 1 cent, with no reallocation. |
| A legitimate zero-duration interval | Allocate zero; append invalidation without a monetary effect or payroll correction row. |
| Exact retry with original preview identity | Return original result and effects without additional inserts, despite changed current state. |
| Same key but changed reason or pair | `REPLAY_MISMATCH`; original result unchanged. |
| New key for same invalidated pair | `ALREADY_INVALIDATED`; no second compensation. |
| Invalidation wins concurrent payroll | Payroll sees ineligible work and omits it. |
| Payroll wins concurrent invalidation | Unpaid preview is stale; deny `PREVIEW_CHANGED`, then refreshed paid preview can recover its allocation. |
| Concurrent corrections/reversal on one $45 credit | Serialized Ledger cap permits combined recovery of at most $45; stale confirmations fail. |
| Checking $2, savings $3, debit $10, protection enabled | Shortfall $8 cannot be covered entirely; savings stays $3, checking becomes −$8; no correction fee. |
| Checking $2, savings $12, debit $10, protection enabled | Transfer $8 atomically; checking becomes $0, savings $4; recovery attribution counts $10 only. |
| Checking $2, savings $12, debit $10, protection disabled | No transfer; checking −$8, savings $12. |
| Own-account transfer exceeds source funds | Existing insufficient-funds denial remains; charge/deduction overdraft rule does not apply. |
| Teacher or pair belongs to another class | Scope denial; no reads outside authorized class and no writes. |
| Historical credit lacks provable original membership or allocation | `PROVENANCE_UNAVAILABLE`; neither invalidation nor correction commits. |
| Audit emission, reservation, or posting fails midway | Full rollback leaves no invalidation, payroll correction, reservation, or partial funds transfer. |
| Target seat or class is lawfully destroyed | Remove dependent business records under existing lifecycle authority; no retained earnings archive. |

## X. Amendment

Version 1.2 (2026-10-03) defines conditional historical priced whole-pair business proof and distinct derived historical attribution. It supersedes no monetary proof gate and does not claim original allocation was recorded.

Version 1.1 (2026-10-03) completes the invalidation linkage schema/protocol without changing the terminal eligibility or recovery rules.

Version 1.0 establishes the incorporated contract authorized on 2026-10-03. It replaces the exclusive whole-payroll-reversal correction rule only through the amended governing DOM/FEAT contracts. Revisions increment version, effective date, and supersedes; preserve invariant hierarchy, original history, monetary ownership, and deterministic reproduction.

# SPEC-PROD-002: Historical Attendance Proof Assessment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| SPEC-PROD-002 | 1.4 | 2026-10-06 | 1.3 | Normative |

## I. Purpose

Define a bounded, pure assessment separating reconstructable historical attendance, arithmetic replay, original signed coverage, and correction eligibility.

## II. Scope

One class and target seat, with bounded payroll-event selection and bounded complete source evidence. The assessment itself is pure. The separately incorporated reconstruction supplies owning-domain inputs for FEAT-PROD-005/003 atomic correction; no original-row mutation, historical adoption, migration or new teacher surface is authorized by this SPEC alone.

## III. Authority Level

Technical contract, binding only through incorporation by the owning DOM contracts and FEAT-PROD-006. Subordinate to INV-CORE-000 §III.1–6 and INV-ARC-006/007/009/016/021; informative source history cannot grant execution authority.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6 and [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V.
- [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX; [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII.
- [SPEC-TIME-001](SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md): UTC evidence, class-local day boundaries and elapsed-time primitives.

## V. Pure assessment dimensions and bounded evidence

Keep separate domain-owned observations: canonical pair reconstruction; original-window source membership; original pricing/rule replay; unique scoped credit identity; original signed-field coverage; prior compensation and current correction eligibility. Reconstruction is not a new INV-ARC-016 lineage state. Original VERIFIED/UNVERIFIED/INVALID/DEGRADED remains separately reported; no source gains signed coverage from arithmetic agreement.

Complete immutable attendance in the original payroll window, all relevant original payroll boundaries and retained versioned settings define the historical reconstruction. Replay uses recognized original writer/selection/time/rate rules, then Ledger compares the resulting paid aggregate exactly to the original credit. A matching total without unique rule-based selection is insufficient; conflicting selections deny. Newly introduced membership/allocation/reservation/compensation fields or a separate signed source-visibility snapshot are not retroactive prerequisites. Missing actual source/rule/configuration facts, malformed inputs or ambiguous selection still deny. Changed evidence during assessment or confirmation is unavailable.

Default page size 50, maximum 100; fixed server-owned caps are 2,000 attendance rows, 1,000 payroll boundaries, 500 settings, 1,000 monetary candidates and 1,000 audit events. Bound complete relevant inputs before pairing or pagination. Cap+1/count exhaustion yields EVIDENCE_LIMIT_EXCEEDED, never a truncated graph considered complete. Canonical context proves one class and target seat before evidence access. Reject foreign/nonpositive/malformed IDs. Reads use no-autoflush and no locks, reconciliation, flush, commit, audit/IntegrityStatus writes or caches.

## VI. Explicit historical rule descriptors

Descriptors are immutable server-owned exact-source algorithms; clients cannot select a writer by passing a proof flag, revision or monetary amount. Recognized historical business shape, settlement markers and original credit representation select the supported descriptor unambiguously. Unknown/malformed modern representations, unknown versions or conflicting rule selection deny rather than choosing the algorithm that happens to match cents. Preserve the complete rule/material identity in previews. No retired mutation writer is invoked.

Pinned closed-session source `ad9574334d72fd92cc93402e851ab0ebc22aaad9`, `app/services/attendance_service.py:calculate_seat_payroll_intervals` / `_split_sessions`, continues an existing session on repeated active rows, caps at canonical class-day end, pays closed intervals after the prior payroll boundary, and clips already-paid legacy portions. Original setting is selected at close; complete retained original settings determine it. Pricing `app/services/payroll/pricing.py:amount_for` first divides the original rate by 60 at Decimal precision 28/ROUND_HALF_EVEN, multiplies by the aggregate integer share seconds and quantizes that share once to cents. Preserve `elapsed_duration`'s aggregate truncation; do not sum independently floored interval seconds.

Pinned legacy source `c42f882b8e610d43f355d684a8632d1fa8d50f72`, `app/feats/prod.py:_calculate_attendance_seconds_since`, uses the prior payroll's inclusive lower timestamp bound, restarts on repeated active rows, caps each segment at its opening's class-day end, and uses the run instant for trailing open work. Its rate is the original retained setting at the original run boundary, including the pinned legacy `pay_rate_per_second` rule that treats a retained falsy rate as its then-declared $0.25/minute constant. Preserve that original algorithm separately in Policies' `legacy_rate_per_minute` input; do not apply the legacy zero-rate behavior to modern frozen pricing or substitute a current default. Replay must account explicitly for surviving sources after the original boundary and never infer a different source shape solely from matched totals. Current frozen `allocation_version = 1` uses its canonical modern membership and multiply-first pricing; it cannot enter legacy reconstruction to bypass original business/monetary creation verification. Modern signatures are checked against their exact registries.

### VI.1 Whole-pair and remainder reconstruction

PROD `reconstruct_historical_payroll_graph` returns the complete canonical pairs, selected exact UTC segments, original windows, setting/share/rule identities and coverage limitations. Policies supplies retained immutable original setting inputs through FEAT. Ambiguous boundaries, tied setting selection, invalid original rates or sources outside scope deny. Event timestamps plus deterministic original-window rules are reconstruction inputs; they are not represented as cryptographic creation-visibility evidence. Absent old linkage is a visible coverage limitation, not an automatic reconstruction denial.

Ledger `validate_historical_settlement` uniquely binds the original positive credit and compares exact original paid aggregate to replay. Class/target/actor/mechanism/account/type and original command/correlation linkage follow the pinned writer. Matching amount or temporal proximity alone cannot establish identity. A zero payroll run remains an original boundary and has no invented zero credit. Pending original money denies PAYROLL_PENDING by the exact scoped reconciliation cursor. Historical attribution version 1 is a newly derived rational largest-remainder allocation over grouped exact original-duration weights, with ascending closing UTC/opening ID/closing ID ties. Preserve exact original share cents and conserve each share/payment; do not claim those cents were historically persisted.

### VI.2 Complete historical attribution graph

Include all connected original fragments, closed remainders, recognized PROD-PAY-001 positive incident top-up windows and their canonical completed pair identities. Still-open pairs cannot be invalidated. Keep every intervening zero-valued payroll boundary. Unrelated manual credits have no inferred work allocation. Each selected segment belongs uniquely to one canonical pair; duplicate/overlapping claims, missing original events/credits, conflicting source assignment or changed evidence deny the entire graph, never its inconvenient portion.

For the ad957 incident descriptor `app/services/payroll/corrections.py:build_class_correction_proposal`, preserve each original included window's positive delta: separately quantized whole worked-seconds price minus separately quantized replay-paid-seconds price. Original corrected-payroll-event IDs identify its windows; validate every delta and their exact sum against the uniquely identified positive top-up credit. Establish replay-paid segments as a subset of worked segments; form nonoverlapping temporal set difference for each pair's exact loss-duration weight. Preserve original whole-second aggregate truncation separately from those rational weights. Group a pair's components before largest remainder; splitting one pair cannot give it extra rounding positions. A positive delta with zero/negative/ambiguous loss denies. Top-up is an additional original credit, not recovery of another origin.

Ledger returns distinct `ReconstructedSettlement`/`ReconstructedOrigin` evidence containing fixed allocations and complete prior recoveries. It is not `LedgerCreationEvidence` or Operations `VerifiedCreationEvidence`. Legacy prior reversal requires original business reference, unique negative counterpart, full original credit magnitude and matching scoped original writer facts; count it once. Absence of new origin/intent columns alone cannot imply zero. Modern recovery principals and their business interval associations require complete current v3 creation evidence. Unattributed relevant negatives, unknown partial attribution or unsupported versions deny. Funding legs have zero attribution; all accepted pending and posted principals count against the original-credit cap. Fully recovered origins contribute zero; partial interval recovery requires unique contribution identity. No proportional guess for unknown recovery is allowed.

Each origin's original credit equals original quantized shares and bounds total accepted recovery. Complete graph correction uses one atomic FEAT, stable origin locks, one aggregate funding resolution and one reservation covering all principal/funding legs. Exact accepted replay precedes fresh reconstruction. Confirmation revalidates complete graph, balances, configuration and prior compensation under locks. Any missing origin, changed preview or intermediate failure rolls back eligibility, business, monetary, reservation and audit effects together. No original rows/signatures or cycle/Interpretation history changes.

## VII. Audit diagnostics and monetary boundary

Operations diagnoses the linked original event's scope, envelope HMAC and continuous complete chain/head within budget, independently of row-payload coverage. A verified prefix is insufficient. Scalar head observations before and after the complete walk must agree; concurrent legitimate advancement returns unavailable EVIDENCE_CHANGED_DURING_READ, never a false integrity failure. No row locks or transaction mutation are used. Batch diagnostics walk one bounded complete class chain once per invocation; no caller proof input or persisted cache is allowed. Unsupported per-record source assignment is rejected rather than accepted through an arbitrary descriptor argument. Missing linkage is a coverage gap; wrong scope, invalid envelope or broken chain are integrity failures; unavailable infrastructure or over-budget chain is unavailable. Diagnostics must not write canonical integrity status. Assessment and reconstruction themselves write nothing and offer no old-format or compatibility path for creating state; any correction effect is written only by FEAT-PROD-005/003 under current lineage, command reservation and immutability guards (§VIII). This version does not endorse selecting a descriptor by recognized business shape, settlement markers or credit representation (§VI) for records that carry no stored version: under `SOP-DB-004` §VII.7 that selection is unresolved history awaiting an owner ruling, and no new such selection may be added before it.

At deployed `ad9574334`, `app/services/ledger_posting_service.py:_TRANSACTION_AUDIT_FIELDS` and `app/utils/transaction_idempotency.py:_TRANSACTION_AUDIT_FIELDS` declare exactly eleven fields: amount, account_type, type, status, class_id, seat_id, target_seat_id, actor_seat_id, mechanism, description, correlation_id. The historical verifier's eight-field list is not the emitter definition. This source establishes a descriptor only; version 1 by itself does not establish per-record emitter provenance. Preserve exact historical payload serialization if provenance and original protected values are available. Without them report declared candidate coverage separately from confirmed signed coverage. Do not substitute a hypothetical creation status, derived cursor status, or guessed status until a digest matches.

Envelope authentication alone never proves unsigned timestamp, amount_cents, posting_sequence, command reservation, idempotency key, policy reference, or compensation attribution. It never returns VerifiedCreationEvidence, overrides canonical lineage, rewrites signatures, or changes existing v2/v3 verification. Missing historical compensation fields or unsigned reversal linkage cannot imply zero prior recovery. Ledger owns monetary comparisons, scoped credit identity and compensation conclusions, taking FEAT-supplied Operations observations without importing Operations internals.

## VIII. Execution and verification

FEAT-PROD-006 assessment remains pure; reconstruction supplies internally validated evidence to FEAT-PROD-005/003, not an executable client permission. Modern exact creation proof and recognized legacy reconstruction are distinct per-source modes. Unknown original fields alone do not deny a supported legacy reconstruction; actual INVALID scope/payload/HMAC/chain evidence does. Unavailable cryptographic infrastructure prevents required evidence and new lawful audit emission. Every new effect and business decision uses current lineage, command reservation and immutability guards.

Targeted acceptance includes genuine ad957 predecessor-created and forward-migrated original evidence; successful aggregate replay/cent allocation without fabricated old fields; legacy repeated-active/open fragments, closed remainder and incident top-up; zero boundaries; aggregate fractional-second truncation; mismatching totals or conflicting membership; invalid/ambiguous settings; unsupported writer/versions; actual chain/HMAC/payload contradiction; modern malformed records refusing historical fallback; prior legacy reversal counted once, complete modern partial/full/residual recovery; pending originals; mixed-origin graphs; same-key exact retry and changed-intent mismatch; concurrent payroll/full/partial/residual recovery, complete rollback and original signature preservation. Consult pytest_result first; targeted tests only. Synthetic observations must be distinguished from genuine predecessor fixtures.

## IX. Amendment

Version 1.4 (2026-10-06) clarifies that §VII diagnostics and reconstruction write nothing themselves and add no compatibility path, consistent with the owner's compatibility ruling in `SOP-DB-004` §VII–VIII, and records that shape-based descriptor selection for unversioned records (§VI) is unresolved under `SOP-DB-004` §VII.7. Supersedes no assessment dimension, descriptor or monetary boundary.

Version 1.3 (2026-10-03) supersedes v1.0–1.2 diagnostic-only execution restriction and demanded historical signed source/visibility/modern-field evidence for recognized immutable-source reconstruction. Separate reconstructed evidence now contributes to authorized correction FEATs. Modern canonical proof, actual integrity denial, original signatures and all new-write lineage remain unchanged.


Version 1.2 (2026-10-03) separately specifies conditional pure multi-payment graph evaluation (§VI.2), superseding future-only graph design scope without widening §VI.1 or changing runtime, persistence or monetary authority.


Version 1.1 (2026-10-03) conditionally defines original priced whole-pair business proof for later pure evaluation. It supersedes diagnostic-only scope solely at the documentation contract level; Phase 1 runtime and all monetary execution gates remain unchanged. No incomplete source evidence becomes proof.

Initial 1.0 (2026-10-03) defines diagnostic assessment only. Later proof adoption or recovery requires separate owning-domain and FEAT authority; no rule here supersedes the unchanged correction proof gates.

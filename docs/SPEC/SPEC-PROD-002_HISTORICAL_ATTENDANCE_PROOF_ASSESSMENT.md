# SPEC-PROD-002: Historical Attendance Proof Assessment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| SPEC-PROD-002 | 1.0 | 2026-10-03 | N/A | Normative |

## I. Purpose

Define a bounded, pure assessment separating reconstructable historical attendance, arithmetic replay, original signed coverage, and correction eligibility.

## II. Scope

One class and target seat, with bounded payroll-event selection and bounded complete source evidence. No persistence, migration, historical adoption, recovery authorization, teacher controls, or mutation is included.

## III. Authority Level

Technical contract, binding only through incorporation by the owning DOM contracts and FEAT-PROD-006. Subordinate to INV-CORE-000 §III.1–6 and INV-ARC-006/007/009/016/021; informative source history cannot grant execution authority.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6 and [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V.
- [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX; [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII.
- [SPEC-TIME-001](SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md): UTC evidence, class-local day boundaries and elapsed-time primitives.

## V. Pure assessment dimensions and bounded evidence

Return distinct domain-owned observations with explicit reasons and relevant source identifiers: canonical pair reconstruction; business replay consistency and original membership completeness; original pricing/rule provenance; scoped monetary identity and arithmetic comparison; signed-field coverage; compensation completeness; and current execution eligibility. Diagnostic labels such as consistent, mismatch, unavailable, and unsupported are observations, never new INV-ARC-016 lineage states. Preserve its VERIFIED/UNVERIFIED/INVALID/DEGRADED classification separately when canonical verification is performed.

A matched total or elapsed duration does not prove membership, creation visibility, original rule assignment, compensation completeness, or lawful creation. Candidate fragments/remainders/top-ups must be labelled unsupported attribution in this phase, not silently assigned to whole pairs. Zero-value payroll events provide boundaries and no invented Ledger credit. Reconstructed pair IDs and seconds retain original scans, including repeated-active handling, persisted system closure and canonical day/DST rules.

Default payroll-event page size is 50, maximum 100. Each invocation has fixed positive upper bounds for source rows, monetary candidates and complete chain walk (defaults are 2,000 attendance rows, 1,000 payroll boundary rows, 500 setting inputs, 1,000 monetary candidates and 1,000 audit events). Reject malformed budgets and foreign/nonpositive event IDs. Query cap+1 or bounded counts; exceeding a budget yields explicit EVIDENCE_LIMIT_EXCEEDED for the affected dimension, never a truncated source set presented as complete. Pairing precedes presentation slicing. The source set must include relevant earlier payroll boundaries; ambiguous tied boundaries or absent visibility proof remain unavailable. Reads use no-autoflush and perform no commit, flush, locks, reconciliation, audit emission, IntegrityStatus repair, or cache writes.

## VI. Explicit historical rule descriptors

Descriptors are immutable server-owned constants identified by version and exact source revision/path/function. They describe an algorithm, not which record was created by it. Assignment requires independently established original source provenance; a present deployment revision, caller claim, timestamp, matching amount, or today's configuration cannot establish a record's original writer. Unknown assignment returns unavailable even if candidate replay matches. Retained original pricing inputs can support an explicitly labelled arithmetic replay without claiming emitter assignment or source-set completeness. No present-day rate/default fallback is authorized.

The deployed source `ad9574334d72fd92cc93402e851ab0ebc22aaad9`, `app/services/payroll/pricing.py:amount_for`, defines `Decimal(str(rate)) / Decimal("60")`, then elapsed integer seconds multiplication, then `.quantize(Decimal("0.01"))` using its decimal context (precision 28, ROUND_HALF_EVEN). Historical replay must preserve this divide-first order, not substitute today's multiply-first pricing. Its setting-share algorithm groups by original setting at close and quantizes each share once; `amount_from_summary` sums those shares. Valid retained pricing requires finite nonnegative rates, canonical nonnegative integer seconds, unambiguous policy identity and original inputs. Missing settings or malformed inputs are unavailable, not defaults. Any additional legacy algorithm needs an explicit exact-source descriptor and targeted predecessor tests before support; guesses and retired writer invocation are forbidden.

A separately labelled candidate reconstruction may replay the exact historical closed-session timestamp cutoff and legacy remainder clipping described by `ad9574334:app/services/attendance_service.py:calculate_seat_payroll_intervals`; this read never changes canonical pair IDs/duration or claims clipped candidates were original membership. Original source visibility and per-record writer assignment remain unavailable without independent evidence.

No reconstructed interval allocation becomes original recorded allocation. No paid membership fallback is installed in current payroll selection or correction preview. Existing SPEC-PROD-001 proof requirements remain unchanged.

## VII. Audit diagnostics and monetary boundary

Operations diagnoses the linked original event's scope, envelope HMAC and continuous complete chain/head within budget, independently of row-payload coverage. A verified prefix is insufficient. Scalar head observations before and after the complete walk must agree; concurrent legitimate advancement returns unavailable EVIDENCE_CHANGED_DURING_READ, never a false integrity failure. No row locks or transaction mutation are used. Batch diagnostics walk one bounded complete class chain once per invocation; no caller proof input or persisted cache is allowed. Unsupported per-record source assignment is rejected rather than accepted through an arbitrary descriptor argument. Missing linkage is a coverage gap; wrong scope, invalid envelope or broken chain are integrity failures; unavailable infrastructure or over-budget chain is unavailable. Diagnostics must not write canonical integrity status.

At deployed `ad9574334`, `app/services/ledger_posting_service.py:_TRANSACTION_AUDIT_FIELDS` and `app/utils/transaction_idempotency.py:_TRANSACTION_AUDIT_FIELDS` declare exactly eleven fields: amount, account_type, type, status, class_id, seat_id, target_seat_id, actor_seat_id, mechanism, description, correlation_id. The historical verifier's eight-field list is not the emitter definition. This source establishes a descriptor only; version 1 by itself does not establish per-record emitter provenance. Preserve exact historical payload serialization if provenance and original protected values are available. Without them report declared candidate coverage separately from confirmed signed coverage. Do not substitute a hypothetical creation status, derived cursor status, or guessed status until a digest matches.

Envelope authentication alone never proves unsigned timestamp, amount_cents, posting_sequence, command reservation, idempotency key, policy reference, or compensation attribution. It never returns VerifiedCreationEvidence, overrides canonical lineage, rewrites signatures, or changes existing v2/v3 verification. Missing historical compensation fields or unsigned reversal linkage cannot imply zero prior recovery. Ledger owns monetary comparisons, scoped credit identity and compensation conclusions, taking FEAT-supplied Operations observations without importing Operations internals.

## VIII. Execution and verification

The assessment cannot authorize execution. Historical results remain blocked unless the existing unchanged PROD membership and Ledger/Operations creation/compensation proof gates independently qualify. Return specific blocking reasons; do not mark every displayed reconstructed interval ineligible for unpaid work merely because historical monetary evidence is unavailable. No reads change originals, cycles or completed Interpretation records.

Targeted verification covers scope, malformed bounds, cap exhaustion, exact pairs/repeated-active/day-end/DST; tied boundaries and backdated visibility ambiguity; missing/invalid/stale setting evidence; exact replay with incorrect membership; zero runs; eleven-versus-eight coverage; valid envelope with incomplete protected values; unsupported per-record emitter assignment; bounded chain completeness; pure reads and unchanged current v2/v3 proof. Synthetic fixtures must not fabricate old signatures as genuine historical proof; genuine predecessor-runtime evidence is distinguished explicitly.

## IX. Amendment

Initial 1.0 (2026-10-03) defines diagnostic assessment only. Later proof adoption or recovery requires separate owning-domain and FEAT authority; no rule here supersedes the unchanged correction proof gates.

# Historical attendance and payroll proof: decision and implementation plan

Date: October 3, 2026 (America/Los_Angeles). Status: **Phase 1 implemented and verified locally; Phases 2–5 proposed; historical monetary execution remains blocked**. This working decision package grants no runtime authority and changes no existing invariant, domain contract, signature, or production record.

## Objective and first delivery

Establish exactly what surviving historical evidence proves, expose reconstructable attendance and payment contributions without claiming unavailable proof, and identify the authority needed before historical recovery can execute.

The first delivery implements a pure, class/target-scoped historical evidence assessment and its tests. It does not enable historical recovery. Historical signatures remain attached to their original rows. Newly signed observations, if later authorized, attest today's observation only.

## Phase 0 — Discovery and established evidence

Read the contracts below before implementation. Apply [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) and register any later numbered contract through [SOP-DOC-001](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md). This unnumbered tracking package is informative under SOP-DOC-000 §V–VI, not a SPEC or new FEAT.

| Authority | Constraint |
|---|---|
| [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6 | Class/seat scope, deterministic financial outcomes, counter-entries, immutable originals, lifecycle destruction |
| [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII | INV → DOM → FEAT authority; a plan or SPEC cannot grant authority on its own |
| [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX | Original protected payload and continuous chain; UNVERIFIED/INVALID/DEGRADED distinction; lawful write paths |
| [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII | One coordinating FEAT; no domain-to-domain policy or proof calls |
| [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §VII–XI, XV.7–8 | Canonical source pairs, business settlement membership, historical gaps and creation-only linkage |
| [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §VII.1A, VIII–IX.1 | Monetary ownership, compensation cap, cursor posting, unavailable historical proof |
| [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5.1–5.4, 6.1–6.2 | Version-specific signed coverage, exact payload parity, immutable original signatures and typed creation evidence |
| [FEAT-PROD-005](../FEATURE-EXECUTION/FEAT-PROD-005_INVALIDATE_ATTENDANCE_INTERVAL.md) §V–VIII | Paid proof prerequisite, atomic execution, denial and preview/replay |
| [FEAT-PROD-003](../FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md) §VI | Full/residual recovery permission and business provenance |
| [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §V–VII | Incorporated interval identity, exact cent allocation, historical evidence and recovery conservation |
| [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md), [SPEC-LED-002](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) | Incorporated monetary proof and permanent command reservations |
| [SPEC-TIME-001](../SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md) | Class-local boundaries, UTC evidence and exact elapsed-time primitives |

**Production observation, October 3:** app `ad9574334d72fd92cc93402e851ab0ebc22aaad9`, database `a4b50fee84c3`. On-host read-only replay found 539 completed source pairs, no missing close IDs and no current open sessions. All 402 positive payroll credits reproduce exactly; 119 zero-value payroll events reproduce with no positive credit. These counts are time-bounded observations, not future release criteria.

| Historical cohort | Findings | Initial disposition |
|---|---|---|
| 153 closed-session events with aggregate pricing | Exact setting-share seconds and original credits; 160 complete pair occurrences | First business-membership proof candidate cohort |
| 157 closed-session events without pricing | Original amounts reproduce; 138 events / 143 complete pair occurrences; 19 have clipped legacy remainders | Retained configuration and historical writer provenance need separate proof |
| 211 legacy payroll events | 92 credits, 119 zero events; 81 paid a still-open fragment | Requires explicit fragment-to-complete-interval attribution |
| 79 PROD-PAY-001 manual credits | Source payroll-event IDs exist; every credit matches a scoped command key | Positive top-ups must participate in any future multi-payment attribution |

The 291 complete-pair candidate events account for 303 pair occurrences; distinctness must be checked explicitly. The replay matched credit identity using scoped correlation **or command key**; the earlier correlation-only observation did not establish orphaned incident credits.

All 854 production Ledger effects use version-1 lineage. No creation audit records exist in `audit_events` for attendance/payroll/settings/classes. Attendance UPDATE/DELETE guards exist, but scans lack an attested creation instant proving when a backdated scan became visible. A present-day consistent replay alone cannot prove the original database snapshot.

### Existing APIs and patterns

These are current APIs, not proposed historical APIs:

- PROD: `list_attendance_intervals(seat_id, class_id, *, ctx, as_of_utc=None)` in `app/services/attendance_service.py`; `AttendanceInterval.as_evidence()` retains canonical source IDs/timestamps/seconds.
- PROD: `payroll_interval_memberships(seat_id, class_id, *, ctx, as_of_utc=None)` in `app/services/payroll_interval_provenance.py`; frozen membership validation currently denies missing historical evidence.
- Operations: `verified_creation_evidence(table, row, class_id, *, required_fields=())` in `app/utils/audit_verifier.py`; exact signature coverage and full chain are required.
- Ledger: `get_credit_recovery_evidence_records(*, class_id, target_seat_id, origin_locator)` and `get_credit_compensation_proof(*, class_id, target_seat_id, origin_locator, through_posting_sequence, creation_evidence)` in `app/services/ledger_recovery_service.py`.
- FEAT: `app/feats/attendance_interval_invalidation_feat.py` composes owning-domain queries, signed preview and one atomic correction; `app/feats/ledger_proof_inputs.py` maps Operations evidence into Ledger-owned immutable inputs.
- Historical source: deployed `ad9574334` attendance/pricing/settings writers; predecessor commits `bc5c07a2` and its parent; deployed `app/services/payroll/corrections.py`; migration `a7e3c9d1f5b2` documents the historical setting remap. The [PROD-PAY-001 incident record](../ops/audits/INCIDENT_2026-09-28_PROD-PAY-001.md) supplies context, not substitute runtime authority.

Consult `pytest_result` first. Existing genuine historical v2 tests prove original signatures survive forward migration and unprovable old compensation blocks execution. Their success does not prove v1 historical coverage.

## Authority conflict and decision gate

**Blocked approach:** signing today's reconstructed membership and using that new row to label old creation evidence VERIFIED would contradict INV-ARC-016 §V and DOM-OPS-002 §6.1–6.2. Teacher confirmation cannot grant missing cryptographic coverage. No lower-level SPEC, migration, route or compatibility adapter may make this substitution.

Legacy v1 must be examined using each actual emitter, not the old verifier's registry alone. At deployed `ad9574334`, both monetary emitters sign eleven fields: amount, account_type, type, status, class_id, seat_id, description, correlation_id, target_seat_id, actor_seat_id, mechanism. The old verifier listed eight. Exact source locations: `app/services/ledger_posting_service.py:8–12`, `app/utils/transaction_idempotency.py:139–143`, and `app/utils/audit_verifier.py:28–39` in that revision. The payload did not protect timestamp, amount_cents, posting_sequence, command reservation, idempotency key, policy reference or compensation attribution. The HMAC envelope authenticates its declared chain/row/operation/context/payload digest (`app/services/audit_service.py:190–214,293–311`); it does not silently expand that payload coverage. Writer history before this deployment still needs exact per-record attribution.

The old creation command signs PENDING, while old settlement changes stored status and attaches sequence. Under the locked decisions, do not substitute a hypothetical creation status, use a derived cursor label as signed input, enumerate guessed states until a digest matches, or add a verifier override. A version-1 diagnostic must report the covered and unavailable facts without returning the typed creation proof expected by recovery.

This plan preserves the higher invariants. If originals cannot provide all required evidence, historical automatic recovery stays unavailable. Any proposal to relax that standard is an explicit higher-authority decision outside this implementation plan; stop and flag it rather than silently amending DOM/FEAT to bypass the invariant.

## Phase 1 — Pure historical assessment, no monetary enablement

Implemented through [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §XIII.9 and the dedicated pure read [FEAT-PROD-006](../FEATURE-EXECUTION/FEAT-PROD-006_ASSESS_HISTORICAL_ATTENDANCE_PROOF.md), with [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) explicitly incorporated by the owning domain contracts. The bounded class/target assessment reuses canonical pairing/time evidence and returns separate business, monetary and audit observations. Policies supplies retained setting inputs, Class Configuration establishes current owner binding, and Identity establishes teacher/target scope. Operations walks a bounded complete chain once per invocation and reports legitimate concurrent head advancement as unavailable. Historical source descriptors remain conditional candidates: matching replay does not establish per-record writer assignment or original source visibility. No fallback is installed in current payroll selection, and no retired incident writer is invoked. No teacher controls or new routes are included in this phase.

Return separate dimensions: canonical pair availability; business replay consistency; original membership completeness; original pricing/rounding provenance; scoped credit identity; signed-field coverage; compensation completeness; and current execution eligibility. Keep observation results separate from INV-ARC-016's canonical lineage states. Money and recovered totals come from Ledger; Operations owns signature/chain coverage; PROD owns participation and business membership. Compose them at the FEAT read boundary.

For v1, copy exact historical serialization/emitter field definitions into a documented diagnostic contract only after emitter provenance is established. Verify the actual audit envelope independently. Missing original protected values remain unavailable. A matching envelope alone cannot return VERIFIED creation evidence or prove unsigned fields. Do not persist earnings, allocated cents, a new posted status, or a historical eligibility cache.

Verification: scoped and cross-class denial; exact canonical pair IDs; repeated active scans; day-end/DST boundaries; backdated insertion ambiguity; malformed/missing settings; tied payroll boundaries; exact replay with incorrect membership; eleven-versus-eight payload mismatch; valid envelope with incomplete protected evidence; stale configuration; zero-value runs; source purity (no flush, reconciliation or audit emission). Use synthetic fixtures and genuine predecessor runtimes; no fabricated old signatures. Confirm current v2/v3 proof remains unchanged.

### Phase 1 local implementation handoff (October 3, 2026)

The completed verification covers **72 distinct runtime checks** (49 runtime-author checks, 19 Operations diagnostic checks and four additional independent-review checks), plus **705 documentation link/registration checks**: 777 distinct passing checks. The independent review passed all ten selected checks; its six overlapping checks and focused reruns are not added again. Results are retained in `pytest_result`; runtime-author node identities are recorded in `/tmp/phase1-runtime-verification.json`. Supporting logs are `/tmp/phase1-runtime-final-tests.log`, `/tmp/phase1-runtime-postguard-tests.log`, `/tmp/phase1-ops-tests.log`, `/tmp/phase1-authority-docs.log` and `/tmp/attendance-phase1-independent-review.log`.

Coverage includes genuine predecessor-runtime version-1 creation and forward migration without signature rewriting, conditional historical pricing replay, canonical source-pair regressions, scope and malformed identifiers, bounded sources and chain evidence, exact eleven-versus-eight historical field definitions, original serialization, valid envelopes with unavailable creation coverage, pure reads, and concurrent legitimate chain-head advancement. Synthetic diagnostic envelopes are labelled test observations and are not presented as genuine historical proof.

Original scans, payroll records, signatures and monetary effects remain unchanged. No new schema, historical membership fallback, proof adoption, recovery path, route or teacher controls are enabled. Independent review found no unresolved issue. The architecture gate and final whitespace/link checks passed. These local checks do not certify production data or authorize deployment. Phase 2 and later phases remain proposed and require separate reviewed authority.

## Phase 2 — Historical business proof contract, smallest cohort first

Propose amendments to DOM-PROD-001 §XV.7, FEAT-PROD-005 and incorporated SPEC-PROD-001 §VI that explicitly permit a **proven** historical membership query from existing immutable evidence. The current blanket timestamp-gap handling must not be replaced before this authority exists. Specify minimum evidence for source-set completeness, original setting selection, original rule version, original quantization and one-to-one scoped payment identity. Audit coverage gaps must be surfaced; multiple possible memberships deny.

Start with the 153 priced full-pair candidate events. Require exact source-set proof in addition to matching seconds and amounts. Then consider the 138 unpriced full-pair candidate events only if retained historical configuration and original writer/rate are independently established. Preserve original per-share quantization; largest remainder attribution must use a documented version, not pretend the new allocation was recorded historically. Do not reprice with today's rate or silently rewrite original summaries.

Verification: exact largest-remainder conservation and deterministic ties; unique source membership; two different source sets with equal seconds/amount must deny; missing creation-visibility evidence must deny; invalid rates or inconsistent credit identity fail closed; reconstruction never advances payroll/cycle boundaries. The new read result may remain reconstruction-only even when arithmetic matches perfectly.

**Exit gate:** business proof is not monetary authorization. Even a proven source mapping leaves execution blocked while Ledger creation/compensation proof is unavailable.

## Phase 3 — Multi-payment attribution design, separately incorporated

Before implementation, extend PROD-owned settlement vocabulary and incorporated SPEC-PROD-001 to describe a complete canonical interval's original paid fragments, later remainder, incident top-up and every original credit involved. Specify positive top-up identity separately from negative recovery. Every fragment must reference one canonical pair and original business event; opaque credit locators remain Ledger-owned, without cross-domain internal FKs.

Ledger must own allocation/conservation across this attribution graph. Preserve each original payment's total, historical per-window truncation and quantization. Allocate attributable cents once over a complete proven source set; do not sum independently rounded guesses or recover an interval twice through both a fragment and its top-up. An incomplete graph denies the entire paid invalidation. Zero-value original events provide business boundaries, not fake zero-cent Ledger credits.

This is a fresh explicit historical attribution command model if authorized, never a compatibility bridge. Any new immutable evidence surface needs DOM-CORE-002 schema authority, DOM-OPS-002 protected-field registration, owning-domain writers, named FEAT authority, exact replay/preview receipt, and lifecycle destruction rules before a migration is written. It must attest the new decision's time and actor, not claim old creation lineage.

Verification: legacy active-row restart; payroll while open; later clipped remainder; the 79 top-up source references; one interval spanning multiple credits; multiple intervals within one correction credit; zero runs; different graphs with equal total; partially/fully recovered credits; actor destruction cannot remove another target's evidence; target/class destruction removes any new records.

## Phase 4 — Monetary proof gate and conditional integration

Do not implement this phase unless existing lawful evidence proves all required Ledger facts under INV-ARC-016 and incorporated SPEC-LED-001. Document any proposed extension in DOM-LED-001/DOM-OPS-002 and governing FEAT before changing proof APIs. Keep v2/v3 verification byte-for-byte version-specific. Never default missing historical compensation to zero, trust unsigned reversal pointers, backfill reservations/sequences, reinterpret signatures, or bypass required evidence.

If the gate passes, extend the existing atomic FEAT-PROD-005 coordinator: one target seat and ClassEconomy lock, deterministic locking of all original credits before monetary sources, one command reservation covering all funding/recovery legs, and all-or-nothing eligibility/correction/audit effects. Ledger owns every origin's aggregate cap including pending recovery; funding attribution remains zero. Full/residual/interval commands share the same serialization. Preserve shared protection, no correction fee, signed preview, accepted replay first and exact uncertain retry.

Verification: independent PostgreSQL sessions racing interval/full/residual recovery across every involved origin; aggregate recovery never exceeds any original credit; one missing origin denies all writes; failures at reservation/funding/business/audit/commit roll back the whole graph; original signatures and rows stay unchanged; completed Interpretation/cycle records stay unchanged.

## Phase 5 — Teacher presentation and final verification

Show reconstructed scans/duration and replay findings separately from recovery permission. Explain the specific missing evidence in visible text. Offer automatic correction only if both business and monetary proof gates pass. A pure read must not enroll a historical record into a new proof model; any later authorized adoption is an explicit command with preview and confirmation.

Consult previous pytest results and run only new/affected tests, including pure routes, scope/CSRF, stale preview, uncertain retry and 390px keyboard/touch/axe behavior. Review the authority chain, registrations, typed owning-domain evidence, immutable fields, original signatures, money conservation and absence of fallbacks. Use read-only production aggregate preflight; keep deployment and any historical command execution separately authorized.

## Immediate next action and completion criterion

Phase 1's pure assessment contract and diagnostic runtime are implemented locally. The next proposed slice is **Phase 2's historical business-proof authority design**, beginning with the priced full-pair candidate cohort. Per-record legacy emitter provenance, original source-set completeness and creation visibility remain unresolved; arithmetic agreement does not close those gaps. Historical monetary execution is not authorized or promised by this plan. Any later proof extension requires reviewed owning-domain and FEAT authority before implementation. It must never convert incomplete evidence into financial authority. Production remains unchanged; deployment and historical command execution require separate instructions.

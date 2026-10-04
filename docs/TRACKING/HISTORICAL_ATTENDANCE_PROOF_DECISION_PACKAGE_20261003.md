# Historical attendance and payroll proof: decision and implementation plan

Date: October 3, 2026 (America/Los_Angeles). Status: **Phase 1 implemented and verified locally; Phase 2 conditional authority specified and independently reviewed; Phase 3 separate graph authority specified and independently reviewed; Phases 4–5 proposed; historical monetary execution remains blocked**. This working decision package grants no runtime authority and changes no existing invariant, domain contract, signature, or production record.

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

Conditional authority is specified by DOM-PROD-001 §XV.9, DOM-LED-001 §IX.3, SPEC-PROD-001 §VI.1, SPEC-PROD-002 §VI.1 and FEAT-PROD-006 §VI.1. FEAT-PROD-005 §VI.1 preserves its later integration gate. This documentation package authorizes a future pure evaluation contract; it introduces no implemented API, migration, original-row rewrite, new signature, observation enrollment or correction path.

The initial shape is a priced positive payroll business event settling only completed whole pairs with exactly one scoped original credit. Original source-set completeness and creation visibility, lawful protected business inputs, per-event writer/temporal rule assignment, original policy selection and quantization are independent cumulative requirements. Exact arithmetic and retained current rows cannot fill those gaps. The October 3 **153 priced events remain candidates, not proven or recovery-eligible**; their known original visibility/completeness, business-lineage and writer-provenance gaps remain unresolved.

Ledger derives historical attribution version 1 only after proven original whole-pair shares and scoped monetary identity. Preserve each original share's cents and exact original pricing descriptor; deployed divide-first decimal precision 28/ROUND_HALF_EVEN is not replaced by modern multiply-first pricing. Rational largest remainder uses canonical closing UTC/opening ID/closing ID ties and exact share/payment conservation. The derived attribution is a current read calculation, never claimed to have been recorded historically. Two equally priced source sets, or equal-second pairs swapped between settings, cannot pass without independent original assignment proof.

The 138 unpriced whole-pair candidates, 19 clipped remainders, legacy open fragments, zero runs and 79 manual incident top-ups remain outside this first proof shape. Their future work requires separate reviewed authority. Verification of this documentation package checks incorporation, scope, ownership, versions, links and registrations; runtime acceptance examples are requirements for a later implementation, not tests claimed executed now.

**Exit gate:** business proof is not monetary authorization. Original Ledger creation/posting and complete compensation remain independently required; current v1 gaps still block execution. Missing required original evidence is an unavailable outcome, not permission to invent lineage or weaken higher invariants. No contradiction with higher invariants is introduced because the conditional query denies whenever their evidence requirements cannot be satisfied.

### Phase 2 documentation handoff (October 3, 2026)

The nine-file documentation package passed independent authority/ownership review and **33 distinct targeted documentation checks** covering affected links, archive-citation rules and index completeness. The author's 13 checks overlap that set and are not added again. Verification logs are `/tmp/phase2-authority-docs.log` and `/tmp/phase2-independent-docs.log`; retained test summaries are in `pytest_result`. Version/supersedes entries, explicit DOM/FEAT incorporation and whitespace checks passed. No higher-invariant conflict or unresolved review finding remains.

This handoff completes conditional business-proof authority design only. No runtime API, migration, historical proof record, signature, policy input, recovery path, UI or production change was made. A later implementation must demonstrate the original-evidence requirements with targeted positive/negative fixtures and keep current diagnostic results unchanged until independent proof exists. The present production evidence gaps remain unresolved; neither the 153 candidates nor later cohorts are certified. Implementation design, broader attribution and any deployment remain separate steps.

## Phase 3 — Multi-payment attribution design, separately incorporated

Conditional pure graph authority is separately specified by DOM-PROD-001 §XV.10, DOM-LED-001 §IX.4, DOM-POL-001 §X.3, SPEC-PROD-001 §VI.2, SPEC-PROD-002 §VI.2 and FEAT-PROD-006 §VI.2. FEAT-PROD-005 §VI.2 retains the later atomic integration gate; FEAT-PROD-003's historical graph interaction boundary preserves per-origin full/residual recovery authority. Phase 2's priced whole-pair/single-credit shape remains unchanged. This design adds no schema, protected record, writer, implemented API, proof cache or adoption command.

PROD owns completed canonical pairs connected to all original paid fragments, later remainders, positive incident top-up loss components and original business windows, including zero-event boundaries. Every original source set, creation visibility, exact writer/temporal rule and policy assignment needs independent original evidence. Ledger owns the complete per-credit monetary graph, exact original truncation/quantization replay, allocation, conservation and prior compensation. Multiple credits may legitimately contribute to one interval; each original cent can be attributed and recovered at most once on its own origin. Positive top-up credits are independent original credits, never negative recovery.

Historical graph attribution version 1 is a separate new derived read contract. Preserve original integer whole-second pricing aggregates and per-window/share cents. Group proven exact rational selected subsegment durations by canonical pair before largest remainder. For incident top-ups, preserve each original positive separately quantized worked-price minus replay-paid-price window delta. Prove replay-paid temporal sets are subsets of worked sets; allocate each window delta over exact nonoverlapping loss-duration weights, with canonical closing UTC/opening ID/closing ID ties. Duplicate/overlapping claims, negative losses, zero total loss for positive cents, guessed credit partition or failed conservation deny. No per-component independent rounding or latest-rate wage-minus-payment guess is allowed; amounts are not persisted into PROD.

Original complete compensation remains an independent Ledger prerequisite. Proven full/residual recovery contributes zero further recovery; a partial aggregate without unique interval attribution cannot be distributed by guess or pro rata. Any incomplete/ambiguous origin or graph denies the entire paid invalidation. Pure graph results and the 79 observed top-up references remain separate from original monetary lawfulness and recovery permission. Current v1 gaps still block execution; no old signature, pointer, reservation or sequence is rewritten.

Verification requirements are worked through in SPEC-PROD-001 §VI.2.D: active-row restart, payroll while open, later remainder, complete zero-run boundaries, original aggregate truncation, multiple credits/intervals/top-up windows, exact tie/group conservation, equal-total different graphs, partial/full/residual recovery, missing proof and existing lawful destruction. These are later runtime obligations, not tests executed by this documentation phase. Deployment and historical execution remain separately authorized.

### Phase 3 documentation handoff (October 3, 2026)

The ten-document package passed independent authority/ownership and worked-example review and **33 distinct targeted documentation checks**: 29 affected-document link/archive/dependency checks and four index completeness checks. Author and independent runs select the same 33 nodes and are not added together. Logs are `/tmp/phase3-authority-docs.log` and `/tmp/phase3-independent-docs.log`; retained summaries are in `pytest_result`. Versions, superseded scope, incorporation and whitespace checks passed. No higher-invariant conflict or unresolved review finding remains.

This handoff completes conditional graph authority design only. No runtime code, schema, protected registry, writer, implemented graph API, proof adoption, new signature, historical mutation, UI or production change was made. Source/writer/visibility and monetary gaps remain unresolved; no discovered cohort is qualified for recovery. Phase 4 begins with the independent monetary proof gate: current historical v1 evidence remains unavailable under unchanged requirements, so this handoff does not authorize integration or automatic historical recovery. A later implementation plan must resolve that gate without weakening audit or Ledger invariants.

## Phase 4 — Monetary proof gate and conditional integration

Do not implement this phase unless existing lawful evidence proves all required Ledger facts under INV-ARC-016 and incorporated SPEC-LED-001. Document any proposed extension in DOM-LED-001/DOM-OPS-002 and governing FEAT before changing proof APIs. Keep v2/v3 verification byte-for-byte version-specific. Never default missing historical compensation to zero, trust unsigned reversal pointers, backfill reservations/sequences, reinterpret signatures, or bypass required evidence.

If the gate passes, extend the existing atomic FEAT-PROD-005 coordinator: one target seat and ClassEconomy lock, deterministic locking of all original credits before monetary sources, one command reservation covering all funding/recovery legs, and all-or-nothing eligibility/correction/audit effects. Ledger owns every origin's aggregate cap including pending recovery; funding attribution remains zero. Full/residual/interval commands share the same serialization. Preserve shared protection, no correction fee, signed preview, accepted replay first and exact uncertain retry.

Verification: independent PostgreSQL sessions racing interval/full/residual recovery across every involved origin; aggregate recovery never exceeds any original credit; one missing origin denies all writes; failures at reservation/funding/business/audit/commit roll back the whole graph; original signatures and rows stay unchanged; completed Interpretation/cycle records stay unchanged.

## Phase 5 — Teacher presentation and final verification

Show reconstructed scans/duration and replay findings separately from recovery permission. Explain the specific missing evidence in visible text. Offer automatic correction only if both business and monetary proof gates pass. A pure read must not enroll a historical record into a new proof model; any later authorized adoption is an explicit command with preview and confirmation.

Consult previous pytest results and run only new/affected tests, including pure routes, scope/CSRF, stale preview, uncertain retry and 390px keyboard/touch/axe behavior. Review the authority chain, registrations, typed owning-domain evidence, immutable fields, original signatures, money conservation and absence of fallbacks. Use read-only production aggregate preflight; keep deployment and any historical command execution separately authorized.

## Immediate next action and completion criterion

Phase 1's pure assessment contract and diagnostic runtime are implemented locally. Phase 2's conditional historical business-proof authority is specified and independently reviewed, beginning with the priced full-pair candidate shape. Phase 3's separately incorporated pure graph authority is specified and independently reviewed; it introduces no runtime, persistence or proof adoption. Its implementation is a later step and cannot be represented as production qualification. Per-record legacy emitter provenance, original source-set completeness and creation visibility remain unresolved; arithmetic agreement does not close those gaps. Historical monetary execution is not authorized or promised by this plan. Any later proof extension requires reviewed owning-domain and FEAT authority before implementation. It must never convert incomplete evidence into financial authority. Production remains unchanged; deployment and historical command execution require separate instructions.

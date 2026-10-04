# FEAT-PROD-006: Assess Historical Attendance Proof

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-006 | 1.1 | 2026-10-03 | 1.0 | Normative |

## I. Purpose

Authorize a teacher's pure bounded historical attendance assessment, preserving the distinction between reconstructable work, reproducible arithmetic, signed evidence, and current recovery authority.

## II. Scope

One canonical class and target student seat. This is a read FEAT composed beneath existing teacher/student-detail scope; this phase creates no HTTP route or teacher controls. No mutation FEAT context, reservation, audit observation write, adoption, migration or monetary action is authorized.

## III. Authority Level

Normative, subordinate to INV-CORE-000/001 and the owning-domain authorities below. Incorporates SPEC-PROD-002 in full as a read contract; it does not independently authorize runtime behavior.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6; [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V; [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX; [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md) §V, VIII: pure current teacher/class owner binding through `verify_teacher_owns_class`; class authority is not inferred from historic actors.
- [DOM-IDEN-006](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md): current canonical teacher authority and target scope.
- [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §XIII.9, XV.9: pair, conditional original business proof, payroll boundary, original business evidence and historical descriptors.
- [DOM-POL-001](../DOMAIN/DOM-POL-001_POLICIES_DOMAIN.md) §X.1–2: bounded retained original payroll-setting input DTOs and conditional original-setting evidence contribution.
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §IX.2–3: conditional historical attribution, monetary identity, arithmetic replay and compensation diagnostic conclusions.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §6.1–6.2: unchanged canonical original creation/coverage evidence for conditional proof; §6.2A: separate envelope/coverage diagnostics only.
- [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VIII, incorporated in full; [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §VI–VI.1 incorporates conditional priced whole-pair business proof and derived attribution while retaining execution proof gates.

## V. Inputs and domain interfaces

`assess_historical_attendance_proof(*, ctx, target_seat_id, payroll_event_ids=None, limit=50)` uses class/actor only from current canonical context, never a caller-supplied authority claim. Domain query budgets are fixed server-owned positive bounds under SPEC-PROD-002 §V. Inputs must be canonical positive IDs and bounded selection; scope denial reveals no foreign records. Class Configuration owns current teacher/class binding, and Identity owns current teacher capability and target resolution; this read does not infer authority from a historic actor.

Policies `get_historical_payroll_setting_inputs` supplies bounded immutable retained setting inputs through the existing setting-query boundary. FEAT supplies them to PROD without a direct domain call. PROD `get_historical_attendance_business_evidence` supplies canonical pairs, source-set/boundary limitations, selected payroll facts, retained original pricing and explicit descriptor candidates. Ledger `assess_historical_payroll_money` supplies scoped credit identities, arithmetic comparison, compensation completeness and independent current monetary proof eligibility. Operations `diagnose_historical_audit_coverages` (single-row form `diagnose_historical_audit_coverage`) supplies envelope continuity/coverage observations and limitations. Domain-owned immutable DTOs cross the FEAT boundary; no domain calls another domain or constructs another domain's truth. The FEAT maps observations without computing money, reparsing attendance, or reinterpreting signatures.

## VI. Read orchestration

1. Resolve current Class Configuration owner binding and Identity scope/capability and validate bounded inputs before reading target evidence.
2. Obtain bounded Policies original-setting inputs and bounded complete PROD evidence and Ledger candidate requirements through their domain interfaces. A source cap produces unavailable evidence, not clipped canonical pairing.
3. Obtain Operations batch diagnostics for required original rows/events with one bounded complete class-chain walk per invocation and pass immutable scoped observations to Ledger for its diagnostic monetary conclusion. Do not pass a boolean proof override or convert diagnostics into typed creation evidence.
4. Return separate reconstruction, business replay/membership, pricing provenance, scoped monetary comparison, signed coverage, compensation completeness and current execution-eligibility observations with reasons and locators. Recovery eligibility is blocked unless existing independent proof gates qualify; diagnostic arithmetic success alone never qualifies.

Every query runs without autoflush, locking, commit, reconciliation, closure emission, audit or integrity-status writes. A bounded complete snapshot yields observations of surviving records now; it does not attest historical visibility. No present-day pricing fallback, historical membership override, signature reinterpretation or new proof cache is permitted.

### VI.1 Future conditional business-proof orchestration

The separate future pure evaluation contract in DOM-PROD-001 §XV.9 is coordinated solely by this FEAT, incorporating SPEC-PROD-002 §VI.1 and SPEC-PROD-001 §VI.1. This amendment supplies authority for later implementation design; the current `assess_historical_attendance_proof` runtime remains diagnostic and no new API is claimed. Its fixed server-owned scopes/bounds, no-autoflush and complete-read requirements remain in force.

Identity and Class Configuration establish current teacher/target authority before evidence access. PROD supplies original payroll/source/boundary facts and validates canonical membership; Policies supplies independently proven original setting creation/effective visibility and immutable pricing inputs; Operations supplies original canonical protected-payload and complete-chain evidence through unchanged interfaces, keeping historical diagnostic envelopes separate. Ledger supplies unique scoped original-credit evidence, exact original share arithmetic and derived historical attribution. FEAT composes these owned results only; no domain calls another or interprets another's internal rows. Retained setting DTOs without original visibility proof and candidate emitter descriptors are insufficient. Any unavailable required proof returns its specific reason and preserves reconstruction observations.

Only original priced positive payroll events consisting wholly of completed canonical pairs and one unique original credit qualify for this conditional evaluation. The immutable read result must identify class/target/original business event, complete original source/boundary evidence, per-share original source/policy/rule provenance, independent scoped credit locator and each prerequisite's disposition. Ledger-owned derived cents and historical attribution version are separate from PROD-owned membership. Neither result is `VerifiedCreationEvidence`, a canonical lineage state, a durable enrollment record or correction authority. Ambiguous membership, swapped equal-second policy shares, missing original visibility, unproven protected business lineage, pending/ambiguous credit or changed evidence deny a positive result.

No original scan, summary, signature, reservation, sequence, policy row, cycle or completed Interpretation record is modified. No historical signing, adoption, proof cache, compatibility adapter, correction preview integration, route or UI is authorized. Even a positive original-business result leaves automatic recovery unavailable until original monetary creation/posting and complete compensation are independently proven under unchanged governing contracts and a later scoped integration is authorized. The observed 153-event candidate cohort remains diagnostic; unpriced events, zero runs, fragments/remainders and manual/top-up attribution remain separate future scopes.

## VII. Denials and verification

Reject malformed/overlarge selection and unauthorized scope before target evidence. Return explicit unavailable/unsupported/mismatch observations for missing source assignment, pricing, credit identity, coverage, compensation, visibility or bounds; separate actual integrity failures from unverified historical gaps. Avoid names or other PII in diagnostics.

Verify SPEC-PROD-002 §VIII with targeted tests and consult prior pytest_result first. Current FEAT-PROD-005/003 proof gates, v2/v3 verification, original records and signature bytes must remain unchanged.

## VIII. Amendment

Version 1.1 (2026-10-03) authorizes future conditional original priced whole-pair business proof composition, superseding diagnostic-only contract scope solely for §VI.1. Existing diagnostic runtime, canonical evidence and recovery gates are unchanged.

Initial 1.0 (2026-10-03) authorizes bounded pure assessment. Historical recovery, evidence adoption, routes and presentation require their own later scoped authority and verification.

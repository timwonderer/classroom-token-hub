# FEAT-PROD-006: Assess Historical Attendance Proof

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-006 | 1.3 | 2026-10-03 | 1.2 | Normative |

## I. Purpose

Authorize a teacher's pure bounded historical attendance assessment, preserving the distinction between reconstructable work, reproducible arithmetic, signed evidence, and current recovery authority.

## II. Scope

One canonical class and target student seat. This is a read FEAT composed beneath existing teacher/student-detail scope; this phase creates no HTTP route or teacher controls. This assessment uses no mutation FEAT context, reservation, audit observation write, adoption, migration or monetary action. Its pure reconstruction interfaces are also composed directly by the separately authorized correction FEATs; this read FEAT is never nested.

## III. Authority Level

Normative, subordinate to INV-CORE-000/001 and the owning-domain authorities below. Incorporates SPEC-PROD-002 in full as a read contract; it does not independently authorize runtime behavior.

## IV. Dependencies

- [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6; [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII.
- [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V; [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V; [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V; [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX; [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII.
- [DOM-CLASS-001](../DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md) §V, VIII: pure current teacher/class owner binding through `verify_teacher_owns_class`; class authority is not inferred from historic actors.
- [DOM-IDEN-006](../DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md): current canonical teacher authority and target scope.
- [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §XIII.9, XV.9–10: pair, conditional original business proof, payroll boundary, original business evidence and historical descriptors.
- [DOM-POL-001](../DOMAIN/DOM-POL-001_POLICIES_DOMAIN.md) §X.1–3: bounded retained original payroll-setting input DTOs and conditional original-setting evidence contribution.
- [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §IX.2–4: conditional historical attribution, monetary identity, arithmetic replay and compensation diagnostic conclusions.
- [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §6.1–6.2: unchanged canonical original creation/coverage evidence for conditional proof; §6.2A: separate envelope/coverage diagnostics only.
- [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VIII, incorporated in full; [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §VI–VI.2 incorporates conditional priced whole-pair business proof and derived attribution while retaining execution proof gates.

## V. Inputs and domain interfaces

`assess_historical_attendance_proof(*, ctx, target_seat_id, payroll_event_ids=None, limit=50)` uses class/actor only from current canonical context, never a caller-supplied authority claim. Domain query budgets are fixed server-owned positive bounds under SPEC-PROD-002 §V. Inputs must be canonical positive IDs and bounded selection; scope denial reveals no foreign records. Class Configuration owns current teacher/class binding, and Identity owns current teacher capability and target resolution; this read does not infer authority from a historic actor.

Policies `get_historical_payroll_setting_inputs` supplies bounded immutable retained setting inputs through the existing setting-query boundary. FEAT supplies them to PROD without a direct domain call. PROD `get_historical_attendance_business_evidence` supplies canonical pairs, source-set/boundary limitations, selected payroll facts, retained original pricing and explicit descriptor candidates. Ledger `assess_historical_payroll_money` supplies scoped credit identities, arithmetic comparison, compensation completeness and independent current monetary proof eligibility. Operations `diagnose_historical_audit_coverages` (single-row form `diagnose_historical_audit_coverage`) supplies envelope continuity/coverage observations and limitations. Domain-owned immutable DTOs cross the FEAT boundary; no domain calls another domain or constructs another domain's truth. The FEAT maps observations without computing money, reparsing attendance, or reinterpreting signatures.

## VI. Read orchestration

1. Resolve current Class Configuration owner binding and Identity scope/capability and validate bounded inputs before reading target evidence.
2. Obtain bounded Policies original-setting inputs and bounded complete PROD evidence and Ledger candidate requirements through their domain interfaces. A source cap produces unavailable evidence, not clipped canonical pairing.
3. Obtain Operations batch diagnostics for required original rows/events with one bounded complete class-chain walk per invocation and pass immutable scoped observations to Ledger for its diagnostic monetary conclusion. Do not pass a boolean proof override or convert diagnostics into typed creation evidence.
4. Return separate reconstruction, business replay/membership, pricing provenance, scoped monetary comparison, signed coverage, compensation completeness and current execution-eligibility observations with reasons and locators. Recovery eligibility requires independently validated complete reconstruction or modern exact proof under §VI.1–2; diagnostic arithmetic alone never qualifies.

Every query runs without autoflush, locking, commit, reconciliation, closure emission, audit or integrity-status writes. A bounded complete snapshot yields observations of surviving records now; it does not attest historical visibility. No present-day pricing fallback, client membership override, signature reinterpretation or new proof cache is permitted.

### VI.1 Historical reconstruction composition

This FEAT incorporates SPEC-PROD-002 §V–VIII and SPEC-PROD-001 §VI.1–2 under DOM-PROD-001 §XIII.9/XV.9–10, DOM-POL-001 §X.1–3 and DOM-LED-001 §IX.3–4. Current Identity/Class Configuration capability precedes scoped source access. Policies supplies complete retained original immutable settings; PROD `reconstruct_historical_payroll_graph` supplies complete original-window pairs, selected fragments/remainders/top-up components and original rules. Operations supplies canonical modern creation evidence and separate original audit observations; Ledger `validate_historical_settlement` returns its distinct immutable reconstruction evidence, exact original-credit aggregate replay, derived allocations and complete prior recovery. FEAT never computes cents, selects policies or pairs scans itself.

Recognized legacy immutable-source inputs can qualify despite missing post-rollout allocation fields, original business lineage or signed source visibility. These are visible coverage observations, not an upgrade of original lawfulness. Actual integrity contradictions, ambiguous input/graph/credit identity, unavailable source budget or cryptographic infrastructure, unsupported versions, pending originals or unassociated prior recovery deny. Modern frozen business/monetary sources retain strict version-specific creation proof and cannot fall through to legacy reconstruction. The immutable result binds complete class/target/source/settings/rule/origin/compensation identities; changed relevant evidence is unavailable. No audit, reconciliation, reservation or proof-cache write occurs.

### VI.2 Correction boundary

Complete graph reconstruction includes zero payroll boundaries, original fragment/remainder/top-up credits and relevant prior compensation. Ledger returns newly derived graph attribution version separately from original recorded facts and original canonical lineage. A positive result is an internally validated correction input, not an executable permission or fake CreationEvidence. FEAT-PROD-005/003 compose these owning-domain interfaces directly inside their existing commands; they never execute this FEAT. Their signed preview, locks, replay, one-reservation/new-lineage and all-or-nothing requirements govern correction. No new route, teacher control, migration, historical signing or original-record enrollment is authorized by this read contract.

## VII. Denials and verification

Reject malformed/overlarge selection and unauthorized scope before target evidence. Return explicit unavailable/unsupported/mismatch observations for missing source assignment, pricing, credit identity, coverage, compensation, visibility or bounds; separate actual integrity failures from unverified historical gaps. Avoid names or other PII in diagnostics.

Verify SPEC-PROD-002 §VIII with targeted tests and consult prior pytest_result first. Current FEAT-PROD-005/003 modern proof and new-write gates, v2/v3 verification, original records and signature bytes remain unchanged. Historical reconstruction acceptance follows the separately incorporated current contracts.

## VIII. Amendment

Version 1.3 (2026-10-03) supersedes v1.0–1.2 diagnostic-only/future graph restrictions for explicit immutable-source reconstruction composition. The assessment stays pure; modern proof and actual integrity rejection remain binding. Correction executes only through FEAT-PROD-005/003.


Version 1.2 (2026-10-03) separately incorporates future conditional pure graph composition (§VI.2). Supersedes future-only graph design scope, preserving §VI.1, implemented diagnostics, all proof gates and no-write authority.


Version 1.1 (2026-10-03) authorizes future conditional original priced whole-pair business proof composition, superseding diagnostic-only contract scope solely for §VI.1. Existing diagnostic runtime, canonical evidence and recovery gates are unchanged.

Initial 1.0 (2026-10-03) authorizes bounded pure assessment. Historical recovery, evidence adoption, routes and presentation require their own later scoped authority and verification.

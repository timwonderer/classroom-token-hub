# Historical attendance Phase 4: original proof and integration gate review


**Historical decision record:** the observations below remain a dated read-only investigation. Its blanket no-reconstruction conclusion is superseded by the later user-authorized immutable-source reconstruction contracts summarized in the [current decision package](HISTORICAL_ATTENDANCE_PROOF_DECISION_PACKAGE_20261003.md#current-ruling--immutable-source-reconstruction-and-lawful-new-correction). Original signatures, canonical coverage classifications and actual integrity-failure denials are not superseded. This report does not certify current production or authorize deployment.

Date: October 3, 2026 (America/Los_Angeles). Classification: **informative working review** under SOP-DOC-000 §V–VI. Status: **proof-gap review complete; historical integration gate not satisfied**. This review grants no authority, changes no normative contract, and certifies no production signature. It neither introduces a proof policy nor implements Phase 2/3's conditional interfaces.

## Decision and scope

The database contains useful original relationships, monetary projections and diagnostic repayment evidence. Historical recovery remains unavailable because the unchanged original-payload, business-visibility and complete-compensation requirements have not been established. This is a missing-proof conclusion, not a finding that every stored record is corrupt or that no original fact was authenticated.

The Phase 4 **conditional integration** branch stops at this gate. No partial-proof adapter, historical signature matcher, status substitution, lineage replacement, backfill, migration or recovery command is authorized. Existing prospective code remains separately supported by its previously recorded local tests; this review does not certify its production deployment or qualifying production data.

## Governing contracts

The [decision package](HISTORICAL_ATTENDANCE_PROOF_DECISION_PACKAGE_20261003.md) retains the full implementation sequence and prior verification handoffs. This review applies the following existing authority rather than creating exceptions:

| Contract | Governing requirement |
|---|---|
| [INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6 and [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII | Class/seat isolation, deterministic traceable counter-entries, immutable originals and authority hierarchy |
| [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, VIII–IX | Exact current protected-payload parity and continuous authenticated chain; coverage gaps are distinct from disproven integrity |
| [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII | FEAT composition; no domain-to-domain proof or policy calls |
| [DOM-LED-001](../DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md) §VII.1A, VIII.1.1, IX.1–4 | Per-origin compensation cap, immutable sequence/cursor standing, independent monetary proof and conditional historical attribution |
| [DOM-OPS-002](../DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md) §5.1–5.4, 6.2–6.2A | Exact version-specific payload/envelope and separate diagnostic coverage; no replacement signatures or original-value guesses |
| [DOM-PROD-001](../DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md) §XV.8–10 | Creation-only business lineage, independently proven original membership/visibility/writer, conditional graph scope |
| [FEAT-PROD-005](../FEATURE-EXECUTION/FEAT-PROD-005_INVALIDATE_ATTENDANCE_INTERVAL.md) §VI.1–2, [FEAT-PROD-006](../FEATURE-EXECUTION/FEAT-PROD-006_ASSESS_HISTORICAL_ATTENDANCE_PROOF.md) §VI.1–2 and [FEAT-PROD-003](../FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md) §VI | Independent cumulative paid gates; no historical activation; exact/residual/interval recovery serialization |
| [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §VI–VII and [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §VI–VIII | Incorporated original business/attribution requirements and diagnostic separation |
| [SPEC-LED-001](../SPEC/SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md) §III–V and [SPEC-LED-002](../SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md) §III–VIII | Incorporated independent bounded monetary reconstruction and permanent command identity |
| [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) §V–VI | Informative tracking classification; this unnumbered review is not a runtime contract |

## Evidence provenance and confidence

The read-only TablePlus observation on October 3, 19:34–19:41 PDT used the saved Production connection, PostgreSQL 14.24, database `classroom_economy`, schema `public`, revision `a4b50fee84c3`. Its aggregate report is `/tmp/tableplus-production-proof-inspection-2026-10-03.md`. This review copies only aggregate findings; it performs no additional production query or sensitive row export. The preceding connection interruption was attributed by the user to the server's expired Tailscale key and resolved by reauthentication; that connectivity observation is separate from database proof readiness.

Source inspection is pinned to Git revision `ad9574334d72fd92cc93402e851ab0ebc22aaad9`, previously observed on the deployed server. TablePlus did not independently recheck the live code revision. Earlier record creation requires its own writer attribution: one v1 label cannot select every historical emitter. Relevant source history includes `27c2a7f0816af2be27f3540a08ae716181ea1baa` (seat ownership and reservation serializers), `b821a7b19369a85d977dcc3c1f02ce06f4328d9e` (Store review changes), `bc5c07a2ee71138fdad492358951c331b8c85eb4` and its exact parent `c42f882b8e610d43f355d684a8632d1fa8d50f72` (payroll temporal/pricing changes). These are historical implementation evidence, not current authority.

| Observation | What was checked | What was not checked |
|---|---|---|
| 854 Ledger effects, all v1, with audit links/tokens/versions | Same-class INSERT audit pointers resolve and table/row/token/version agree | Production HMAC authentication, full authenticated chain walk, exact original payload values |
| Positive sequences and reservation references on all 854; 693 reservations | Scoped links exist | Signed original sequence/reservation binding or independent original-command proof |
| All 854 admitted by exact account cursors; zero label/cursor, amount/cents and balance-sum disagreements | Present projection arithmetic and reconciliation agreement | Original immutable sequence authority or independent proof boundary; a snapshot is not its own proof |
| 606 business events: 521 payroll, 84 manual credits, one reversal | Stored classifications and structural relationships | Original protected payroll creation lineage |
| 153 payroll pricing shares; 310 closed-session markers; 79 incident source-reference sets | Surviving summaries | Original complete visible source set, original writer assignment, original allocation proof |
| Zero payroll/attendance/settings INSERT audit records; no allocation version on 521 payroll events | Coverage search in inspected database | Existence or contents of any external contemporaneous archive |

The earlier on-host arithmetic replay (402 positive payroll credits and 119 zero runs) remains a separate diagnostic observation. It does not acquire authentication from this later inspection.

## Exact v1 signed surface: payload, envelope and unsigned context

At the pinned revision, `app/services/ledger_posting_service.py:8–12` and `app/utils/transaction_idempotency.py:139–143` declare eleven payload fields. The historical verifier's eight-field registry (`app/utils/audit_verifier.py:28–39`) is not the emitter definition.

`app/services/audit_service.py:_canonical_payload`, `_compute_context_digest`, `_compute_event_hash`, and `emit_audit_event` establish three different surfaces:

1. The payload digest covers `__table__`, `__pk__`, `__op__`, `__class_id__` and the exact emitter's business values. HMAC binds that digest. Original field-value authentication requires lawful exact payload reconstruction and chain authentication, not just an existing digest.
2. The HMAC envelope directly includes previous hash, chain scope, sequence number, table, row, operation, actor-context JSON, payload digest and audit creation UTC. Its actor-context JSON includes **actor_type, actor_id_hash, feat_id and correlation_id**. These context facts are not absent merely because they are outside the eleven-field business payload. Their production authenticity remains unverified in this inspection.
3. Stored `context_digest` includes feat, class, actor metadata, correlation and **idempotency key**, but that digest is **not an input to this HMAC**. The separately stored context digest/key therefore cannot authenticate the command key. HMAC-bound class chain scope establishes scope context; it does not alone establish every unsigned row field or its original values. Audit `seat_id`, request ID, signer metadata and version label likewise are not additional signed payload fields merely because they are stored.

Audit creation UTC is the audit instant, not authenticated Ledger effective time, scan visibility, policy visibility or payroll window. An authenticated audit FEAT identity is original execution context, not proof that the row's later FEAT label still has that identity. Even a valid envelope and continuous chain cannot enlarge the payload or satisfy all modern required coverage.

## Field-by-field evidence matrix

“Candidate signed” below means declared by the pinned emitter, pending per-record emitter assignment, exact original-value parity and production authentication. “Present unsigned” is not missing data; it is data that cannot supply the required signature coverage. “Unavailable” does not assert tampering.

| Required fact / field | Surviving evidence and exact v1 coverage | Gate disposition / owner |
|---|---|---|
| Table, row ID, INSERT operation | Audit locators match structurally; directly HMAC-bound envelope plus payload-prefix digest | Authentication not performed; Operations |
| Class | Same-class joins agree; signed chain scope and candidate payload `class_id`/prefix | Context is potentially authenticatable; no blanket claim of absent coverage; Operations/Ledger scope |
| Target / actor seats and mechanism | Candidate payload `seat_id`, `target_seat_id`, `actor_seat_id`, `mechanism` | Candidate coverage, original-value validation outstanding; Ledger monetary identity |
| Original amount | Candidate payload Decimal `amount`; present `amount_cents` equals it | Signed amount candidate does not authenticate unsigned integer cents or complete modern credit coverage; Ledger |
| Account and transaction type | Candidate payload `account_type`, `type` | Candidate coverage, exact original parity outstanding; Ledger |
| Description and correlation | Candidate payload `description`, `correlation_id`; correlation also HMAC context | Context can be authenticated separately; matching descriptions/correlation do not by themselves prove settlement membership; Operations/Ledger/PROD |
| Persisted legacy status | Candidate payload `status`; writer creates PENDING and settlement later changes stored value to POSTED | Original full payload not stored. No fabricated PENDING substitution, derived-status override or digest search. Strict v1 creation coverage unavailable; Operations |
| Ledger timestamp/effective time | Present row fields outside eleven-field payload | Present unsigned; audit creation UTC is not substitute time evidence; Ledger |
| Posting sequence | All positive and cursor-admitted; source assigns during later settlement | Present unsigned, not protected original creation input; fails modern original-credit proof requirement; Ledger |
| Current posted/pending standing | Exact class/seat/account cursor admits all effects | Present observed standing. No status-column authority; independent strict reconstruction still requires lawful monetary inputs/boundary; Ledger |
| Initiating FEAT | Original audit `feat_id` in HMAC context; current row labels differ for all 854 | Original context is potentially authenticatable; modern signed row field missing. Known update restamping explains a source-supported mechanism; not proof of corrupt origin; Operations/Ledger |
| Command key | Present row/reservation/audit metadata with historical differences | Not in eleven-field payload or HMAC actor context. Unsigned context digest does not fill this gap; Ledger |
| Reservation link / replay plan | All references resolve; 693 reservations with fingerprints | Present unsigned binding; hash fingerprint is a replay comparison, not original HMAC lineage; Ledger |
| Original policy reference | Present retained policy/summary data when available; outside Ledger v1 payload | Present unsigned monetary reference; original selection/visibility independently required; Policies/PROD/Ledger |
| Compensation origin, attributed cents, correction intent | New three fields absent in production; original/reversal Ledger pointers empty | Required original compensation attribution unavailable; never default NULL/absent to zero; Ledger |
| Payroll business summary and original event identity | 153 pricing sets, 79 incident source references, one reversal source ID | Structurally useful but no original business INSERT audit; cannot promote to lawful protected membership; PROD |
| Scan source-set visibility and original rate selection | Completed current pairs, retained settings, replay agreement | No original attendance/settings creation audit. Original visibility/completeness and writer/rule selection remain unavailable; PROD/Policies |
| Derived exact interval allocation | No original allocation version; Phase 2/3 specify conditional derivation | New derived attribution needs proven original inputs and every independent monetary gate; no automatic execution; Ledger with FEAT composition |

## Interpreting legacy identity differences

The structural observations are 322 row/reservation key differences, 532 audit-context/row key differences, zero audit/row correlation differences, and 854 audit/current-row and reservation/current-row FEAT differences. These counts are not modern-parity corruption verdicts.

Pinned source supports the following mechanisms:

- `app/services/ledger_transfer_service.py:create_transfer_pair` creates one reservation and two effects through the direct `command_reservation` path. That path in `ledger_posting_service.py` does not copy the key onto the individual effect. A NULL effect key versus a non-NULL reservation key is therefore possible by original writer design. The 322 count is consistent with two-leg transfers, but the aggregate report does not establish that exact cohort. Do not claim 161 proven transfer commands from division alone.
- `app/services/ledger_command_service.py:create_reserved_effects` assigns effect keys after creation audit (`115–119`). `app/feats/base.py:audit_protected` does not pass a key to `emit_audit_event`; that emitter defaults FEAT/correlation, not key. Stored NULL audit keys can therefore coexist with populated effect keys. The 532 count is consistent with those mechanisms, not independently classified per row.
- `app/models.py:_enforce_transaction_integrity` runs before both INSERT and UPDATE and restamps `feat_code` from the active FEAT. The settlement path changes status/sequence under settlement authority. Original audit/reservation FEAT versus a later settlement-stamped row FEAT can differ while correlation remains unchanged. Exact per-record execution attribution still needs independent verification.

These source explanations narrow investigation. They do not make unsigned key/reservation/sequence fields authenticated, nor authorize rewriting them to modern parity.

## Existing reversal and incident-credit attribution

One stored reversal's `summary_json.reversed_payroll_event_id` identifies an original payroll event. Scoped joins using command key or correlation find exactly one original positive credit and one negative payroll effect, with exact offsetting amounts. This is positive diagnostic evidence that recovery happened; absent Ledger original/reversal pointers cannot support a zero-recovery assertion.

The inspected summary has no original protected creation audit, and the negative effect's compensation origin/intent and its unsigned business association do not meet current Ledger compensation requirements. The review therefore does not certify that original as fully recovered under the canonical recovery query, does not permit a second debit, and does not derive zero recovery for other originals by absence of links. Complete attribution includes accepted pending effects as well as posted ones; a global observation of no pending effects today does not authenticate complete original recovery history.

The 79 incident manual credits retain `corrected_payroll_event_ids` and scoped original-credit candidates. They are **positive top-ups**, not negative compensation. The remaining five manual credits cannot be assumed attendance-related. Each top-up still needs independently proven original business window/loss component, source visibility, writer/rate/quantization, unique original credit and monetary proof before Phase 3 graph allocation. Matching a present command key is diagnostic identity evidence, not signed command proof.

## Workflow gate decisions

| Workflow | Disposition on inspected historical evidence | Independent missing requirement |
|---|---|---|
| Raw completed intervals and duration display | Supported as scoped present-day evidence through existing pure reads | Display must not claim original visibility or paid eligibility proof |
| Historical arithmetic/payment relationships display | Diagnostic only; Phase 1 existing runtime | Matching totals are not membership or canonical monetary proof |
| Historical original-credit strict proof | No inspected candidate has established every required gate | Exact v1 current protected payload, per-record emitter/authentication and required signed monetary coverage |
| Historical whole-event reversal | Blocked | Lawful original credit/business authority and proven complete zero prior compensation; observed existing reversal is an additional explicit warning |
| Historical residual recovery | Blocked | Lawful original credit and complete authenticated attributable compensation; missing fields cannot mean zero |
| Historical interval correction, including zero additional money | Blocked | Original business membership/visibility/settings/writer, exact allocation and every origin's lawful creation/posting/compensation proof |
| Historical multi-credit/top-up graph correction | Blocked | All graph/business gates plus independent per-origin compensation conservation; one missing origin denies the whole action |
| Prospective unpaid invalidation and qualifying modern paid correction | Separately implemented and locally tested in earlier foundation/feature work | Production deployment/preflight and actual per-record qualification remain separate; historical modernity is never inferred from schema migration |

This review neither relabels raw unpaid intervals ineligible nor turns candidate paid intervals into unpaid work. A payment with unavailable proof remains an unavailable paid correction, not permission for eligibility-only partial commit. No existing strict proof or typed creation-evidence API is changed.

## Handoff and smallest next work

Phase 4 review completes the decision gate; historical integration remains blocked under unchanged authority. Business proof and monetary proof are independent: proving the 153 summaries would not close unsigned original sequence/reservation/cents or unknown compensation; authenticating an envelope would not close original source visibility or protected business lineage.

The smallest next delivery within the existing boundaries is Phase 5 **display of the existing bounded diagnostics**, with explicit evidence-gap explanations, pure scoped reads and no historical correction activation. That UI needs its own implementation plan and targeted route/accessibility checks. Future qualifying-payment controls already implemented earlier can be verified separately; deployment remains separately instructed and gated by production preflight. Optional archive discovery can determine whether contemporaneous original evidence exists, but no archive is claimed found here and unsigned exports cannot retroactively extend original signature coverage.

Any proposed historical recovery exception requires an explicit higher-authority decision outside this package. Stop before runtime integration if it would weaken INV-ARC-016 or Ledger/audit requirements. No unresolved contradiction in the current contracts is introduced by this review: their fail-closed outcome applies.

## Verification record

Prior results consulted: Phase 1's genuine predecessor v1/forward-migration and diagnostic handoff; Phase 2/3 targeted documentation handoffs; `pytest_result/20261004_pytest_test_docs_archive_citations_summary_1.md`. Existing passing runtime tests are context, not rerun or new production certification. This phase edits this informative review, its existing tracking handoff, and exact exclusions for both working documents in `docs-site/docusaurus.config.js`; the publication guard requires these informative working records to remain off the public documentation site. Verification passed **53 distinct targeted documentation checks**: four affected link/archive checks, 45 working-state publication checks, and four documentation-index checks. The independent selection passed eight link/archive/index checks plus two affected publication checks; its six overlapping checks are not added again. Author results are `pytest_result/20261004_pytest_specific_summary_5.md`; independent review confirmed source coverage, identity-transform explanations, scope, denial gates, publication exclusions and absence of historical proof substitutions. No unresolved actionable finding remains. Final whitespace checks passed. No runtime tests or full suite were required or run for these documentation/publication changes.

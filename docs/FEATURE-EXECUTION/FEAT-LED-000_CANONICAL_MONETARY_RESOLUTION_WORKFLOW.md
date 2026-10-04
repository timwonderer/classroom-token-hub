# FEAT-LED-000: Canonical Monetary Resolution Workflow

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-000 | 0.4 | 2026-10-03 | 0.3 | Normative |

---

> **Execution-model reconciliation (2026-09, supersedes conflicting wording below).**
> Per the higher-authority execution model (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2)
> and FEAT-CORE-000 §V.1, there is **no FEAT-to-FEAT execution**. FEAT-LED-000 is
> therefore the canonical monetary-resolution **workflow expressed as Ledger domain
> commands** — `build_intended_ledger_plan` / `resolve_intended_ledger_plan` /
> `apply_resolved_ledger_plan` (plain domain functions), plus the LED-001 posting
> command — which a money-moving business FEAT composes **inside its own single FEAT
> context**. Where this document says a business FEAT "uses FEAT-LED-000" or
> "delegates to FEAT-LED-001", read that as *invokes the corresponding Ledger domain
> command*, never as executing a second FEAT.

## I. Purpose

This FEAT defines the canonical orchestration contract that resolves an intended ledger plan into a resolved ledger plan before any ledger mutation is committed.

It exists to separate:

- business intent
- intended ledger construction
- domain authority decisions
- ledger execution

This FEAT does not define business meaning, translate business intent, or construct the initial ledger plan. It defines the canonical resolution workflow that every money-moving business FEAT must use before its originating FEAT invokes the Ledger posting domain command described by `FEAT-LED-001`.

The resolved plan MUST target the canonical ledger contract:

- class-scoped transaction facts
- immutable insert-only rows
- reconciliation-derived posting state
- snapshot-owned mutable settlement state

---

## II. Scope

This FEAT applies to all class-scoped business workflows that produce or consume a monetary plan before posting.

This FEAT does not own:

- business policy semantics
- monetary truth
- balance derivation
- ledger posting mechanics
- reversal mechanics
- domain-specific entitlement or obligation semantics

---

## III. Authority Level

Normative, subordinate to `INV-CORE-000` §III.1,3–6 and `INV-CORE-001` §III, VIII. Explicit domain commands, pure queries and domain-owned truth derive from `INV-ARC-006` §V, `INV-ARC-007` §V and `INV-ARC-009` §V. `INV-ARC-016` §V and `FEAT-CORE-000` §II–V govern lawful lineage and one atomic FEAT context. `INV-ARC-021` §V, VII forbids nested FEAT execution and direct domain coupling.

---

## IV. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md`
- `docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md`
- `docs/SPEC/SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-005_INVALIDATE_ATTENDANCE_INTERVAL.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`
- `docs/SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md`
- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## V. Canonical Problem Statement

Business features can express monetary intent in many forms, and each such feature must first construct an intended ledger plan:

- a store purchase
- a rent payment
- a fine
- payroll
- an admin adjustment
- interest payout
- a savings transfer

Each of these plans must be resolved against the domains that own monetary truth and policy, and then posted as append-only ledger mutations.

This FEAT defines the canonical ledger plan resolution workflow.

---

## VI. Canonical Objects

### 1. Business Intent

The originating business action and its requested money movement.

### 2. Intended Ledger Plan

An immutable representation of the ledger entries a business FEAT intends to create prior to domain resolution.

This object is not authoritative and MUST NOT be posted directly.

### 3. Domain Resolution

The set of read-only decisions returned by domain authorities that govern whether the plan may proceed, must be transformed, or must be denied.

### 4. Resolved Ledger Plan

The authoritative ledger plan after all required domain decisions have been applied.

This object is the only plan eligible for posting by `FEAT-LED-001`.

Resolved plans should carry the final ledger row shape, including:

- `class_id`
- `target_seat_id`
- `actor_seat_id`
- `mechanism`
- `amount_cents`
- `timestamp`
- `account_type`
- `description`
- `correlation_id`
- `feat_code`
- `idempotency_key`
- `policy_id`
- `type`
- lineage fields

---

## VII. Contract Statement

### 1. Promise

Given a resolved `seat_id`, `class_id`, `correlation_id`, `idempotency_key`, an intended ledger plan, and the relevant class-scoped policy inputs, this FEAT MUST return one of the following:

- a resolved ledger plan
- a denial with an auditable reason

### 2. Canonical Workflow

The FEAT MUST:

1. receive an intended ledger plan from the initiating business FEAT
2. resolve the intended plan against the owning domains
3. apply any authorized plan transformation
4. produce a resolved ledger plan or a denial
5. return the resolved plan to the originating FEAT, which invokes the Ledger posting domain command in its own FEAT context

### 3. Immutable Boundary

This FEAT MUST NOT:

- commit ledger mutations directly
- reinterpret domain truth
- bypass domain authority
- construct the initial intended ledger plan
- decide business meaning outside the plan provided by the initiating FEAT

---

## VIII. Inputs

### 1. Required Context

- `user_id`
- `seat_id`
- `class_id`
- `correlation_id`
- `idempotency_key`

### 2. Required Business Intent

- `action_type`
- `amount`
- any business-specific metadata required to build the intended ledger plan

### 3. Required Domain Inputs

The initiating FEAT resolves Identity actor/target seats and queries Class Configuration for immutable class-scoped banking directives before invoking Ledger. Inputs carry explicit protection applicability and enablement, fee applicability and fee-pricing inputs where separately authorized, canonical account targets, and scoped resolved actor/target identifiers. Typed directives must name their canonical class; a foreign/missing scope, invalid flag, malformed applicable fee value, or unsupported account denies the command. No caller-supplied ORM configuration or Identity model is a substitute for these domain conclusions.

Ledger performs monetary balance, funding, fee-arithmetic and compensation decisions using its own queries plus these supplied directives. Ledger domain functions do not import or call Class Configuration or Identity. The initiating FEAT refreshes their conclusions under serialization for confirmation; preview receives the same pure inputs and writes nothing. All existing charge/deduction callers must supply this interface directly; there is no legacy helper or fallback configuration lookup.

The `BankingDirective` is the immutable Class-owned projection with `class_id`, `version_locator`, `protection_enabled`, optional `flat_fee`, nullable immutable `progressive_fee` pairs, optional `cwi`, and optional UTC `fee_period_start`. Correction directives exclude all fee/CWI/period evaluation. Fee authority supplied by the initiating FEAT is explicitly `NONE`, `FAILED_AGREEMENT`, or `EXPLICIT_FEE`; labels alone grant no authority. `NONE` never emits a fee, including payroll corrections. `progressive_fee=()` means absent/not requested; a tuple of tier/rate pairs means available evidence; `None` means configured evidence unavailable or malformed. Only the applicable fee calculation rejects `None`; `NONE` authority and a fully funded charge ignore irrelevant fee evidence. Period/CWI/fee inputs affect only a separately authorized applicable fee. Ledger derives the exact fee arithmetic and recovery funding from these inputs; it never queries the Class configuration table itself.


Fee applicability is an explicit owning-domain decision separate from protection. A payroll correction supplies no-fee authority and creates no obligation/deferred deduction. An own-account transfer supplies no protection/no fee and must satisfy the existing sufficient-source-funds rule. An authorized checking charge may debit below zero even if savings cannot cover the entire shortfall; insufficient savings is not itself a denial and never permits a partial savings sweep.

---

## IX. Authority Sources

This FEAT MUST derive authority only from:

1. `INV-CORE-000` for class-scoped isolation and deterministic financial logic
2. `INV-CORE-001` for capability-based evaluation at request time
3. `INV-ARC-006` for explicit command boundaries
4. `INV-ARC-008` for seat-scoped identity resolution
5. `INV-ARC-009` for domain-owned state truth
6. `INV-ARC-021` for FEAT-only cross-domain coordination
7. `DOM-CLASS-001` for banking policy inputs
8. `DOM-LED-001` for monetary truth and balance derivation

This FEAT MUST NOT invent authority from:

- route-local logic
- cached state
- prior request outcomes
- label-based heuristics
- business names alone

---

## X. Resolution Outcomes

### 1. ACCEPT

The intended ledger plan may proceed unchanged.

### 2. TRANSFORM

The intended ledger plan must be transformed into a different posting shape before execution.

### 3. DENY

The intended ledger plan cannot proceed under current authority.

---

## XI. Orchestration Rules

### 1. Plan Construction

The initiating business FEAT MUST express its monetary intent as an intended ledger plan before invoking the corresponding Ledger domain resolution command inside its own FEAT context.

### 2. Domain Resolution

The FEAT MUST evaluate the intended ledger plan against the owning domains using read-only authority checks.

The FEAT MUST NOT:

- mutate domain state during resolution
- infer non-provided business meaning
- bypass a domain's authoritative decision

### 3. Finalization

The FEAT MUST convert the resolved result into a resolved ledger plan before posting.

Only the resolved ledger plan MAY be sent to the Ledger posting domain command described by `FEAT-LED-001`; executing another FEAT is forbidden.

### 4. Posting Delegation

`FEAT-LED-001` remains the canonical posting boundary.

This FEAT is upstream of posting and does not replace posting authority.

---

### 5. Shared Charge Funding and Compensation

This workflow explicitly incorporates `SPEC-ECON-003` §4.5.1.1A under `DOM-CLASS-001` §X and `DOM-CLASS-002` §VII. The originating FEAT obtains the class-scoped protection configuration from Class Configuration and available integer-cent balances from Ledger; it passes authorized policy inputs into Ledger resolution without direct domain-to-domain calls. For all authorized checking charges/deductions, including penalties and payroll corrections, resolve an exact savings-to-checking transfer only when protection is enabled and savings covers the **entire** shortfall. Otherwise transfer nothing and allow checking to become negative. No partial savings sweep is permitted. Own-account transfers require sufficient source funds, use no protection and incur no fee.

Funding is separate from business eligibility and failed-agreement fee applicability. The originating business FEAT owns any applicable fee/obligation orchestration. Payroll corrections incur no NSF fee, obligation or deferred deduction. The originating FEAT composes Operations' public typed creation-evidence query over the complete Ledger-owned candidate requirements; Ledger accepts only evidence matching its locked scoped sources and never invokes Operations itself. A correction plan uses `DOM-LED-001` §VII.1A for attributable recovery; funding transfer legs contribute no recovered cents. Productivity owns interval eligibility, frozen source inputs and provenance, and the allocation policy incorporated by `FEAT-PROD-005` and `FEAT-PROD-003` through `SPEC-PROD-001`. Ledger establishes authoritative arithmetic monetary allocations and the recovery cap from proven inputs supplied by the originating FEAT; it does not reconstruct attendance evidence or pricing-policy truth.

Pure preview reports the resolved debit, funding legs and resulting balances without writes. Confirmation revalidates under the shared seat/original-credit locks; any changed expected preview fails closed. All business records, reservations, effects and audit evidence commit atomically through the originating FEAT.

## XII. Invariants

1. **Plan Before Posting**: Every monetary action MUST be resolved into a ledger plan before posting.
2. **Domain-Owned Truth**: Only the owning domain may answer questions about its own truth.
3. **Read-Only Resolution**: Resolution MUST be side-effect free.
4. **Resolved Plan Requirement**: Only a resolved plan may be posted.
5. **Single Posting Authority**: Ledger mutation MUST occur through `FEAT-LED-001`.
6. **Business Neutrality**: This FEAT MUST remain business-domain agnostic.

---

## XIII. Audit Requirements

The DOM-OPS audit record MUST contain:

- `correlation_id`
- `seat_id`
- `class_id`
- initiating business FEAT identifier
- intended ledger plan summary
- resolution outcome
- resolved plan summary or denial reason

---

## XIV. Non-Goals

This FEAT does not:

- define rent semantics
- define store semantics
- define insurance semantics
- define payroll semantics
- define fine semantics
- define admin correction semantics
- define ledger reversal semantics

---

## XV. Change Notes

**0.4 (2026-10-03)** incorporates typed FEAT-supplied banking/Identity directives into Ledger domain commands. It supersedes direct cross-domain configuration or Identity lookup inside monetary resolution and requires all caller paths to adopt the same interface; no compatibility bridge or new fee applicability is authorized.

**0.3 (2026-10-03)** supersedes 0.2's delegated FEAT execution wording with domain-command composition and explicitly incorporates universal full-shortfall charge funding. Prior charge/purchase rejection or partial-savings-sweep behavior is not a compatibility alternative: later implementation must migrate authorized charge paths to this rule while preserving independent business and NSF-fee authority. Runtime behavior is not changed or certified by this document.

## XVI. Amendment

Increment the version, date and supersedes fields; preserve the INV → DOM → FEAT authority chain and side-effect-free resolution.

This contract explicitly incorporates SPEC-LED-002 v1.2 version-4 charge-plan fingerprinting: immutable effect vector plus FEAT-established canonical business identity. Accepted replay resolves before current funding/fee calculation; changed business intent denies. Internal transfers retain their separate exact two-leg serializer and sufficient-funds authority.

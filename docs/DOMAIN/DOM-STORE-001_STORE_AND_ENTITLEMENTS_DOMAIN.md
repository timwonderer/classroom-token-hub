# DOM-STORE-001: Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 5.2 | 2026-09-24 | 5.1 | Normative |

## I. Purpose

Define the Store and Entitlements domain as the canonical authority over what a seat is entitled to and how that entitlement changes over its lifecycle.

This domain records:

- which configured capability was granted to which seat;
- which immutable entitlement lifecycle facts occurred after the grant;
- which entitlement actions are pending authoritative resolution.

This domain does not own class configuration, policy definitions, monetary truth, or obligations. It does own the entitlement that results after a policy definition is lawfully consumed.

## II. Scope

The domain begins when a configured capability or product is lawfully granted to a seat.

The domain ends where another domain owns the authoritative business fact produced by exercising the entitlement.

Examples:

- a late-use entitlement is granted and later consumed entirely inside Store and Entitlements;
- an insurance entitlement is granted here, and each claim made under it is recorded here as durable claim state (§VII.C); claim execution coordinates Ledger and Productivity and Payroll through FEAT;
- a hall pass entitlement is granted here, but the authoritative consumption event may be recorded by another domain;
- a pending delayed-use redemption is preserved here until the lawful FEAT resolves it.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants.

It is subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

## IV. Canonical Business Authority

The Store and Entitlements domain is the sole business authority over:

- entitlement grant lineage;
- entitlement exercise lineage when Store and Entitlements owns the exercise;
- entitlement lifecycle facts for all entitlement types the domain owns;
- pending entitlement actions awaiting authoritative resolution;
- whether a granted entitlement remains currently exercisable;
- the insurance claim lifecycle: claim existence, status, submitted basis and structured evidence, teacher decision, and claim correlation (§VII.C).

Owning both entitlements and claims does not make a claim an entitlement event. An entitlement, a claim, and a pending action are different objects with independent lifecycles inside one domain.

The domain does not own:

- class configuration;
- policy definitions;
- monetary balances or Ledger transactions;
- obligations assessments or satisfaction truth;
- productivity or attendance truth;
- the external business event owned by another domain when that event is the authoritative result of exercising the entitlement;
- derived availability, balance, or remaining-use counts.

Consumers SHALL NOT:

- maintain entitlement counts independently;
- persist `uses_remaining`, `bundle_remaining`, `remaining_claims`, or equivalent mutable entitlement balances;
- infer entitlement existence from labels, cached UI state, or route-local calculations;
- treat a configured product definition as proof that a seat possesses the corresponding entitlement;
- mutate Store and Entitlements persistence directly outside FEAT;
- duplicate another domain's authoritative exercise record.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A specific entitlement was granted.
2. The entitlement belongs to a specific `target_seat_id` within a specific `class_id`.
3. A specific `actor_seat_id` caused or authorized the entitlement event.
4. The entitlement refers to a specific configured product definition from the Policies domain.
5. The grant or subsequent event has a specific provenance.
6. The entitlement event may participate in a specific correlated cross-domain operation.
7. A Store-and-Entitlements-owned entitlement was consumed, expired, or lawfully revoked.
8. A claim-like or redemption-like action was submitted and remains pending authoritative resolution.
9. The pending action preserves the canonical submission timestamp and the authoritative FEAT that must resolve it.
10. The canonical payload for an entitlement event records the type-specific facts necessary to interpret that event.
11. A rent-granted entitlement may expire at the rent-period boundary even when the underlying policy UUID remains current for later cycles.
12. An insurance claim was filed under a specific insurance entitlement, with its submitted basis and structured evidence, and was or was not decided by a lawful teacher decision.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- class boundary and actor resolution from Class Configuration and Identity;
- product definitions and policy terms from Policies;
- Ledger transactions used as purchase funding or coordinated reimbursement truth;
- Productivity, Attendance, or Hall-Pass facts used to evaluate an entitlement action;
- obligation facts that cause a grant or coordinated entitlement effect.

### C. Derived state

The following SHALL be derived and SHALL NOT be persisted as canonical Store and Entitlements truth:

- entitlement balance;
- available count;
- remaining uses;
- remaining claims;
- current display status such as `active`, `used`, `expired`, or `redeemed` when deterministically derivable from canonical facts and policy;
- approval history summaries when those summaries can be derived from immutable facts.

### D. Display-only state

Names, class labels, product labels, descriptions, and other presentation metadata SHALL be resolved through the lawful display/view-model pipeline and SHALL NOT be cached into canonical Store and Entitlements rows merely for presentation convenience.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `entitlement_events`
- `pending_actions`
- `insurance_claims`
- `insurance_claim_productivity_dates`

`insurance_claims` was listed as superseded in v4.0–v5.0, which routed claim truth through `pending_actions` and a `CONSUMED` entitlement event. v5.1 reverses that: claim truth is durable claim state (§VII.C), not entitlement history and not pending-action payload.

The following legacy or superseded persistence concepts are not part of the v5 canonical Store and Entitlements contract:

- `entitlements` as a mutable grant table separate from lifecycle facts;
- `entitlement_consumptions` as a separate terminal-history table;
- `store_purchases`;
- `redemption_events`;
- domain-owned `store_items`;
- domain-owned `store_item_visibility`;
- persisted purchase quantity as entitlement truth;
- `uses_remaining`;
- `bundle_remaining`;
- mutable purchase lifecycle status used as entitlement authority;
- separate obligation-owned entitlement stores.

Store and Entitlements SHALL consume product and policy definitions from the Policies domain and SHALL treat those definitions as external authority.

## VII. Canonical Persistence

### A. `entitlement_events`

`entitlement_events` is append-only canonical entitlement history.

One row represents one immutable entitlement fact.

Key fields:

- `event_id` — primary key for the row
- `entitlement_id` — internal Store/Entitlements lineage key for the entitlement lifecycle
- `class_id` — FK to `classes`; canonical class boundary
- `target_seat_id` — FK to `seats`; seat that possesses or is affected by the entitlement
- `actor_seat_id` — FK to `seats`; teacher seat or student seat that lawfully caused the event
- `product_id` — FK/reference to Policies product definition
- `entitlement_type` — closed enum of lawful entitlement kinds
- `acquisition_type` — closed enum describing how the entitlement arose
- `event_type` — `GRANTED` | `CONSUMED` | `EXPIRED` | `REVOKED`
- `correlation_id` — identifier tying the event to the coordinated lifecycle or cross-domain operation
- `payload` — JSON payload containing type-specific canonical facts required to interpret the event
- `timestamp` — canonical timestamp

Closed `entitlement_type`:

- `INSURANCE`
- `PRIVILEGE`
- `IMMEDIATE_USE`
- `DELAYED_USE`
- `COLLECTIVE_GOAL`
- `HALL_PASS`

Closed `acquisition_type`:

- `PURCHASE`
- `GRANT`
- `PERK`

Actor rules:

- `actor_seat_id` SHALL always be a real seat.
- For teacher-directed or system-originated class actions, `actor_seat_id` is the teacher seat for the class.
- For student-originated actions, `actor_seat_id` is the student seat.

Rules:

- `entitlement_id` SHALL remain stable across the lifecycle of the same entitlement.
- `event_id` identifies one immutable row only.
- `correlation_id` is cross-domain lineage.
- `entitlement_id` is internal Store/Entitlements lifecycle lineage.
- `product_id` SHALL refer to a Policy-owned product definition lawful for the same class boundary.
- `payload` SHALL contain only the type-specific authoritative facts necessary to interpret the event.
- `payload` SHALL NOT duplicate monetary truth, policy rules, or derived balances.
- `entitlement_events` SHALL NOT contain quantity, remaining balance, mutable redemption status, or display metadata.
- Grant rows SHALL NOT be edited to represent later consumption.
- Lawful lifecycle permutations are determined by `entitlement_type` and `acquisition_type` and SHALL be constrained by the domain contract.

### B. `pending_actions`

`pending_actions` holds in-flight work: entitlement actions submitted and not yet resolved. It is persisted (no generic TTL) but transient: a row exists only while its action is unresolved, and it is never authoritative durable state for any record the work produces.

One row represents one submitted entitlement action that has not yet reached canonical resolution.

Key fields:

- `pending_action_id` — primary key for the row
- `class_id` — canonical class boundary
- `seat_id` — seat that submitted or will be affected by the pending action
- `correlation_id` — identifier tying the pending action to the cross-domain operation
- `entitlement_id` — entitlement lifecycle being acted upon
- `authoritative_feat` — the FEAT that is lawfully authorized to resolve the pending action
- `payload` — canonical typed request inputs produced and validated by the submitting FEAT and required by the authoritative FEAT for later resolution
- `submitted_at` — canonical submission timestamp

Rules:

- `pending_actions` exists only while an entitlement action is unresolved.
- `authoritative_feat` SHALL identify the one lawful FEAT path for resolution.
- `payload` SHALL be the canonical typed request envelope produced and validated by the submitting FEAT, not an arbitrary dump of unrelated state.
- `submitted_at` is authoritative and SHALL be preserved.
- No generic TTL may delete pending actions.
- A pending action is not canonical entitlement history.
- `payload` MAY carry a domain-specific request (for example an unresolved insurance-claim request) while the work is in transit. Claim-specific structured data SHALL NOT live permanently in `payload`; it belongs in claim-owned relational state (§VII.C).
- A successful resolution SHALL atomically write the canonical durable record(s) the action produces (entitlement event(s), or claim state under §VII.C) and delete the pending action.
- Resolving or deleting a pending action SHALL NOT delete or rewrite any durable record the work produced.
- A failed resolution SHALL leave the pending action intact.

### C. `insurance_claims`

Durable insurance claim truth. One row is one claim, filed under one insurance entitlement.

Key fields:

- `claim_id` — primary key
- `class_id` — FK to `classes`; canonical class boundary
- `entitlement_id` — the insurance entitlement lineage the claim is made under; a soft reference (entitlements are event-sourced, so there is no row to reference), validated through this domain
- `target_seat_id` — FK to `seats`; the covered seat
- `actor_seat_id` — FK to `seats`; the seat that filed the claim
- `status` — `SUBMITTED` | `APPROVED` | `REJECTED`
- `correlation_id` — unique; idempotent submission lineage
- `claim_basis` — the product-specific facts the student submitted, never frozen policy terms
- `submitted_at` — canonical submission timestamp; authoritative for submission-time rules
- `decided_by_seat_id`, `decided_at`, `decision_note`, `filing_window_override_reason`, `result_amount` — the decision
- `payroll_event_id`, `ledger_transaction_id` — downstream lineage, populated only on approval

Rules:

- a claim references the insurance entitlement; it is not an entitlement event and never writes one;
- `SUBMITTED` is the only non-terminal status; `APPROVED` and `REJECTED` are terminal and immutable;
- policy terms are resolved from the immutable policy the entitlement references, not copied onto the claim;
- no mutable remaining-count, allowance, or payout-capacity field is stored; those are derived from claim history (§XI);
- the claim does not duplicate monetary truth; any Ledger or Payroll effect remains that domain's authority.

### D. `insurance_claim_productivity_dates`

Structured evidence for a `PRODUCTIVITY` claim: one row per asserted class-local loss date, child of `insurance_claims` (CASCADE).

Key fields: `id`, `claim_id`, `entitlement_id`, `class_id`, `claim_date`, `student_claimed_hours`, `student_explanation`, `teacher_approved_hours`, `adjustment_note`, `recognized_payout`.

Rules:

- a date may be claimed at most once per claim and at most once per entitlement;
- the student's submitted hours and explanation are immutable; the teacher's adjudication is recorded alongside them, not over them;
- this evidence is relational claim state, never an opaque list in the claim basis or a pending-action payload.

## VIII. Entitlement Semantics

### A. Grant semantics

An entitlement grant is not synonymous with a purchase. `acquisition_type` is
the authoritative provenance of the grant and MUST distinguish at least
`PURCHASE`, `GRANT`, and `PERK`. Source-specific eligibility and limits belong
to the coordinating FEAT and the owning policy domain; Store and Entitlements
records the resulting immutable entitlement lifecycle.

For products that expose a holding limit, the limit is source-independent:
the student's active quantity for the product lineage MUST NOT exceed the
holding limit after any lawful grant. A purchase limit governs only
`acquisition_type = PURCHASE` and MUST NOT be used as a proxy for current
possession.

`GRANTED` records that the seat acquired the entitlement.

The grant payload MAY be small and need only preserve the minimal authoritative facts required by the entitlement type.

### B. Consumption semantics

`CONSUMED` records that the entitlement was exercised or otherwise reached final disposition for the lawful entitlement lifecycle.

For entitlement types where the exercise is repeatable, multiple `CONSUMED` rows MAY exist for the same `entitlement_id`.

For entitlement types where the exercise is terminal, `CONSUMED` ends the entitlement lifecycle unless the type explicitly allows further terminal facts.

An individual insurance claim is not a consumption event (§VIII.E.1). No exception to the rules above is needed for insurance, because insurance records no `CONSUMED` at all.

### C. Expiration semantics

`EXPIRED` records that the entitlement ceased to be exercisable because the configured validity period or goal boundary ended without further lawful exercise.

Rent-granted entitlements expire at the rent-period boundary. Purchased rent-linked entitlements do not automatically expire just because the rent cycle rolled unless the product contract explicitly says so.

For insurance, the lawful coverage-end boundaries are the end of the last period when renewal stops, and the nonpayment deadline of a `CANCEL_AFTER_X_DAYS` policy (§VIII.E.1). An expiry at the nonpayment deadline is recorded as `EXPIRED` with a nonpayment cause in its payload. It is not a revocation.

### D. Revocation semantics

`REVOKED` records that an otherwise-valid entitlement was lawfully withdrawn through an authorized revocation path.

Revocation law is entitlement-type specific.

### E. Type-specific rules

#### 1. Insurance

Insurance is a continuing entitlement lifecycle.

An insurance purchase SHALL create an entitlement grant and may coordinate an initial obligation assessment/payment lifecycle in the lawful Obligations and Ledger paths.

An insurance entitlement is reusable coverage. It is referenced by claims and is not consumed by any of them.

Claims are durable claim state (§VII.C and §VII.D), not entitlement events. The claimed subject, decision, and outcome that later eligibility checks depend on are read from claim history.

A claim request MAY travel through `pending_actions` while unresolved (§VII.B). The pending action is never the claim record, and resolving it does not delete or rewrite the claim.

Filing, approving, rejecting, or fulfilling a claim SHALL NOT:

- write `CONSUMED`, `EXPIRED`, or `REVOKED` for the insurance entitlement;
- otherwise alter the insurance entitlement.

An `INSURANCE` entitlement records no `CONSUMED` event.

Multiple claims MAY reference the same entitlement while its coverage is lawful, as the governing policy terms permit (claim allowance and payout capacity, FEAT-STOR-003 §XII).

The insurance entitlement terminates only through its coverage lifecycle: `EXPIRED` at a lawful coverage-end boundary (§VIII.C; FEAT-STOR-002). Claim activity never produces a terminal entitlement event.

**Coverage periods.** The entitlement's premium lineage (`DOM-OBL-001` §II.B, one lineage per entitlement) defines its coverage periods: each bill cycle's half-open period `[cycle_boundary_at, next_assessment_at)`. The first period begins at the purchase instant and is never backdated to midnight; the purchase's class-local calendar date anchors the cadence, and every later boundary is class-local midnight on an anchored date (`SPEC-TIME-001` §IX.12, cadence and overflow per `DOM-POL-001A` §V.E). At a boundary the previous period ends unconditionally and can no longer authorize a claim.

**Usability.** An insurance entitlement is usable at a reference time only when all of the following hold:

- it was granted, and no `EXPIRED` or `REVOKED` event takes effect at or before that time;
- Obligations reports the required obligations of its lineage satisfied at that time (`DOM-OBL-001` §VIII).

Store consumes that answer as a boolean. It does not inspect obligation tables, reconstruct payment status, or persist a cached `SUSPENDED`, `payment_current`, or similar authorization state. Because the answer covers every required obligation on the lineage, paying only the newest premium does not restore usability while an older one is outstanding.

**Advance premium and rollover.** Each period's premium is assessed at the bill preview point before the period begins (`DOM-OBL-001` §V.7), and the coordinating FEAT attempts automatic satisfaction from available funds when it is assessed. A failed attempt leaves the premium outstanding; the student may satisfy it manually before or after the boundary. At the boundary, a satisfied premium makes the new period usable immediately, giving continuous coverage; an unsatisfied premium leaves the new period gated.

**Prospective restoration.** Usability is evaluated from facts recorded at or before the reference time. Satisfying a premium late restores usability from the moment of satisfaction forward; it never retroactively restores the gated interval. A claim's eligibility is fixed at filing (§IX, `FEAT-STOR-003`), so a claim filed while gated is not validated by a later payment, and a claim filed while usable is not invalidated by a later lapse, expiry, or termination.

**Nonpayment.** The policy version's frozen `nonpayment_mode` (`DOM-POL-001A` §V.E) governs an unsatisfied premium:

- `ACCUMULATE` — Premiums continue to be assessed on cadence and may accumulate as outstanding obligations. The entitlement stays gated until every required premium is satisfied, and then becomes usable again for the then-current period, provided it has not otherwise terminated. Nonpayment alone never terminates it.
- `CANCEL_AFTER_X_DAYS` — The nonpayment deadline is the coverage boundary at which the earliest outstanding required premium lapsed, plus `cancel_after_days` class-local calendar days. Later assessments do not reset it. `cancel_after_days` may exceed one period, so further premiums may lawfully be assessed before the deadline. If that premium is still unsatisfied at the deadline, the entitlement records `EXPIRED` with a nonpayment cause, effective at the deadline, and its premium lineage is terminated with the deadline as its termination instant (`DOM-OBL-001` §V.7). No premium is assessed for any period after termination. The interval before the deadline is not free coverage: the entitlement is gated throughout.

**Stopping renewal.** Stopping renewal ends coverage at the end of the last committed period (`DOM-OBL-001` §V.7), and the entitlement records `EXPIRED` then:

- if the next period's premium was already paid in advance, that period was purchased: it takes effect, stays usable through its end, and no withdrawal or refund occurs;
- if the next period's premium was assessed but not paid, coverage ends at the current period's end and that premium is withdrawn (`DOM-OBL-001` §V.8): it never becomes owed.

"Cancel" means stop renewal after the coverage already purchased. It never undoes a completed purchase; a refund would be its own explicit contract.

**Debt survives termination.** Termination, whether by nonpayment or by stopping renewal, does not erase, forgive, reverse, or void a premium for any period that began before the termination instant (`DOM-OBL-001` §IX.14). The only premiums that do not survive are unpaid advance premiums for periods beginning at or after it, which are withdrawn because they never became owed (`DOM-OBL-001` §V.8). Satisfying one after termination settles that obligation only and does not resurrect the entitlement. Coverage after termination requires a new purchase, which creates a new entitlement and a new premium lineage.

**Claim periods.** Claim allowance and payout capacity are scoped to one coverage period of the entitlement and reset with each period. A claim draws on the period containing its filing time (`FEAT-STOR-003` §XII).

Resolution of a pending action, the lifecycle of a claim, and termination of an entitlement are independent lifecycle events. Completing one does not complete another.

Any Ledger or Payroll effect of a claim remains that domain's authority; claim state does not duplicate it.

#### 2. Privilege

Privilege represents a non-counted state such as permission to choose a seat or similar class privilege.

Privilege entitlements SHALL:

- grant `GRANTED`;
- end by `EXPIRED` or `REVOKED`;
- not use `CONSUMED`.

#### 3. Immediate use

Immediate-use entitlements are granted and consumed within the same lawful coordinated action.

Immediate-use entitlements SHALL:

- grant `GRANTED`;
- immediately record `CONSUMED`;
- not use `REVOKED`.

#### 4. Delayed use

Delayed-use entitlements may be redeemed later.

Delayed-use entitlements SHALL:

- grant `GRANTED`;
- support a pending action before resolution;
- record `CONSUMED` on successful redemption;
- record `REVOKED` when redemption is rejected and the entitlement is returned/refunded through the lawful reversal path;
- record `EXPIRED` when the configured expiration boundary is reached without lawful exercise.

#### 5. Collective goal

Collective-goal entitlements are granted under a configured threshold or deadline and may be consumed when the configured collective conditions are satisfied.

Collective-goal entitlements SHALL:

- grant `GRANTED`;
- support `CONSUMED` when lawfully exercised;
- record `EXPIRED` when the goal is not reached by the deadline and coordinate a lawful refund;
- record `REVOKED` when the entitlement is withdrawn individually or classwide and coordinate a lawful refund.

#### 6. Hall pass

Hall-pass entitlements are granted here, but their authoritative exercise may be recorded by another domain.

Hall-pass entitlements SHALL:

- grant `GRANTED`;
- support pending action if the exercise requires approval;
- record `EXPIRED` when a perk-based pass reaches the end of the governing rent period without exercise;
- permit `REVOKED` only for direct-grant hall passes when the governing policy allows revocation;
- not create a duplicate Store-and-Entitlements `CONSUMED` row when another domain is the authoritative consumer.

## IX. Pending Action Semantics

`pending_actions` stores durable unresolved entitlement actions.

The row is a deferred FEAT invocation envelope.

The `authoritative_feat` field SHALL identify the canonical FEAT that will resume or finalize the action.

The `payload` SHALL contain the canonical request inputs, and those inputs SHALL be the same inputs that the authoritative FEAT would accept if the action had been executed synchronously.

The `submitted_at` timestamp is authoritative for any rule that depends on submission-time truth.

Examples:

- an insurance claim submitted while coverage is valid remains eligible even if coverage expires before review (the claim's own `submitted_at` governs; §VII.C);
- a delayed-use redemption submitted before expiration remains governed by the submission timestamp where the policy requires that boundary;
- a hall-pass request remains pending until the authoritative FEAT resolves it.

Pending actions SHALL be deleted only as part of successful lawful resolution or lawful deletion of the governing class boundary.

Pending actions SHALL NOT be interpreted as entitlement consumption, approval, rejection, or revocation.

## X. Cross-Domain Contracts

### A. Policies

The Policies domain owns product definitions and versioned feature rules.

Store and Entitlements SHALL consume:

- the configured product identity;
- the product type;
- the active product version or version lineage;
- the product-specific rule payload.

Store and Entitlements SHALL NOT mutate policy definitions directly.

### B. Class Configuration

Class Configuration owns the class universe, enabled features, and class-wide economic environment.

Store and Entitlements may consume class configuration for:

- entitlement availability;
- feature enablement;
- product activation;
- class-scoped visibility;
- grant eligibility;
- policy mode or economic multipliers where the product definition requires them.

### C. Ledger

Ledger owns all monetary truth.

Store and Entitlements may:

- reference Ledger transactions as purchase funding;
- reference Ledger transactions or results as canonical monetary evidence;
- coordinate a lawful Ledger credit/debit through FEAT.

Store and Entitlements SHALL NOT directly write Ledger persistence outside the lawful Ledger mutation boundary.

### D. Productivity and Attendance

Store and Entitlements may read Productivity or Attendance facts only when a product or entitlement type lawfully depends on them.

The authoritative attendance or productivity record SHALL remain in the owning domain.

### E. Obligations

Obligations may lawfully trigger a Store entitlement through a FEAT
coordination path. An obligation-triggered grant is not a purchase, MUST retain
its grant provenance, and MUST be evaluated against the product's
source-independent holding limit. Obligations remains authoritative for
obligation satisfaction and overdue state; Store and Entitlements remains
authoritative for the resulting entitlement lifecycle.

Obligations may cause entitlement grants or coordinated entitlement effects.

Store and Entitlements SHALL not duplicate obligation truth.

### F. Other domains

When an entitlement type produces a business event owned by another domain, that domain owns the authoritative exercise record.

Store and Entitlements may lawfully read that authoritative record for availability or lifecycle projections.

## XI. Projection Rules

Availability, remaining uses, remaining claim counts, and display status SHALL be derived from:

- canonical entitlement event history;
- insurance claim history, for claim allowance and payout capacity (§VII.C);
- lawful pending action state;
- governing policy or product version;
- canonical temporal context;
- authoritative cross-domain records when another domain owns the exercise or settlement fact.

The following SHALL NOT be persisted as canonical truth:

- `uses_remaining`;
- `bundle_remaining`;
- entitlement quantity;
- remaining claims;
- current active/used state;
- current claim allowance;
- current payout allowance;
- other mutable balance-like fields.

## XII. Guarantees

Economic role is configuration guidance, not entitlement authority. A Store
product SHALL carry exactly one `economic_role` from `necessity`, `convenience`,
or `add_on`; the role does not reclassify the product, change its configured
price, or create a new acquisition path. CWI reference position and purchase
scenarios belong to the Economic Engine Helper, while Store remains authoritative
for the product policy and resulting entitlement lifecycle.

This domain guarantees:

- entitlement facts are immutable;
- pending actions preserve unresolved user intent without pretending to be canonical outcome history;
- insurance coverage is not consumed by claims, and claim truth outlives the pending work that carried it;
- product rules are consumed from Policies, not recreated in Store and Entitlements;
- monetary truth remains Ledger-owned;
- other domains retain authority over their own exercise or settlement records;
- availability is derived, not stored;
- no compatibility bridge is required for v5 canonical behavior.

# DOM-POL-001: Policies Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-POL-001 | 2.7 | 2026-10-03 | 2.6 | Constitutional |

## I. Purpose

Define the Policies domain as the class-scoped reference library for teacher-defined products, rules, and entitlements.

Policies answers:

- what definition a teacher configured for a specific capability or product family;
- which exact immutable definition UUID applies to a specific row;
- what contract terms a downstream domain may consume at creation time;
- what class-scoped configuration item is currently selectable for new work.

Policies does not own class identity, class feature enablement, seat identity, money movement, obligations truth, entitlement history, or any other operational fact created after a Policy definition is consumed.

Policies rows are locators, not foreign keys. A row has:

- an immutable `policy_uuid`;
- an immutable family/product identity;
- an immutable definition payload;
- a mutable availability state.

Consumers use the `policy_uuid` to locate the exact definition. Downstream facts own any terms they must preserve after the Policy row is later hidden, retired, or deleted.

## II. Scope

The domain begins when a teacher submits a policy definition for a class-scoped capability.

The domain ends where another domain records the actual business fact produced from that definition.

Examples:

- rent settings define the current or future rent contract and its rent-linked items;
- store items define purchasable or rent-linked entitlement offerings;
- insurance definitions define the insurance product and its claim/coverage terms;
- any other teacher-defined policy family follows the same pattern.

## III. Authority Level

Tier 1 — Constitutional. This document defines the authoritative rule contracts consumed by FEATs and downstream business domains.

It is subordinate to:

- `../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-012_HARD_DELETION_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`

## IV. Canonical Business Authority

Policies is the sole business authority over:

- class-scoped policy definitions for teacher-customized products and rules;
- immutable policy UUIDs that identify exact definitions;
- the payload contract required for downstream domains to consume a definition;
- policy availability for new work.

Policies does not own:

- class existence or class identity;
- feature enablement;
- seat identity;
- entitlement history;
- obligations history;
- Ledger truth;
- productivity or attendance truth;
- display-only state.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A class-scoped policy definition exists for a family or product concept.
2. The policy has a stable `policy_uuid` that identifies the exact definition.
3. The definition payload is immutable after insert.
4. The policy availability state determines whether the definition may be used for new work.
5. A downstream fact may record the `policy_uuid` it used for provenance.
6. A downstream fact that must remain executable after Policy removal must own the terms it needs.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- class boundary and enablement truth from Class Configuration;
- identity and seat truth from Identity;
- monetary truth from Ledger;
- entitlement lifecycle history from Store and Entitlements;
- obligation lifecycle facts from Obligations;
- operational execution facts from their owning domains.

### C. Derived state

The following SHALL be derived and SHALL NOT be treated as canonical Policies truth:

- current visible item list;
- computed eligibility outcomes;
- current claim allowance usage;
- resolved payout amounts;
- remaining limits;
- downstream business facts.

## VI. Insert and Availability Contract

### 0. `policy_uuid` is the version

`policy_uuid` **is** the version identifier for a policy definition. There is no separate version pointer, version number, or active/next-version column layered on top of it.

- Each row in the Policies repository has exactly one immutable `policy_uuid`, assigned at insert and never rewritten.
- Every new submission (first-time or resubmission of an existing family) produces a new row with a new `policy_uuid`.
- Consumers pin provenance by recording the exact `policy_uuid` in force at the moment they created their operational fact (see `DOM-POL-001` §V.A and §VII).
- Availability state (`IN_USE` / `HIDDEN` / `RETIRED`) is a mutable projection *over* the immutable row, not a version pointer.

Any schema element that attempts to create an alternative "current version" or "next version" pointer alongside `policy_uuid` — whether a self-referential FK on a Policies table or an external version-tracking table — is redundant and prohibited, without exception. Domain-specific versioning belongs here, in each family's own table.

*(2.4, operator ruling 2026-09-30.)* The exception carved out of this prohibition on 2026-08-15 for the class-wide `policy_versions` / `policy_transitions` tables (`e6f10734e`) is withdrawn. Those tables were removed from this domain on 2026-08-03 (`184910af8`), were never authorized as canonical, and are retired and dropped. Economic policy is versioned the same way as every other family: by its own rows (`DOM-CLASS-003` §V).

### 1. Repository behavior

Policies is an append-only, immutable repository. It does not originate mutation flows on behalf of other domains — the domain that initiates a policy change (Class Config UI, insurance authoring flow, store curation flow, etc.) submits a new definition through Policies, and Policies records it as a new immutable row keyed by a new `policy_uuid`.

FEAT-POL is the only surface through which rows enter or change availability in this repository.

It supports only these user-visible actions:

1. Insert: record a new policy definition row with a new `policy_uuid` (may be a first-time submission or a resubmission of an existing family)
2. Disable: mark an existing row `HIDDEN` (availability projection only; the definition payload is untouched)
3. Retire: mark an existing row `RETIRED` (availability projection only; the definition payload is untouched)
4. Delete: remove a retired policy row once no surviving downstream fact can lawfully resolve terms from it (§IX)

Any submission — first-time or resubmission — produces a new `policy_uuid`. The backend MUST NOT infer whether a change is meaningful; a submission is a new contract.

Definition payload columns are immutable after insert. There is no "update in place."

When a teacher resubmits Rent Settings, Store Items, Insurance settings, or any other policy family, the result is a new immutable row with a new `policy_uuid`. Prior rows remain readable for provenance.

`HIDDEN` means temporarily unavailable for new selection and may later return to `IN_USE`.
`RETIRED` means permanently unavailable for new selection. It does not by itself make the row deletable (§IX).

### 2. Effective-dated families: `payroll_settings`

*Operator ruling 2026-09-30.* `payroll_settings` is the sole authority for payroll. Payroll reads nothing else. Its selection is by time, not by availability, so the availability projection and actions 2–4 of §VI.1 do not apply to it:

- **Append-only, with an effective date.** Every submission inserts a new row carrying an `effective_date`. No row is updated, hidden, retired, or deleted; the database refuses UPDATE and refuses DELETE except while a class universe is being destroyed. The legal columns are exactly those in `DOM-POL-001A` §V.F; `policy_uuid` is the primary key.
- **In force at an instant.** The row in force at instant *t* is the one with the greatest `effective_date` ≤ *t*; among rows sharing that `effective_date`, the latest `created_at` wins. A row whose `effective_date` is still ahead is *pending*: visible, immutable, and not yet in force. There is no activation step.
- **Effective date on save.** A class's first setting is in force from the moment it is saved (`effective_date = created_at`). Any later submission takes effect at the class's next payroll date (`DOM-PROD-001` §XV.5), so it never governs the cycle that is open when it is made (`DOM-CLASS-003` §VII).
- **One resolver.** Every reader resolves `payroll_settings` through a single domain-service resolver answering "the row in force for `class_id` at *t*". No route, job, or other service queries the table directly.
- **Frozen by reference.** A `payroll_event` records the `policy_uuid` that priced it (`DOM-PROD-001` §XI.3), so every referenced row must stay resolvable; that is satisfied by the table never deleting a row outside class destruction.

## VII. Downstream Domain Contract

Policies is a reference library. It is never the authority for a downstream operational fact; the owning domain is.

A downstream authoritative fact freezes the policy terms it depends on at the moment it is created. There are two lawful ways to freeze them, and the owning domain's document specifies which one a given fact uses:

- **Frozen by value.** The downstream fact persists the terms it needs. It never reads the source policy again.
- **Frozen by reference.** The downstream fact persists the exact immutable `policy_uuid` in force when it was created, and later resolves its terms from that exact version. Because a `policy_uuid` is immutable (§VI.0), resolving it is resolving a contract, not consulting policy state.

Resolving a frozen reference MUST return the exact version identified by the stored `policy_uuid`. It MUST NOT substitute a newer, active, latest, successor, or otherwise different version of the same family, and it is not a read of "the current policy". A downstream fact frozen by reference is unaffected by any later submission in its family.

Where a downstream fact is frozen by reference, the referenced `policy_uuid` is part of that fact's historical contract. The referenced version MUST remain resolvable for as long as any surviving downstream fact can lawfully resolve terms from it (§IX), consistent with `INV-ARC-016`: historical facts remain interpretable from lawful state and are not rewritten by later configuration.

Examples of current contracts:

- an obligation assessment and the bill cycle that drives it are frozen by reference: the assessment amount, and the cycle's scheduling terms, resolve from the `policy_uuid` they carry (`DOM-OBL-001`);
- an insurance entitlement is frozen by reference: its limits, benefits, and claim rules resolve from the `policy_uuid` in its grant (`FEAT-STOR-003`);
- an entitlement created from a Store item carries the terms it needs to keep executing even if the source row is later removed;
- a rent-linked entitlement created from a rent cycle stands on its own until the rent-period boundary closes it out.

Policies may be consulted to create a downstream fact. After creation, the only lawful policy read is the resolution of a frozen reference.

## VIII. FEAT-POL Contract

FEAT-POL actions:

- `New` creates a new policy row and immutable definition.
- `Update` creates a new policy row with a new `policy_uuid`.
- `Disable` sets the current row to `HIDDEN`.
- `Retire` sets the current row to `RETIRED`.
- `Delete` removes a retired row only when live dependencies have drained.

FEAT-POL MUST NOT mutate downstream domain facts directly.
FEAT-POL MUST NOT rewrite historical downstream facts to match changed policy terms.

## IX. Persistence and Schema Status

The v2 persistence model is:

- one immutable `policy_uuid` per policy definition row;
- one stable family/product identity per policy concept;
- one mutable availability state per row (except effective-dated families, §VI.2, which have none);
- one immutable definition payload per row;
- no foreign keys from downstream domains to Policies;
- downstream domains store `policy_uuid` as a non-FK locator and freeze the terms they need, by value or by reference (§VII);
- rent-linked item rows may exist before a rent cycle becomes current, but they are not reachable until OBL makes their rent UUID current.

Availability states:

- `IN_USE` - selectable for new work if the current class/cycle rules make it reachable
- `HIDDEN` - not selectable for new work, but may return to `IN_USE`
- `RETIRED` - not selectable for new work, may remain readable while live dependencies drain, and may later be physically deleted

Definition payloads are immutable after insert.
Replacement creates a new `policy_uuid`.

A retired or superseded policy version MAY be physically deleted only when no surviving downstream fact can lawfully resolve terms from it. Retirement, supersession, or the absence of new issuance does not by itself establish that a version is deletable. Deletion of a class boundary removes its policy rows together with every downstream fact in that class, so no dependency survives it.

Because downstream references are non-FK locators, the database does not enforce this rule; the deletion path must prove it. As of 2026-09-24 no runtime path physically deletes a Policies-repository row outside class deletion (insurance "delete" retires the row), so the rule is latent rather than unenforced.

## X. Boundary Examples

The intended boundary is:

- rent enablement -> Class Configuration
- rent settings -> Policies
- rent-granted items -> Store and Entitlements
- payroll enablement -> Class Configuration
- payroll settings (wage rate, frequency, reward/fine catalog) -> Policies
- payroll events -> Productivity & Payroll (`DOM-PROD-001`)
- hall-pass enablement -> Class Configuration
- hall-pass settings (allowed destinations, limits) -> Policies
- hall-pass consumption records -> Productivity & Payroll (`DOM-PROD-001`)
- store offerings -> Policies
- insurance definitions -> Policies
- insurance entitlement lifecycle -> Store and Entitlements
- banking / interest / overdraft (savings APY, overdraft fees, interest formulas) -> Class Configuration / `economic-engine` (**not** Policies)

This means Class Configuration decides whether a capability exists in the class, Policies stores the class-customized reference material for that capability as immutable version rows, and the consuming operational domain owns the resulting fact.

### X.1 Bounded historical payroll-setting inputs

Policies owns `get_historical_payroll_setting_inputs(*, ctx, class_id, limit=500)`, exposed only through the existing payroll-setting domain query boundary. This pure bounded query returns immutable retained class/policy identity, effective/created UTC instants and original rate inputs with availability limitations; no current/default rate or missing field is synthesized. FEAT-PROD-006 supplies these owned DTOs to PROD for candidate historical setting selection. Policies incorporates [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VI for bounds, pure reads, original configuration and descriptor limitations. Retained values and dates alone do not attest original visibility, original writer assignment or lawful historical creation. No policy write, active selection behavior or deletion rule changes.

### X.2 Conditional original payroll-setting evidence contract

Policies incorporates SPEC-PROD-002 §VI.1 only for a future pure original-setting evidence contribution through FEAT-PROD-006. This contract designation does not claim an implemented API or promote §X.1's retained DTOs to proof. Required inputs are canonical context, explicit class, original payroll-execution identity/boundary, relevant retained setting identities and FEAT-supplied canonical original creation evidence from Operations. Policies establishes the original immutable inputs, creation/effective visibility and completeness of boundary-relevant setting history from independently verifiable original evidence. Present dates, current settings, candidate writer descriptors, fresh signatures or caller proof flags cannot supply unavailable original facts. Source scope and complete bounded reads are mandatory; missing evidence returns unavailable.

Policies neither assigns attendance pairs to shares, computes monetary amounts, verifies Operations internals nor queries another domain. PROD owns original per-pair setting assignment and Ledger owns arithmetic; FEAT coordinates those conclusions. No current setting selection, policy write, proof cache, migration, signature repair or historical recovery is enabled. Existing protected policy lawful-lineage requirements remain unchanged.

### X.3 Conditional graph-setting evidence contribution

Policies separately incorporates SPEC-PROD-002 §VI.2 for its future pure contribution to FEAT-PROD-006's graph evaluation. Each original fragment/remainder/top-up window needs independently proven original immutable setting inputs, creation/effective visibility and complete boundary-relevant history; §X.2's original-evidence requirements apply cumulatively. The exact original writer may select rates differently across legacy windows, so current closing-time selection or the latest retained rate cannot substitute. FEAT supplies canonical original Operations evidence; this domain does not call Operations, PROD or Ledger. It does not assign selected attendance subsegments, compute top-up deltas, sum credits or allocate cents. No implemented API, policy write, new schema, cache, proof adoption or selection fallback is introduced.

## XI. Amendment

Version 2.7 (2026-10-03) separately incorporates original graph-setting evidence contribution (§X.3). Supersedes no policy selection, diagnostic or original-lawfulness rule and enables no runtime or recovery.


Version 2.6 (2026-10-03) adds conditional original-setting evidence contribution (§X.2), superseding no retained-input diagnostic or policy execution rule. It changes documentation authority only, not runtime.

Version 2.5 (2026-10-03) adds §X.1's bounded original-setting input query. It supersedes no policy mutation/selection rule and authorizes no historical recovery.


Revisions must remain consistent with `DOM-CLASS-001`, the consuming operational domain, and the governing FEAT and temporal invariants.

### Seat attribution (INV-ARC-019)

Policy/product authors and transition initiators are recorded as `created_by_seat_id`
within the explicit `class_id`. No User foreign key or principal author alias is permitted.

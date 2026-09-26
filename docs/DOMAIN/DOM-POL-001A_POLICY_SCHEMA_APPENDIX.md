# DOM-POL-001A: Policies Schema Appendix

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-POL-001A | 2.1 | 2026-09-24 | 2.0 | Constitutional Appendix |

## I. Purpose

This appendix records the current domain-specific persistence surfaces that are relevant to `DOM-POL-001`.

It is an appendix to the Policies domain definition, not a replacement for it.

Its job is to answer a narrow question:

> What persistence is currently owned by the domains that consume Policy-defined reference material?

This appendix does **not** define a generic Policy schema beyond the contract already established by `DOM-POL-001`.

## II. Scope

This appendix covers the domain-level persistence definitions currently established for:

- Store and Entitlements
- Obligations
- Class Configuration

It does not add new authority, new tables, or new persistence rules.

## III. Authority Level

This appendix is subordinate to:

- `../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-012_HARD_DELETION_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`

## IV. Class-Level Boundary

Policies are class-scoped reference material.

Before a Policy record can be used, the class boundary and capability boundary must already exist.

Class Configuration owns:

- `classes`
- `feature_settings`
- `class_features`

That domain decides whether the relevant capability exists in the class.

Policies then supplies the class-customized reference material for that capability.

## V. Current Domain Persistence Surfaces

### A. Store and Entitlements

`DOM-STORE-001` currently owns:

- `entitlement_events`
- `pending_actions`

Domain-level persistence notes:

- `entitlement_events` is the immutable entitlement lifecycle history;
- `pending_actions` is the durable unresolved action queue for entitlement work;
- entitlement facts remain sovereign after creation;
- rent-granted entitlements and purchased entitlements may have different lifecycles;
- a granted entitlement may carry a `policy_uuid` for provenance, but not as an FK.

Policy relevance:

- Store and Entitlements consumes class-scoped entitlement/item definitions from Policies;
- the entitlement fact must carry the terms it needs to remain lawful after the source Policy row is later hidden, retired, or deleted;
- the entitlement fact owns the operational truth after creation.

### B. Obligations

`DOM-OBL-001` currently owns:

- `assessment_events`
- `bill_cycles`

Domain-level persistence notes:

- `assessment_events` records liability facts and their lawful resolution history;
- `bill_cycles` records recurring temporal progression for continuing obligation-producing relationships;
- the current rent cycle is the cycle whose period contains the reference time (`DOM-OBL-001` §V.7), not the latest cycle and not a mutable current flag;
- a bill-cycle row may carry the rent `policy_uuid` that it invokes.

Policy relevance:

- Obligations consumes policy inputs when a liability is assessed or scheduled;
- the assessment record freezes the source terms by reference: it carries the exact `policy_uuid` and resolves that immutable version, never the family's current row (`DOM-POL-001` §VII);
- the obligation fact owns the resulting liability truth;
- recurring rent changes are versioned by teacher submission, not inferred from payload diffs.

### C. Class Configuration

`DOM-CLASS-001` currently owns:

- `classes`
- `feature_settings`
- `class_features`

Domain-level persistence notes:

- `classes` stores the class boundary itself;
- `feature_settings` stores class-level economic and feature setup;
- `class_features` stores class-level capability enablement;
- rent enablement belongs here, but rent settings belong to Policies.

### D. Insurance definition tier grouping

The immutable `insurance_policies` definition rows carry optional tier-group columns:

- `tier_group` (string) — the class-scoped group label; NULL = an ungrouped ("single") offering;
- `tier_level` (integer ordinal) — the rank within the group: 1 = basic, 2 = mid, 3 = premium;
- `tier_name` — presentation label for the group/tier.

A tier group is not a table — it is the shared `tier_group` label across member rows.
Within one group at most one **available (`IN_USE`)** row may occupy each rank, so a
group holds at most three active tiers. The constraint is scoped to `IN_USE` rows
because definitions are immutable (an edit mints a new `policy_uuid` and retires the
prior row); a partial unique index
`(class_id, tier_group, tier_level) WHERE availability_state = 'IN_USE' AND tier_group
IS NOT NULL` backstops the FEAT-CLASS-003 command guard. The group-level semantics
(rank set, three-tier cap, one-active-coverage-per-group at purchase) are specified in
FEAT-CLASS-003 §VIII.

### E. Recurring billing terms (rent and insurance)

A recurring policy family carries the terms that schedule its obligations. Each is part of the immutable definition row; a downstream bill cycle resolves them from the exact `policy_uuid` it carries (`DOM-POL-001` §VII, frozen by reference), never from the family's current row.

**Bill preview.** `bill_preview_days` is the interval before a period's coverage boundary at which the obligation for that period is assessed and becomes payable (`DOM-OBL-001` §V.7). It permits early satisfaction; it does not move the due boundary, grace, late-fee, or coverage semantics.

- Rent: `bill_preview_days` MAY be `0` (the rent is assessed at its due boundary, as before). `bill_preview_enabled = false` is equivalent to `0`.
- Insurance: `bill_preview_days` is required and MUST satisfy `0 < preview < minimum_period_duration(charge_frequency)` (`SPEC-TIME-001` §IX.12–13). A zero preview would recreate a coverage gap at every boundary.

**Insurance cadence.** `charge_frequency` is the canonical cadence of an insurance definition: `WEEKLY` or `MONTHLY`, resolved as anchored recurrence from the class-local calendar date of purchase (`SPEC-TIME-001` §IX.12). Monthly recurrence rolls forward when the anchor day does not exist in a month; it never clamps backward.

**Insurance nonpayment.** Each insurance definition fixes, at authoring, what happens when a required premium is not satisfied by its coverage boundary (`DOM-STORE-001` §VIII.E.1):

- `nonpayment_mode` — `ACCUMULATE` or `CANCEL_AFTER_X_DAYS`;
- `cancel_after_days` — required, and greater than zero, when the mode is `CANCEL_AFTER_X_DAYS`; absent otherwise. It may exceed one billing period.

These terms are frozen with the purchased policy version: a later submission changes them only for entitlements purchased under the new `policy_uuid`.

**Policies read.** Policies exposes one family-agnostic read, "the preview interval for `policy_uuid` X", used by Obligations to schedule succession. Obligations does not open `rent_settings` or `insurance_policies`, and does not branch on the family.

## VI. Deferred Policy Schema Areas

The following are intentionally deferred and are not fixed by this appendix:

- whether a given policy family should persist as one table or several family tables;
- which policy families require typed discriminator columns versus JSON-only substructures;
- how each family names its own definition sub-objects;
- how many family-specific payload columns a given policy family needs.

These questions must be answered by working backward from the consuming domains, not by locking in a generic Policy persistence design first.

## VII. Boundary Summary

The current working boundary is:

- Class Configuration decides whether a capability exists in the class.
- Policies defines the class-scoped reference material for that capability.
- Store and Entitlements and Obligations own the resulting operational facts.

## VIII. Amendment

Revisions to this appendix must:

1. remain consistent with `DOM-POL-001`;
2. remain consistent with the owning domain documents;
3. add only schema surfaces that are explicitly authorized by a domain document.

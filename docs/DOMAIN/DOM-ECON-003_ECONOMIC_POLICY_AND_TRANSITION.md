# DOM-ECON-003: Economic Policy and Transition

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-ECON-003 | 2.0 | 2026-05-20 | DOM-ECON-000 (transitional concepts only) | Constitutional |

# I. Purpose

This specification defines the constitutional governance model for economic policy evolution within Classroom Token Hub (CTH).

This specification establishes:
- immutable economic policy lineage,
- lawful future economic state transitions,
- append-only policy evolution,
- visible future economic law,
- operational-boundary activation sovereignty,
- policy supersession legality,
- economic governance transparency requirements.

This specification replaces hidden delayed settings mutation behavior with explicit constitutional policy transition lineage.

---

# II. Scope

This specification governs:
- economic policy versions,
- policy transition legality,
- economic policy mode semantics,
- rebalance governance,
- policy supersession,
- pending economic law visibility,
- activation intent semantics,
- economic transition legality.

This specification applies to:
- rent policy,
- insurance policy,
- banking policy,
- payroll policy,
- future economy-governed operational domains.

---

# III. Authority Hierarchy

This specification is subordinate to:
- INV-CORE-000
- INV-CORE-001
- INV-ARC-015
- INV-ARC-016
- DOM-CORE-001

This specification is authoritative over:
- economic policy governance,
- economic transition legality,
- economic policy evolution semantics.

This specification does NOT define:
- FEAT orchestration behavior,
- operational execution timing,
- scheduler implementation,
- route-layer mechanics.

## Supersession Boundary

This specification supersedes `DOM-ECON-000` with respect to:
- Policy transition governance semantics
- Hidden delayed mutation patterns (prohibited by `ECON-CONST-001`)
- Mutable singleton policy truth (prohibited by `ECON-CONST-006`)
- Any implicit write-on-read or GET-triggered policy activation behavior

`DOM-ECON-000` remains authoritative for:
- Classroom Wage Index (CWI) definition and canonical derivation formulas
- Policy mode ratio bands (tight / default / comfortable) and economic climate definitions
- Savings and interest philosophy, compound growth formulas, and doubling-time constraints
- Solvency validation formulas (budget survival test, catastrophe stability rule)
- Analytics categories and canonical metrics
- Canonical normalization rules (monthly → weekly, semester → weekly, daily → weekly)

Implementations MUST NOT treat `DOM-ECON-000` ratio bands and CWI formulas as superseded. Only the policy mutation and transition governance model is superseded by this document.

## Related Documents

- `docs/DOMAIN/DOM-ECON-000_ECONOMY_GOVERNANCE_FOUNDATION.md` — CWI, ratio bands, solvency rules (remains authoritative)
- `DOM-ECON-004_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE_SPECIFICATION.md` — pending policy visibility requirements
- `FEAT-ECON-001_ECONOMIC_POLICY_TRANSITION_EXECUTION_AND_ACTIVATION_ORCHESTRATION.md` — FEAT-layer execution

---

# IV. Constitutional Principles

## ECON-CONST-001 — Economic Policy Evolution Is Append-Only

Economic policy MUST evolve exclusively through policy transitions.

Direct mutation of active policy state is prohibited.

All economic policy evolution SHALL be represented as immutable transition lineage.

This includes:
- immediate policy changes,
- delayed policy changes,
- rebalance-generated changes,
- manual administrative policy changes.

---

## ECON-CONST-002 — Economic Policy Versions Are Immutable

Economic policy versions represent constitutional economic truth.

Activated policy versions MUST remain immutable.

Historical policy versions MUST remain:
- replayable,
- auditable,
- referentially stable.

Previously active policy versions MUST NOT be modified after replacement.

---

## ECON-CONST-003 — Future Economic Law Must Be Visible

Pending policy transitions are considered publicly announced future economic law.

Pending future economic state MUST be visible to:
- teachers,
- affected students,
- operational domains.

Hidden future economic state is prohibited.

---

## ECON-CONST-004 — Operational Domains Own Boundary Legality

Economic policy governance MUST NOT interpret operational timing legality.

Operational domains remain sole authority over:
- cycle closure legality,
- renewal legality,
- accrual legality,
- rollover legality,
- operational boundary interpretation.

Examples:
- Rent domain owns rent cycle legality.
- Insurance domain owns renewal legality.
- Banking domain owns accrual rollover legality.

---

## ECON-CONST-005 — Policy Governance Owns Policy Lineage

Economic governance remains sole authority over:
- policy version lineage,
- policy transition lineage,
- supersession legality,
- active policy selection,
- pending policy state.

Operational domains MUST NOT directly mutate policy lineage objects.

---

## ECON-CONST-006 — Economic Law Must Be Deterministic

Future economic transitions MUST produce deterministic outcomes.

Policy activation behavior MUST NOT depend on:
- hidden scheduler state,
- mutable delayed payloads,
- undocumented precedence rules,
- implicit operational assumptions.

---

# V. Canonical Objects

## 1. policy_versions

Represents immutable constitutional economic policy truth.

A policy version defines the exact economic rules active for a:

```
(class_id, domain)
```

during a given operational period.

Example fields:

```
id
class_id
domain
version_number
policy_payload_json
created_at
activated_at
created_by_transition_id
is_active
```

Constraints:
- exactly one active policy version per (class_id, domain)
- historical versions MUST remain immutable

---

## 2. policy_transitions

Represents append-only economic policy evolution lineage.

A policy transition defines:
- source policy state,
- target policy state,
- activation intent,
- transition legality,
- supersession lineage.

Example fields:

```
id
class_id
domain
source_policy_version_id
target_policy_version_id
activation_mode
status
created_at
created_by
applied_at
correlation_id
superseded_by_transition_id
cancelled_at
```


---

# VI. Transition States

Allowed transition states:

```
pending | applied | cancelled | superseded | failed
```

Definitions:

| State | Meaning |
|---|---|
| pending | Future economic law exists but is not yet active |
| applied | Transition lawfully activated |
| cancelled | Transition intentionally withdrawn |
| superseded | Replaced by newer lawful transition |
| failed | Transition activation failed |

---

# VII. Activation Intent

Economic governance MAY store abstract activation intent.

Allowed activation modes:

```
immediate | next_boundary | manual
```

Definitions:

| Mode | Meaning |
|---|---|
| immediate | Activate immediately |
| next_boundary | Activate at next lawful operational boundary |
| manual | Await explicit activation |

Economic governance MUST NOT encode:
- operational cycle calculations,
- renewal calculations,
- timezone legality,
- operational timing interpretation.

---

# VIII. Policy Supersession

If a newer lawful transition conflicts with an existing pending transition:

```
new_transition.created_at > existing_pending_transition.created_at
```

the older transition MUST become `superseded`.

The newer lawful transition becomes authoritative.

Supersession MUST remain append-only lineage.

Previously recorded transitions MUST NOT be deleted.

---

# IX. Rebalance Governance

Teacher-visible rebalance operations represent grouped economic governance actions.

Operationally:
- each selected economic change SHALL create an independent policy transition,
- each operational domain SHALL retain sovereign activation legality,
- rebalance execution SHALL NOT collapse multiple domains into single mutable state.

Examples:
- rent transition
- insurance transition
- banking transition

Each transition remains independently governed.

---

# X. Visibility Requirements

Pending economic transitions MUST remain visible through relevant operational surfaces.

Required visibility includes:
- current economic law,
- future economic law,
- activation intent,
- future economic impact.

Affected students MUST be able to view future policy changes affecting:
- obligations,
- premiums,
- pricing,
- recurring economic obligations.

---

# XI. Prohibited Architectural Patterns

The following patterns are constitutionally prohibited.

---

## 1. Hidden Deferred Mutation

Future economic state MUST NOT exist exclusively inside hidden delayed payloads.

Examples:
- `economy_pending_rebalance_json` 

---

## 2. Direct Active Policy Mutation

Active policy versions MUST NOT be mutated directly.

---

## 3. Centralized Operational Timing Interpretation

Economic governance MUST NOT determine:
- rent-cycle legality,
- insurance renewal legality,
- operational rollover legality.

---

## 4. Mutable Singleton Policy Truth

Economic governance MUST NOT rely on:
- singleton mutable settings blobs,
- mutable pending payload pointers,
- overwrite-style future-state mutation.

---

# XII. Relationship to Operational Domains

Operational domains:
- consume active policy versions,
- determine lawful activation boundaries,
- trigger lawful activation requests,
- apply operational consequences.

Operational domains do NOT:
- own policy lineage,
- mutate policy versions,
- determine policy supersession legality.

---

# XIII. Relationship to FEAT Layer

FEAT layer:
- orchestrates execution,
- enforces idempotency,
- coordinates transition application,
- records execution correlation.

FEAT layer does NOT:
- define economic law,
- define policy governance legality,
- define operational timing legality.

---

# XIV. Relationship to DOM-OPS

DOM-OPS owns:
- execution evidence,
- operational telemetry,
- retry traces,
- audit evidence,
- lawful execution observability.

DOM-OPS does NOT own economic policy truth.

---

# XV. Architectural Outcome

This model establishes:
- append-only economic governance,
- immutable economic history,
- visible future economic law,
- deterministic policy evolution,
- sovereign operational timing authority,
- replayable economic policy lineage,
- constitutional economic transparency.

Economic governance therefore behaves as constitutional system law rather than mutable delayed configuration state.

---

## XVI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards.

# DOM-CLASS-003: Economic Policy

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-CLASS-003 | 2.4 | 2026-09-30 | 2.3 | Constitutional |

> [!IMPORTANT]
> **v2.4 (2026-09-30), operator ruling.** "policy versions is explicitly legacy, it was never authorized by me as a canonical table. any documentation that said otherwise were direct violation of my directive." The class-wide tables `policy_versions` and `policy_transitions` are **retired** and dropped (migration `dd52b19d48d8`). The owner removed them from the Policies domain on 2026-08-03 (`184910af8`, PR #1293); this document recreated them on 2026-08-08 (`abb49d75e`, PR #1321) without that authority, and v2.3 had marked them legacy. From v2.4, economic policy lineage **is** each owning domain's own append-only, effective-dated table (§V). There is no separate version table, no transition row, and no activation step.

# I. Purpose

This specification defines the constitutional governance model for class economics within Classroom Token Hub (CTH).

This specification derives its authority from `DOM-CLASS-002`, which in turn derives from `DOM-CLASS-001`. It governs how class economics evolves over time. It owns no table of its own: every economic change is a new row in the owning domain's own table (§V), and `DOM-POL-001` owns how definition tables version.

This specification establishes:
- immutable economics policy lineage,
- append-only policy evolution,
- visible future economic law,
- policy activation sovereignty,
- policy supersession legality,
- rebalancing governance,
- economic transparency requirements.

---

# II. Scope

This specification governs:
- how economic policy evolves in its owning tables,
- when a recorded change governs,
- economic policy mode semantics for `tight`, `default`, and `comfortable`,
- rebalance governance,
- pending future policy visibility,
- activation intent semantics.

This specification applies to the creation of domain-specific rows due to rebalancing actions that apply to:
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
- DOM-CLASS-002

This specification is authoritative over:
- economics policy governance,
- policy activation legality,
- economic policy evolution semantics.

This specification does NOT define:
- FEAT orchestration behavior,
- operational execution timing,
- scheduler implementation,
- route-layer mechanics.

`DOM-CLASS-002` remains authoritative for:
- the supported class economy modes
- the class-economy facts that policy lineage builds on
- the class-level economic posture consumed by downstream specs
- economic configuration context owned by class configuration

`SPEC-ECON-001` and `SPEC-ECON-002` remain authoritative for savings interest behavior and policy visibility behavior, respectively.

## Related Documents

- `docs/DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md` — class economy facts and supported modes
- `docs/SPEC/SPEC-ECON-001_SAVINGS_INTEREST_ACCRUAL_AND_DISBURSEMENT_SPECIFICATION.md` — savings interest accrual and disbursement behavior
- `docs/SPEC/SPEC-ECON-002_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE.md` — pending policy visibility requirements
- `docs/FEATURE-EXECUTION/FEAT-ECON-001_ECONOMIC_POLICY_TRANSITION_EXECUTION_AND_ACTIVATION_ORCHESTRATION.md` — FEAT-layer execution
- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md` — the derived next payroll date that bounds a payroll cycle (§XV.5) and pricing by the setting in force (§XV.3)
- `docs/DOMAIN/DOM-POL-001_POLICIES_DOMAIN.md` §VI.2 — effective-dated `payroll_settings`, the sole payroll authority

---

# IV. Constitutional Principles

## ECON-CONST-001 — Economic Policy Evolution Is Append-Only

Class economics MUST evolve by appending rows to the owning domain's table (§V), each carrying the instant from which it governs (§VII).

Direct mutation of active economics policy state is prohibited.

All economics policy evolution SHALL be represented as immutable rows of the owning table.

This includes:
- immediate policy changes,
- delayed policy changes,
- rebalance-generated changes,
- manual administrative policy changes.

---

## ECON-CONST-002 — Economic Policy Versions Are Immutable

Economics policy versions represent constitutional class-economy truth.

Activated policy versions MUST remain immutable.

Historical policy versions MUST remain:
- replayable,
- auditable,
- referentially stable.

Previously active policy versions MUST NOT be modified after replacement.

---

## ECON-CONST-003 — Future Economic Law Must Be Visible

Pending policy versions are considered publicly announced future economic law.

Pending future economic state MUST be visible to:
- teachers,
- affected students,
- operational domains.

Hidden future economic state is prohibited.

---

## ECON-CONST-004 — Operational Domains Own Boundary Legality

Economics policy governance MUST NOT interpret operational timing legality.

Operational domains remain sole authority over:
- cycle closure legality,
- renewal legality,
- accrual legality,
- rollover legality,
- operational boundary interpretation.

Examples:
- Rent domain owns rent cycle legality.
- Insurance domain owns renewal legality.


---

## ECON-CONST-005 — Policy Governance Owns Policy Lineage

Class economics governance remains sole authority over:
- the rule that selects the row in force at an instant (§VII),
- supersession legality (§VIII),
- what counts as pending policy state (§X).

The lineage itself is the owning domain's append-only table (§V). No domain rewrites a row of it.

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

Economic policy lineage is held in the owning domain's own table. Each row is immutable once written; a change is a new row; the row's own identity (`policy_uuid`, or `economic_version_id` for the Economic Engine) is its version (`DOM-POL-001` §VI.0).

| Economic policy | Owning table | Versioned by |
|---|---|---|
| Payroll | `payroll_settings` | `policy_uuid`, with `effective_date` (`DOM-POL-001` §VI.2) |
| Rent | `rent_settings` | `policy_uuid`; binds when a period is issued (`DOM-OBL-001` §V.7) |
| Insurance | `insurance_policies` | `policy_uuid`; frozen per bill cycle and entitlement (`DOM-STORE-001`) |
| Store prices | `store_products` | `policy_uuid` within a product lineage |
| Banking, overdraft fee, economy mode, CWI inputs | `economic_engine` | `economic_version_id`, with `effective_at` (§VII) |

Downstream facts freeze the owning row's identity (bill cycles and assessments freeze `policy_uuid`, `DOM-OBL-001`; payroll events freeze `payroll_settings.policy_uuid`, `DOM-PROD-001` §XI.3).

The class-wide tables `policy_versions` and `policy_transitions` were retired by operator ruling 2026-09-30. They were never authorized as canonical, and they MUST NOT be reintroduced under any name: no class-wide version table, no transition table, no pointer from a domain row to either.

---

# VI. Policy States

A recorded row is in exactly one of these states, determined by time alone:

| State | Meaning |
|---|---|
| pending | Its effective date is still ahead. It is visible future economic law (§X) and governs nothing yet. |
| in force | It is the row selected at the current instant (§VII). |
| superseded | A later row governs. It remains readable for every fact that froze it. |

There is no `applied`, `cancelled` or `failed` state and no transition row carrying one. A pending row that should not take effect is superseded by saving another row for the same boundary (§VIII); nothing is deleted or rewritten.

---

# VII. Activation Intent

A change is recorded with the instant from which it governs:

| Intent | Recorded as |
|---|---|
| immediate | a row effective when recorded |
| next boundary | a row effective at the owning domain's next boundary, which that domain defines (ECON-CONST-004) |

The row in force at instant *t* is the one with the greatest effective instant at or before *t*; among rows sharing it, the latest recorded wins. Nothing activates a row. Time does: a pending row becomes the row in force when its date is reached. That is not hidden deferred mutation (§XI.1) — the future row is visible, immutable, and carries its own date.

Economics governance MUST NOT encode:
- operational cycle calculations,
- renewal calculations,
- timezone legality,
- operational timing interpretation.

Each owning domain states its boundary:
- **Payroll** — the class's next payroll date (below).
- **Rent** — the first rent period not yet issued. A rent policy binds when a period is issued (`DOM-OBL-001` §V.7), so every period already issued keeps the `policy_uuid` it froze and a change saved mid-period governs the next period. `rent_settings.rent_effective_at` records the start of that period.
- **Economic Engine** — no operational boundary is defined; a change governs from the `effective_at` it is saved with, immediate unless a later instant is given. Which version is in force is answered by one resolver only, the version with the greatest `effective_at` at or before the instant (owner ruling 2026-09-30). A `class_features` row records whether a feature is on; it is not a second answer to which engine version governs.
- **Store prices** and **insurance definitions** — no later boundary; a new row governs new purchases at once, and every bill cycle or entitlement already created keeps the `policy_uuid` it froze.

## Pending Next-Cycle Payroll-Governing Changes

*Restated by operator ruling 2026-09-30 (v2.3). The earlier text recorded a payroll change as a pending transition row with `activation_mode = next_boundary`. That mechanism was never authorized and is retired (§V).*

When a teacher changes a payroll setting (pay rate, pay frequency, first pay date, daily limit, or any other `payroll_settings` column) while a payroll cycle is open, the change MUST NOT govern the open cycle (`INV-ARC-015` §VI.7). Work done under the old setting is paid under the old setting. The change governs from the next payroll cycle boundary.

The change is recorded as an **effective-dated append** to `payroll_settings`, the sole payroll authority (`DOM-POL-001` §VI.2, `DOM-POL-001A` §V.F):

1. Saving settings inserts a new row; no row is ever updated.
2. The new row's `effective_date` is the class's **next payroll date** at the moment of the save — the boundary that closes the open cycle. The next payroll date is derived, never stored (`DOM-PROD-001` §XV.5), so the boundary is known at save time; it is not a guess. A save made while the next payroll date has already passed, but before the scheduled run has happened, takes the following boundary: the overdue boundary already closed the cycle the teacher is working in.
3. The first payroll setting a class ever records governs from the moment it is saved (`effective_date = created_at`): there is no earlier setting to protect.
4. The setting in force at an instant is the row with the greatest `effective_date` at or before it; among rows sharing that `effective_date`, the latest `created_at` wins. A second save before the same boundary therefore supersedes the first at that boundary, while both remain as history. No row is deleted, hidden, or rewritten to express supersession.

Activation needs no transition, command, or scheduler flag: a pending row simply becomes the row in force when its `effective_date` is reached. A manual payroll run does not move the boundary (`DOM-PROD-001` §XV.5), so running payroll early never activates a pending change early.

Pending settings MUST be visible (§X): the teacher's payroll surface shows the setting currently in force and every pending setting with the date it takes effect.

---

# VIII. Policy Supersession

Supersession is expressed by recording, never by rewriting. When two rows of the same owning table and `class_id` claim the same effective instant, the one recorded later governs, and the tie-breaker when timestamps are equal is the table's documented total order (for `payroll_settings` and `economic_engine`: `effective_date`/`effective_at`, then `created_at`, then the row identity). Exactly one row governs each `class_id` at each instant.

Superseded rows remain as history and MUST NOT be deleted while any fact froze them.

---

# IX. Rebalance Governance

A teacher-visible rebalance groups several economic changes into one review. It writes nothing of its own:

- each selected change is carried out by the command that owns it, and its record is that command's new row in the owning table;
- each owning domain keeps its own boundary legality (ECON-CONST-004);
- a change the teacher schedules for the next cycle is a row dated to the owning domain's next boundary (§VII); a change type whose owner defines no later boundary can only be applied immediately.

Examples:
- rent rebalance → a new `rent_settings` row (scheduled: dated to the first rent period not yet issued)
- store price correction → a superseding `store_products` version
- overdraft fee → a new `economic_engine` version

Changing the class's economy mode MUST NOT cancel, supersede or otherwise revoke a scheduled rebalance, and nothing may revoke one implicitly: the scheduled change is already a row of its owning table, and it is changed, like any other row, by recording another. Owner ruling 2026-09-30: "Scheduling the rebalance was an explicit teacher action. Changing mode should not implicitly revoke a separately requested future action. If we want cancellation, that should itself be explicit."

The teacher does not choose when a rebalanced change takes effect; its owning domain does (§VII). A rent change takes effect from the first rent period not yet billed, and there is no "apply immediately" for rent (owner ruling 2026-09-30: a billed period keeps its frozen terms either way, so offering both options was misleading).

---

# X. Visibility Requirements

Pending policy versions MUST remain visible through relevant operational surfaces.

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

Future economic state MUST NOT exist exclusively inside hidden delayed payloads or
undocumented serialized fields.

---

## 2. Direct Active Policy Mutation

Active policy versions MUST NOT be mutated directly.

---

## 3. Centralized Operational Timing Interpretation

Economics governance MUST NOT determine:
- rent-cycle legality,
- insurance renewal legality,
- operational rollover legality.

---

## 4. Mutable Singleton Policy Truth

Economics governance MUST NOT rely on:
- singleton mutable settings blobs,
- mutable pending payload pointers,
- overwrite-style future-state mutation,
- a class-wide version or transition table beside the owning tables (§V).

---

# XII. Relationship to Operational Domains

Operational domains:
- consume the row in force, and freeze its identity on the facts they create,
- define their own boundaries (§VII),
- apply operational consequences.

Operational domains do NOT:
- rewrite a policy row,
- keep a second record of policy lineage,
- determine policy supersession legality.

---

# XIII. Relationship to FEAT Layer

FEAT layer:
- orchestrates execution,
- enforces idempotency,
- writes the owning domain's new row through that domain's command,
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
- append-only economic governance in the owning tables,
- immutable economic history,
- visible future economic law,
- deterministic selection by time,
- sovereign operational timing authority,
- replayable economic policy lineage,
- constitutional economic transparency.

Class economics governance therefore behaves as constitutional system law rather than mutable delayed configuration state.

---

## XVI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards.


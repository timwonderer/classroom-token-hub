# FEAT-ECON-001: Economic Rebalance Execution

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-ECON-001 | 3.0 | 2026-09-30 | 2.1 | FEAT |

> [!IMPORTANT]
> **3.0 (2026-09-30), operator ruling.** Versions 1.x–2.x executed economic changes by creating rows in the class-wide `policy_versions` / `policy_transitions` tables and activating them at operational boundaries. Those tables were never authorized as canonical and are retired (`DOM-CLASS-003` §V, v2.4). This version replaces transition creation, activation, supersession and cancellation with one rule: each change is a new row in its owning domain's table, carrying the instant from which it governs. The file keeps its former name so existing references resolve.

## I. Purpose

This specification defines lawful FEAT-layer execution of a teacher's economic rebalance:
- routing each selected change to the command that owns it,
- recording a change for the owning domain's next boundary,
- refusing a change that cannot run in the requested mode.

This specification governs execution behavior only.

Economic governance law remains defined by:
`DOM-CLASS-003`

---

## II. Scope

This specification governs:
- teacher rebalance workflows,
- immediate execution,
- next-boundary execution,
- idempotent rebalance execution.

This specification does NOT define:
- economic formulas,
- policy legality,
- operational timing legality,
- solvency rules,
- constitutional policy ownership.

---

## III. Governing Authority

This specification is subordinate to:
- FEAT-CORE-000
- DOM-CLASS-003
- DOM-CLASS-001
- DOM-POL-001
- INV-ARC-015
- INV-ARC-016

---

## IV. FEAT Execution Principles

### FEAT-ECON-001 — FEAT Executes, Does Not Govern

The FEAT layer carries out a rebalance through the owning domains' commands.

The FEAT layer MUST NOT define:
- economic law,
- policy legality,
- operational timing legality,
- supersession legality.

---

### FEAT-ECON-002 — FEAT Is Idempotent

All rebalance execution MUST be idempotent.

Execution MUST include:

```
correlation_id
idempotency_key
feat_id
class_id
```

Duplicate execution MUST NOT record a change twice.

---

### FEAT-ECON-003 — FEAT Writes Only Through the Owning Command

A rebalance keeps no record of its own. The owning command's new row is the whole record of each change.

The FEAT MUST NOT:
- rewrite a row of any policy table,
- keep a second record of a change beside the owning row (no version, transition, queue or activation row),
- skip a selected change and still report success.

---

### FEAT-ECON-004 — FEAT Must Respect Sovereignty

Operational domains remain sole authority over their boundaries (`DOM-CLASS-003` §VII).

The FEAT MUST NOT independently determine:
- rent cycle closure,
- insurance renewal legality,
- accrual rollover legality.

---

## V. Rebalance Execution Flow

### Step 1 — Teacher Opens Rebalance Review

System displays:
- current economic configuration,
- recommended values,
- projected impacts,
- selectable changes.

Teacher selects:
- desired changes,
- one activation mode for the submission (immediate or next cycle).

### Step 2 — FEAT Routes Each Change to Its Owner

Each selected change is carried out by the command that owns it (`FEAT-CLASS-005` §XI):

| Change | Owning command | Record |
|---|---|---|
| Rent amount, rent late penalty | rent supersession (`DOM-POL-001` §VI.1) | a new `rent_settings` row |
| Store price | product-version supersession | a new `store_products` version |
| Overdraft fee | Economic Engine evolution (`FEAT-CLASS-005`) | a new `economic_engine` version |

A change type with no owning command is refused, not skipped. Insurance premiums are advisory in the review and change only through insurance management (`FEAT-CLASS-003`).

Grouped teacher rebalance actions MUST NOT collapse several domains into shared pending state. Terms of one contract (a rent amount and its late penalty) are recorded as one row of that contract.

---

## VI. Immediate Execution

If the activation mode is `immediate`, each owning command records its row now. The row governs from the moment it is recorded, subject to the owning domain's rule for work already issued (a rent period already issued keeps the `policy_uuid` it froze, `DOM-OBL-001` §V.7).

Immediate execution MUST remain append-only and preserve historical replayability. Direct mutation of active policy state is prohibited.

---

## VII. Next-Boundary Execution

If the activation mode is next cycle, each change is recorded now as a row of its owning table dated to that domain's next boundary (`DOM-CLASS-003` §VII):

- **Rent** — the start of the first rent period not yet issued. The open period is billed under the terms it froze; the next period issued takes the new row.

The row is pending until its date and visible as pending (`DOM-CLASS-003` §X). Nothing is queued and nothing activates it later: no job, command or boundary hook runs when the date arrives.

---

## VIII. Change Types Without a Later Boundary

Store prices change by product-version supersession, which retires the live version at once, and the overdraft fee by Economic Engine evolution with no operational boundary. Neither owning domain defines a later boundary, so both can only be applied immediately. A next-cycle submission that includes either is refused as a whole; nothing in it is recorded.

---

## IX. Supersession

A later row of the same owning table supersedes an earlier one for the same effective instant (`DOM-CLASS-003` §VIII). Superseded rows remain as history, remain replayable, and MUST NOT be deleted while any fact froze them.

---

## X. Withdrawing a Scheduled Change

A scheduled change is a real row of its owning table. It is withdrawn the way any policy is changed: by recording another row for the same boundary through the owning domain's own surface. Saving a new economy mode does not withdraw it. No row is deleted or marked cancelled.

---

## XI. UI Interaction Contracts

### Teacher Actions

Teachers MUST be able to:
- see which economy changes are scheduled and when each takes effect,
- navigate to the owning domain's surface to change a scheduled row.

### Operational Domain UI Integration

Operational domains SHALL expose:
- pending future policy,
- future economic impact,
- the date a pending row takes effect,
- current active policy.

---

## XII. Operational Safety Constraints

The FEAT layer SHALL NOT:
- mutate historical transactions,
- mutate historical policy rows,
- record a change anywhere but the owning table,
- bypass idempotency enforcement,
- perform write-on-GET behavior.

---

## XIII. Observability Requirements

Rebalance execution MUST record, through the owning commands' own evidence and the application log:
- which changes were applied or scheduled,
- the activation mode,
- refusals.

All execution evidence MUST preserve correlation and idempotency lineage and remain auditable through DOM-OPS observability systems.

---

## XIV. Relationship to DOM-OPS

DOM-OPS owns:
- operational telemetry,
- execution traces,
- retry traces,
- incident evidence,
- execution observability.

FEAT owns:
- lawful orchestration behavior.

DOM-OPS runs no job that activates a scheduled change (`DOM-OPS-001` §8).

---

## XV. Architectural Outcome

This specification establishes:
- one record of each economic change, in its owning table,
- time, not a command, putting a scheduled change in force,
- idempotent economic governance execution,
- sovereign operational timing authority,
- replayable execution history.

The FEAT layer therefore acts as constitutional execution orchestrator rather than policy-law authority.


### Seat attribution (INV-ARC-019)

Policy/product authors are recorded as `created_by_seat_id` within the explicit `class_id`
where the owning table carries an author. No User foreign key or principal author alias is permitted.

# DOM-PROD-001: Productivity and Payroll Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-PROD-001 | 1.12 | 2026-10-03 | 1.11 | Constitutional |

---

## I. Purpose

This document defines the Productivity and Payroll domain as the sovereign of productivity facts, hall-pass execution history, payroll event records, and the business-side facts that justify payroll settlement.

It is the canonical authority for:

- work and participation timing facts
- payroll event records and settlement history
- hall-pass execution history

This domain provides the business meaning that precedes monetary posting. It does not own monetary truth itself.

---

## II. Scope

This domain governs the runtime persistence and authority of:

- productivity session facts
- hall-pass execution facts
- payroll event records and payroll-run lineage

This domain does not own:

- ledger balance truth
- ledger posting authority
- wage policy directives
- class configuration
- rent-derived entitlement quotas
- store entitlement state
- global identity

Class-level tap enablement is owned by Class Configuration and stored on the `classes` table, not inside this domain.

Productivity and Payroll is a business authority, not a monetary authority. It decides what happened and whether that business event may drive a payroll settlement workflow. Ledger decides what money moved.

---

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

---

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

### IV.1 Incorporated contract and governing sections

[INV-CORE-000](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md) §III.1–6 and [INV-CORE-001](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md) §III, VIII govern isolation, authority, financial traceability, and lifecycle. [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md) §V–VII, [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V, and [INV-ARC-009](../INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md) §V–VII govern commands, pure reads, and domain-owned conclusions. [INV-ARC-015](../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md) §VI–VII and [INV-ARC-016](../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md) §V–VI, IX–XI govern time and protected lineage. [INV-ARC-021](../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md) §V, VII forbids direct cross-domain calls and internal cross-domain FKs.

This domain incorporates [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) for interval identity, eligibility, pricing-input provenance, and business correction authorization. This incorporation authorizes no direct dependency on another domain. Cross-domain monetary, identity, configuration, and audit coordination is declared by the applicable FEAT.

## V. Canonical Business Authority

The Productivity and Payroll domain is the sole business authority responsible for:

- productivity participation facts
- hall-pass execution facts
- payroll events
- payroll eligibility and settlement intent derived from productivity facts
- business-side reversal and correction authorization for payroll-originated monetary facts
- terminal interval eligibility decisions without changing attendance evidence

Consumers SHALL NOT:

- reconstruct payroll truth from ledger rows alone
- derive productivity state from unrelated domains
- mutate productivity or payroll persistence directly
- reinterpret payroll business meaning outside this domain

Consumers SHALL instead invoke the canonical business operations owned by this domain.

---

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `attendance_sessions`
- `attendance_interval_invalidation`
- `hall_pass_logs`
- `payroll_event`

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact runtime table list. This domain owns the tables listed there that are assigned to it. `payroll_event` is the canonical payroll event table owned by this domain.

The legacy v1 runtime table `tap_events` has been retired. `attendance_sessions` is the canonical productivity fact table in the active v2 runtime and migration chain.

---

## VII. Owned Tables

### 1. `attendance_sessions`

Append-only productivity timeline facts. Each row records a single tap-in or tap-out event for a seat within a class.

Current attendance state, accumulated daily minutes, and hall-pass elapsed time are derived from this timeline and are not stored on this table.

An interval is the canonical completed opening `active` / closing `inactive` event pair for exactly one `(class_id, target_seat_id)`. The domain pairs its ordered timeline; a caller cannot choose arbitrary endpoints. Eligibility is separately derived from append-only interval decisions, never by filtering or editing the underlying evidence.

Once written, an `attendance_sessions` row is permanent for as long as its seat exists. It SHALL NOT be edited, deleted, soft-deleted, marked as deleted, hidden from payroll, or corrected in place. The sole exceptions are lifecycle destruction of the seat or of the class universe, defined in §VII.1.a.

Inactive attendance records must include a reason:

- `hall_pass`
- `done_for_day`
- `daily_limit`

If the inactive reason is `hall_pass`, the row must carry the specific consumed entitlement instance identifier. This is the same value stored in `hall_pass_logs.hall_pass_id`.

This table does not store hall-pass destination or payroll amount.

#### VII.1.a Immutability Scope and Lifecycle Destruction

Attendance immutability applies to the productivity timeline **of a seat that
exists, within a surviving class universe**. While its seat exists, an
attendance row MUST NOT be edited or deleted by any path, for any purpose.

A row's seat is its `target_seat_id`: the seat whose participation the row
records and whose pay it can justify. `actor_seat_id` is a provenance
reference — the seat that initiated the event (§XI.1) — and does not own the
row, in the same sense that DOM-LED-001 §VII.2 distinguishes ledger provenance
from economic ownership.

This is membership by existence (INV-ARC-013, derived from INV-CORE-000
§III.6) applied to the records anchored on an identity: an entry anchored to the
class boundary (`class_id`) or to an economic actor seat (`seat_id`) exists only
while that anchor exists, and ceases with it (owner ruling 2026-10-01).

Two lifecycle events destroy attendance rows, and neither is correction in
place:

1. **Lawful seat removal.** Removing a seat from a class erases that seat from
   the class "as if they never existed in that class" (INV-CORE-000 §III.6).
   The seat's attendance rows are destroyed together with the seat, in the same
   transaction, by the deletion of the seat itself. There is never a lawful
   state in which the seat is gone but its attendance remains, and never one in
   which the seat remains but some of its attendance is gone.
2. **Lawful class or teacher-account destruction.** The entire class-scoped
   timeline is removed with the class universe (INV-CORE-000 §III.5).

The distinction is between mutating a timeline that continues to exist and
destroying the entity whose timeline it is. While the seat exists, its
attendance is evidence that payroll and Interpretation still depend on, and
removing any part of it would falsify that evidence. When the seat is
destroyed, the participation and everything it justified cease together.

**Enforcement consequence.** The database guard on `attendance_sessions`
refuses every `UPDATE`. It refuses every `DELETE` except (a) one that removes
a row whose target seat no longer exists — reachable only through the
foreign-key cascade of the seat's own deletion — or (b) one made inside a
transaction that has declared class or teacher-account destruction. Deleting
the attendance rows of a seat that still exists is refused regardless of
caller. Deleting an actor seat does not license deleting the rows it acted on:
a cascade from `actor_seat_id` reaches the same guard and is refused while the
row's target seat survives.

### 2. `hall_pass_logs`

Canonical immutable table for issued hall passes. Each row records the approved hall-pass and represents consumption of a single hall pass.

Fields:

- `id`
- `timestamp` — request time
- `class_id`
- `requested_by_seat_id`
- `approved_by_seat_id`
- `correlation_id` — source event/provenance linkage for the consumed hall-pass entitlement; if the pass was purchased from the Store domain, the same correlation ID is also carried by the upstream ledger entry
- `hall_pass_id` — FK-style reference to the specific consumed entitlement instance's `entitlement_id`
- `destination` — preset by teacher

This table does not own actual exit time or return time. Those are logged by `attendance_sessions`.

The presence of a row indicates the pass is approved and consumed.

Hall-pass approval consumes an entitlement. The Entitlement domain records granting or purchasing hall pass.

### 3. `payroll_event`

Canonical append-only table for payroll credits, exact reversals, and separately authorized corrections.

This domain must maintain the authoritative payroll event surface that explains why a payroll FEAT exists, what participation was settled, and what business event was approved for monetary posting.

The payroll event is the human-meaningful authority for:

- what productivity window was settled
- which seats were included
- what payroll batch or run occurred
- whether a payroll-originated monetary fact may later be reversed

---

### 4. `attendance_interval_invalidation`

Append-only, protected terminal decision that a completed interval does not qualify for compensation. It is owned by its target seat within its class. It does not modify the attendance timeline, hall-pass consumption, or completed observations. Exact schema is §XI.4; lifecycle is §VII.1.a: destroy with the target seat or class, never because the acting seat is removed while its target survives.

## VIII. Canonical Write Operations

The only lawful write operations for this domain are the following.

### 1. `record_attendance_session_command(...)`

The PROD-owned command `record_attendance_session_command` is implemented in the same-domain attendance writer service. `record_attendance_session` is FEAT-PROD-001 ingress and composes this command; the domain writer does not import a FEAT executor. `FEAT-PROD-003` and `FEAT-PROD-004` may compose the narrow `close_due_attendance_intervals` PROD command for system closing events, in their existing atomic context; no nested FEAT executes.

Writes a new row to `attendance_sessions`.

Use cases:

- student taps in
- student taps out
- student is marked out for a hall pass
- student is marked done for the day
- student is marked out due to the daily limit

Rules:

- MUST be append-only
- MUST treat every written attendance row as immutable and permanent
- MUST require `class_id` and `seat_id`
- MUST set `status` to `active` or `inactive`
- MUST set `reason_code` when writing an inactive row
- MUST set `hall_pass_id` when `reason_code = hall_pass`
- MUST not store current attendance state, accumulated daily minutes, hall-pass destination, or payroll amount
- MUST not infer or mutate hall-pass entitlement state
- MUST NOT provide delete, soft-delete, mark-deleted, edit, or correction-in-place behavior for attendance rows. Destruction of a seat's rows together with the seat, or of a class's rows together with the class (§VII.1.a), is lifecycle destruction and not such behavior.
- MUST NOT correct payroll outcomes by mutating attendance history

Teacher interval correction is authorized through `FEAT-PROD-005`: append a terminal interval invalidation and, when needed, a payroll correction. Exact whole-event reversal and residual recovery remain `FEAT-PROD-003` operations. No operation mutates attendance evidence.

### 2. `record_hall_pass_log(...)`

Owned by `FEAT-PROD-002`.

Writes or updates the canonical approved hall-pass row in `hall_pass_logs`.

Use cases:

- teacher issues a hall pass
- teacher approves a hall pass request
- approved hall pass is recorded for entitlement consumption

Rules:

- MUST require `class_id`, `requested_by_seat_id`, `approved_by_seat_id`, and `destination`
- MUST read class-scoped `hall_pass_settings` before granting the pass
- MUST fail closed when class-scoped hall-pass settings prohibit the requested destination or limit
- MUST set `correlation_id` to the consumed entitlement grant's `correlation_id`
- MUST set `hall_pass_id` to the consumed entitlement instance's `entitlement_id`
- MUST be the authoritative approved hall-pass instruction
- MUST not record exit time or return time
- MUST not record hall-pass elapsed time
- MUST not record payroll amount
- MUST not be used to derive current attendance state

### 3. `record_payroll_event(...)`

Owned by this domain; lawfully coordinated by `FEAT-PROD-003`, by `FEAT-PROD-004` for class-level settlement, and by `FEAT-PROD-005` for interval corrections, through this domain command.

Writes a new row to `payroll_event`.

Use cases:

- automatic payroll run based on attendance
- teacher-entered manual credit
- reversal of a prior payroll or manual credit event

Rules:

- MUST be append-only
- MUST require `class_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, `idempotency_key`, `mechanism`, `payroll_event_type`, `recorded_at`, and `summary_json`
- MUST record policy provenance according to the authority that determined the amount, not the storage event type alone:
  - `payroll` (amount priced by the payroll settings from attendance/hours): `policy_uuid` is REQUIRED and MUST be a `payroll_settings.policy_uuid` of the same class (§XI.3)
  - `manual_credit` initiated by a teacher who enters the amount directly: no payroll policy is required, and a class with no payroll configuration can still record it
  - `manual_credit` used as the posting mechanism for another domain's lawful calculation (for example a productivity insurance reimbursement): MUST retain the policy provenance that calculation used
  - `reversal` and `correction`: carry the original event provenance; `correction` identifies `original_payroll_event_id` and its correction intent in `summary_json` (§XI.3)
- This is a minimum requirement for `payroll` events only. It MUST NOT be inverted into a rule that `manual_credit` events carry no policy provenance
- MUST set `mechanism` to the path that initiated the event: `SYSTEM` for a payroll run started by the automatic schedule, `TEACHER` for a run the teacher started. The mechanism is supplied by the initiating caller and never inferred (§XV.5 depends on it)
- MUST set `payroll_event_type` to `payroll`, `manual_credit`, `reversal`, or `correction`
- MUST derive payroll amount from authoritative productivity facts or manual credit intent, but MUST not store the amount on the table
- MUST use the same `correlation_id` as the original event when writing a reversal
- MUST preserve original business correlation for exact reversal while its Ledger effect carries the new command correlation and explicit original-credit/compensation locators
- MUST not store payroll period boundaries as persisted fields

### 4. `record_payroll_business_recovery(...)`

Owned by `FEAT-PROD-003`.

Writes the full or residual recovery business record after the owning FEAT establishes Ledger recovery. This PROD command does not call Ledger or calculate money.

Use cases:

- teacher reverses a payroll credit
- teacher reverses a manual credit

Rules:

- MUST create `payroll_event_type = reversal` for `EXACT_REVERSAL` or `correction` for `RESIDUAL`, with the protected command receipt (§XI.3)
- MUST reuse the original event's business `correlation_id` for exact reversal; residual recovery uses its new command correlation
- MUST not mutate the original payroll row
- MUST retain the FEAT-supplied opaque Ledger result and correction-intent locators; Ledger alone establishes exact or residual cents
- MUST fail closed if the original event cannot be established
- MUST require zero prior attributable compensation for exact reversal; after any partial compensation, only the separately authorized residual correction is lawful (§VIII.6)

---

### 5. `record_interval_invalidation(...)`

Owned by this domain and coordinated exclusively by `FEAT-PROD-005`.

- Require a canonical completed pair, class-bound teacher actor, target seat, structured reason, command identity, UTC timestamp, correlation, and lawful audit lineage (§XI.4).
- Append one terminal decision; no restore, replace, edit, delete, or freeform-note command is authorized while its target seat/class exists.
- Exclude the interval from future compensation eligibility. Preserve the scans and all derived factual attendance duration.
- Validate the nonmonetary receipt against PROD-owned membership: unpaid work requires `UNPAID` and no outcome locators; recorded work requires `PAID`, `RECOVERED`, or `ZERO_CENT` and the exact original payroll-event locator. Other/unprovable membership fails closed. This checks business provenance without inferring Ledger amounts; the FEAT remains responsible for verified monetary effects and atomicity.
- Serialize with payroll settlement and all recovery commands for the same `(class_id, target_seat_id)` before resolving eligibility or settlement membership. Use the shared order: target seat, ClassEconomy, original credit, then pending/snapshot monetary sources; a multi-seat run locks seats in stable identifier order. No successful race can both pay work as eligible after committed invalidation and omit its required compensation.
- Paid work requires provable original settlement membership and pricing. The FEAT must append invalidation and any required recovery atomically; unprovable lineage denies the entire action.
- Exact replay returns the original result before recalculating eligibility or money. A different key for an invalidated pair denies `ALREADY_INVALIDATED` and never recovers again.

### 6. `record_payroll_business_correction(...)`

Owned by this domain; coordinated by `FEAT-PROD-005` for `INTERVAL_INVALIDATION` or `FEAT-PROD-003` for `RESIDUAL_RECOVERY`.

Append a `correction` business event through this domain writer, identifying the original event and correction intent. Monetary recovery is supplied by Ledger's domain-owned resolution, not calculated from Ledger internals by PROD. Require original business authority and preservation of policy provenance. No monetary amounts are persisted on PROD rows. The correction uses a new correlation for its command and opaque Ledger source locator; the original event and its correlation remain unchanged.

Partial correction leaves the original settlement intact. Residual recovery compensates only the remaining original credit after attributable compensation. Once fully recovered, further interval invalidation appends the eligibility decision with no new monetary event. Corrected or reversed work stays settled and never becomes payable again. Recovery never advances payroll windows, scheduled occurrences, or economic-cycle boundaries.

## IX. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Productivity Session** | Authoritative Event | Immutable record of a participation interval. |
| **Hall Pass Log** | Authoritative Event | Immutable record of an approved hall-pass instruction. |
| **Payroll Event** | Authoritative Event / Record | Canonical business explanation of a payroll settlement run. |
| **Interval Invalidation** | Authoritative Event | Terminal eligibility decision; original attendance survives. |
| **Payroll Correction Permission** | Derived / Authority State | Original settlement and compensation intent authorized by PROD; monetary effect owned by Ledger. |
| **Payroll Eligibility** | Derived State | Determined from productivity facts, class policy, and current context. |
| **Payroll Reversal Permission** | Derived / Authority State | Determined by this domain before any payroll-originated monetary reversal request is allowed. |

---

## X. Invariants

- **INV-PROD-001: Seat-Scoped Isolation**. All productivity and payroll state shall be anchored to a `seat_id` and `class_id`. No cross-class leakage is permitted.
- **INV-PROD-002: Append-Only Facts**. Productivity sessions and payroll events must be recorded append-only. Corrections require new events or records, not mutation of the original fact.
- **INV-PROD-002A: Attendance Immutability**. Attendance session rows are permanent facts after insertion for as long as their seat exists. They may not be deleted, soft-deleted, edited, marked as deleted, excluded from payroll by mutation, or otherwise corrected in place. Lawful seat removal destroys the seat's attendance with the seat, and lawful class destruction destroys the class's attendance with the class (INV-CORE-000 §III.5–§III.6, §VII.1.a); this is lifecycle destruction, not correction in place.
- **INV-PROD-003: Business Truth Ownership**. This domain owns the business truth for productivity-based earning and payroll settlement. Ledger does not own payroll meaning.
- **INV-PROD-004: Payroll Settlement Requires Authority**. A payroll monetary posting may only occur after this domain has established that the underlying productivity record and payroll event authorize it.
- **INV-PROD-005: No Hidden Payroll State**. Payroll status, payroll eligibility, and reversal permission must be explicit domain state or derived from authoritative domain records. They may not be reconstructed from ledger rows alone.
- **INV-PROD-006: Class-Time Evaluation**. Productivity windows and payroll eligibility MUST use class-local temporal evaluation.
- **INV-PROD-007: Hall-Pass History Preservation**. Completed hall-pass history must not be silently erased. Hall-pass history is never erased in place: while its seat exists, a `hall_pass_logs` row is neither deleted nor corrected. It is destroyed only with its seat, by lawful seat removal, or with its class, by lawful class or teacher-account destruction (INV-CORE-000 §III.5–§III.6; membership by existence, INV-ARC-013) — the same lifecycle boundary §VII.1.a states for attendance. That destruction is not an erasure of surviving history.
- **INV-PROD-009: Terminal Eligibility**. Invalidation excludes compensation without hiding attendance; previous recovery does not make settled work unpaid.
- **INV-PROD-008: No Financial Truth**. This domain does not compute balances, spendable funds, or monetary reconciliation.

---

## XI. Schema Contract

### 1. `attendance_sessions`

Key fields:

- `id`
- `actor_seat_id` — FK to `seats` (`ON DELETE CASCADE`); provenance — the seat that initiated the event. For `self` rows it equals `target_seat_id`.
- `target_seat_id` - FK to `seats` (`ON DELETE CASCADE`); the seat the row belongs to (§VII.1.a)
- `mechanism` - `self` | `teacher` | `system`
- `class_id` — FK to `classes`; canonical isolation boundary
- `status` — `active` | `inactive`
- `timestamp` — UTC
- `reason_code` — enumerated: `hall_pass` | `done_for_day` | `start_work`
- `hall_pass_id` — FK-style reference to the specific consumed entitlement instance's `entitlement_id`, required when `reason_code = hall_pass`


Rules:

- `attendance_sessions` is append-only.
- Rows are never edited after creation.
- Rows are never deleted or marked as deleted while their target seat exists. They are destroyed only with their seat or with their class (§VII.1.a).
- There is no canonical attendance-row deletion, soft-deletion, or correction API. Seat removal removes a seat's rows only by deleting the seat; class and teacher-account destruction declare themselves before removing the class's rows.
- Teacher correction of an interval is performed by `FEAT-PROD-005` using append-only invalidation and any required payroll correction; original attendance remains unchanged.
- Every session is scoped to exactly one `class_id`.
- At most one active session may exist for a given `(class_id, target_seat_id)` without a corresponding inactive event.
- The platform SHALL execute the following state transition automatically:
    - Starting an active session SHALL automatically generate an `inactive` row for any `active` session under the same `(class_id, target_seat_id)` with the `reason_code = done_for_day`
    - Any `active` sessions SHALL automatically terminate by end of day at canonical class timezone with the `reason_code = done_for_day`. Timestamp for the `inactive` entry SHALL be recorded using the same date as the originating `active` entry.
    - An `inactive` state with `reason_code = hall_pass` exist without a corresponding `active` row (known as "hanging hall pass") SHALL automatically generate an `active` row and an `inactive` + `reason_code = done_for_day` using the same timestamp when the following occurs: the day ends in the canonical class timezone. Activity in another class never selects or closes this seat's timeline.
    - An `active` session reaching or exceeding the set daily limit SHALL generate an `inactive` row with `reason_code = done_for_day`. If the session exceeds the set limit, the closing row shall correct the timestamp so the accumulated time is equal to the set limit.
- System-generated transitions MUST use the canonical teacher seat for the explicit class_id, resolved through the Identity domain’s canonical seat-resolution operation.
- Current attendance state and accumulated daily minutes are derived from this timeline and are not stored here. 
- Hall-pass destination and hall-pass elapsed time are derived elsewhere and are not stored here.
- Payroll amount is derived from this table but is not stored here.

### 2. `hall_pass_logs`

Key fields:

- `id`
- `timestamp` — request time, UTC
- `class_id` — FK to `classes`
- `requested_by_seat_id` — FK to `seats`
- `approved_by_seat_id` — FK to `seats`
- `correlation_id` — source event/provenance linkage for the consumed hall-pass entitlement
- `hall_pass_id` — FK-style reference to the specific consumed entitlement instance's `entitlement_id`
- `destination` — preset by teacher

Rules:

- This table is immutable, append-only. Rows are destroyed only with their seat or their class (INV-PROD-007).
- A row gets created when the pass is approved.
- The presence of a row indicates the pass is approved and consumed.
- Actual exit time and return time are not stored here.
- `hall_pass_logs` is the authoritative hall pass consumption record. Stores and Entitlement Domain SHALL store hall pass grant or purchase.
- Remaining hall pass count is a derived value, not stored.

### 3. `payroll_event`

Key fields:

- `id`
- `class_id` — FK to `classes`; canonical isolation boundary
- `payroll_cycle_id` — durable economic-period identity (UUID) for the class-level payroll run that produced this event; NULL only for non-boundary events that are not part of a run (see rules below)
- `actor_seat_id` — FK to `seats`; the seat that initiated or authorized the payroll event
- `target_seat_id` — FK to `seats`; the seat whose productivity settlement or reversal is affected
- `correlation_id` — workflow correlation identifier linking payroll business and ledger facts; reversals reuse the original event's correlation_id
- `idempotency_key` — unique payroll-run replay guard
- `policy_uuid` — the `payroll_settings.policy_uuid` that priced the amount; required for `payroll` events, absent for teacher-entered manual credits (see §VIII). A non-FK locator (`INV-ARC-021` §V.7)
- `mechanism` — `TEACHER` | `SYSTEM`; for a `payroll` event, `SYSTEM` means the run was started by the automatic schedule and `TEACHER` that the teacher started it (§VIII.3)
- `payroll_event_type` — `payroll` | `manual_credit` | `reversal` | `correction`
- `recorded_at` — UTC; display in class canonical time
- `summary_json` — structured payroll summary and settlement metadata, including the pricing inputs of a `payroll` event (§XV.3) and, for a `SYSTEM` `payroll` event, the scheduled occurrence it settled (§XV.5)
- `lineage_event_id`, `lineage_token`, `lineage_version` — opaque Operations audit linkage initialized together during creation (§XV.8); historical null linkage remains unverified.

Rules:

- `payroll_event` is append-only and permanent for as long as its seat exists. A payroll event belongs to its `target_seat_id`; `actor_seat_id` is a provenance reference and does not own it. The database refuses every business-field UPDATE and every post-commit linkage UPDATE; only complete one-time linkage initialization within the creating transaction is allowed (§XV.8). It refuses every DELETE except (a) one removing an event whose target seat no longer exists, reachable only through the foreign-key cascade of that seat's own deletion (lawful seat removal, `FEAT-IDEN-006`), or (b) one inside a transaction that has declared class-universe destruction (`FEAT-CLASS-006`, `FEAT-IDEN-007`). This is membership by existence (`INV-ARC-013`, `INV-CORE-000` §III.6): an entry anchored to `seat_id` or `class_id` ceases with its anchor, the same lifecycle boundary §VII.1.a states for attendance. Deleting the events of a seat that still exists is refused regardless of caller, and deleting an actor seat does not license deleting the events it recorded.
- Each row records one payroll business event for one class.
- Each row records one payroll business event for one affected seat.
- `payroll` events are the only boundary-bearing event type.
- The payroll window for a `payroll` event is derived from the previous `payroll` event timestamp through the current event timestamp.
- `manual_credit`, `reversal`, and `correction` events do not participate in payroll-window boundary derivation.
- `reversal` events must carry the same `correlation_id` as the original event they reverse.
- `policy_uuid` is immutable and must record the exact `payroll_settings.policy_uuid` used to evaluate the event. A database check constraint requires it on every `payroll` event. *(Operator ruling 2026-09-30: the former `policy_version_id` column is removed, and the `policy_versions` table it pointed into is retired (1.5); it was never an authority for payroll.)*
- Where one `payroll` event settles sessions governed by more than one setting, `policy_uuid` records the setting that governed the latest-closing session, and `summary_json` records every setting's share (§XV.3).
- The row must identify the productivity window and settlement intent that authorized any downstream ledger write.
- The row must not duplicate ledger monetary truth beyond what is necessary for business provenance.
- `payroll_event_type` carries the event semantics, so no separate lifecycle `status` column is permitted on the canonical table.
- `payroll_cycle_id` identifies the class-level payroll run (the economic cycle) that produced the event. It is generated once, as a UUID, by the canonical completion command (see §XV) when the class-level run begins, and stamped identically on every `payroll` event written by that run.
- `payroll_cycle_id` is a durable economic-period identity and is distinct from both `correlation_id` (per-seat event/obligation lineage) and `idempotency_key` (command replay guard). These three identities MUST NOT be conflated or derived from one another. See §XV.2.
- A `manual_credit` event recorded outside a class-level payroll run carries no `payroll_cycle_id`. A `reversal` event carries the `payroll_cycle_id` of the event it reverses where one exists, and NULL otherwise. A reversal never opens or closes a cycle.

---

### 4. `attendance_interval_invalidation`

Fields: `id`, `class_id`, `actor_seat_id`, `target_seat_id`, `opening_event_id`, `closing_event_id`, `recorded_at` (UTC), `reason_code`, `idempotency_key`, `correlation_id`, `receipt_json`, `lineage_event_id`, `lineage_token` (String(64)), `lineage_version` (Integer).

- `reason_code`: `INVALID_ATTENDANCE`, `NON_WORK_ACTIVITY`, or `DUPLICATE_PARTICIPATION`; no unrestricted personal notes.
- All business fields are immutable and protected before INSERT. Class/seat are shared anchors. Both attendance IDs are same-domain references that must prove the canonical pair belongs to the same class and target seat. The three audit-linkage fields are opaque Operations metadata with no internal cross-domain FK; they are excluded from their own signed payload. They begin all-null and initialize together exactly once within the creating FEAT-PROD-005 transaction through Operations. Commit requires matching complete creation evidence; replacement, partial initialization and post-commit attachment fail closed. After commit every field is immutable. Application payload verification and deferred database structural verification follow DOM-OPS-002 §6.1; no historical backfill or general UPDATE path is authorized.
- One row per `(class_id, target_seat_id, opening_event_id, closing_event_id)` and one accepted command per `(class_id, FEAT-PROD-005, idempotency_key)` are structurally unique. The target, pair, reason, actor, and expected preview identity define immutable replay intent; `receipt_json` retains `expected_preview_identity`, `fingerprint_version`, `canonical_intent_digest`, `original_settlement_disposition`, and `opaque_outcome_locators`. This immutable protected receipt permits exact replay, including unpaid or previously recovered work, without monetary values.
- No amount, balance, mutable eligibility flag, or earnings cache is authorized. The row is destroyed only with its owning target seat or class (§VII.1.a).

`payroll_event.summary_json` for new settlements retains allocation-version 1, exact interval IDs, credited seconds, and original pricing inputs under SPEC-PROD-001. A correction retains `original_payroll_event_id` (same-domain reference), `correction_intent` (`INTERVAL_INVALIDATION` or `RESIDUAL_RECOVERY`), invalidation ID where relevant, original policy provenance, and opaque Ledger locators. It stores no original, allocated, recovered, or remaining monetary amount. Full/residual recovery business events also retain a protected nonmonetary `command_receipt` containing `expected_preview_identity`, `fingerprint_version`, `canonical_intent_digest`, `original_settlement_disposition`, and `opaque_outcome_locators`, permitting exact accepted-command replay without repricing or a second recovery. A correction retains the original `payroll_cycle_id` as lineage where present and never opens/closes a cycle.

## XII. Cross-Domain Rules

- **Payroll FEAT ownership**: The payroll FEAT is a coordinator, not the authority over payroll meaning. It consumes productivity facts from this domain and posts monetary facts through Ledger.
- **Ledger coordination**: The coordinating FEAT composes Ledger domain commands governed by `FEAT-LED-000` and `FEAT-LED-001` inside its own transaction; it never executes another FEAT. PROD neither calls Ledger nor reconstructs balances or compensation totals.
- **Policies coordination (payroll)**: Wage rate, frequency, and other payroll policy inputs are stored in the Policies repository (`DOM-POL-001`) as immutable, effective-dated `payroll_settings` rows (`DOM-POL-001` §VI.2). Class Configuration decides whether the `payroll` capability is enabled in the class (`class_features`); Policies stores the class-customized definition; `DOM-PROD-001` reads `payroll_settings` — and nothing else — through one resolver, which answers "which setting was in force at instant *t*", and records the `policy_uuid` that priced each `payroll_event`.
- **Policies coordination (hall pass)**: `hall_pass_settings` is stored in the Policies repository (`DOM-POL-001`) as immutable version rows. Class Configuration decides whether the `hall_pass` capability is enabled; Policies stores the definition (allowed destinations, limits); `FEAT-PROD-002` reads the current hall-pass `policy_uuid` before granting a pass because those settings constrain whether a PROD hall-pass event may be written.
- **Obligations coordination**: Hall-pass entitlement quotas remain owned by Obligations, and fine/debit manual deductions belong there rather than in `DOM-PROD`.
- **Store coordination**: Store-owned entitlements and redemption state remain separate from productivity and payroll history.
- **Reversal coordination**: Reversal of a payroll-originated monetary fact must consult this domain's authoritative business record before the reversal may proceed.

---

## XIII. Canonical Business Surface

The long-term implementation goal of this domain is to expose a canonical business surface rather than persistence-oriented behavior.

### 1. `record_productivity_session(...)`

Records one append-only productivity session fact for a seat within a class.

Rules:

- MUST require `class_id` and `seat_id`
- MUST be append-only
- MUST not mutate prior session rows
- MUST not delete, soft-delete, mark-delete, or correct prior session rows
- MUST use class-local temporal evaluation for any boundary-sensitive values

### 2. `record_hall_pass_event(...)`

Records one mutable hall-pass issuance fact.

Rules:

- MUST require `class_id` and `seat_id`
- MUST require a `hall_pass_id`
- MUST capture request, approval, and destination information
- MUST not store exit time or return time
- MUST not alter the approved hall-pass row after issuance except through lawful domain mutation

### 3. `record_payroll_event(...)`

Records one append-only payroll business event.

Rules:

- MUST require `class_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, and `idempotency_key`, plus `policy_uuid` for `payroll` events and for any event whose amount a policy calculation determined (§VIII)
- MUST record `payroll_event_type`
- MUST treat `payroll` as the only boundary-bearing event type
- MUST preserve `manual_credit`, `reversal`, and `correction` as non-boundary event types
- MUST use the original event's `correlation_id` for reversals
- MUST not mutate prior payroll event rows

### 4. `get_payroll_event(...)`

Returns the authoritative payroll event record or records for a given class/seat scope.

Rules:

- MUST be read-only
- MUST not derive payroll truth from ledger rows
- MUST return the source payroll event lineage needed by FEATs and presentation surfaces

### 5. `get_payroll_window(...)`

Derives the payroll settlement window for a given payroll event from the previous `payroll` event timestamp through the current `payroll` event timestamp.

Rules:

- MUST ignore `manual_credit`, `reversal`, and `correction` events for boundary derivation
- MUST return the lower/upper productivity boundary used for payroll settlement
- MUST be read-only and deterministic

### 6. `authorize_payroll_reversal(...)`

Determines whether a payroll-originated monetary fact may be reversed.

Rules:

- MUST consult the authoritative payroll event record
- MUST fail closed if the relevant event cannot be established
- MUST not authorize based on ledger rows alone

### 7. `class_has_claimed_student_work(class_id)`

*Owner rulings 2026-10-01 (1.7).* Answers whether any claimed student seat of `class_id` has work: a session in progress or a session already completed. It is the qualifying-work test of §XV.6.

Rules:

- MUST be read-only and MUST be scoped by `class_id`
- MUST count only student seats that are claimed now (`seats.user_id IS NOT NULL`, `DOM-IDEN-002` §VIII "Participation and Visibility of an Unclaimed Seat", item 4); work kept on a seat that has since been unclaimed does not count
- MUST read `attendance_sessions` only. A session exists once its opening `active` row exists, so an open session and a completed one both qualify; elapsed duration is not part of the test
- MUST NOT consult `class_features`, `payroll_settings` or `payroll_event`

The exact implementation may evolve, but business consumers SHALL interact with canonical domain operations rather than directly manipulating tables or reconstructing derived business state.

---

### 8. Interval eligibility and correction queries

`get_completed_work_interval(class_id, target_seat_id, opening_event_id, closing_event_id)` proves canonical pairing and source facts. `get_interval_eligibility(...)` derives the terminal decision separately from attendance. `get_interval_settlement_membership(...)` returns authoritative original payroll membership and retained original pricing inputs. `authorize_payroll_correction(...)` establishes business permission and correction intent. All are pure and scoped; missing provenance is explicit, never fabricated. Ledger monetary conclusions are consumed only by the FEAT through Ledger's queries.

### 9. Pure historical business assessment

`get_historical_attendance_business_evidence(*, ctx, class_id, target_seat_id, setting_inputs=(), payroll_event_ids=None, limit=50, source_limit=2000, event_limit=1000, as_of_utc)` is a PROD-owned bounded pure query, authorized solely for FEAT-PROD-006. It returns canonical pair evidence, payroll boundaries, retained original pricing inputs, frozen membership availability, explicit original-source rule descriptor candidates and source-set/visibility limitations. It receives immutable setting inputs only from its governing FEAT. It neither derives money nor queries/imports Policies or invokes another domain. This domain incorporates [SPEC-PROD-002](../SPEC/SPEC-PROD-002_HISTORICAL_ATTENDANCE_PROOF_ASSESSMENT.md) §V–VI and its purity/bounds requirements in §VIII for this query only. Arithmetic agreement cannot promote reconstructed membership to canonical settlement membership; unknown original writer assignment and backdated visibility remain unavailable. No current price/default, fragment clipping fallback, new persistence or correction eligibility override is authorized. Existing §XV.7 and SPEC-PROD-001 historical execution denials remain binding.

## XV. Payroll Cycle Completion and the Economic-Cycle Boundary

### 1. Payroll completion is the canonical class-level economic-cycle boundary

A single `payroll` event is a per-seat boundary fact (§XI.3). A **payroll cycle** is the class-level economic period that a completed payroll run closes: the collection of all `payroll` events written by one class-level run, sharing one `payroll_cycle_id`.

Successful completion of a class-level payroll run — whether initiated manually by the teacher or automatically by a scheduled run — is the canonical **economic-cycle boundary event** for the class. It is the single point at which:

1. the closing economic cycle is settled against productivity facts under the configuration that governed it, and
2. downstream domains may lawfully materialize a permanent, cycle-bound view of that closed cycle.

A payroll-governing change the teacher saved during the open cycle is not activated here: it is a `payroll_settings` row already dated to this boundary, in force from it with nothing to activate (§XV.3, `DOM-CLASS-003` §VII). *(1.6: the former third fact, activation of a staged change, belonged to the retired `policy_transitions` table.)*

This domain owns fact (1). It does NOT own fact (2), and it MUST NOT invoke Interpretation directly. Interpretation's materialization is a downstream side effect orchestrated by the canonical completion FEAT (`FEAT-PROD-004`), never by a direct domain-to-domain call, per `INV-ARC-021` §V.1–§V.2.

### 2. Three distinct identities

A payroll run carries three identities that MUST remain separate:

| Identity | Meaning | Lifetime / Scope |
| :--- | :--- | :--- |
| `payroll_cycle_id` | Durable economic-period identity for the class-level run | One UUID per class-level run, stamped on every `payroll` event in that run; permanent |
| `correlation_id` | Per-seat event/obligation lineage identity linking a payroll event to its ledger and obligation facts | One per settled seat per run |
| `idempotency_key` | Command replay guard for the write operation | One per write; guarantees safe retry, not economic meaning |

`payroll_cycle_id` MUST NOT be derived from, or substituted by, `correlation_id`, `idempotency_key`, or any per-command replay nonce. It is generated as a fresh UUID by the canonical completion command when the class-level run begins.

### 3. Prospective configuration during an open cycle

*Restated by operator ruling 2026-09-30.* Per `INV-ARC-015` §VI.7, a configuration change never reinterprets an already-open cycle. When the teacher changes payroll settings during open cycle N, the change MUST NOT govern cycle N: work done under the old setting is paid under the old setting, and the change governs from the next payroll cycle boundary.

The change is an effective-dated append to `payroll_settings` whose `effective_date` is the next payroll date (§XV.5) at the moment of the save (`DOM-CLASS-003` §VII, `DOM-POL-001` §VI.2). Because the next payroll date is derived rather than stored, and a manual run does not move it, the boundary is known when the change is made. No policy transition is recorded and none is activated at completion.

**Pricing.** Each session a payroll run settles is priced by the `payroll_settings` row in force at the instant the session closed (the greatest `effective_date` at or before that instant; ties broken by the latest `created_at`). Work that closed before the class's first setting existed is priced by that first setting, since no earlier setting was ever in force. A run whose sessions fall under more than one setting prices each setting's share separately and records, in the event's `summary_json`, one entry per setting — its `policy_uuid`, the seconds it priced, and its per-minute `pay_rate` — so the amount is reproducible from recorded inputs (`INV-CORE-000` §III.3). The amount itself is not stored (§VIII.3). The event's `policy_uuid` names the setting that governed the latest-closing session.

**No time rounding.** Allocation version 1 uses exact decimal/rational elapsed-seconds pricing, quantizes each setting share once with nearest-cent ties-to-even (`ROUND_HALF_EVEN`), and allocates cents by SPEC-PROD-001's largest-remainder rule. A setting's share is exactly its elapsed seconds × its per-minute rate ÷ 60, quantized once to the cent. No time rounding is defined or applied; rounding is not a payroll setting (operator ruling 2026-09-30; the retired `rounding_mode` column is historical data only, `DOM-POL-001A` §V.F). The overtime threshold is recorded but no overtime is applied to payroll pricing until the owner rules on its semantics.

### 4. Interaction with `record_payroll_event`

`record_payroll_event` (§VIII.3) writes only `payroll` and `manual_credit` under FEAT-PROD-003 or class settlement FEAT-PROD-004; the approved FEAT-STOR-003 productivity-insurance payout may compose its manual-credit domain path. `record_payroll_business_correction` (§VIII.6) writes interval/correction business events under FEAT-PROD-005 or FEAT-PROD-003. `record_payroll_business_recovery` (§VIII.4) exclusively writes signed full/residual recovery business records under FEAT-PROD-003. No generic type parameter bypasses these declarations. When invoked as part of a class-level run orchestrated by `FEAT-PROD-004`, the caller supplies the run's `payroll_cycle_id`; `record_payroll_event` stamps it unchanged onto each `payroll` row. `record_payroll_event` does not generate `payroll_cycle_id` and does not itself orchestrate any cross-domain side effect. Class-level cycle completion orchestration is exclusively `FEAT-PROD-004`'s responsibility; correction orchestration is declared separately by `FEAT-PROD-003` and `FEAT-PROD-005`.

### 5. The next payroll date is derived, never stored

*Operator ruling 2026-09-30.* A class's next payroll date is computed from `payroll_settings` and `payroll_event` alone. It is never persisted, and no schedule cursor exists on any table.

It takes one of three forms:

1. **`first_pay_date`** — while the class has no `SYSTEM` `payroll` event (whether `first_pay_date` is still ahead or has already arrived and is due);
2. **`first_pay_date` + pay frequency** — the case of form 3 in which the last scheduled run was the one on `first_pay_date`;
3. **last `SYSTEM` `payroll` event + pay frequency** — once the automatic schedule has run.

The anchor for forms 2 and 3 is the *scheduled occurrence* the last `SYSTEM` `payroll` event settled, recorded in its `summary_json`, not the wall-clock instant the run happened to execute, so a late run never moves later paydays. An event that predates that record anchors on its `recorded_at`. Only `payroll` events with `mechanism = SYSTEM` anchor the schedule: a teacher-started (`TEACHER`) payroll run, a `manual_credit` (including a platform-computed correction recorded as `SYSTEM`), a `reversal`, and a `correction` never move it.

`first_pay_date` and the pay schedule are read from the setting in force at the moment of evaluation. Every setting has a `first_pay_date`; a class without payroll settings has not set up payroll and has no scheduled payroll date. Every payroll date is a boundary of one recurrence anchored on `first_pay_date` (`SPEC-TIME-001` §IX.12, `anchored_recurrence_boundary`): boundary *n* is computed from the anchor and *n*, never from the previous boundary, at class-local midnight. `pay_schedule_type` is the whole cadence and is `weekly`, `biweekly` or `monthly`: weekly and biweekly step one or two weeks; monthly steps calendar months with `overflow = roll_forward`, so an anchor on the 31st runs 1/31 → 3/1 → 3/31 → 5/1 → 5/31. Pay frequency is derived this way and never stored as a number of days (operator ruling 2026-09-30). The next payroll date is boundary 0 until the schedule has run, then the first boundary strictly after the last `SYSTEM` occurrence.

### 6. Work recorded before the class's first payroll setting

*Owner rulings 2026-10-01 (1.7).* Start Work does not depend on payroll: a class can record productivity facts before it has any `payroll_settings` row. Those facts are payable. The first payroll run after the first setting exists pays them, priced by that first setting (§XV.3). No earlier work is lost because configuration was absent. Explicit terminal invalidation under §VIII.5 still excludes an interval from compensation.

While a class is in that state, its teacher is told once. This is a one-time bootstrap guard for the period before the first setting. It is not a recurring payroll-health warning.

**Condition.** The notice applies to a class exactly when all three hold:

1. the class has no `payroll_settings` row (`DOM-POL-001` §VI.2), read through the payroll settings service;
2. `class_has_claimed_student_work(class_id)` is true (§XIII.7);
3. the class's teacher has not acknowledged it: `classes.unpaid_work_notice_acknowledged_at` is NULL (`DOM-CLASS-001` §VII.1).

`payroll_settings` is append-only, so once the first setting exists the notice is permanently inapplicable for the class. It can never recur, whether or not it was acknowledged. Payroll has no off switch (`DOM-CLASS-001` §VII.3), so the notice has no capability-disabled branch.

**Derived, never stored.** The condition is computed on read from the three sources above and exposed to the page through a view model. No route or template reconstructs it. Rendering it is a pure read (`INV-ARC-007`): a page view never records an acknowledgement.

**Disclosure.** The teacher's dashboard and payroll page show, in plain language, that students are working while payroll is not set up, and that those hours will be paid at the teacher's first rate once payroll is set up. Students see nothing: this notice has no student surface.

**Acknowledgement.** The teacher dismisses the notice with an explicit POST, executed by `FEAT-CLASS-008`. Acknowledgement and resolution are independent. An acknowledgement records only that the class's teacher saw the notice. It does not assert that the condition still holds, it does not alter, exclude or pre-empt any productivity fact, and it does not stop the first payroll run from paying earlier work. A dismissal submitted after the class's first setting exists (for example, from a tab left open) is recorded like any other.

### 7. Due System Closure and Read Projections

`close_due_attendance_intervals` locks the target seat before timeline selection and appends only missing system `inactive` / `done_for_day` events when the originating canonical day-end or daily limit has been reached. A system event ID is as valid as a human scan ID. The daily limit is resolved from the effective-dated setting in force at the interval opening, never a future wall-clock setting. Prior completed work in that same day reduces the remaining limit. Every attendance writer and payroll settlement shares seat serialization; multi-seat settlement acquires seats in ascending ID order before monetary effects. Commands neither modify original rows nor manufacture source IDs. Closures and the invoking payroll roll back together on failure. Completed-run replay is resolved before closure or pricing.

Pure interval queries expose original pair IDs, UTC timestamps, credited seconds, mechanism and unclosed evidence. Pairing precedes pagination. Pure settlement-membership queries verify frozen source evidence against the canonical pair; historical timestamps do not prove original membership. New version-1 settlement exclusion follows recorded pair membership, not an event timestamp cutoff, so a later-recorded backdated system close is not silently dropped. An unresolved historical partial payment blocks new settlement of its overlapping interval; no compatibility clipping is authorized. Read queries never emit closures, audits, or payroll writes.

### 8. Payroll Audit Linkage Initialization

Under INV-ARC-016 and DOM-OPS-002 §5.4, every new payroll event carries complete protected-field audit lineage. The business fields, including the full summary, are fixed at insertion. The three audit-linkage fields may move together exactly once from all-null to complete solely within that row's creating transaction, with a matching signed AuditEvent for its class, table and row ID. This initialization completes creation; it does not authorize amendment of a committed record. Commit without required valid lineage fails, replacement and post-commit attachment fail, and failures roll back the row and audit together. Historical null linkage stays unverified and is never backfilled. Lifecycle destruction remains the sole deletion exception.

### 9. Conditional Pure Historical Business Membership Evaluation

PROD authorizes a future pure **evaluate proven historical membership** query contract through FEAT-PROD-006 only, incorporating SPEC-PROD-002 §VI.1 and SPEC-PROD-001 §VI.1. This is a contract designation, not a claim that an implemented API exists. Required inputs are canonical context, explicit class/target and original payroll-event identity, complete original PROD source/boundary evidence, and immutable original setting, audit and scoped credit evidence supplied by the coordinating FEAT. Inputs are obtained from owning-domain interfaces, never client proof claims. PROD validates source completeness/creation visibility, original writer/temporal selection, whole-pair identity and per-policy source assignment; it neither computes money nor verifies another domain's proof internally. Scope, bounds and purity requirements of §XIII.9 remain binding.

The permitted positive conclusion is original business membership proven, distinct from canonical lawful-lineage state and independent monetary authorization. It requires every SPEC-PROD-002 §VI.1 prerequisite. A current scan set, matching seconds/cents, frozen rate alone, timestamp cutoff or post-hoc signing cannot meet original visibility/completeness requirements. Historical source ambiguity remains unavailable. Original protected business evidence must meet INV-ARC-016 §V; this query cannot manufacture it.

This narrowly qualifies §XV.7's timestamp-gap rejection only if independent original evidence proves the complete original selection. It does not install a membership fallback or change unpaid selection, paid preview, correction command, cycle boundaries or Interpretation records. The initial shape is one priced positive payroll event settling only complete original pairs with one unique original credit. The observed 153-event cohort remains diagnostic because original source visibility/completeness, per-record writer assignment and business lineage gaps have not been closed. Unpriced, fragment/remainder, manual/top-up, zero-run and multi-credit shapes remain outside this proof contract. Monetary recovery still requires every separate existing Ledger and Operations gate; no writer, migration, signature or compatibility path is authorized.

## XVI. Amendment

**Version 1.12 (2026-10-03)** conditionally qualifies §XV.7 for a future pure proven priced whole-pair membership contract (§XV.9), incorporating SPEC-PROD-002 §VI.1 and SPEC-PROD-001 §VI.1. Supersedes no immutable-history, current runtime or monetary proof rule; current production candidates remain diagnostic.

**Version 1.11 (2026-10-03)** supersedes v1.9's exclusion of historical reconstruction only for the bounded diagnostic read in §XIII.9. It preserves the exclusion of reconstructed history from settlement/recovery truth and authorizes no historical monetary execution or write.


**Version 1.10 (2026-10-03)** registers the complete one-time invalidation creation-linkage protocol, superseding the incomplete single-pointer field list. It authorizes no mutable eligibility or business record.

**Version 1.9 (2026-10-03)** supersedes the exclusive attendance-writer declaration for due system closure only, and defines the narrow payroll audit-linkage creation phase. Authorizes interval-detail/prospective provenance implementation; no historical reconstruction or monetary correction UI is included.


**Version 1.8 (2026-10-03)** supersedes the v1.7 whole-payroll-only correction rule. Authorizes terminal completed-interval invalidation and partial/residual payroll correction; incorporates SPEC-PROD-001. The new surface is authorized, not runtime implemented. Existing immutable attendance, settlement boundaries, and lifecycle rules remain binding.


Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
4. Maintain consistency with `DOM-CORE-002`.

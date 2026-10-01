# DOM-PROD-001: Productivity and Payroll Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-PROD-001 | 1.5 | 2026-10-01 | 1.4 | Constitutional |

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

## V. Canonical Business Authority

The Productivity and Payroll domain is the sole business authority responsible for:

- productivity participation facts
- hall-pass execution facts
- payroll events
- payroll eligibility and settlement intent derived from productivity facts
- business-side reversal authorization for payroll-originated monetary facts

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
- `hall_pass_logs`
- `payroll_event`

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact runtime table list. This domain owns the tables listed there that are assigned to it. `payroll_event` is the canonical payroll event table owned by this domain.

The legacy v1 runtime table `tap_events` has been retired. `attendance_sessions` is the canonical productivity fact table in the active v2 runtime and migration chain.

---

## VII. Owned Tables

### 1. `attendance_sessions`

Append-only productivity timeline facts. Each row records a single tap-in or tap-out event for a seat within a class.

Current attendance state, accumulated daily minutes, and hall-pass elapsed time are derived from this timeline and are not stored on this table.

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

Canonical append-only table for positive ledger credit events.

This domain must maintain the authoritative payroll event surface that explains why a payroll FEAT exists, what participation was settled, and what business event was approved for monetary posting.

The payroll event is the human-meaningful authority for:

- what productivity window was settled
- which seats were included
- what payroll batch or run occurred
- whether a payroll-originated monetary fact may later be reversed

---

## VIII. Canonical Write Operations

The only lawful write operations for this domain are the following.

### 1. `record_attendance_session(...)`

Owned by `FEAT-PROD-001`.

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

If a teacher believes an attendance row produced an incorrect payroll outcome, the correction path is a payroll reversal through `FEAT-PROD-003`, not mutation of the attendance row.

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

Owned by `FEAT-PROD-003`.

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
  - `reversal`: carries the provenance of the event it compensates
- This is a minimum requirement for `payroll` events only. It MUST NOT be inverted into a rule that `manual_credit` events carry no policy provenance
- MUST set `mechanism` to the path that initiated the event: `SYSTEM` for a payroll run started by the automatic schedule, `TEACHER` for a run the teacher started. The mechanism is supplied by the initiating caller and never inferred (§XV.5 depends on it)
- MUST set `payroll_event_type` to `payroll`, `manual_credit`, or `reversal`
- MUST derive payroll amount from authoritative productivity facts or manual credit intent, but MUST not store the amount on the table
- MUST use the same `correlation_id` as the original event when writing a reversal
- MUST write the compensating amount to Ledger with the same correlation linkage
- MUST not store payroll period boundaries as persisted fields

### 4. `record_payroll_reversal(...)`

Owned by `FEAT-PROD-003`.

Writes a compensating `payroll_event` row and coordinates the matching Ledger reversal.

Use cases:

- teacher reverses a payroll credit
- teacher reverses a manual credit

Rules:

- MUST create a new `payroll_event` row with `payroll_event_type = reversal`
- MUST reuse the original event's `correlation_id`
- MUST not mutate the original payroll row
- MUST calculate the compensating ledger amount as the negative of the original ledger amount
- MUST fail closed if the original event cannot be established

---

## IX. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Productivity Session** | Authoritative Event | Immutable record of a participation interval. |
| **Hall Pass Log** | Authoritative Event | Immutable record of an approved hall-pass instruction. |
| **Payroll Event** | Authoritative Event / Record | Canonical business explanation of a payroll settlement run. |
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
- Teacher correction of an already-paid attendance outcome is performed by reversing the affected payroll event, not by changing attendance history.
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
- `payroll_event_type` — `payroll` | `manual_credit` | `reversal`
- `recorded_at` — UTC; display in class canonical time
- `summary_json` — structured payroll summary and settlement metadata, including the pricing inputs of a `payroll` event (§XV.3) and, for a `SYSTEM` `payroll` event, the scheduled occurrence it settled (§XV.5)

Rules:

- `payroll_event` is append-only. The database refuses every UPDATE, and refuses DELETE except while a class universe is being destroyed (`FEAT-CLASS-006`, `FEAT-IDEN-007`), the same exemption `ledger_transaction` carries.
- Each row records one payroll business event for one class.
- Each row records one payroll business event for one affected seat.
- `payroll` events are the only boundary-bearing event type.
- The payroll window for a `payroll` event is derived from the previous `payroll` event timestamp through the current event timestamp.
- `manual_credit` and `reversal` events do not participate in payroll-window boundary derivation.
- `reversal` events must carry the same `correlation_id` as the original event they reverse.
- `policy_uuid` is immutable and must record the exact `payroll_settings.policy_uuid` used to evaluate the event. A database check constraint requires it on every `payroll` event. *(Operator ruling 2026-09-30: the former `policy_version_id` column, a foreign key into the legacy `policy_versions` table, is removed. `policy_versions` was never an authority for payroll.)*
- Where one `payroll` event settles sessions governed by more than one setting, `policy_uuid` records the setting that governed the latest-closing session, and `summary_json` records every setting's share (§XV.3).
- The row must identify the productivity window and settlement intent that authorized any downstream ledger write.
- The row must not duplicate ledger monetary truth beyond what is necessary for business provenance.
- `payroll_event_type` carries the event semantics, so no separate lifecycle `status` column is permitted on the canonical table.
- `payroll_cycle_id` identifies the class-level payroll run (the economic cycle) that produced the event. It is generated once, as a UUID, by the canonical completion command (see §XV) when the class-level run begins, and stamped identically on every `payroll` event written by that run.
- `payroll_cycle_id` is a durable economic-period identity and is distinct from both `correlation_id` (per-seat event/obligation lineage) and `idempotency_key` (command replay guard). These three identities MUST NOT be conflated or derived from one another. See §XV.2.
- A `manual_credit` event recorded outside a class-level payroll run carries no `payroll_cycle_id`. A `reversal` event carries the `payroll_cycle_id` of the event it reverses where one exists, and NULL otherwise. A reversal never opens or closes a cycle.

---

## XII. Cross-Domain Rules

- **Payroll FEAT ownership**: The payroll FEAT is a coordinator, not the authority over payroll meaning. It consumes productivity facts from this domain and posts monetary facts through Ledger.
- **Ledger coordination**: All payroll monetary effects must go through `FEAT-LED-000` and `FEAT-LED-001`.
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
- MUST preserve `manual_credit` and `reversal` as non-boundary event types
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

- MUST ignore `manual_credit` and `reversal` events for boundary derivation
- MUST return the lower/upper productivity boundary used for payroll settlement
- MUST be read-only and deterministic

### 6. `authorize_payroll_reversal(...)`

Determines whether a payroll-originated monetary fact may be reversed.

Rules:

- MUST consult the authoritative payroll event record
- MUST fail closed if the relevant event cannot be established
- MUST not authorize based on ledger rows alone

The exact implementation may evolve, but business consumers SHALL interact with canonical domain operations rather than directly manipulating tables or reconstructing derived business state.

---

## XV. Payroll Cycle Completion and the Economic-Cycle Boundary

### 1. Payroll completion is the canonical class-level economic-cycle boundary

A single `payroll` event is a per-seat boundary fact (§XI.3). A **payroll cycle** is the class-level economic period that a completed payroll run closes: the collection of all `payroll` events written by one class-level run, sharing one `payroll_cycle_id`.

Successful completion of a class-level payroll run — whether initiated manually by the teacher or automatically by a scheduled run — is the canonical **economic-cycle boundary event** for the class. It is the single point at which:

1. the closing economic cycle is settled against productivity facts under the configuration that governed it,
2. downstream domains may lawfully materialize a permanent, cycle-bound view of that closed cycle, and
3. any economic-configuration change that the teacher staged during the open cycle becomes lawfully activated for the next cycle.

This domain owns fact (1). It does NOT own facts (2) or (3), and it MUST NOT invoke Interpretation or Class Configuration directly. Interpretation's materialization and Class Configuration's pending-policy activation are downstream side effects orchestrated by the canonical completion FEAT (`FEAT-PROD-004`), never by direct domain-to-domain calls, per `INV-ARC-021` §V.1–§V.2.

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

**No rounding.** A setting's share is exactly its elapsed seconds × its per-minute rate ÷ 60, quantized once to the cent. No time rounding is defined or applied; rounding is not a payroll setting (operator ruling 2026-09-30; the retired `rounding_mode` column is historical data only, `DOM-POL-001A` §V.F). The overtime threshold is recorded but no overtime is applied to payroll pricing until the owner rules on its semantics.

### 4. Interaction with `record_payroll_event`

`record_payroll_event` (§VIII.3, owned by `FEAT-PROD-003`) remains the sole writer of `payroll_event` rows. When invoked as part of a class-level run orchestrated by `FEAT-PROD-004`, the caller supplies the run's `payroll_cycle_id`; `record_payroll_event` stamps it unchanged onto each `payroll` row. `record_payroll_event` does not generate `payroll_cycle_id` and does not itself orchestrate any cross-domain side effect. Cross-domain orchestration is exclusively `FEAT-PROD-004`'s responsibility.

### 5. The next payroll date is derived, never stored

*Operator ruling 2026-09-30.* A class's next payroll date is computed from `payroll_settings` and `payroll_event` alone. It is never persisted, and no schedule cursor exists on any table.

It takes one of three forms:

1. **`first_pay_date`** — while the class has no `SYSTEM` `payroll` event (whether `first_pay_date` is still ahead or has already arrived and is due);
2. **`first_pay_date` + pay frequency** — the case of form 3 in which the last scheduled run was the one on `first_pay_date`;
3. **last `SYSTEM` `payroll` event + pay frequency** — once the automatic schedule has run.

The anchor for forms 2 and 3 is the *scheduled occurrence* the last `SYSTEM` `payroll` event settled, recorded in its `summary_json`, not the wall-clock instant the run happened to execute, so a late run never moves later paydays. An event that predates that record anchors on its `recorded_at`. Only `payroll` events with `mechanism = SYSTEM` anchor the schedule: a teacher-started (`TEACHER`) payroll run, a `manual_credit` (including a platform-computed correction recorded as `SYSTEM`), and a `reversal` never move it.

`first_pay_date` and the pay schedule are read from the setting in force at the moment of evaluation. Every setting has a `first_pay_date`; a class without payroll settings has not set up payroll and has no scheduled payroll date. Every payroll date is a boundary of one recurrence anchored on `first_pay_date` (`SPEC-TIME-001` §IX.12, `anchored_recurrence_boundary`): boundary *n* is computed from the anchor and *n*, never from the previous boundary, at class-local midnight. `pay_schedule_type` is the whole cadence and is `weekly`, `biweekly` or `monthly`: weekly and biweekly step one or two weeks; monthly steps calendar months with `overflow = roll_forward`, so an anchor on the 31st runs 1/31 → 3/1 → 3/31 → 5/1 → 5/31. Pay frequency is derived this way and never stored as a number of days (operator ruling 2026-09-30). The next payroll date is boundary 0 until the schedule has run, then the first boundary strictly after the last `SYSTEM` occurrence.

## XVI. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
4. Maintain consistency with `DOM-CORE-002`.

# DOM-OBL-001: Obligations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OBL-001 | 3.2 | 2026-09-24 | 3.1 | Constitutional |

---

## I. Purpose

This document defines the Obligations domain as the canonical authority over instantiated monetary liabilities, recurring rent cycles, and their lawful resolution.

Obligations owns:

- the existence of a liability after it has been lawfully assessed;
- the lifecycle of that liability through payment or waiver, or its withdrawal before it ever became owed (§V.8);
- recurring bill-cycle state for liabilities that must be reconsidered at a later boundary;
- the current rent cycle that is in force for the class.

Obligations does not own:

- the teacher-defined policy terms that create the liability;
- the Ledger movement that records money;
- the entitlement lifecycle or perk lifecycle itself;
- post hoc monetary correction after a ledger action;
- any mutable status flag that duplicates what can be derived from immutable facts.

---

## II. Scope

This domain governs:

- obligation event facts;
- recurring bill-cycle progression;
- derived obligation projections such as satisfied, outstanding, visible, and past due.

Obligations operates on class-scoped and seat-scoped truth. It never owns global money, global identity, or cross-class authority.

### A. Rent

Rent is a homegrown obligation lifecycle owned by Obligations. It is configured upstream by Class Configuration and Policies, but Obligations owns the assessment and recurring debt progression once the lawful rent contract exists.

### B. Insurance

Insurance is not owned by Obligations as a product lifecycle. Store and Entitlements owns the insurance entitlement / coverage lifecycle, and Policies owns the insurance definition. Obligations may service recurring insurance premiums as debt lifecycle, but only with lawful inputs supplied by the owning authority. One insurance entitlement is one premium lineage: its `internal_ref` derives from the `entitlement_id` alone and never from a purchase command's idempotency key, so a repurchase is a new entitlement and a new lineage.

### C. Immediate Charges

Overdraft fees, NSF fees, and other immediately collected charges are still obligations when the system lawfully instantiates a liability before or alongside settlement. The fact that the liability is settled immediately does not remove it from this domain.

### D. Exclusions

Obligations does not own store purchases. Store purchases are immediate exchanges, not assessed liabilities.

---

## III. Authority Level

Tier 1 - Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants.

It is subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

---

## IV. Canonical Business Authority

The Obligations domain is the sole business authority responsible for:

- lawful assessment of monetary liabilities;
- lawful resolution of assessed liabilities through payment or waiver, and lawful withdrawal of an advance assessment that never became owed (§V.8);
- recurring bill-cycle progression;
- the current rent cycle that is currently in force;
- derived status over obligation facts;
- cross-domain lineage preserved by internal reference, correlation, and bill-cycle identity.

Consumers SHALL NOT:

- derive obligation status independently;
- derive payment completeness independently;
- mutate obligation persistence directly;
- reinterpret the meaning of an obligation using label-based or route-local logic;
- write mutable status columns that duplicate derived truth.

Consumers SHALL instead invoke the canonical business operations owned by this domain.

---

## V. Vocabulary

### 1. Obligation

An obligation is an instantiated monetary liability associated with a seat.

An obligation exists because a lawful upstream authority determined that a seat owes money under a specific relationship or enforcement action.

The obligation does not own the monetary amount itself. The authoritative amount comes from the upstream contract/configuration or from the lawful caller supplying the assessed terms.

### 2. Internal Reference

An internal reference identifies a continuing obligation-producing relationship.

It answers:

> Which continuing relationship are these assessments part of?

The internal reference is stable across recurring assessments for the same continuing relationship.

It does not encode the business meaning of that relationship inside Obligations.

### 3. Correlation ID

A correlation ID identifies one individual instantiated obligation.

It binds together the immutable events that belong to that single liability instance.

### 4. Assessment

An assessment is the immutable fact that a liability lawfully came into existence.

Every liability begins with exactly one assessment.

### 5. Payment

A payment is the immutable fact that Ledger-backed monetary movement was applied toward an assessment.

Multiple payments may exist for the same assessment.

### 6. Waiver

A waiver is the immutable fact that the remaining outstanding rent liability no longer requires payment.

Waiver is rent-only.

Waiver creates no Ledger movement.

A waiver MAY carry a teacher-entered note explaining the reason. The note is optional, informational, and immutable after insert. It is not authoritative business truth — derived satisfaction rules (§VIII) do not consult it. It is stored solely so teachers and the affected student can later see why the waiver was granted. See §VII.1 `notes`.

### 7. Bill Cycle

A bill cycle is a recurring temporal instruction that says which policy UUID is current for a continuing obligation-producing relationship and when that cycle must be assessed again. It serves any recurring obligation lineage (rent per class, and insurance premiums per insurance entitlement), distinguished by `internal_ref` and `obligation_type`.

Bill cycle does not know the teacher's intent beyond the persisted policy UUID and the next assessment boundary.

Bill cycle may carry the exact `policy_uuid` that it invokes. That reference freezes the cycle's terms by reference (`DOM-POL-001` §VII): every term the cycle depends on, its amount and its scheduling terms alike, resolves from that exact immutable version and never from the family's current or latest row.

**Period.** A cycle's period is the half-open interval `[cycle_boundary_at, next_assessment_at)`. `cycle_boundary_at` is the cycle's coverage/due boundary, where its period begins; `next_assessment_at` is where it ends and where the successor's period begins. The calendar day before `next_assessment_at` is the period's final covered day and its payment deadline; it is never itself called a boundary.

**Current cycle.** The current cycle of a lineage at a reference time is the non-terminal cycle whose period contains that time, `cycle_boundary_at ≤ reference_time < next_assessment_at`, provided no terminal row of the lineage takes effect at or before that time. The highest cycle number, or the most recently created cycle, MUST NOT be used as a proxy for the current cycle. Under advance assessment the latest cycle is routinely an upcoming one whose period has not begun.

**Scheduled is not effective.** A cycle row records that a period was scheduled. Whether the period ever becomes effective is decided by termination (below): a scheduled cycle whose `cycle_boundary_at` is at or after the lineage's termination instant never becomes effective. Its row is not altered; it remains evidence that the period was scheduled.

**Advance assessment.** A successor is assessed before its period begins, at `next_assessment_at − preview`, where `preview` is the bill preview interval of the immutable policy referenced by the predecessor's `policy_uuid`, obtained through the Policies read (`DOM-POL-001A` §V.E). Obligations does not read policy tables or branch on the policy family. A preview of `0` assesses the successor at its own boundary. Assessment availability and the due boundary are separate temporal concepts: early assessment permits early satisfaction, and it does not advance delinquency, grace, late-fee, or coverage-boundary semantics, all of which remain anchored to the cycle's `cycle_boundary_at`.

The bill-cycle lifecycle has two operations, each an explicit command. Position in history is authoritative state, not API surface.

- **Succession** (`schedule_next_bill_cycle`): records the next lawful schedule row for a lineage. The domain derives the cycle number from authoritative Obligations state — `1` where no cycle exists for the lineage, otherwise `current + 1`. The cycle number is never caller-selected and never caller-supplied, per `INV-ARC-009` §V (only domain queries may define authoritative state). A caller requests succession for a lineage; it does not assert the lineage's position.
- **Termination**: a terminal cycle row with `next_assessment_at = NULL` (see §VII.2) stops future recurrence; the lawful cancellation/termination authority performs it. Termination is cessation, not succession — it writes no next assessment boundary — so it remains a separate command and is not routed through succession. It does not rewrite prior obligation events (§IX.7).

  The terminal row's `cycle_boundary_at` is the **termination instant**, set by the terminating authority:

  - when renewal is stopped, it is the end of the last committed period. The current period is committed. An upcoming, not-yet-begun period is committed only if its obligation was satisfied in advance; then the lineage terminates at that period's end, and otherwise at the current period's end;
  - when an owning domain terminates for nonpayment, it is that domain's lawful deadline, which may fall inside a period.

  In every case, each unsatisfied advance assessment for a period beginning at or after the termination instant is withdrawn (§V.8) in the same transaction, and every assessment for a period that began before the termination instant remains due. The termination instant may therefore precede the latest scheduled cycle's `next_assessment_at`.

**Succession eligibility.** Succession is lawful only when one of the following holds for the lineage, as read from authoritative Obligations state:

- the lineage has no cycle; or
- the latest cycle is non-terminal and its assessment point (`next_assessment_at − preview`, preview resolved from that cycle's own `policy_uuid`) has arrived at the canonically resolved reference time.

Succession is unlawful for a lineage whose latest cycle is terminal, and unlawful before the latest cycle's assessment point. A later policy submission in the same family cannot move an existing cycle's assessment point, because that point resolves only from the cycle's own `policy_uuid`. "Has arrived" is evaluated through the Canonical Temporal Evaluation helper (`INV-ARC-015` §VII) against the reference time resolved for the command, never against a command-local current-time read or a direct datetime comparison. Eligibility is a domain determination; callers do not reconstruct it (`INV-ARC-009` §V). A caller's own scheduling predicate does not substitute for this rule.

There is no separate genesis command. "First cycle" is a property of the lineage's state at the moment of succession, not a distinct operation.

**Replay identity.** Succession is idempotent on **command identity**, not on the shape of the row it would write. The governing question is whether this command has already executed, never whether a row with this `(internal_ref, cycle_number)` already exists. Two unrelated commands that independently derive the same successor are two commands, not a replay. Three cases, and only these:

1. **Exact replay** — same command identity, matching request fingerprint: the original execution's outcome is returned. The existing row is not mutated and no second row is written.
2. **Identity match, fingerprint mismatch** — the same command identity presented with different terms: the command fails closed with a replay-mismatch result. No write, no mutation, no silent acceptance.
3. **Distinct commands racing for the same derived successor** — exactly one may create it. Every other command fails closed with a **succession conflict**: the successor it derived was created by a different command. The conflict is determined after the identity lookup — a command that finds its own identity already recorded is in case (1) or (2), never case 3. Reporting a conflict as a successful replay is unlawful, as is reporting it as a generic uniqueness failure. A command derives its successor once, from the lineage state it evaluated; on conflict it MUST NOT re-evaluate against the advanced lineage and create a later successor instead.

The `(internal_ref, cycle_number)` uniqueness constraint is the integrity backstop for case 3. It is not the idempotency mechanism and must not be used as one.

This clause is built to match the replay model ratified for Ledger commands in `SPEC-LED-002` §VI, so that the two domains do not drift into different replay semantics. `SPEC-LED-002` §II scopes itself to Ledger paths creating monetary effects and does not govern Obligations; it is the model here, not the authority (`INV-ARC-021`).

### 8. Withdrawal

A withdrawal is the immutable fact that an advance assessment never became owed, because the future period it was assessed for was lawfully cancelled before it began.

It exists for one reason: **advance assessment MUST NOT make a future liability survive an action that, absent advance assessment, would have prevented that liability from ever arising.** A bill preview interval changes when a liability becomes payable; it never changes whether the liability exists.

A withdrawal is lawful only when all of the following hold:

- the assessment is bound to a bill cycle whose period has not begun at the reference time;
- no satisfaction of any kind (`PAYMENT` or `WAIVED`) has been recorded against it;
- it is recorded atomically with the action that makes that future period no longer lawful (termination of the lineage, or disablement of the capability that the period depends on).

Effects:

- the original `ASSESSMENT` is untouched (§IX.5); the withdrawal is an appended `WITHDRAWN` event for the same correlation;
- the assessment is not outstanding, not satisfied, not required, never past due, never delinquent, never gating, and ineligible for late fees or any other derived penalty;
- a withdrawn assessment cannot later be satisfied;
- a withdrawal creates no Ledger movement.

A withdrawal is not a waiver. A waiver forgives a liability that was owed (§V.6, rent-only); a withdrawal records that a liability was never owed. Withdrawal is product-blind: any lineage whose future period is lawfully cancelled uses it.

---

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `assessment_events`
- `bill_cycles`
- `obligation_command_reservation` — succession command identity for the replay contract in §V.7; execution state, not domain state

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact target table set. This document defines the obligations-side meaning of those tables.

This domain does **not** own:

- any mutable paid/overdue/reversed scalar state
- insurance entitlement state
- Ledger transactions

---

## VII. Canonical Persistence

### 1. `assessment_events`

Records the historical fact of obligation events.

Key fields:

- `id`
- `timestamp` - time when the row is created, which represents the time when the assessment took place.
- `seat_id` - FK to `seats`
- `class_id` - FK to `classes`
- `internal_ref` - stable lineage key for the continuing obligation-producing relationship
- `correlation_id` - identifier for this individual liability instance
- `event_type` - `ASSESSMENT` | `PAYMENT` | `WAIVED` | `WITHDRAWN`
- `obligation_type` - closed enum of lawful assessment categories
- `policy_uuid` - lawful source policy locator
- `bill_cycle_id` - nullable FK to `bill_cycles`
- `ledger_transaction_id` - nullable FK to `ledger_transaction`; required for `PAYMENT`
- `notes` - optional free-text metadata (see below)

Rules:

- exactly one `ASSESSMENT` exists per individual liability instance;
- `PAYMENT` may occur multiple times for the same assessment;
- `WAIVED` is rent-only;
- `WITHDRAWN` is lawful only under §V.8, and no `PAYMENT` or `WAIVED` may follow it;
- no amount is persisted here;
- no paid/unpaid/overdue/satisfied/reversed flag is persisted here;
- an assessment is immutable once lawfully written.

Notes column contract:

- `notes` is optional free-text metadata attached to any event row (`ASSESSMENT`, `PAYMENT`, `WAIVED`, or `WITHDRAWN`).
- `notes` is set at insert time by the FEAT that writes the event, from an actor-supplied string (typically a teacher's reason for a waiver, an admin's justification for a manual adjustment, etc.).
- `notes` is immutable after insert, consistent with the general event immutability rule above.
- `notes` is NOT authoritative business truth. No derived satisfaction rule (§VIII), no cross-domain contract, and no operational legality check MAY read `notes` to decide behavior. Its purpose is human-audit visibility only.
- `notes` is visible to any actor who can see the underlying event (i.e., the teacher who administers the class, and the affected student for events on their own seat).
- Callers that omit `notes` (or pass empty string) SHALL result in `NULL`. Empty and NULL are equivalent in semantics.

### 2. `bill_cycles`

Records recurring temporal progression for any continuing obligation-producing relationship (rent per class; insurance premiums per insurance entitlement), distinguished by `internal_ref` and the driven assessments' `obligation_type`.

Key fields:

- `id`
- `class_id` - FK to `classes`; the tenant isolation boundary (`INV-CORE-000` §1, `DOM-CORE-002` §IV.1), not a business subject
- `internal_ref` - for specific assessment_event referencing and advancement
- `cycle_number` - for advancement tracking
- `policy_uuid` - the immutable policy version in force for this cycle, frozen by reference
- `cycle_boundary_at` - where this cycle's period begins: its coverage/due boundary
- `next_assessment_at` - where this cycle's period ends and the successor's begins; the successor is assessed at `next_assessment_at − preview` (§V.7)

Rules:

- bill cycles carry `class_id` as their tenant isolation boundary and no other class or seat identity: they do not record which class or seat a charge is about (that lives in the opaque `internal_ref` and in the assessments), and they store no `seat_id`;
- bill cycles do not store amount;
- bill cycles do not store business meaning for the reference;
- bill cycles are only lawful when they point to a currently continuing relationship;
- the current cycle, and therefore the policy UUID in force at a reference time, is the cycle whose period contains that time (§V.7); the latest cycle MUST NOT be used as a proxy for it;
- **succession** (`schedule_next_bill_cycle`) creates the next lawful cycle for the lineage, with the cycle number derived from authoritative state (`1` when the lineage is empty, otherwise `current + 1`) and never supplied by the caller; succession is lawful only under the eligibility rule in §V.7 (empty lineage, or a non-terminal latest cycle whose assessment point has arrived), and never after a terminal row; **termination** writes a terminal row that stops future recurring assessment and is not a succession;
- for a non-terminal cycle, `next_assessment_at` MUST be strictly later than `cycle_boundary_at`;
- a terminal bill-cycle row with `next_assessment_at = NULL` stops future recurring assessment for the lineage; its `cycle_boundary_at` is the termination instant (§V.7), which may precede the latest scheduled cycle's `next_assessment_at`;
- a scheduled cycle whose `cycle_boundary_at` is at or after the termination instant never becomes effective; its row is not altered;
- when the helper is late, the next scheduled run processes the due cycle if it still exists and has not been superseded.

---

## VIII. Derived State

The following SHALL be derived and SHALL NOT be persisted as canonical obligation truth:

- satisfied;
- outstanding;
- past due;
- visible;
- partial payment;
- amount paid;
- amount outstanding;
- days late;
- overpayment handling;
- any mutable lifecycle flag that can be inferred from immutable events.

### Derived evaluation rules

For one assessment:

```text
paid_amount = sum(authoritative Ledger amounts referenced by PAYMENT events for the same correlation_id)
has_waiver = exists(WAIVED for the same correlation_id)
is_withdrawn = exists(WITHDRAWN for the same correlation_id)

if is_withdrawn:
    status = WITHDRAWN
elif paid_amount >= assessed_amount:
    status = SATISFIED
elif has_waiver:
    status = SATISFIED
else:
    status = OUTSTANDING
```

An assessment bound to a bill cycle is due at that cycle's `cycle_boundary_at`, regardless of when it was assessed.

For one lineage at a reference time, **required obligations satisfied** is derived as: every assessment on the lineage that is due at or before the reference time is SATISFIED by facts recorded at or before that time. Assessments not yet due, including advance-assessed ones, are not required yet, and a `WITHDRAWN` assessment is never required. This is the product-blind domain read other domains consume; they MUST NOT inspect obligation tables or reconstruct payment status. It evaluates persisted obligations only and never synthesizes a hypothetical liability from `next_assessment_at`.

**Default payment target.** When a payment is requested against a lineage without selecting a specific assessment, the target is the oldest OUTSTANDING assessment on that lineage, by due boundary. An explicitly selected assessment is honored when it is lawfully payable. This is a domain read; callers do not order assessments themselves.

Past due is derived as:

```text
status == OUTSTANDING and canonical_now > due_at
```

---

## IX. Operational Rules

1. All obligation mutation SHALL occur through the canonical business operations owned by this domain.
2. GET and read-time logic SHALL remain pure.
3. Neither a cycle's assessment point nor its boundary mutates canonical truth by itself. The assessment point makes succession and assessment eligible (§V.7); the boundary makes the period's consequences eligible (coverage, grace, late fees, period benefits).
4. Assessment creation must remain idempotent for the same lawful lineage and correlation.
5. A lawful assessment SHALL NOT be deleted, reversed, or retroactively rewritten.
6. Monetary correction after settlement SHALL occur through Ledger, not by editing obligation history.
7. Insurance cancellation or termination prevents future recurring assessments; it does not rewrite prior obligation events.
8. Rent waiver is lawful only for rent assessments.
9. At a rent boundary, previously granted rent perks expire regardless of whether the current policy UUID remains the same.
10. Current rent is determined by the cycle whose period contains the reference time (§V.7), not by the latest cycle and not by a mutable current flag.
11. A qualifying rent outcome MAY coordinate a Store entitlement grant, but the
    grant is a separate cross-domain effect with `acquisition_type = GRANT`.
    Obligations does not create, count, expire, or otherwise mutate the Store
    entitlement lifecycle.
12. A coordinating FEAT MAY attempt satisfaction of an obligation immediately upon assessment. A failed attempt leaves the obligation OUTSTANDING; it remains satisfiable by any later lawful payment, before or after its due boundary.
13. A benefit granted for satisfying a period's obligation belongs to that period. Satisfying it early grants nothing before the period begins; the benefit is granted when the period takes effect.
14. Termination of a lineage stops future assessment only. Obligations already assessed remain due and satisfiable, except an unpaid advance assessment for a period that never becomes effective, which is withdrawn (§V.8); satisfying one after termination settles that obligation and nothing else.
15. An advance rent assessment is lawful only if rent is enabled at that period's `cycle_boundary_at` according to the class feature timeline known when it is assessed. A later disablement of rent that takes effect at or before that boundary withdraws the assessment if it is unsatisfied; the disabling FEAT coordinates the withdrawal (§V.8).

---

## X. Cross-Domain Coordination

Obligations may consume authoritative inputs from:

- Class Configuration, for rent enablement and class-level economics;
- Policies, for rent settings and other policy definitions;
- Store and Entitlements, for insurance coverage lifecycle inputs and entitlement effects;
- Ledger, for monetary settlement truth.

Obligations does not own those upstream facts.

Where an upstream domain supplies the lawful inputs for an assessment, Obligations records the liability and its resolution while preserving the upstream lineage.

When rent satisfaction or another qualifying rent outcome produces a configured
Store benefit, the coordinating FEAT SHALL invoke the lawful Store grant
surface after evaluating the rent-owned condition. The Store grant is not a
purchase, does not use purchase-limit or overdue-purchase checks, and remains
subject to the product's source-independent holding limit. If the holding limit
prevents the grant, the entitlement grant may fail or be skipped without
rewriting the already-established obligation outcome. The coordination MUST be
idempotent and preserve one correlation lineage across the obligation and any
resulting Store event.

---

## XI. Amendment

Revisions to this document must:

1. increment the version number;
2. update the Effective Date;
3. maintain consistency with `INV-CORE-000`;
4. maintain consistency with `INV-ARC-015` and `INV-ARC-016`;
5. keep the obligations domain limited to liability existence, recurring progression, and lawful satisfaction.

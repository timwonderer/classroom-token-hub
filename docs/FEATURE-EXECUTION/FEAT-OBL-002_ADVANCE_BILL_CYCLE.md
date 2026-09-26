# FEAT-OBL-002: Schedule Next Bill Cycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-OBL-002 | 2.1 | 2026-09-24 | 2.0 | Normative |

---

## I. Purpose

This FEAT records the **next lawful bill cycle** for a recurring obligation lineage through the Obligations succession command `schedule_next_bill_cycle` (DOM-OBL-001 §V.7).

There is no separate genesis command. The domain derives the cycle number from authoritative Obligations state: `1` where the lineage has no cycle, otherwise `current + 1`. The caller requests succession for a lineage and never supplies or asserts a cycle number.

The bill cycle is identity-blind temporal reminder state. It does not determine business meaning, amount, class, seat, or contract authority. It only records that a continuing internal reference must be reconsidered at a lawful boundary.

This FEAT is used for recurring rent and recurring insurance premium progression when the lawful upstream authority permits another cycle.

---

## II. Authority

Obligations owns:

- `bill_cycles`
- recurring progression legality for obligation sources

Class Configuration owns:

- rent policy terms
- insurance policy terms
- effective version lineage

Store and Entitlements owns:

- insurance entitlement / coverage lifecycle inputs

Ledger owns:

- monetary truth

This FEAT SHALL NOT decide business meaning from labels or mutate upstream contractual truth.

---

## III. Required Context

Required canonical context:

- `class_id`
- `internal_ref`
- `seat_id` when the source is seat-scoped
- `actor_seat_id`
- `cycle_boundary_at` and `next_assessment_at` for the requested cycle
- `policy_uuid` in force for the requested cycle
- `idempotency_key` — the command identity (DOM-OBL-001 §V.7), scoped to `class_id`
- the canonically resolved reference time (execution context; not part of the command's terms)

The request carries no cycle number. The lawful caller SHALL provide the upstream authority reference and version snapshot needed to validate the requested cycle.

---

## IV. Orchestration Logic

### 1. Verification

1. Look up the command identity. If it was already executed with the same terms, return that execution's cycle (exact replay); if with different terms, fail closed (replay mismatch). Replay is decided before eligibility.
2. Verify succession eligibility from authoritative Obligations state (DOM-OBL-001 §V.7): the lineage is empty, or its latest cycle is non-terminal and its assessment point has arrived at the reference time, evaluated through the Canonical Temporal Evaluation helper (INV-ARC-015 §VII). The assessment point is `next_assessment_at − preview`, where `preview` is the bill preview interval of the immutable policy referenced by that cycle's own `policy_uuid`, obtained through the Policies read (DOM-POL-001A §V.E); a preview of `0` places it at `next_assessment_at`. Succession after a terminal cycle, or before the assessment point, is unlawful.
3. Verify `next_assessment_at` is strictly later than `cycle_boundary_at` (DOM-OBL-001 §VII.2).
4. Derive the cycle number once from the state read in step 2.
5. Verify the recurring source still lawfully exists, and resolve the lawful version snapshot that governs the cycle.

### 2. Mutation

1. Create the `bill_cycles` row and record the command identity (`obligation_command_reservation`: identity, request fingerprint, produced cycle) in the same transaction.
2. If a different command created the derived cycle first, fail with a succession conflict. Do not replay it and do not re-derive a later cycle (DOM-OBL-001 §V.7 case 3).
3. Emit any resulting lawful obligation assessment through the canonical obligations FEAT surface.

### 3. Terminal case

If the authoritative source has terminated, no successor cycle is created. Termination itself is a separate command (`terminate_bill_cycle`) and is not routed through succession.

---

## V. Invariants

1. `bill_cycles` SHALL NOT store monetary amount.
2. `bill_cycles` SHALL NOT store business meaning for the source.
3. `bill_cycles` SHALL NOT store class/seat identity when that identity belongs upstream.
4. A terminated recurring relationship produces no successor cycle.
5. Succession is idempotent on command identity, never on the shape of the row it would write. Two distinct commands deriving the same cycle are two commands: exactly one creates it and the other receives a succession conflict.
6. The cycle number is derived (`1` for an empty lineage, otherwise `current + 1`) and is never caller-supplied.
7. Succession is lawful only for an empty lineage or a non-terminal latest cycle whose assessment point has arrived. A caller's own scheduling predicate does not substitute for this check. A later policy submission cannot move an existing cycle's assessment point.
8. The latest cycle is not the current cycle: under advance assessment it is routinely an upcoming cycle whose period has not begun. Callers that need the current cycle use the period-containment query (DOM-OBL-001 §V.7).

---

## VI. Dependencies

- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md`
- `schedule_next_bill_cycle` (Obligations bill-cycle succession command; DOM-OBL-001 §V.7, §VII.2)

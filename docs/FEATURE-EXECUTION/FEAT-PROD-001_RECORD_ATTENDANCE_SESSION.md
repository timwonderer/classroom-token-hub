# FEAT-PROD-001: Record Attendance Session

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-001 | 1.5 | 2026-10-03 | 1.4 | Normative |

---

## I. Purpose

This FEAT owns attendance ingress. FEAT-PROD-003/004 may compose only the due-system-closure PROD command authorized by DOM-PROD-001 §XV.7 inside their own atomic context.

It records attendance-session rows for the Productivity and Payroll domain and
replaces any other FEAT or route path that would otherwise write to that table.

This FEAT uses `CanonicalContext` for live request authority and `canonical_temporal_resolver("CLE", primitive="current_time", ...)` from `app/utils/canonical_temporal_resolver.py` for class-local time evaluation.

---

## II. Scope

Governs append-only attendance event creation. Terminal interval invalidation is a separate `FEAT-PROD-005` operation; this FEAT does not write eligibility decisions or money.

## III. Authority Level

Normative; subordinate to INV-CORE-000 §III.1–6, INV-CORE-001 §III, VIII, DOM-PROD-001 §VII–XI, and FEAT-CORE-000 §II–V. INV-ARC-006 §V, INV-ARC-007 §V, INV-ARC-009 §V, and INV-ARC-021 §V govern command-only mutation, pure reads, domain authority, and composition.

## IV. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`

- [FEAT-PROD-005](FEAT-PROD-005_INVALIDATE_ATTENDANCE_INTERVAL.md)

---

## V. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext`
- `idempotency_key`: when the caller requires replay protection for the write
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation
- `actor_seat_id`: the seat performing the action
- `target_seat_id`: the seat whose attendance state is being recorded
- `mechanism`: `self`, `teacher`, or `system`

### 2. Canonical Authority

- `ctx.class_id` provides the class boundary
- `ctx.seat_id` provides the actor/target seat for live requests
- `ctx.actor_role` determines whether the action is a student or teacher attendance action

The FEAT MUST fail closed if `ctx.class_id` or `ctx.seat_id` cannot be established.
The FEAT MUST NOT infer authority from legacy identity sources.

The FEAT MUST NOT infer class or seat authority from any legacy identity source.

---

## VI. Canonical Write

### `record_attendance_session(...)`

Attendance ingress uses this FEAT; due system closure may be composed by FEAT-PROD-003/004 under DOM-PROD-001 §XV.7.

Canonical business actions:

- start work
- return from hall pass
- leave for hall pass
- end of day
- automatic session closure when a new active session opens
- automatic session closure at the time limit
- automatic session closure at end of day

Rules:

- MUST require `class_id` and `seat_id`
- MUST treat every written attendance row as immutable and permanent
- MUST require `actor_seat_id`, `target_seat_id`, and `mechanism`
- MUST use class-local canonical time for the timestamp
- MUST set `status` to `active` or `inactive`
- MUST set `reason_code` when writing an `inactive` row
- MUST set `hall_pass_id` when `reason_code = hall_pass`
- MUST set `mechanism` to `self`, `teacher`, or `system`
- MUST set `actor_seat_id` to the initiating seat
- MUST set `target_seat_id` to the seat whose attendance state changes
- MUST NOT persist or select attendance by an authentication principal; target identity is `(class_id, target_seat_id)`
- MUST write `active` with `reason_code = start_work` for start work and hall-pass return
- MUST write `inactive` with `reason_code = hall_pass` for leaving for hall pass
- MUST write `inactive` with `reason_code = done_for_day` for end-of-day closure
- MUST write the automatic closure row(s) rather than mutating prior rows
- MUST append a new `active` row followed by an `inactive` `done_for_day` row when a dangling hall pass is detected at end of day
- MUST use the same timestamp for both rows in that dangling-hall-pass recovery sequence
- MUST not store current attendance state
- MUST not store accumulated daily minutes
- MUST not store hall-pass destination
- MUST not store payroll amount
- MUST NOT delete, soft-delete, edit, mark as deleted, hide, or correct an existing `attendance_sessions` row (destruction of a seat's rows with the seat, or of a class's rows with the class, is lifecycle destruction outside this FEAT — `DOM-PROD-001` §VII.1.a)
- MUST NOT provide a teacher-facing attendance-row deletion or correction endpoint
- MUST NOT use attendance-row mutation to correct a payroll outcome

Correction rule:

- A teacher invalidates a completed work interval through `FEAT-PROD-005`, which appends a separate eligibility decision and any required payroll correction through domain commands. `FEAT-PROD-003` retains exact whole-event reversal and residual recovery authority.
- The original attendance row remains part of the immutable productivity timeline.

Execution steps:

1. Resolve `CanonicalContext` and confirm the request is lawful for the seat and class.
2. Resolve `CLE` with `canonical_temporal_resolver("CLE", primitive="current_time", canonical_execution_context=ctx, reference_time_utc=reference_time_utc)`.
3. Derive the canonical request timestamp in class-local time and normalize it to UTC for persistence.
4. Determine the correct canonical row shape for the requested attendance action.
5. Populate `actor_seat_id`, `target_seat_id`, and `mechanism`.
6. If the row is hall-pass-related, require `hall_pass_id` to reference the consumed entitlement instance's `entitlement_id`.
7. If end-of-day cleanup finds a dangling hall pass, emit `active/start_work` and then `inactive/done_for_day` at the same timestamp.
8. Persist the append-only row or row sequence to `attendance_sessions`.

Failure conditions:

- missing class context
- missing seat context
- invalid hall-pass correlation
- attempt to mutate prior attendance state instead of appending a new row
- attempt to delete, soft-delete, mark-delete, or correct an existing attendance row
- attempt to write `attendance_sessions` outside this FEAT

---

## VII. Temporal Rules

- Attendance comparisons MUST use the canonical temporal resolver.
- Attendance rows are recorded in UTC and displayed in class canonical time.
- Any derived attendance duration MUST be computed from the attendance timeline, not stored on the row.
- End-of-day cleanup MUST respect the current class-local day boundary.

---

## VIII. Write Authority

The PROD attendance command is the sole writer for `attendance_sessions`; FEAT-PROD-001 owns ingress and FEAT-PROD-003/004 may compose its narrow due-system-closure operation.

No other FEAT, route, background job, service, or migration logic may write to
`attendance_sessions` directly.

Other attendance writers MUST compose this domain command under the declared execution contract, never execute a nested FEAT (`FEAT-CORE-000` §V.1). Interval eligibility is a separate domain surface and writes no `attendance_sessions` row.

---

## IX. Invariants

1. Attendance writes are append-only.
2. Attendance rows are immutable after insertion and permanent for as long as their target seat exists; they are destroyed only with that seat or with the class (`DOM-PROD-001` §VII.1.a, `INV-CORE-000` §III.6).
3. There is no delete, soft-delete, mark-deleted, or correction-in-place attendance path. Lifecycle destruction of the seat or class is not such a path.
4. Interval invalidation and payroll recovery append separate records under `FEAT-PROD-005` / `FEAT-PROD-003`; neither changes attendance.
5. Hall-pass attendance rows must carry the same consumed entitlement instance `entitlement_id` recorded as `hall_pass_logs.hall_pass_id`.
6. The FEAT must fail closed if `ctx.class_id` or `ctx.seat_id` cannot be established.
7. The FEAT must not mutate hall-pass entitlement state.
8. All attendance writes use the PROD command under a declared FEAT coordinator; the system-closure exception is limited by DOM-PROD-001 §XV.7.

---

## X. Amendment

Version 1.4 (2026-10-03) supersedes v1.3's whole-payroll-only correction wording; it preserves attendance immutability and identifies the separate interval-invalidation contract. This amendment implements documentation authority only. Revisions must increment version/date, identify superseded rules, and preserve governing invariants.

### Version 1.5: prospective provenance foundation (2026-10-03)

Supersedes 1.4's exclusive writer wording only for canonical due system closure. Incorporates DOM-PROD-001 §XV.7–8 and [SPEC-PROD-001](../SPEC/SPEC-PROD-001_ATTENDANCE_INTERVAL_ELIGIBILITY_AND_PAYROLL_CORRECTION.md) §VI: preserve pair IDs, freeze version-1 settlement inputs, protect complete payroll summaries, and expose pure evidence queries. Every attendance writer locks its class/target seat before selection. New payroll composes `close_due_attendance_intervals` within one FEAT transaction before pricing; class completion resolves completed-run replay first and locks eligible seats in stable order. Audit linkage initializes once within creation and cannot change after commit. No nested FEAT, historical backfill, or correction button is authorized by this foundation.

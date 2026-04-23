# Obligations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OBL-001 | 2.1 | 2026-04-22 | 2.0 | Constitutional |

---

## I. Purpose

This document defines the Obligations domain as the absolute sovereign of recurring seat-scoped debt, policy-driven charges, and the non-optional entitlements they unlock. It ensures deterministic execution of financial duties and prevents "hidden money bugs" through strict invariant enforcement.

## II. Scope

This domain governs the runtime execution and lifecycle of **seat-scoped obligations**, **satisfaction events**, and **entitlement event streams**.

**Obligations operates on seat-scoped economic actors, not global identities.** All runtime state is anchored to `seat_id`. Debts and perks are class-bound; they shall not follow a `student_id` across different class universes.

This domain does not own:
- **Global Identity**: Owned by `Identity`.
- **Obligation Policy**: Owned by `Class Configuration`. Obligations is an execution domain that reads policies as directives.
- **Currency Balances**: Owned by `Ledger`.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-CLASS-001_Class_Configuration_Domain.md` (Policy Source)

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `obligation_assessment` (historical fact of debt)
- `obligation_satisfaction` (payments, waivers)
- `obligation_reversal` (corrections, nullifications)
- `entitlement_events` (grant/consumption stream)
- `insurance_enrollments` (seat-level contracts)
- `insurance_claims` (decision state)

**Policy Ownership:** Class Configuration owns the obligation policy (rates, schedules). Obligations shall execute the policy into runtime events.

## VI. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Assessment Event** | Authoritative Event | Immutable record of a seat's liability. |
| **Satisfaction Event** | Authoritative Event | Immutable record of debt resolution (Payment/Waiver). |
| **Reversal Event** | Authoritative Event | Immutable record of an assessment nullification. |
| **Entitlement Event** | Authoritative Event | Immutable stream of grants, consumptions, and revocations. |
| **Entitlement Balance** | Derived State | Strictly derived from the Entitlement Event stream. |
| **Seat Obligation Status** | Derived State | Intersection of Assessment, Satisfaction, and Reversal events. |
| **Due Date (`due_at`)** | Authoritative Event State | Snapshotted at assessment time from policy + calendar logic. |

## VII. Invariants

- **INV-OBL-001: Seat-Scoped Isolation**. All obligation state shall be anchored to a `seat_id`. Economic reality is class-bound; debt shall not follow a student across classes.
- **INV-OBL-002: Event-Only Entitlements**. Entitlement balances MUST NOT be stored as authoritative state; they are views derived from the `entitlement_events` stream.
- **INV-OBL-003: Consumption Idempotency**. Entitlement consumption triggers MUST be idempotent. A duplicate `trigger_id` shall never result in multiple decrements.
- **INV-OBL-004: Assessment Idempotency**. A policy-period assessment MUST be idempotent. A duplicate trigger for the same `(seat_id, policy_id, period_key)` shall never create multiple assessments.
- **INV-OBL-005: Reversal Primacy**. A reversed assessment shall be treated as non-existent for all downstream interpretations (delinquency, reporting), overriding any prior satisfaction events. **Reversal wins.**
- **INV-OBL-006: Deterministic Entitlement Compensation**. Any `ReversalEvent` targeting an assessment that previously triggered a `GRANT` MUST emit a corresponding `REVOCATION` event.
- **INV-OBL-007: Period Key Determinism**. The `PeriodKey` shall be derived from the `ClassCalendar` and `PolicySchedule`. It ensures a 1:1 mapping between a time-slice and a liability.
- **INV-OBL-008: Overdue Definition**. A seat is `Overdue` if and only if `now > due_at` AND no `SatisfactionEvent` or `ReversalEvent` exists for that assessment.
- **INV-OBL-009: Policy Snapshotting**. Assessments MUST snapshot `amount` and `due_at`. Mid-cycle policy changes shall not retroactively affect existing debt.
- **INV-OBL-010: Local Time Sovereignty**. All due dates and triggers shall be calculated using the `ClassTimeZone`.

## VIII. Schema Contract

### 1. `obligation_assessment`

Records the historical fact of a seat becoming liable for a policy-defined charge.

- `id` (PK)
- `seat_id` (FK to seats)
- `policy_id` (FK to Class Configuration policies)
- `amount_snap` (Decimal)
- `period_key` (String: `[YYYY]-[PERIOD]`) [Unique: `seat_id`, `period_key`]
- `due_at` (Timestamp: Snapshotted from policy + calendar)
- `assessed_at` (Timestamp)

### 2. `obligation_satisfaction`

Records how a valid debt was resolved.

- `id` (PK)
- `assessment_id` (FK; Unique)
- `method` (Enum: `PAYMENT`, `WAIVER`)
- `satisfied_at` (Timestamp)

### 3. `obligation_reversal`

Records the correction or nullification of an assessment.

- `id` (PK)
- `assessment_id` (FK; Unique)
- `reason` (String)
- `reversed_at` (Timestamp)

### 4. `entitlement_events`

Append-only stream of obligation-linked perks (e.g., hall pass quota).

- `id` (PK)
- `seat_id` (FK to seats)
- `assessment_id` (FK; Nullable)
- `trigger_id` (String; Nullable - for consumption idempotency)
- `quantity_delta` (Integer: +N for Grant, -N for Consumption/Revocation)
- `type` (Enum: `GRANT`, `CONSUMPTION`, `REVOCATION`)
- `occurred_at` (Timestamp)

## IX. Derived / Cross-Domain Rules

- **Status Hierarchy**: Status is derived as: `REVERSED` > `WAIVED` > `PAID` > `OVERDUE` (if `now > due_at`) > `DUE`.
- **Entitlement Sovereignty**: Obligations owns **obligation-linked** entitlements (e.g., rent-linked hall passes). Store owns **store-purchased** items.
- **Consumption Flow**: Attendance emits `ConsumptionIntent`. Obligations validates against the derived balance and records the `CONSUMPTION` event.
- **Ledger Coordination**: All assessment and satisfaction events shall emit `PostingRequests` to Ledger via FEAT. Obligations does not own ledger rows.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.

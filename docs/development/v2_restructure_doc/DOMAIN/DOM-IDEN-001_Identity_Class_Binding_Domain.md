# Identity and Class Binding Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 1.2 | 2026-04-23 | 1.1 | Constitutional |

---

## I. Purpose

This document defines the Identity and Class Binding domain as the absolute sovereign of human identity (users), classroom participation (seats), and the logical boundaries of the classroom economy (classes). It ensures that every economic action is anchored to a verified participant and prevents identity leakage or cross-class contamination.

## II. Scope

This domain governs:
- **Global Human Identity**: The origin and lifecycle of `users` records.
- **Class Context**: The definition and lifecycle of `classes`.
- **Actor Binding**: The "Claim" lifecycle that links a global user to a class-local seat.
- **Session Resolution**: The mapping of an authenticated session to an active class context.

This domain does not own:
- **Financial Truth**: Owned by `Ledger`.
- **Operational Facts**: Owned by `Attendance`.
- **Policy/Directives**: Owned by `Class Configuration`.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`
- `DOM-IDEN-003_Teacher_Identity_Architecture.md`
- `docs/development/specs/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `users`
- `seats`
- `identity_profiles`
- `classes`

## VI. Owned Tables

### 1. `users`

Global human identity. Owns authentication credentials, recovery state, and session nonces.

### 2. `seats`

Class-local participant record. The "Economic Identity." Every activity record in other domains MUST reference `seat_id`.

### 3. `identity_profiles`

Human-facing display identity (Names, initials). One-to-one with `seats`.

### 4. `classes`

The universe anchor. Defines the boundary of a classroom economy.

---

## VII. Schema Contract

### 1. `users`

Key fields:
- `id` (PK)
- `user_role` — `'teacher'` | `'student'` | `'sysadmin'`
- `username_lookup_hash` — HMAC-based lookup
- `totp_secret_encrypted` / `pin_hash` / `passphrase_hash`
- `current_session_nonce` — binds requests to a specific login event
- `last_active_seat_id` — nullable FK to `seats`; tracks the last resolved context for multi-device continuity

Rules:
- One row per human identity.
- `user_role` is immutable after creation.
- No PII (Date of Birth) shall be stored.

### 2. `seats`

Key fields:
- `id` (PK)
- `user_id` — nullable; FK to `users` (The Binding)
- `class_id` — FK to `classes` (The Anchor)
- `role` — `'teacher'` | `'student'`
- `claimed_at` — timestamp of binding

Rules:
- A seat is "Unclaimed" if `user_id` is NULL.
- A seat is "Claimed" if `user_id` is NOT NULL.
- **INV-IDEN-011: One-to-One Binding per Class**: A single `user_id` may own multiple seats across the system, but at most ONE seat per `class_id`.

---

## VIII. Identity Lifecycle & Provisioning Law

### 1. User Origin
- **Teacher Origin**: Created via Sysadmin provisioning or verified Invite flow.
- **Student Origin**: Created at the moment of the **First Seat Claim**. If a person claims their first seat, a `users` record is created. Subsequent claims bind to the existing `user_id`.
- **Sysadmin Origin**: Bootstrapped via secure environment configuration or existing Sysadmin promotion.

### 2. Seat Provisioning
- **Teacher Seat**: Created automatically when a Teacher initializes a class.
- **Student Seat**: Created by a Teacher (Roster Upload) or as a "Generic Placeholder" waiting for a claim.

---

## IX. Seat Binding & Context Law

### 1. The Claim Lifecycle
Binding a global user to a class-local seat is a non-reversible transaction (within the scope of a single class cycle).

- **Claim Logic**: A user provides a `join_code` + `claim_credentials` (e.g. roster name).
- **Binding**: On match, the `user_id` is written to the `seats` row. This seat is now "Claimed."
- **Immutable Association**: Once `claimed_at` is set, the `user_id` on a seat MUST NOT be changed to a different `user_id`.

### 2. Context Resolution (The Binding Guard)
Every request operating within a class MUST be resolved to a specific `seat_id`.

- **INV-IDEN-012: Context Authority**: The system MUST verify that the authenticated `user_id` owns the `seat_id` provided in the request context for that `class_id`.
- **Global vs. Scoped Requests**:
  - **Global Requests**: Authentication only (`user_id`). Permitted for identity management, class selection, and Sysadmin actions.
  - **Scoped Requests**: Authentication + Authorization (`user_id` + `seat_id`). MANDATORY for all activity in Ledger, Obligations, Attendance, and Store domains.
- Cross-seat or cross-class requests where the `user_id` does not own the target `seat_id` MUST be rejected.

### 3. Context Restoration Law (The Sticky Context)
To support multi-device continuity and prevent "Class Drift," the system maintains a persistent pointer to the last used context.

- **Storage**: The `users.last_active_seat_id` is updated every time a user explicitly switches their active class context. This includes the initial binding during the **First Seat Claim**.
- **Restoration**: On initial authentication (or session recovery), if no context is provided, the backend SHOULD resolve the request to the `last_active_seat_id`.
- **Validation**: Restored context must still pass `INV-IDEN-012` validation. If the seat is no longer valid (e.g. deleted or unassigned), the user must be prompted to select a new context.

---

## X. Invariants

- **INV-IDEN-001: Unified Role Model**. No separate `students` or `teachers` tables. All role differentiation happens via `user_role` (Global) and `role` (Seat).
- **INV-IDEN-002: Seat Sovereignty**. `seat_id` is the primary key for all activity-tracking in other domains.
- **INV-IDEN-011: One-to-One Binding per Class**. A user shall not hold multiple seats in the same class universe.
- **INV-IDEN-012: Context Authority**. Requests must prove ownership of the `seat_id` context.

---

## XI. Derived / Cross-Domain Rules

- Other domains reference `seat_id` (activity) and `class_id` (policy).
- `user_id` is for authentication, recovery, and global security only.
- Identity does not grant financial or attendance authority; it only provides the *binding* for those domains to record facts.

---

## XII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.

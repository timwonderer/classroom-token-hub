# DOM-CORE-002: Canonical Schema Definition

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CORE-002     | 1.0     | 2026-04-25     | N/A        | Constitutional |

---

## I. Purpose

To define the **canonical runtime schema** of the system as a direct expression of domain authority.

This document defines the **only valid set of runtime tables**, their responsibilities, and their structural constraints.

---

## II. Scope

This document applies to all runtime tables supporting:

- Identity and class binding
- Economic activity and financial recording
- Attendance and mobility tracking
- Obligation lifecycle and entitlement issuance
- Store interaction and redemption
- Operational observability and audit
- Interpretation and analytics
- Support and communication systems

---

## III. Authority

This document is the authoritative definition of the V2 runtime schema.

- The runtime schema **consists exclusively of the tables defined in this document**.
- Any deviation in implementation is considered **non-compliant**.
- The presence of additional tables in the database does not grant them validity.

---

## IV. Global Schema Invariants

### 1. Seat-Scoped Isolation

All class-scoped state is anchored to:

- `seat_id` (actor scope)
- `class_id` (universe boundary)

No table relies on indirect or inferred scope.

---

### 2. Domain Ownership

Each table has exactly one owning domain.

- Only the owning domain defines constraints and mutation authority
- Cross-domain access does not imply shared ownership

---

### 3. Event-Log Authority

Authoritative state is represented as:

- Immutable event records, or
- Explicit state tables derived from those events

No implicit state exists.

---

### 4. Domain Blindness (Ledger Constraint)

The Ledger domain does not encode business meaning.

- No policy identifiers
- No product abstractions
- No domain-specific classification beyond operational category

---

### 5. No Label-Based Authority

Fields such as:

- `block`
- `period`
- any human-readable grouping label

are not used for:

- scoping
- uniqueness constraints
- identity resolution

Labels are metadata only.

---

### 6. Global Idempotency

All write operations include:

- `idempotency_key`

The system guarantees:

- no duplicate side effects
- deterministic replay safety

---

### 7. Class Scope Resolution

`join_code` is a user-facing alias only.

- It is not used for internal scoping
- All internal relationships resolve through `class_id`

---

## V. Canonical Domain Tables

---

### 1. Identity & Class Binding (DOM-IDEN-001)

**Purpose:** Define global identity and class-local actor binding.

**Tables:**

- `users`
- `seats`
- `classes`
- `identity_profiles`

---

### 2. Class Configuration (DOM-CLASS-001)

**Purpose:** Define class-level directives and policy.

**Tables:**

- `class_features`
- `feature_settings`
- `hall_pass_settings`
- `rent_settings`
- `payroll_settings`
- `banking_settings`

---

### 3. Attendance & Mobility (DOM-ATT-001)

**Purpose:** Record time-based participation and movement.

**Tables:**

- `attendance_sessions`
- `hall_pass_logs`
- `seat_attendance_state`

---

### 4. Obligations & Entitlements (DOM-OBL-001)

**Purpose:** Manage seat-scoped debt lifecycle and benefits.

**Tables:**

- `assessment_events`
- `obligation_lifecycle`
- `obligation_satisfaction`
- `obligation_reversal`
- `entitlement_events`

---

### 5. Ledger & Money (DOM-LED-001)

**Purpose:** Record all monetary movement.

**Tables:**

- `ledger_transaction`
- `ledger_balance_snapshot`

**Constraints:**

- Anchored to `seat_id`
- Does not store `join_code`
- Enforces `idempotency_key`
- Remains domain-blind

---

### 6. Store & Redemption (DOM-STORE-001)

**Purpose:** Manage catalog, purchase, and redemption of items.

**Tables:**

- `store_items`
- `store_item_visibility`
- `store_purchases`
- `redemption_events`

---

### 7. Operations & Observability (DOM-OPS-001)

**Purpose:** Record system behavior, health, and audit trace.

**Tables:**

- `operational_events`
- `audit_log`
- `incident_events`
- `incident_summary`
- `alert_events`
- `invariant_run_events`
- `job_events`
- `health_check_events`

---

### 8. Interpretation (DOM-ITR-001)

**Purpose:** Derive behavioral and structural insights.

**Tables:**

- `interpretation_snapshots`
- `interpretation_annotations`

**Constraint:**

- Read-only domain

---

### 9. Support & Communication (DOM-SUP-001)

**Purpose:** Manage issue lifecycle and system communication.

**Tables:**

- `issues`
- `issue_status_history`
- `issue_resolution_actions`
- `ticket_correlation_packs`
- `announcements`
- `issue_categories`

---

## VI. Explicit Prohibitions

The following do not exist in the V2 schema:

1. Separate identity tables for roles (e.g., `students`, `teachers`)
2. Label-based scoping tables
3. Cross-domain mutation through direct table access
4. Business meaning encoded in the Ledger domain
5. Duplicate authority paths for the same concept
6. Internal scoping via `join_code`

---

## VII. Compliance

Only the tables defined in this document are valid within the V2 system.

No additional tables may be introduced without amendment to this document.

---

## VIII. Amendment

Any modification to the canonical schema requires:

- Version increment
- Updated Effective Date
- Explicit justification tied to domain authority


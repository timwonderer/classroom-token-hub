# V2 Schema Compliance Audit

| Document | Version | Date | Author | Authority Level |
|---|---|---|---|---|
| V2_SCHEMA_COMPLIANCE_AUDIT | 1.0 | 2026-04-25 | Timothy Chang | Informative |

**Branch:** `codex/v2.0`  
**Runtime baseline at time of audit:** 619 passed · 123 failed · 1 skipped  
**Governing authority:** INV-CORE-000, INV-CORE-001, DOM-CORE-000/001, all registered DOM-* documents

---

## I. Purpose

This document audits every table in the current `models.py` schema against the v2 domain
authority documents. It records each table's role, columns, constraint state, v2 invariant
violations, and recommended action.

It supersedes the preliminary schema audit produced earlier in the same session, which was
compiled before the `docs/development` directory was read.

---

## II. Reading Guide

Every table is assigned one of five status tiers:

| Tier | Meaning |
|---|---|
| **COMPLIANT** | Name, ownership, and key constraints match the governing domain contract |
| **TRANSITIONAL** | In use for v2.0 launch; carries known gaps deferred per `V2_Class_Scope_Normalization_Target.md` |
| **DIVERGENT** | Exists but name, authority model, or field constraints conflict with the owning domain spec |
| **DEPRECATED** | Identified for removal in `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` or superseded by a domain spec |
| **MISSING** | Domain spec declares the table authoritative; it does not exist in the current schema |

---

## III. Domain Authority Map

Per `DOM-CORE-001` v1.0 (2026-04-22) every table must have exactly one owning domain.

| Domain | Canonical Table Names | Spec |
|---|---|---|
| Identity & Class Binding | `users`, `seats`, `identity_profiles`, `classes` | DOM-IDEN-001 |
| Class Configuration | `class_features`, `feature_settings`, `hall_pass_settings`, `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `banking_settings` | DOM-CLASS-001 |
| Attendance | `tap_events`, `hall_pass_logs`, `seat_attendance_state` | DOM-ATT-001 |
| Obligations | `obligation_assessment`, `obligation_satisfaction`, `obligation_reversal`, `entitlement_events`, `insurance_enrollments`, `insurance_claims` | DOM-OBL-001 |
| Ledger | `ledger_transaction`, `ledger_balance_snapshot` | DOM-LED-001 |
| Store | `store_items`, `store_item_visibility`, `student_items`, `redemption_audit_logs` | DOM-STORE-001 |
| Operations | `operational_events`, `audit_log`, `invariant_run_events`, `incident_events`, `incident_summary`, `alert_events`, `job_events`, `health_check_events` | DOM-OPS-001 |
| Interpretation | `interpretation_snapshots`, `interpretation_annotations` | DOM-ITR-001 |
| Support | `issue_categories`, `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_packs`, `user_reports`, `announcements` | DOM-SUP-001 |

---

## IV. Table Inventory by Domain

---

### Domain: Identity & Class Binding (DOM-IDEN-001)

**Constitutional rule — INV-IDEN-001:** No separate `students` or `teachers` tables. All
role differentiation via `user_role` in `users` and `role` in `seats`.

---

#### `users` — COMPLIANT (dormant)

| Column | Type | Nullable |
|---|---|---|
| `id` | Integer PK | NOT NULL |
| `public_id` | UUID String(36) | NOT NULL unique |
| `username` | String(255) | NOT NULL unique |
| `password_hash` | Text | NOT NULL |
| `created_at` / `updated_at` | DateTime(tz) | NOT NULL |

**Gaps vs DOM-IDEN-001 §VII.1:** Missing `user_role`, `username_lookup_hash` (HMAC),
`totp_secret_encrypted`, `pin_hash`, `passphrase_hash`, `current_session_nonce`,
`last_active_seat_id`. These are required before the unified identity flow can be activated.

**Action:** Keep. Add missing fields when activating unified identity.

---

#### `identity_profiles` — TRANSITIONAL

| Column | Type | Nullable |
|---|---|---|
| `id` | Integer PK | NOT NULL |
| `profile_type` | String(32) | NOT NULL |
| `first_name` | PIIEncryptedType | NOT NULL |
| `last_initial` | String(1) | NOT NULL |
| `created_at` / `updated_at` | DateTime(tz) | NOT NULL |

Currently FKed from `students` and `teacher_blocks`. Target is one-to-one with `seats`.

**Action:** Keep. Re-anchor FK to `seats` when `students` is retired.

---

#### `seats` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `public_id` | UUID String(36) | NOT NULL | |
| `user_id` | FK → users | nullable | ✅ NULL = unclaimed per DOM-IDEN-001 |
| `class_id` | FK → class_economies | **nullable** | ❌ Must be NOT NULL — universe anchor |
| `role` | String(20) | NOT NULL | |
| `block_identifier` | String(10) | nullable | ❌ INV-CORE-000 §6 — label on identity record |
| `block` | String(10) | nullable | ❌ Duplicate of `block_identifier`; same violation |
| `roster_fingerprint` | String(128) | nullable | |
| `dedupe_code` | String(8) | nullable | |
| `claimed_at` | DateTime(tz) | nullable | ✅ |
| `join_code` | String(20) | NOT NULL | ❌ INV-CORE-000 §1 — should resolve via `class_id` FK, not stored |
| `student_id` | FK → students | nullable | ❌ Deprecated bridge per `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` |

**Invariants violated:** INV-CORE-000 §1 (explicit class anchor), §6 (label fields on
identity record), INV-IDEN-002 (seat's own `class_id` is nullable).

**Action:** Deferred per `V2_Class_Scope_Normalization_Target.md`. Make `class_id` NOT
NULL. Drop `block_identifier`, `block`. Drop `student_id` per backwards compat cleanup.

---

#### `class_economies` (domain target name: `classes`) — COMPLIANT

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `class_id` | UUID String(36) PK | NOT NULL | |
| `join_code` | String(20) | NOT NULL unique | user-facing public alias |
| `teacher_id` | FK → teachers | NOT NULL | RESTRICT |
| `display_name` | String(100) | nullable | metadata only ✅ |
| `class_timezone` | String(64) | NOT NULL | immutable via event listener |
| `created_at` / `updated_at` | DateTime(tz) | NOT NULL | |
| `created_by_admin_id` | FK → teachers | nullable | audit field |

`status` property hardcoded to `"active"` — correctly implements INV-CORE-000 §6 (no
lifecycle states). `class_timezone` immutable per `prevent_class_timezone_mutation()`.

**Table name divergence:** Domain spec says `classes`. Rename is a post-normalization item.

**Action:** Keep. Table rename deferred.

---

#### `class_memberships` — DEPRECATED (superseded by `seats`)

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `class_id` | FK → class_economies | NOT NULL | ✅ |
| `join_code` | String(20) | nullable | redundant |
| `admin_id` | FK → teachers | nullable | XOR with student_id |
| `student_id` | FK → students | nullable | XOR with admin_id |
| `role` | Enum(ADMIN\|STUDENT) | NOT NULL | |

DOM-IDEN-001 §V declares `seats` as the sole class-local binding table. `class_memberships`
creates dual-authority for enrollment alongside `seats`.

**Action:** Deprecate. Migrate callers to `seats` when unified identity is activated.

---

#### `teacher_blocks` — TRANSITIONAL (provisioning artifact serving two roles)

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `teacher_id` | FK → teachers | NOT NULL | |
| `block` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 — label used as index key |
| `class_label` | String(50) | nullable | display metadata ✅ |
| `first_name` | PIIEncryptedType | NOT NULL | nulled on claim ✅ |
| `last_initial` | String(1) | NOT NULL | |
| `identity_id` | FK → identity_profiles | NOT NULL | |
| `last_name_hash_by_part` | JSON | nullable | nulled on claim ✅ |
| `dob_sum_hash` | String(64) | nullable | nulled on claim ✅ |
| `salt` / `first_half_hash` | Bytes/String | NOT NULL | claim credentials |
| `join_code` | String(20) | NOT NULL | |
| `class_id` | FK → class_economies | **nullable** | ❌ Must be NOT NULL |
| `dedupe_key` | String(64) | nullable | |
| `student_id` | FK → students | nullable | set on claim |
| `is_claimed` | Boolean | NOT NULL | |
| `claimed_at` | DateTime(tz) | nullable | |

**Is `teacher_blocks` necessary?**

No — not in the v2 target model. But it is currently load-bearing, and for a specific
reason: it has accreted a second job beyond its stated provisioning purpose.

**Job 1 — Claim credential store (stated purpose):**  
Holds `first_half_hash`, `dob_sum_hash`, `last_name_hash_by_part`, `first_name`,
`last_initial` — all nullified on claim. This is a clean provisioning pattern that satisfies
INV-CORE-000 §2 (PII destroyed after identity-binding is complete).

**Job 2 — Runtime class roster index (accidental, load-bearing):**  
`_student_scope_subquery_for_join_code()` in `admin.py:882` — the primary query for "which
students are in this class?" — joins `Student` through `TeacherBlock.student_id` scoped by
`TeacherBlock.join_code`. The payroll engine (`payroll.py:249–326`) does the same. Scheduled
tasks and the app factory also query it. `teacher_blocks` has become the de facto class
membership lookup table even though `class_memberships` (and eventually `seats`) exists for
that purpose.

**What the v2 target says:**  
DOM-IDEN-001 §VIII.2: unclaimed student seats are created at roster-upload time as `seats`
rows with `user_id = NULL`. Claim credentials would live on `seats.roster_fingerprint` or
a `seat_claim_credentials` table that CASCADE-deletes on claim. `teacher_blocks` as a
concept disappears.

**Retirement gate:** Removing `teacher_blocks` requires first migrating every caller of
`_student_scope_subquery_for_join_code`, payroll's student-list queries, scheduled task
store-item cleanup, and the app factory seeding logic to use `class_memberships`/`seats`
instead. This is the core work of `V2_ADMIN_ROUTE_REFACTOR.md` and
`V2_Class_Scope_Normalization_Target.md`.

**Legacy shim:** `dob_sum` property — remove per `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` §3.

**Action:** Necessary for launch. Make `class_id` NOT NULL. Remove `dob_sum` property.
Retire as part of the admin-route refactor wave.

---

#### `students` — DEPRECATED (INV-IDEN-001)

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `first_name` | PIIEncryptedType | NOT NULL | |
| `last_initial` | String(1) | NOT NULL | |
| `identity_id` | FK → identity_profiles | NOT NULL | |
| `block` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 — label as identity field |
| `join_code` | String(20) | nullable | transitional |
| `class_id` | FK → class_economies | nullable | transitional |
| `first_half_hash` / `second_half_hash` | String(64) | nullable | claim credential hashes (active) |
| `username_hash` / `username_lookup_hash` | String(64) | nullable | auth lookup |
| `pin_hash` / `passphrase_hash` | Text | nullable | auth credentials |
| `has_completed_profile_migration` | Boolean | NOT NULL | ❌ REMOVE per cleanup §5 |
| `is_teacher` | Boolean | NOT NULL | role flag (legacy) |
| `hall_passes` / `is_rent_enabled` / `insurance_plan` / `insurance_last_paid` | mixed | mixed | ❌ Obligation/financial state on identity record — DOM-CORE-000 §2 violation |

INV-IDEN-001 states explicitly: *"No separate `students` or `teachers` tables."* This entire
table is deprecated in the v2 target state.

**Cross-domain contamination:** `hall_passes`, `is_rent_enabled`, `insurance_plan`,
`insurance_last_paid` are obligation/financial state stored on the identity record. These
belong in DOM-OBL-001 tables.

**Active cleanup items (per `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md`):**
- Remove `has_completed_profile_migration` (Phase 1, §5)
- Update misleading "legacy" comment on `second_half_hash` (Phase 2, §2)

**Action:** Keep for v2.0 launch. Execute backwards compat cleanup items. Full retirement
when `users`/`seats` unified identity is activated.

---

#### `student_teachers` — DEPRECATED

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `student_id` | FK → students | NOT NULL | |
| `teacher_id` | FK → teachers | NOT NULL | |
| `class_id` | FK → class_economies | nullable | |
| `join_code` | String(20) | nullable | |
| `created_at` | DateTime(tz) | nullable | ❌ Should be NOT NULL |
| `admin_id` | synonym for `teacher_id` | — | ❌ REMOVE per cleanup §4 |

Superseded by `seats`. Teacher ownership as a separate concept is eliminated in DOM-IDEN-001.

**Action:** Remove `admin_id` synonym per `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` §4. Full
table retirement when `seats` is activated.

---

#### `teachers` (Admin model, tablename: `teachers`) — DEPRECATED (INV-IDEN-001)

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `username` | String(80) | nullable | ❌ REMOVE per cleanup §1 |
| `username_hash` / `username_lookup_hash` | String(64) | nullable | active auth |
| `public_id` | UUID String(36) | NOT NULL | |
| `display_name` | PIIEncryptedType | NOT NULL | |
| `totp_secret` | PIIEncryptedType | NOT NULL | |
| `created_at` | DateTime(tz) | **nullable** | ❌ Make NOT NULL per cleanup §12 |

**Active cleanup items:**
- Remove `username` column + `@validates('username')` + legacy fallback in
  `_find_admin_by_auth_username()` (Phase 1, §1)
- Make `created_at` NOT NULL (Phase 2, §12)

**Action:** Keep for v2.0 launch. Execute cleanup items. Retire when `users` is activated.

---

#### `system_admins` / `admin_credentials` / `system_admin_credentials` — COMPLIANT

No domain violations. Keep.

---

#### `admin_invite_codes` — UNCLASSIFIED

Not claimed by any domain spec. Keep pending DOM-IDEN clarification on invite provisioning.

---

### Domain: Ledger (DOM-LED-001)

**INV-LED-001:** All financial state anchored to `seat_id`. *"Ledger does not own
`join_code`. Isolation is inherited via the `seat_id`."*  
**INV-LED-002:** POSTED transactions are immutable.  
**INV-LED-006:** `idempotency_key` must be globally unique.  
**INV-LED-010:** Domain blindness — `category` classifies operational provenance only; must
not encode business meaning.

---

#### `transaction` (domain target name: `ledger_transaction`) — DIVERGENT

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `seat_id` | FK → seats | **NOT NULL** | ✅ INV-LED-001 |
| `student_id` | FK → students | nullable | ❌ Deprecated — violates INV-LED-001 |
| `teacher_id` | FK → teachers | nullable | ❌ Domain-blind ledger should not reference teacher |
| `join_code` | String(20) | nullable | ❌ INV-LED-001: Ledger does not own `join_code` |
| `class_id` | FK → class_economies | **nullable** | ❌ Must be NOT NULL (required for idempotency constraint) |
| `amount` | Numeric(12,2) | NOT NULL | ⚠️ DOM-LED-001 §VIII specifies `amount_cents` only |
| `amount_cents` | Integer signed | NOT NULL | ✅ |
| `account_type` | String(20) | — | ⚠️ Not in domain contract — checking/savings split violates domain-blindness |
| `status` | Enum(PENDING\|POSTED\|VOID) | NOT NULL | ✅ |
| `correlation_id` | String(100) | NOT NULL | ✅ INV-LED-004 |
| `feat_code` | String(100) | nullable | ⚠️ Application-layer annotation; not in domain contract |
| `idempotency_key` | String(100) | **nullable** | ❌ DOM-LED-001 §VIII requires NOT NULL |
| `is_void` | Boolean | — | ❌ Redundant with `status = VOID` — dual state encoding |
| `policy_id` | FK → insurance_policies | nullable | ❌ INV-LED-010 — business meaning on ledger row |
| `type` | String(50) | nullable | ❌ INV-LED-010 — encodes business meaning (`insurance_reimbursement`, `rent_payment`, etc.) instead of operational provenance |
| `original_transaction_id` | Integer | nullable | ✅ INV-LED-003 reversal link |

**Critical divergences from DOM-LED-001 §VIII:**
1. Table name: `transaction` vs target `ledger_transaction`
2. `join_code` is stored — INV-LED-001 explicitly says Ledger does not own it
3. `account_type` (checking/savings split) is not in the domain contract
4. `is_void` is redundant with `status = VOID`
5. `policy_id` FK encodes insurance business meaning on a domain-blind table
6. `type` encodes business meaning; domain contract uses `category: SYSTEM | MANUAL | ADJUSTMENT`
7. `idempotency_key` nullable — contract requires NOT NULL
8. `class_id` nullable — required NOT NULL for the idempotency partial index to function correctly
9. `teacher_id` present — domain-blind design prohibits this

**Action:** Deferred bulk normalization. Immediate: make `class_id` NOT NULL; make
`idempotency_key` NOT NULL; drop `is_void` (redundant). Flag `policy_id` and `type` for
eventual removal. Full rename and schema rebuild tracked in `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`.

---

#### `balance_cache` (domain target name: `ledger_balance_snapshot`) — DIVERGENT

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | ❌ DOM-LED-001 §VIII.2: `seat_id` should be the PK |
| `seat_id` | FK → seats | NOT NULL | ✅ INV-LED-001 |
| `class_id` | FK → class_economies | NOT NULL | ✅ |
| `student_id` | FK → students | nullable | ❌ deprecated bridge |
| `join_code` | String(20) | nullable | ❌ INV-LED-001: Ledger does not own `join_code` |
| `posted_checking_balance_cents` | Integer | NOT NULL | ⚠️ Domain contract is account-type agnostic; specifies single `posted_balance_cents` |
| `posted_savings_balance_cents` | Integer | NOT NULL | ⚠️ Same |
| `last_settlement_at` | DateTime(tz) | nullable | |

**Divergences from DOM-LED-001 §VIII.2:**
1. Table name: `balance_cache` vs target `ledger_balance_snapshot`
2. PK: integer `id` vs `seat_id` as direct PK per spec
3. Two account-type balance fields vs single `posted_balance_cents`
4. Missing `last_event_id` FK to `ledger_transaction`

**Action:** Drop `student_id`; drop `join_code` per backwards compat cleanup. Full rebuild
tracked in `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`.

---

### Domain: Attendance (DOM-ATT-001)

**INV-ATT-010:** At most one active tap event per `seat_id` — atomic single-active guard.

---

#### `tap_events` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `student_id` | FK → students | NOT NULL | ❌ Should be `seat_id` per DOM-ATT-001 §VII.1 |
| `seat_id` | FK → seats | **nullable** | ❌ DOM-ATT-001 requires `seat_id` as anchor |
| `period` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 — label; not a scoping authority |
| `class_id` | FK → class_economies | **nullable** | ❌ INV-CORE-000 §1 — must be NOT NULL |
| `join_code` | String(20) | nullable | ⚠️ DOM-ATT-001 §VII.1 requires `join_code` on each row |
| `status` | String(10) | NOT NULL | `active` \| `inactive` ✅ |
| `timestamp` | DateTime(tz) | NOT NULL | ✅ |
| `reason_code` | Enum | nullable | ✅ |
| `is_deleted` / `deleted_at` / `deleted_by` | mixed | nullable | ❌ DOM-ATT-001: "completed tap history must not be silently erased" |

**Violations:** Authority is inverted — `student_id` NOT NULL while `seat_id` nullable.
Soft-delete fields (`is_deleted`, `deleted_at`, `deleted_by`) imply deletability of
attendance history; DOM-ATT-001 prohibits silent erasure.

**Action:** Make `seat_id` NOT NULL, `class_id` NOT NULL; deprecate `student_id`. Remove
soft-delete fields (if deletion is needed, emit a compensating event per domain spec).

---

#### `student_blocks` (domain target: `seat_attendance_state` + `entitlement_events`) — DIVERGENT

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `student_id` | FK → students | NOT NULL | ❌ Should be `seat_id` |
| `seat_id` | FK → seats | **nullable** | ❌ |
| `period` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 — label as uniqueness key |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | nullable | |
| `tap_enabled` | Boolean | NOT NULL | → `seat_attendance_state` (DOM-ATT-001) |
| `done_for_day_date` | Date | nullable | → `seat_attendance_state` (DOM-ATT-001) |
| `rent_hall_passes` | Integer | NOT NULL | → `entitlement_events` stream (DOM-OBL-001) |

**Constraint violations:**
- `uq_student_blocks_student_period (student_id, period)` — period is a label per
  INV-CORE-000 §6; unique constraint on a label is prohibited
- `uq_student_blocks_seat_period (seat_id, period)` — same violation

**Design note:** Per `V2_STUDENT_BLOCKS_REDESIGN_NOTE.md`, this table is architecturally
condemned. It mixes two domains: `tap_enabled` + `done_for_day_date` belong in
`seat_attendance_state` (DOM-ATT-001); `rent_hall_passes` belongs in `entitlement_events`
(DOM-OBL-001).

**Action:** Interim — make `seat_id` NOT NULL, `class_id` NOT NULL. Full split into
`seat_attendance_state` + `entitlement_events` deferred per the redesign note.

---

#### `hall_pass_logs` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | Integer PK | NOT NULL | |
| `student_id` | FK → students | NOT NULL | ❌ Should be `seat_id` |
| `seat_id` | FK → seats | **nullable** | ❌ DOM-ATT-001 §VII.2 requires `seat_id` |
| `period` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | nullable | ⚠️ DOM-ATT-001 requires it |
| `status` | String | NOT NULL | `pending`\|`approved`\|`rejected`\|`left`\|`returned` ✅ |
| `request_time` / `decision_time` / `left_time` / `return_time` | DateTime | mixed | ✅ |

**Action:** Make `seat_id` NOT NULL, `class_id` NOT NULL; deprecate `student_id`.

---

#### `seat_attendance_state` — MISSING

DOM-ATT-001 §VI.3 declares this table authoritative for per-seat mutable attendance gate
state. Does not exist.

Required fields: `seat_id` (UNIQUE FK), `join_code`, `tap_enabled`, `done_for_day_date`,
`created_at`/`updated_at`.

Currently covered by `student_blocks` (mixed with obligation state).

---

### Domain: Class Configuration (DOM-CLASS-001)

**Domain rule:** One record per class. `class_id` is the scope authority. No `teacher_id`
scoping — *"The class (`class_id`) is the scope boundary, not the teacher."*

---

| Table | `class_id` nullable | `teacher_id` present | Key violations | Status |
|---|---|---|---|---|
| `class_features` | NOT NULL ✅ | No | CHECK on `feature_name` ✅; existence = enabled ✅ | **COMPLIANT** |
| `feature_settings` | NOT NULL unique ✅ | Yes | Unique constraint on `(teacher_id, join_code, block)` — wrong authority; DOM-CLASS-001 §VII.2 requires uniqueness on `class_id` alone | **DIVERGENT** |
| `hall_pass_settings` | NOT NULL unique ✅ | Yes | `teacher_id` on record; DOM-CLASS-001 prohibits teacher scoping | **TRANSITIONAL** |
| `rent_settings` | **nullable** ❌ | Yes | `class_id` nullable; `teacher_id` on record | **TRANSITIONAL** |
| `payroll_settings` | **nullable** ❌ | Yes | `class_id` nullable; `teacher_id` on record | **TRANSITIONAL** |
| `payroll_rewards` | **nullable** ❌ | Yes | `class_id` nullable | **TRANSITIONAL** |
| `payroll_fines` | **nullable** ❌ | Yes | `class_id` nullable | **TRANSITIONAL** |
| `banking_settings` | **nullable** ❌ | Yes | `class_id` nullable; `block` label on record | **TRANSITIONAL** |
| `payroll_cache` | NOT NULL unique ✅ | Yes | `teacher_id` redundant but harmless | **COMPLIANT** |

`feature_settings` uniqueness issue: current constraint is `(teacher_id, join_code, block)`.
DOM-CLASS-001 §VII.2 requires uniqueness on `class_id` alone (one record per class).

**Action:** Make `class_id` NOT NULL on `rent_settings`, `payroll_settings`,
`payroll_rewards`, `payroll_fines`, `banking_settings`. Fix `feature_settings` unique
constraint to `(class_id)`. `teacher_id` columns on settings tables should be removed once
class ownership is derivable via `class_economies.teacher_id`.

---

### Domain: Obligations (DOM-OBL-001)

**INV-OBL-001:** All obligation state anchored to `seat_id`. Debts do not follow a student
across classes.

---

#### `obligation_assessment` / `obligation_satisfaction` / `obligation_reversal` / `entitlement_events` — MISSING

DOM-OBL-001 v2.1 (2026-04-22) declares these as the authoritative obligation event tables.
None exist in the current schema.

Currently covered by `rent_payments` (satisfaction), `rent_waivers` (waiver),
`student_blocks.rent_hall_passes` (entitlement quota — scalar, not event stream).

---

#### `rent_payments` (domain target: `obligation_satisfaction`) — DEPRECATED

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `seat_id` | FK → seats | NOT NULL | ✅ |
| `class_id` | FK → class_economies | NOT NULL | ✅ |
| `student_id` | FK → students | nullable | ❌ deprecated bridge |
| `period` | String(10) | NOT NULL | ❌ INV-CORE-000 §6 label |
| `join_code` | String(20) | nullable | |
| `period_month` / `period_year` | Integer | NOT NULL | |
| `payment_date` / `coverage_month` / `coverage_year` | mixed | NOT NULL | |
| `was_late` / `late_fee_charged` | Boolean | NOT NULL | |

Maps to `obligation_satisfaction` in DOM-OBL-001. Not claimed by any declared domain.
`period` as uniqueness key violates INV-CORE-000 §6; temporal scoping should use
`period_key` per INV-OBL-007.

**Action:** Drop `student_id` writes per backwards compat cleanup. Deprecate in favor of
`obligation_satisfaction` post-launch.

---

#### `rent_waivers` (domain target: `obligation_satisfaction` method=WAIVER) — DEPRECATED

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `student_id` | FK → students | NOT NULL | ❌ Anchor should be `seat_id` |
| `seat_id` | FK → seats | **nullable** | ❌ |
| `join_code` | String(20) | nullable | |
| `class_id` | **absent** | — | ❌ No `class_id` column at all |
| `created_by_teacher_id` | FK → teachers | nullable | |

**Critical:** No `class_id` column; `student_id` is the anchor.

**Action:** Add `class_id` NOT NULL; make `seat_id` NOT NULL. Superseded by
`obligation_satisfaction` (method=WAIVER) post-launch.

---

#### `rent_items` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `rent_setting_id` | FK → rent_settings | NOT NULL | |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | nullable | |
| `store_item_id` | FK → store_items | nullable | cross-domain link |

**Action:** Make `class_id` NOT NULL.

---

#### `insurance_enrollments` (currently `student_insurance`) — DIVERGENT

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `seat_id` | FK → seats | NOT NULL | ✅ |
| `class_id` | FK → class_economies | NOT NULL | ✅ |
| `student_id` | FK → students | nullable | ❌ deprecated |
| `policy_id` | FK → insurance_policies | NOT NULL | |
| `join_code` | String(20) | nullable | |
| `status` | String | NOT NULL | `active`\|`cancelled`\|`suspended`\|`expired` |
| `frozen_policy_*` | multiple | mixed | ✅ policy snapshot per INV-OBL-009 |

**Critical:** Event listener `_sync_student_insurance_scope()` auto-creates synthetic
`ClassEconomy` records when none is found for a policy's teacher. This is a scope-leakage
violation — `class_economies` rows must only originate from teacher onboarding, not from
insurance event listeners. Replace with hard failure + structured error log per INV-OPS-005.

**Table name divergence:** DOM-OBL-001 §V says `insurance_enrollments`.

**Action:** Remove synthetic `ClassEconomy` creation from event listener. Drop `student_id`.
Table rename deferred.

---

#### `insurance_claims` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `seat_id` | FK → seats | **nullable** | ❌ DOM-OBL-001 requires seat anchor |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `student_id` | FK → students | nullable | ❌ deprecated |
| `student_insurance_id` | FK → student_insurance | NOT NULL | |
| `status` | String | NOT NULL | ✅ |

**Action:** Make `seat_id` NOT NULL, `class_id` NOT NULL; drop `student_id`.

---

#### `insurance_policies` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `teacher_id` | FK → teachers | **nullable** | ❌ All policies must have an owning teacher |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | nullable | |
| `policy_code` | String | unique | |
| Tier fields (`tier_category_id`, `tier_name`, `tier_color`, `tier_level`) | mixed | nullable | ⚠️ Design smell — mutual-exclusion logic encoded outside domain |

**Action:** Make `class_id` NOT NULL, `teacher_id` NOT NULL; add `uq (class_id, policy_code)`.

---

#### `insurance_policy_blocks` — DEPRECATED

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `policy_id` | FK | composite PK | |
| `block` | String(10) | composite PK | ❌ INV-CORE-000 §6 — label as PK |
| `class_id` | FK → class_economies | **nullable** | ❌ |

DOM-STORE-001 §VII.2 (which owns visibility patterns) states: *"Per INV-CORE-000 §6,
label-based grouping must not be used for scoping or visibility decisions. Visibility is
expressed per seat, not per label."*

**Action:** Replace with `insurance_policy_visibility (policy_id, seat_id)`. Deferred
post-launch.

---

### Domain: Store (DOM-STORE-001)

---

#### `store_items` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `class_id` | FK → class_economies | **nullable** | ❌ DOM-STORE-001 §VII.1 requires NOT NULL |
| `join_code` | String(20) | nullable | ✅ explicitly required per spec |
| `teacher_id` | FK → teachers | NOT NULL | ⚠️ DOM-STORE-001 does not include `teacher_id`; ownership derives from `class_id` |
| Collective goal fields | multiple | nullable | ✅ |
| `is_rent_linked` | Boolean | NOT NULL | ✅ |

**Action:** Make `class_id` NOT NULL; remove `teacher_id`.

---

#### `store_item_blocks` (domain target: `store_item_visibility (store_item_id, seat_id)`) — DEPRECATED

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `store_item_id` | FK | composite PK | |
| `block` | String(10) | composite PK | ❌ INV-CORE-000 §6 — label as PK |
| `class_id` | FK → class_economies | **nullable** | ❌ |

DOM-STORE-001 §VIII explicitly states no table in the Store domain may use label strings
as scoping or grouping keys.

**Action:** Replace with `store_item_visibility (store_item_id FK, seat_id FK)`.
Deferred post-launch.

---

#### `student_items` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `seat_id` | FK → seats | **nullable** | ❌ DOM-STORE-001 §VII.3 requires `seat_id` as anchor |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | nullable | ✅ per spec |
| `purchase_transaction_id` | FK → transaction | nullable | ✅ cross-domain reference |
| `correlation_id` | String(100) | nullable | ⚠️ DOM-CORE-001 requires `idempotency_key` on all writes |

**Action:** Make `seat_id` NOT NULL, `class_id` NOT NULL.

---

#### `redemption_audit_logs` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `id` | UUID | NOT NULL | ✅ |
| `student_item_id` | FK → student_items | nullable | |
| `teacher_id` | FK → teachers | nullable | ❌ DOM-STORE-001 §VII.4 uses `initiated_by_user_id` FK → users |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `seat_id` | FK → seats | **nullable** | ❌ |
| `join_code` | String(20) | nullable | ✅ |

**Action:** Make `class_id` NOT NULL, `seat_id` NOT NULL; rename `teacher_id` to
`initiated_by_user_id` → `users` when identity is unified.

---

### Domain: Operations (DOM-OPS-001)

DOM-OPS-001 v2.1 (2026-04-22) declares 8 authoritative tables. **None exist in the current
schema.**

---

#### MISSING: `operational_events`, `audit_log`, `invariant_run_events`, `incident_events`, `incident_summary`, `alert_events`, `job_events`, `health_check_events`

Currently covered by transitional tables:

| Current table | Closest target | Gap |
|---|---|---|
| `error_log` | `operational_events` | Flat structure; no `correlation_id`, `domain`, `level`; no `seat_id`/`class_id` per INV-OPS-012 |
| `actor_request_traces` | Correlation input for `ticket_correlation_packs` | `class_id` nullable; missing `correlation_id` NOT NULL |
| `error_events` | `operational_events` | Many nullable fields; lacks required structure per INV-OPS-003 |
| `analytics_alerts` | `alert_events` | Wrong domain ownership; `class_id` nullable; unique constraint uses `join_code` not `class_id` |

**Immediate action:** Make `actor_request_traces.class_id` NOT NULL for class-scoped
requests. Add `correlation_id` NOT NULL to `error_events`.

Full Operations domain implementation is post-launch.

---

### Domain: Interpretation (DOM-ITR-001)

---

#### `analytics_snapshots` / `analytics_events` (targets: `interpretation_snapshots` / `interpretation_annotations`) — DIVERGENT

| Table | Key violations |
|---|---|
| `analytics_snapshots` | `class_id` nullable; scoped by `join_code` not `class_id`; `teacher_id` on record violates INV-ITR-001 (read-only domain); raw metric columns vs JSONB `value_payload` per spec |
| `analytics_events` | `class_id` nullable; table name diverges |

DOM-ITR-001 §IX specifies `interpretation_snapshots` with `class_id` UUID NOT NULL, `axis`
(behavioral\|structural), `cycle_id`, and `value_payload` (JSONB).

**Action:** Make `class_id` NOT NULL on both. Full domain restructure deferred.

---

#### `analytics_alerts` — WRONG DOMAIN OWNERSHIP

DOM-OPS-001 §2 owns alert state (`alert_events`). `analytics_alerts` is currently co-located
with analytics tables but its lifecycle management belongs to Operations.

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `join_code` | String(20) | NOT NULL | |
| Unique constraint | `(alert_key, join_code, window_type, window_start, window_end)` | — | ❌ Should use `class_id` |

**Action:** Make `class_id` NOT NULL; update unique constraint to include `class_id`.
Migrate alert management to Operations domain post-launch.

---

#### `economy_snapshots` — UNCLASSIFIED

Stores CWI/affordability snapshots per class. `class_id` NOT NULL ✅. Not claimed by any
domain spec. Likely belongs to DOM-ITR-001 (structural interpretation) or DOM-CLASS-001.

**Action:** Assign domain ownership.

---

### Domain: Support (DOM-SUP-001)

---

#### `issue_categories` — COMPLIANT

Matches DOM-SUP-001 §VI exactly. Keep.

---

#### `issues` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `seat_id` | FK → seats | **nullable** | ❌ DOM-SUP-001 §VI requires `seat_id` |
| `class_id` | FK → class_economies | **nullable** | ❌ |
| `student_id` | FK → students | NOT NULL | ❌ deprecated; `seat_id` is the anchor |
| `teacher_id` | FK → teachers | NOT NULL | ❌ DOM-SUP-001 uses teacher seat or `created_by_user_id` → users |
| `student_first_name` / `student_last_initial` | String | NOT NULL | ✅ Display-safe cached identity per DOM-SUP-001 §VI |
| `opaque_student_reference` | String | NOT NULL | ✅ HMAC-based; sysadmin-safe |
| `share_class_name_with_sysadmin` | Boolean | NOT NULL | ✅ explicit teacher consent |
| Status machine fields | multiple | mixed | ✅ match DOM-SUP-001 §VIII |

**Note on PII fields:** `student_first_name`/`student_last_initial` are intentionally cached
at submission per DOM-SUP-001 §VI ("display-safe cached identity fields... never updated").
These are not violations. The concern is `student_id` FK (raw identity reference), not the
encrypted name fields.

**Action:** Make `seat_id` NOT NULL, `class_id` NOT NULL; drop `student_id` FK.

---

#### `issue_status_history` / `issue_resolution_actions` / `ticket_correlation_packs` — TRANSITIONAL

| Table | `class_id` | Actor FK | DOM-SUP-001 match |
|---|---|---|---|
| `issue_status_history` | nullable ❌ | `changed_by_id` untyped | `join_code` present ✅ |
| `issue_resolution_actions` | nullable ❌ | `teacher_id` FK | DOM-SUP-001 uses `performed_by_user_id` → users |
| `ticket_correlation_packs` | nullable (SET NULL) ❌ | `actor_opaque_id` ✅ | |

**Action:** Make `class_id` NOT NULL on all three. Update `issue_resolution_actions`
actor FK to `performed_by_user_id` → `users` when identity is unified.

---

#### `user_reports` — TRANSITIONAL

| Column | Type | Nullable | v2 Status |
|---|---|---|---|
| `class_id` | FK → class_economies | **nullable** | ❌ for class-scoped reports |
| `anonymous_code` | String | NOT NULL | ✅ HMAC-based |
| `_student_id` (col: `student_id`) | FK → students | nullable | ✅ hidden from sysadmin per spec |

**Action:** Make `class_id` NOT NULL for class-scoped report types.

---

#### `announcements` — TRANSITIONAL

DOM-SUP-001 §VI uses `created_by_user_id` FK → users. Current model uses separate
`teacher_id` and `system_admin_id` FKs.

| Column | Type | v2 Status |
|---|---|---|
| `class_id` | nullable | ❌ Required NOT NULL for class-scoped audience types |
| `teacher_id` | NOT NULL | ❌ Should unify to `created_by_user_id` → users |
| `target_teacher_id` | nullable | ⚠️ DOM-SUP-001 uses `target_user_id` → users |
| `audience_type` values | ✅ | matches DOM-SUP-001 §VI.7 |

**Action:** Make `class_id` NOT NULL for class-scoped audience types. Unify actor FKs
when identity model is activated.

---

### Recovery (no dedicated domain doc)

#### `recovery_requests` / `student_recovery_codes` — TRANSITIONAL

| Table | Issue |
|---|---|
| `recovery_requests` | `join_code` nullable — acceptable; recovery is teacher-scoped |
| `student_recovery_codes` | No `class_id` column; `join_code` nullable |

**Action:** Add `class_id` FK to `student_recovery_codes` for audit trail integrity.

---

#### `teacher_onboarding` — COMPLIANT

Per-teacher onboarding state. No class scope required. Keep.

---

## V. Cross-Cutting Invariant Violation Summary

### INV-CORE-000 §1 — `class_id` nullable on class-scoped tables

Tables where `class_id` is nullable but must be NOT NULL (33 total):

```
analytics_alerts, analytics_snapshots, analytics_events,
transaction, student_blocks, tap_events, hall_pass_logs,
store_items, store_item_blocks, student_items, redemption_audit_logs,
rent_settings, rent_items, rent_waivers,
insurance_policies, insurance_policy_blocks, student_insurance, insurance_claims,
payroll_settings, payroll_rewards, payroll_fines,
banking_settings, feature_settings,
issues, issue_status_history, issue_resolution_actions, ticket_correlation_packs,
actor_request_traces, error_events, user_reports, announcements,
teacher_blocks, seats, student_recovery_codes
```

---

### INV-CORE-000 §6 — Label fields used as scoping authorities (prohibited)

| Table | Violation |
|---|---|
| `student_blocks` | `period` NOT NULL as uniqueness key |
| `tap_events` | `period` NOT NULL as correlation anchor |
| `hall_pass_logs` | `period` NOT NULL |
| `store_item_blocks` | `block` as composite PK |
| `insurance_policy_blocks` | `block` as composite PK |
| `teacher_blocks` | `block` NOT NULL as index key |
| `banking_settings` | `block` nullable on record |
| `payroll_settings` | `block` nullable on record |
| `seats` | `block_identifier` + `block` on identity record |

---

### INV-CORE-000 §2 — PII / obligation state on wrong table

| Table | Violation |
|---|---|
| `students` | `hall_passes`, `is_rent_enabled`, `insurance_plan`, `insurance_last_paid` — obligation/financial state on identity record |

---

### INV-LED-001 — Financial state anchored to `seat_id`; Ledger does not own `join_code`

| Table | Violation |
|---|---|
| `transaction` | comment says "join_code is source of truth" — INV-LED-001 says isolation inherits from `seat_id`; `join_code` nullable AND stored |
| `balance_cache` | `join_code` stored; `student_id` deprecated bridge |

---

### INV-LED-010 — Domain blindness violated

| Violation | Detail |
|---|---|
| `transaction.type` | Encodes business meaning (`insurance_reimbursement`, `rent_payment`) — prohibited |
| `transaction.policy_id` | Insurance FK directly on a domain-blind ledger row |
| `transaction.account_type` | Product abstraction (checking/savings) not in domain contract |

---

### DOM-CORE-000 §2 — Cross-domain mutation authority

| Violation | Detail |
|---|---|
| `StudentInsurance` event listener | Auto-creates `ClassEconomy` records — insurance domain creating class universe records |

---

## VI. Missing Tables

| Table | Domain | Description |
|---|---|---|
| `seat_attendance_state` | DOM-ATT-001 | Per-seat tap_enabled + done_for_day; replaces those fields from `student_blocks` |
| `obligation_assessment` | DOM-OBL-001 | Immutable debt fact record |
| `obligation_satisfaction` | DOM-OBL-001 | Payment/waiver; replaces `rent_payments` + `rent_waivers` |
| `obligation_reversal` | DOM-OBL-001 | Assessment nullification |
| `entitlement_events` | DOM-OBL-001 | Grant/consumption stream; replaces `student_blocks.rent_hall_passes` |
| `ledger_transaction` (rename) | DOM-LED-001 | Target name for `transaction` |
| `ledger_balance_snapshot` (rebuild) | DOM-LED-001 | Single-seat single-balance cache; replaces `balance_cache` |
| `store_item_visibility` | DOM-STORE-001 | Seat-based visibility; replaces `store_item_blocks` |
| `insurance_policy_visibility` | DOM-OBL-001 | Seat-based visibility; replaces `insurance_policy_blocks` |
| `operational_events` | DOM-OPS-001 | Structured telemetry log |
| `audit_log` | DOM-OPS-001 | High-integrity side-effect record |
| `invariant_run_events` | DOM-OPS-001 | Runtime invariant check trace |
| `incident_events` / `incident_summary` | DOM-OPS-001 | Incident lifecycle |
| `alert_events` | DOM-OPS-001 | Alert lifecycle; `analytics_alerts` is in wrong domain |
| `job_events` | DOM-OPS-001 | Background job trace |
| `health_check_events` | DOM-OPS-001 | Liveness/readiness/correctness |
| `interpretation_snapshots` | DOM-ITR-001 | Replaces `analytics_snapshots` |
| `interpretation_annotations` | DOM-ITR-001 | Replaces `analytics_events` |

---

## VII. Recommended Action Plan

### Tier 1 — Pre-launch schema hardening

Narrowly scoped NOT NULL backfills. Backfill `class_id` from
`join_code → class_economies`, then add constraint + index. These are the highest-risk
gaps for cross-class data leakage.

Priority order:
1. `tap_events.class_id` → NOT NULL
2. `student_blocks.class_id` NOT NULL + `seat_id` NOT NULL
3. `transaction.class_id` NOT NULL (required for idempotency constraint to be enforceable)
4. `issues.class_id` NOT NULL + `seat_id` NOT NULL
5. `transaction.idempotency_key` NOT NULL

---

### Tier 2 — Backwards compatibility cleanup

All items in `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md`. Re-enable after test stabilization
(currently blocked at 123 failing).

Phase 1 (clean breaks):
- Remove `Admin.username` column + validator + legacy fallback
- Remove `Student.has_completed_profile_migration`
- Remove `StudentTeacher.admin_id` synonym
- Remove legacy hall pass routes
- Remove `TeacherBlock.dob_sum` property shim

Phase 2 (comment + constraint cleanup):
- Update `second_half_hash` comment to remove misleading "legacy" label
- Make `Admin.created_at` NOT NULL

---

### Tier 3 — `student_insurance` event listener audit (HIGH — scope leakage)

The `_sync_student_insurance_scope()` event listener auto-creates synthetic `ClassEconomy`
records when none is found for a policy's teacher. This is the only code path that creates
class universe records outside normal teacher onboarding. Replace with hard failure +
structured error log per INV-OPS-005.

---

### Tier 4 — `teacher_blocks` retirement (post-launch)

**Not removable until Job 2 is migrated.** `teacher_blocks` currently serves as both the
pre-claim credential store (Job 1) and the runtime class roster index (Job 2). The second
job has leaked into `_student_scope_subquery_for_join_code()`, payroll's student-list
queries, scheduled task store-item cleanup, and the app factory seeding logic.

Retirement requires:
1. Migrate all `_student_scope_subquery_for_join_code` callers to `class_memberships` or `seats`
2. Migrate payroll student-list queries to `seats`
3. Migrate scheduled tasks
4. Ensure all claim flows write to `seats` at provisioning time

This is the core work of `V2_ADMIN_ROUTE_REFACTOR.md` and
`V2_Class_Scope_Normalization_Target.md`.

---

### Tier 5 — Block/label constraint refactoring (post-launch)

Replace `store_item_blocks` and `insurance_policy_blocks` (block-as-PK tables) with
seat-based visibility tables:
- `store_item_visibility (store_item_id FK, seat_id FK)` per DOM-STORE-001 §VII.2
- `insurance_policy_visibility (policy_id FK, seat_id FK)` per DOM-OBL-001

---

### Tier 6 — `student_blocks` retirement (post-launch)

Split per `V2_STUDENT_BLOCKS_REDESIGN_NOTE.md`:
- `tap_enabled` + `done_for_day_date` → `seat_attendance_state` (DOM-ATT-001)
- `rent_hall_passes` → `entitlement_events` stream (DOM-OBL-001)

---

### Tier 7 — Class scope normalization (explicitly deferred)

Full `join_code → class_id` internal scoping migration, session context migration from
`current_join_code` to `current_class_id`, banking ledger rewrite to
`class_id + seat_id + account_type` authority.

Per `V2_Class_Scope_Normalization_Target.md`: *"This is accepted for the port-completion
phase and should not be reworked in-line with launch-critical porting work."*

---

### Tier 8 — Domain rebuild wave (post-launch architecture target)

Sequence: Obligations event tables → Ledger rename + rebuild → Operations domain tables →
Interpretation domain tables → Identity unification (`users`/`seats` activation,
`students`/`teachers` retirement, `teacher_blocks` full removal).

---

## VIII. Compliance Estimate

| Dimension | Score | Notes |
|---|---|---|
| INV-CORE-000 §1 (class isolation) | 40% | 33 tables with nullable `class_id` |
| INV-CORE-000 §2 (minimal PII) | 70% | Obligation state on `students`; acceptable display caches in support |
| INV-CORE-000 §3 (financial traceability) | 75% | Ledger immutability enforced; `join_code` stored in violation of INV-LED-001 |
| INV-CORE-000 §6 (existence-based identity) | 50% | 9 tables use block/period as scoping or uniqueness keys |
| DOM authority separation | 45% | Obligations, Operations, Interpretation domains entirely unimplemented |
| DOM-LED-001 contract | 55% | `seat_id` NOT NULL ✅; `class_id` nullable, domain-blindness violations, table name divergence |
| DOM-IDEN-001 contract | 30% | `users`/`seats` dormant; `students`/`teachers` deprecated by constitution but still active |
| **Overall** | **~55/100** | Core isolation and ledger anchor in place; domain rebuild wave not started |

The revised estimate (down from 75 in the preliminary audit) reflects that the domain
documents define a materially more ambitious target than previously understood. The
Operations, Obligations, and Interpretation domains are entirely unimplemented tables-wise,
and INV-IDEN-001's "no separate students/teachers tables" rule makes the entire
`students` + `teachers` + `student_teachers` stack constitutionally deprecated.

---

## IX. Relationship to Other Tracking Documents

| Document | Relationship |
|---|---|
| `V2_BACKWARDS_COMPATIBILITY_CLEANUP.md` | Specific removal targets for deprecated columns and shims; Tier 2 of this plan |
| `V2_CLASS_ID_INVARIANT_BACKLOG.md` | Tracks the class-lifecycle label cleanup; feeds Tier 5 and 6 |
| `V2_STUDENT_BLOCKS_REDESIGN_NOTE.md` | Design rationale for `student_blocks` split; feeds Tier 6 |
| `V2_Class_Scope_Normalization_Target.md` | Authoritative statement that Tier 7 is deferred post-port |
| `V2_ADMIN_ROUTE_REFACTOR.md` | Required predecessor to `teacher_blocks` retirement (Tier 4) |
| `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md` | Authoritative ledger rebuild plan; feeds Tier 7 + 8 |
| `V2_LAUNCH_READINESS_MATRIX.md` | Current launch readiness state; Tier 1 items are pre-launch |

---

**Last Updated:** 2026-04-25  
**Status:** Informative — no implementation changes implied by this document  
**Next review:** After Tier 1 migrations complete or when a new domain spec is published

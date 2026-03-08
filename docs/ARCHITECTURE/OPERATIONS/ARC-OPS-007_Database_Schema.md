---
# ARC-OPS-007: Database Schema Documentation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|ARC-OPS-007| 1.3 | 2026-03-08 | 1.2 |Constitutional|

## I. Purpose

This document summarizes the current database contract for v2.0 live-test work, with emphasis on class-scoping authority, public identity, and transitional compatibility fields.

## II. Scope

This document covers the runtime-significant models and tables used to enforce class isolation, teacher identity, and core student/admin workflows.

## III. Authority Level
Constitutional. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Core Authority Model

### Class Boundary

- `class_economies.join_code` is the class boundary.
- `class_memberships` is the authority table for membership inside that boundary.
- `student_teachers` remains the teacher-student ownership table, but it is not the class-boundary authority.
- Session class selection is represented by `current_join_code`.

### Transitional Compatibility

The schema still contains compatibility fields and aliases used to ease migration or preserve older call sites. These are transitional and must not be treated as the intended v2 runtime contract.

## VI. Key Tables

### `class_economies`

Represents a class economy keyed by join code.

| Column | Type | Notes |
|---|---|---|
| `join_code` | String(20), PK | Canonical class identifier |
| `display_name` | String(100), nullable | Human-readable class name |
| `status` | Enum(`active`, `archived`) | Archived behavior is not yet fully specified in runtime docs |
| `created_at` / `updated_at` | DateTime | UTC timestamps |
| `created_by_admin_id` | Integer, nullable | FK to `teachers.id`, nullable for historical compatibility |

### `class_memberships`

Represents admin or student membership in a class economy.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | Membership row |
| `join_code` | String(20), FK | FK to `class_economies.join_code` |
| `admin_id` | Integer, nullable | FK to `teachers.id`; used for teacher memberships |
| `student_id` | Integer, nullable | FK to `students.id`; used for student memberships |
| `role` | Enum(`admin`, `student`) | Runtime role |
| `status` | Enum(`active`, `archived`) | Membership status |
| `created_at` / `updated_at` | DateTime | UTC timestamps |

Constraints:
- unique (`join_code`, `admin_id`)
- unique (`join_code`, `student_id`)
- XOR check: exactly one of `admin_id` or `student_id` must be set
- DB-level role/status consistency hardened by migration `a11213ca4afb`

### `teachers`

Teacher/admin accounts.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | Internal primary key |
| `username` | String(80), nullable | Legacy plaintext username; transitional only |
| `username_hash` | String(64), nullable | Hashed auth username |
| `username_lookup_hash` | String(64), nullable | Deterministic login lookup hash |
| `teacher_public_id` | String(120), unique, nullable | Stable public teacher identifier |
| `display_name` | Encrypted string, nullable | Teacher-facing/student-facing display label |
| `hall_pass_verify_token` | String(64), unique, nullable | Older public verification capability token |
| `totp_secret` | String(200) | Encrypted-at-rest TOTP secret |

Runtime note:
- `Admin.public_id` is a SQLAlchemy synonym for `teacher_public_id`.

### `student_teachers`

Teacher ownership linkage for students.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | Link row |
| `student_id` | Integer | FK to `students.id` |
| `teacher_id` | Integer | FK to `teachers.id` |
| `created_at` | DateTime | UTC timestamp |

Runtime note:
- Ownership and class access are related but distinct. Ownership comes from `student_teachers`; class access comes from `class_memberships`.
- `admin_id` still exists as a synonym alias in the ORM for compatibility only.

### `students`

Student record and credential container.

Important fields:
- `id`
- encrypted identity fields
- `dob_sum_hash` and related recovery/claim fields
- transitional legacy columns still present for compatibility

Runtime note:
- Student financial and class-scoped reads must be interpreted through `join_code` and membership context, not the legacy global aggregate assumptions.

### `deletion_requests`

Teacher-originated deletion requests.

Important fields:
- `teacher_id` is the canonical FK
- `admin_id` remains as an ORM synonym alias for compatibility
- `join_code` is present to bind period/class deletions to a tenant boundary

### Class-Scoped Transactional Tables

These tables rely on `join_code` as their class boundary and must not be treated as teacher-global in v2 flows:

- `transactions`
- `tap_events`
- `student_blocks`
- `hall_pass_logs`
- `rent_payments`
- `rent_waivers`
- `student_items`
- `student_insurance`
- `insurance_claims`

Many of these tables also carry transitional fields such as `teacher_id`, `seat_id`, or historical block references. Those fields may remain useful for migration or reporting, but `join_code` is the class-isolation authority for current v2 runtime behavior.

## VII. Migration Notes

- `a11213ca4afb_harden_class_economy_membership_checks.py` hardens `ClassEconomy` / `ClassMembership` enum and check-constraint behavior.
- `e8f1a2b3c4d5_merge_remaining_v2_heads.py` resolves the remaining active v2 migration heads in repo.

## VIII. Current Transitional Fields and Aliases

These remain intentionally present but should not be used to define new v2 behavior:

- `Admin.public_id` -> synonym for `teacher_public_id`
- `StudentTeacher.admin_id` -> synonym for `teacher_id`
- `DeletionRequest.admin_id` -> synonym for `teacher_id`
- `TeacherBlock.dob_sum` compatibility alias for `dob_sum_hash`
- legacy plaintext `username` fields on `teachers` and `system_admins`

## IX. v2 Contract Summary

- `ClassEconomy` + `ClassMembership` define class scope.
- `student_teachers` defines teacher ownership.
- `current_join_code` defines selected class context in session.
- Public teacher identity is `teacher_public_id` / `public_id`, not numeric teacher ID.
- Compatibility aliases remain in schema and ORM, but they are transitional.
## X. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

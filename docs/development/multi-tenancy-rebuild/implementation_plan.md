# Join Code Migration: Refinement Plan (Final)

> [!NOTE]
> Historical planning artifact. The active v2 runtime contract is now tracked on `codex/v2.0`, and current docs no longer treat TeacherBlock fallback as intended runtime behavior.

The primary objective is to transition from `teacher_id` (audit) to a `join_code`-centric model (scoping), establishing `join_code` as the primary identifier for a class economy.

## 1. Governance & Principles
- **Scoping**: `join_code` defines data partitions.
- **Authority**: `ClassMembership` defines authorization.
- **Verify-First Rule**: Any API/route taking a `join_code` must first resolve and verify membership and role.
- **Audit**: `actor_membership_id` is the primary anchor for all state changes.
- **Student Data Privacy**: Any student-facing query over class-scoped tables must include a subject filter keyed to `student_id` unless explicitly designated "class-public" (e.g., current hall pass holders).
- **Observer Privacy**: Observers are restricted to aggregated, non-identifiable statistics.

## 2. Refined Model Specification

### [ClassEconomy](file:///Users/timothychang/Documents/GitHub/classroom-economy/app/models.py) [NEW]
- **PK**: `join_code` (6-char caps/numeric, unique).
- **Collision Policy**: Regenerate on collision at time of creation.
- **Rotation Policy**: `ClassJoinCodeAlias(old_code, current_join_code)` for redirects. **Old codes are NOT joinable**. Required to either (a) backfill all FK-scoped tables to the new code at rotation time, or (b) keep the old code as a valid PK in `class_economies` (mark non-joinable) and use the alias purely for routing.
- **Resolution Order**:
    1. If `join_code` matches `ClassJoinCodeAlias.old_code`, resolve to `current_join_code`.
    2. Verify `ClassMembership` on `current_join_code`.
    3. Treat `old_code` as invalid for joining or membership lookups.
- **Fields**: `status` (active/archived), `created_by_admin_id`, `archived_at`. Archived economies block mutation routes but MUST remain read-only accessible to members.

### [ClassMembership](file:///Users/timothychang/Documents/GitHub/classroom-economy/app/models.py) [NEW]
- **Status**: 'active', 'revoked', 'pending' (reserved).
- **Role Consistency**:
    - `admin_id` set -> `role IN ('admin', 'observer')`.
    - `student_id` set -> `role IN ('student')`.
- **Database Invariants**:
    - XOR: `(admin_id IS NOT NULL) != (student_id IS NOT NULL)` enforced by `CHECK` constraint.
    - Role Consistency enforced by `CHECK` constraint: `(admin_id IS NOT NULL AND role IN ('admin', 'observer')) OR (student_id IS NOT NULL AND role = 'student')`.
    - Uniqueness: Exactly one ClassMembership per `(join_code, admin_id)` OR `(join_code, student_id)`.

## 3. Operations & Audit
| Model | Scoping Field | Audit Anchor (Who) | Subject (Whom) |
| :--- | :--- | :--- | :--- |
| **Transaction** | `join_code` | `actor_membership_id` | `affected_student_id` |
| **Settings** | `join_code` | `actor_membership_id` | N/A |

### [Row Level Security: Student "Subject Filter"]
Students are limited to rows where:
- `affected_student_id == current_student_id` (transactions, insurance, logs).
- They have an `active` membership for the associated `join_code`.

### ["All Sections" Fan-Out Semantics]
"Apply to all sections" MUST explicitly fan-out across all active `join_code` values owned by the teacher. There are no "global" unscoped records. Implementations must iterate over concrete owned join codes.

## 4. Migration & Rollout Strategy
### Phase A (Auth Gate) - CURRENT
- Implement models and backfill.
- Gate every endpoint: `check_membership(user, join_code)`.

### Phase B (Query Inversion)
- Replace filtering logic `(teacher_id, block)` with `join_code` table-by-table.

### Backfill Safeties
- Infer admin membership only if actor is confirmed Admin and no conflict exists.
- **Conflict Definition**:
    - `join_code` in `TeacherBlock` is linked to a different `teacher_id` (single-owner).
    - Inferred admin already exists as a student membership for the same `join_code`.
    - Multiple distinct admins inferred from transactions for the same `join_code` with none in `TeacherBlock`.
- The migration script MUST include a `validate_backfill_safety()` pre-flight function that detects and reports these conflicts before mutating data.

### TeacherBlock Fallback Deprecation
- Historical planning note only. Current v2 live-test docs assume no TeacherBlock fallback as intended runtime behavior.

## 5. Class Deletion Architecture

- **Canonical Deletion**: All destructive paths MUST use a single primitive `collapse_universe(join_code, reason, actor_membership_id)` inside a single DB transaction.
- **Strict Scope**: A deleted `join_code` MUST leave zero remaining rows in any table scoped by that `join_code`. There is no soft delete and no archived financial history.
- **Cascade Enforcement**: High-risk tables (BalanceCache, Transaction, StudentBlock, TapEvent, RentPayment) MUST use `ON DELETE CASCADE` foreign keys referencing `join_code`.
- **Student Erasure**: If a student has zero remaining memberships (or TeacherBlocks) after collapse, the student account is fully deleted.
- **Guardrails**: Deletion MUST require a destructive warning modal and typed confirmation. Sysadmin and "last student deleted" paths must explicitly trigger `collapse_universe`.

## 6. Performance Requirements (Required Indexes)
- `Transaction(join_code, created_at)`
- `ClassMembership(join_code, status, role)`
- `ClassMembership(admin_id, status)` and `ClassMembership(student_id, status)`
- `ClassJoinCodeAlias(old_code)` UNIQUE

---
> [!IMPORTANT]
> **Anti-Regression Spell**: No access decision may reference `TeacherBlock`, `teacher_id`, or `block`. These are UX and audit artifacts only.

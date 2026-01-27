# Audit Report: Join Code Architecture Compliance (v1.0)

This report documents the results of an automated and manual audit of the Classroom Token Hub codebase against the **Access Matrix** and **Join Code Invariants** defined for the migration.

## 1. Scoping Violations (Missing `join_code`)
The following tables currently lack the required `join_code` field for class-level partitioning. According to the architecture, these models must be scoped to a `join_code` to prevent cross-class data pollution.

| Table Name | Current Filter Source | Status | Risk Level |
| :--- | :--- | :--- | :--- |
| `StoreItem` | `teacher_id` | **VIOLATION** | HIGH |
| `PayrollReward` | `teacher_id` | **VIOLATION** | MEDIUM |
| `PayrollFine` | `teacher_id` | **VIOLATION** | MEDIUM |
| `TeacherOnboarding` | `teacher_id` | **VIOLATION** | LOW |
| `DeletionRequest` | `admin_id`, `period` | **VIOLATION** | MEDIUM |
| `StudentItem` | `store_item_id` | **LINKED** | MEDIUM (Requires join to StoreItem) |
| `InsurancePolicy` | `teacher_id` | **VIOLATION** | HIGH |

> [!IMPORTANT]
> **StoreItem** is a critical failure. If a teacher manages two classes, one student could potentially buy an item from the "wrong" class if they guess the ID, as current filtering is too broad.

---

## 2. Authority Violations (Legacy Metadata Usage)
The "Anti-Regression Spell" prohibits using `teacher_id` or `TeacherBlock` for authorization or primary data filtering. The following logic points violate this rule:

### [VIOLATION] `app/routes/api.py`
- **Line 206 (purchase_item)**: `StoreItem.query.filter_by(id=item_id, teacher_id=teacher_id)`
  *   **Issue**: Uses `teacher_id` to verify item ownership. Must use `join_code`.
- **Line 1233 (register_hall_pass)**: `HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None)`
  *   **Issue**: Authority derived from `teacher_id`. Must resolve via `ClassMembership`.

### [VIOLATION] `app/routes/student.py`
- **Line 138 (get_rent_settings_for_context)**: `RentSettings.query.filter_by(teacher_id=teacher_id).first()`
  *   **Issue**: Falls back to `teacher_id` if block is missing/mismatched. 
- **Line 196 (get_feature_settings_for_student)**: `FeatureSettings.query.filter_by(teacher_id=teacher_id, block=None)`
  *   **Issue**: Global fallback uses `teacher_id`.

---

## 3. Data Leakage (Privacy & Partition Failures)
These areas allow data to "leak" across the `join_code` boundary or violate the "Subject Filter" for students.

### Announcement Creep
`app/routes/student.py:1227`
- The dashboard query includes `Announcement.audience_type == 'teacher_all_classes'`.
- **Leak**: Allows an announcement meant for a teacher's "High School Physics" class to appear for their "7th Grade Math" class students.

### Hall Pass Snooping
`app/routes/api.py:775`
- `get_active_hall_passes` accepts an optional `teacher_id` param.
- **Leak**: If omitted, it returns the last 10 hall passes *globally* across the entire application.

### Multi-Class Balance Collision
`app/routes/student.py:228` (`calculate_scoped_balances`)
- **Leak**: This function still includes `(tx.join_code is None and tx.teacher_id == teacher_id)`.
- **Risk**: While intended for migration, it allows legacy transactions to bleed together if a student moves from a teacher's Period 1 to Period 2 without a `join_code` set on those old records.

---

## 4. Audit Policy Failure (Missing Anchors)
The `ClassMembership.id` (`actor_membership_id`) is required for all state changes. 

| Target Action | Current Audit Anchor | Compliance |
| :--- | :--- | :--- |
| Create Transaction | `teacher_id` | **FAIL** (Needs `actor_membership_id`) |
| Approve Hall Pass | N/A | **FAIL** (Needs `actor_membership_id`) |
| Update Settings | `teacher_id` | **FAIL** (Needs `actor_membership_id`) |

---

## Summary Recommendation
1.  **Phase A.1**: Subsurface schema expansion for `StoreItem`, `PayrollSettings`, and `InsurancePolicy` to include `join_code`.
2.  **Phase A.2**: Implementation of `check_membership(user, join_code)` decorator and its systemic application to all `api` and `student` routes.
3.  **Phase B.1**: Rewrite `get_current_class_context` to prioritize the "Active Economy" and throw errors on "Teacher-Only" lookups.

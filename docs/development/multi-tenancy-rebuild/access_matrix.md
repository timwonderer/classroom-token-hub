# Invariant + Access Matrix (vFinal)

This matrix defines the authoritative rules for access control and data integrity in the `join_code` architecture.

## 1. Membership Invariants
| Rule | Logic | Failure Mode |
| :--- | :--- | :--- |
| **XOR Constraint** | `(admin_id != NULL) XOR (student_id != NULL)` | Data corruption / Auth leak |
| **Role Consistency** | Admin -> ['admin','observer']; Student -> ['student'] | Semantic "cursed" data |
| **User Uniqueness** | Exactly one ClassMembership per `(join_code, admin_id)` OR `(join_code, student_id)`. | Duplicate authority rows |

## 2. Access Control Matrix

| Action Type | Role: Admin | Role: Observer | Role: Student | Economy: Active | Economy: Archived |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **View Ledger** | ALLOW | ALLOW (Stats*) | ALLOW (Subject**) | ALLOW | ALLOW (Read-only) |
| **Issue Fine/Bonus**| ALLOW | DENY | DENY | ALLOW | DENY |
| **Edit Settings** | ALLOW | DENY | DENY | ALLOW | DENY |
| **Void Transaction**| ALLOW | DENY | DENY | ALLOW | DENY |
| **Roster Mgmt** | ALLOW | DENY | DENY | ALLOW | DENY |

### *Observer "Stats" Only
Observers may only view aggregated, non-identifiable statistics. They must never access row-level student records.

### **Define "Subject Filter" (Student Scoping)
Students can ONLY see rows where:
1. `affected_student_id == session.user_id` (Transactions, Insurance, Logs, Tickets).
2. `join_code` matches an `active` student membership.
3. EXCEPTION: Explicitly designated "class-public" data (e.g. current hall pass holders).

## 3. State Predicates
- **Read Access** = `Active Membership` AND `Economy in [Active, Archived]` AND `Role Permits View`
- **Write Access** = `Active Membership` AND `Economy == Active` AND `Role == 'admin'`
- **Audit Anchor** = `actor_membership_id` (ClassMembership.id)

---
> [!IMPORTANT]
> **Anti-Regression Spell**: No access decision may reference `TeacherBlock`, `teacher_id`, or `block`. These are UX and audit artifacts only.

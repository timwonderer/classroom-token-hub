# Feature Specification

## Teacher-Student Shadow Identity (Revised with Cross-Universe Enrollment Clarification)

---

## 1. Purpose

Replace demo students with a structurally consistent mechanism that allows teachers to experience the student interface exactly as regular students do.

A teacher-student is a standard student identity with a boolean flag that excludes it from collective goal aggregation and analytics queries. No other behavioral differences exist.

---

## 2. Identity Model Clarification

### 2.1 Platform-Level Identity

Student identities exist at the platform level.

Join codes (universes) isolate economic state, not identity.

An identity may be enrolled in one or more join codes.

Identity existence rule:

- If enrollment\_count > 0 → identity exists
- If enrollment\_count == 0 → identity is permanently deleted

There are no zombie identities without enrollment.

---

## 3. Join Code Scope

Join codes define isolated economic universes.

Each universe maintains independent:

- Ledger
- Payroll
- Rent
- Insurance
- Store
- Economic state

State never leaks between join codes.

Destroying a join code:

- Removes all enrollments tied to that join code
- Deletes all per-universe economic state
- Does NOT delete platform identity unless it was the final enrollment

---

## 4. Teacher-Student (Shadow) Identity

A teacher-student is:

```
is_teacher_shadow = true
```

It is otherwise identical to any regular student.

The flag affects only:

- Collective goal aggregation queries
- Analytics queries

The flag must NOT affect:

- Enrollment
- Authentication
- Ledger
- Payroll
- Insurance
- Rent
- Store
- Deletion logic
- Context switching

---

## 5. Cross-Universe Enrollment Rule (Critical Invariant)

Shadow students are structurally identical to regular students.

Therefore:

A shadow student may enroll in any join code using the same enrollment mechanism as any regular student.

Enrollment eligibility is determined by join code rules only.

Shadow status must NOT restrict enrollment.

This preserves the invariant:

"Shadow student differs from regular student only in aggregation visibility."

---

## 6. Teacher Account Distinction

Teacher accounts are not enrollable identities.

Teacher accounts:

- Create join codes
- Own universes
- Cannot enroll in join codes
- Cannot traverse universes as teachers

Shadow students:

- Are enrollable identities
- Have no administrative privileges
- Have no elevated access
- Do not inherit teacher permissions

Teacher account and shadow student account are strictly separate identities.

---

## 7. Provisioning Rules

When a teacher creates their first join code:

- A shadow student identity is created if one does not already exist
- The shadow student is enrolled in that join code

When additional join codes are created:

- The same shadow student identity is enrolled in the new join code

Provisioning must be atomic with join code creation.

---

## 8. Authentication & Context Separation

Teacher context and student context are strictly separated.

Teacher login route → teacher permissions only Student login route → student permissions only

Shadow student login:

- Has no teacher privileges
- Has no override capability
- Has no elevated access

Session payload in student context must not contain teacher permissions.

---

## 9. Analytics & Collective Goal Exclusion

Shadow students must be excluded at query level using:

```
WHERE is_teacher_shadow = false
```

Shadow students remain included in:

- Ledger totals
- Payroll operations
- Economic state
- Audit logs

Removing the flag must only:

- Increase collective counts by +1
- Add visible activity in analytics

No other system behavior may change.

---

## 10. Structural Guarantees

For each teacher:

- Exactly one shadow student identity exists

For each join code:

- One teacher owner
- Zero or more regular students
- Shadow student enrollment (if teacher exists)

For each student identity:

- Existence requires at least one enrollment

---

## 11. Non-Goals

- No preview mode
- No alternate student lifecycle
- No enrollment restriction based on shadow status
- No privilege inheritance
- No special-case identity rules

---

## 12. Core Invariant Summary

1. Identity is platform-level.
2. State is join-code scoped.
3. Enrollment attaches identity to state.
4. Existence requires enrollment.
5. Shadow flag affects aggregation only.
6. Teacher accounts are not enrollable identities.

This preserves a single, uniform student lifecycle across the entire system.

---

## 13. Shadow Flag Scope Across Universes (Clarification)

The `is_teacher_shadow` flag is identity-level, not join-code-level.

Therefore:

- Shadow status applies in every universe in which the identity is enrolled.
- Shadow exclusion from analytics and collective goals is global and unconditional.
- The flag does not change behavior based on which teacher owns the join code.

Even if a shadow student enrolls in another teacher’s universe, the exclusion still applies.

Rationale:

1. The flag represents measurement exclusion, not ownership relationship.
2. Conditional exclusion based on teacher ownership would introduce asymmetric aggregation logic.
3. Aggregation behavior must remain deterministic and identity-driven, not context-driven.

If shadow participation in another teacher’s analytics is ever desired, that must be implemented via an explicit, separate feature—not by dynamically ignoring the flag.

Core Rule:

Shadow status is global. Aggregation exclusion is identity-based, not universe-owner-based.

---

## 14. Shadow Identity Constraints (Operational Restrictions)

Although a shadow student follows the standard student lifecycle, it has the following additional restrictions:

1. Immutable Identity Fields

   - First Name: CANNOT be changed
   - Last Name: CANNOT be changed
   - Date of Birth: CANNOT be changed

   Rationale: Shadow claim across new join codes depends on consistent hashed identity values. Allowing mutation would break deterministic seat-claim behavior.

2. Deletion Restriction

   - Shadow student cannot be manually deleted.
   - Shadow student is deleted only when enrollment\_count == 0 (i.e., when all associated join codes are deleted).

3. Visual Distinction

   - Shadow student must display a visible badge (e.g., "Teacher-Shadow") in roster and student views.
   - Badge is informational only and does not imply additional permissions.

These constraints preserve identity consistency while maintaining a single unified student lifecycle.


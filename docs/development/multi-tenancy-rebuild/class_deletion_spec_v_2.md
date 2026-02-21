# CLASS DELETION SPECIFICATION (v2.0)

**Status:** Authoritative\
**Scope:** All deletion paths affecting `join_code`\
**Philosophy:** No join\_code = no data

---

## 1. Ontology

### 1.1 Canonical Universe Boundary

`join_code` defines a class universe.

All data with a `join_code` value belongs exclusively to that universe.

If a `join_code` is deleted, the universe ceases to exist.

---

### 1.2 Destruction Principle

> A deleted join\_code MUST leave zero remaining rows in any table scoped by that join\_code.

There is no soft delete.\
There is no archive state.\
There is no preserved financial history.

Universe collapse is total.

---

## 2. Canonical Destruction Primitive

All destructive paths MUST call:

```
collapse_universe(join_code: str, reason: str, actor_membership_id: int | None)
```

No route may manually delete `TeacherBlock` or any join\_code-scoped data directly.

---

## 3. Atomicity Requirements

### 3.1 Transaction Boundary

`collapse_universe` MUST:

- Execute inside a single database transaction.
- Either fully succeed or fully rollback.
- Leave no partial deletion state.

---

### 3.2 Idempotency

If `join_code` does not exist:

- Function returns success.
- No error.
- No side effects.

---

## 4. Deletion Scope

The following tables MUST be fully deleted for the given join\_code:

### 4.1 Core Financial / Ledger

- Transaction
- BalanceCache
- RentPayment
- StudentInsurance
- InsuranceClaim
- StudentItem
- RedemptionAuditLog

### 4.2 Activity Logs

- TapEvent
- HallPassLog
- AnalyticsEvent
- AnalyticsSnapshot
- Issue
- IssueResolutionAction

### 4.3 State Tables

- StudentBlock
- TeacherBlock (for this join\_code)
- Announcement (teacher\_id + join\_code)

### 4.4 Visibility / Store

- StoreItemBlock entries referencing this join\_code
- StoreItem rows ONLY if no remaining visibility entries exist

---

## 5. Student Erasure Rule

After join\_code collapse:

For each affected student:

If the student has zero remaining ClassMembership or TeacherBlock rows:

- Delete Student
- Delete StudentTeacher bridge rows

This ensures:

> A student exists in the CTH universe only if enrolled in at least one active join\_code.

---

## 6. Settings Cleanup

Block-name–scoped settings MUST be evaluated after collapse.

For each deleted block label:

If no remaining TeacherBlock exists for that block name for the teacher:

Delete:

- PayrollSettings (teacher\_id + block)
- RentSettings (teacher\_id + block)
- InsurancePolicyBlock (if block-scoped)
- StoreItemBlock entries tied to that block

This prevents ghost class badges.

---

## 7. Trigger Conditions

Universe collapse MUST occur under the following conditions:

### 7.1 Teacher-Initiated Deletion

Route: `/admin/join-code/delete`

### 7.2 Legacy Block Wrapper

Route: `/admin/students/delete-block`

### 7.3 Sysadmin Period Deletion

Route: `/sysadmin/delete-period/<admin_id>/<period>`

→ MUST resolve period → join\_code → call collapse\_universe

### 7.4 Teacher Account Deletion

Route: `/sysadmin/manage-teachers/delete/<admin_id>`

→ MUST:

- Identify all join\_codes owned by teacher
- Collapse each join\_code
- Then delete teacher settings + Admin row

### 7.5 Last Student Deletion

If deleting a student results in zero students in a join\_code:

- Trigger collapse\_universe
- Requires explicit confirmation

---

## 8. UI Confirmation Requirements

Any action that will result in universe collapse MUST:

- Display a destructive warning modal.
- Explicitly list:
  - Transactions
  - Balances
  - Attendance
  - Hall passes
  - Store purchases
- Require typed confirmation: `DELETE CLASS <BLOCK_NAME>`

Deleting the last student MUST display the same modal.

Sysadmin deletion MUST display an equivalent warning.

---

## 9. Post-Deletion Verification

After collapse, system SHOULD log verification metrics:

For each core join\_code-scoped table:

```
SELECT COUNT(*) WHERE join_code = ?
```

All counts MUST equal zero.

If not zero:

- Log error
- Abort transaction
- Raise alert

---

## 10. Database Integrity Enforcement (Phase 2 Hardening)

The following tables MUST have:

```
FOREIGN KEY (join_code)
REFERENCES ClassEconomy(join_code)
ON DELETE CASCADE
```

Priority order:

1. BalanceCache
2. Transaction
3. StudentBlock
4. TapEvent
5. RentPayment

This converts application-level deletion into DB-enforced annihilation.

---

## 11. Prohibited Patterns

The following are explicitly forbidden:

- Deleting TeacherBlock without collapsing join\_code.
- Deleting Admin row without collapsing owned join\_codes first.
- Using legacy `Student.block` as authoritative source.
- Preserving join\_code-scoped financial history after class deletion.
- Background cleanup scripts as primary enforcement mechanism.

---

## 12. Monitoring

Optional integrity audit job MAY:

- Scan for orphaned join\_code rows.
- Log anomalies.
- MUST NOT auto-delete silently.

If anomalies exist, collapse primitive is considered broken.

---

## 13. Legal & Privacy Alignment

Data retention principle:

- Data exists only while class universe exists.
- Teacher inactivity > 6 months triggers collapse of all join\_codes and deletion of teacher account.
- No archival retention.

---

## 14. Definition of Done

Deletion system is considered hardened when:

- All routes call collapse\_universe
- BalanceCache orphan bug fixed
- Sysadmin soft delete removed
- FK constraints added for high-risk tables
- Ghost class badge reproduction test passes

---

End of Specification.


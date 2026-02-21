# Multi-Tenancy Rebuild — Audit Concerns & Gaps

**Date:** 2026-02-20
**Branch audited:** `join-code-centric-architecture-rebuild`
**Audit scope:** Implementation plan, access matrix, migration scripts, route code, models

---

## Summary Table

| Priority | Issue | Effort |
|---|---|---|
| **P0** | Add DB CHECK constraints to ClassMembership | Small (one migration) |
| **P0** | Write production migration runbook | Small (doc + staging rehearsal) |
| **P1** | Define "all sections" semantics per operation | Medium (spec + implementation) |
| **P1** | Fix join_code rotation to backfill FK-scoped tables | Medium |
| **P1** | Add backfill conflict detection to migration script | Small |
| **P1** | Finish teacher_id → join_code sweep in read paths | Medium |
| **P2** | Fix archived economy to be read-only, not blocked | Small |
| **P2** | Harden `actor_membership_id = None` paths | Small |
| **P2** | Gate TeacherBlock fallback with feature flag | Small |
| **P2** | Document/test StoreItem null join_code behavior | Small |
| **P3** | Remove/defer Observer role and `pending` status | Small (decision + doc) |
| **P3** | Deprecate global balance properties | Small |
| **P3** | Audit `system_admin.py` for multi-tenancy compliance | Medium |

---

## P0: Database-Level Invariants Missing on ClassMembership

**What's wrong:**
The XOR rule (either `admin_id` or `student_id`, never both, never neither) and the role consistency rule (`admin_id → role IN ('admin','observer')`, `student_id → role = 'student'`) are documented but not enforced at the database level. A malformed insert passes silently and corrupts audit trails.

**What to add** (in a new migration):

```sql
ALTER TABLE class_memberships
  ADD CONSTRAINT ck_membership_xor
    CHECK ((admin_id IS NOT NULL AND student_id IS NULL)
        OR (admin_id IS NULL  AND student_id IS NOT NULL));

ALTER TABLE class_memberships
  ADD CONSTRAINT ck_membership_role_consistency
    CHECK ((admin_id IS NOT NULL AND role IN ('admin', 'observer'))
        OR (student_id IS NOT NULL AND role = 'student'));
```

The summer migration window with acceptable downtime is the right time to add these — they're cheap and prevent silent corruption permanently.

---

## P0: No Production Migration Runbook

**What's wrong:**
`scripts/comprehensive_legacy_migration.py` exists, but there is no step-by-step document for the actual production cutover. The questions that must be answered before summer:

1. When relative to the code deploy does the backfill run? (Before? After? Same deploy?)
2. What is the rollback procedure? (Feature flag back to TeacherBlock? DB restore?)
3. What verification queries confirm the backfill succeeded? (Row counts, conflict checks, spot-checks)

Without this, whoever runs the migration is improvising under pressure. A `docs/operations/V2_PRODUCTION_TRANSITION_RUNBOOK.md` is needed with at minimum:
- Pre-deployment checklist (backup, dry-run in staging)
- Phase 1: code deploy (ClassEconomy/ClassMembership tables exist but empty)
- Phase 2: backfill (run script, verify output)
- Phase 3: enable feature flag (routes check ClassMembership instead of TeacherBlock)
- Phase 4: monitoring window (2 weeks before removing fallback)
- Rollback procedure

---

## P1: "All Sections" Fan-Out Is Semantically Undefined

**What's wrong:**
`implementation_plan.md` defines the principle ("fan-out across owned `join_code` values") but never specifies the actual behavior for individual operations. The issues view has partial fan-out logic but it is inconsistent with other surfaces.

**Unanswered questions per operation:**

| Operation | Unanswered Question |
|---|---|
| Payroll run | Fan out over ClassMembership join_codes or TeacherBlock? Include archived economies? |
| Rent collection | Same join_code set as payroll? Separate? |
| Announcements | One record per join_code, or one record with NULL join_code visible to all? |
| Settings propagation | Which tables (PayrollSettings, RentSettings, BankingSettings, InsurancePolicy)? All at once or configurable? |

**Fix:** Define explicit fan-out rules in `implementation_plan.md` and add per-feature regression tests verifying ALL owned join_codes are affected and unowned ones are not.

---

## P1: Join Code Rotation Breaks FK Constraints

**What's wrong:**
`ClassJoinCodeAlias` is implemented and old codes are blocked from joining. But the spec never addresses what happens to existing data scoped to the old join_code. If a teacher rotates from `ABC123` to `DEF456`, all transactions with `join_code='ABC123'` would violate the FK constraint to `class_economies.join_code`.

**The rotation procedure must either:**
- Backfill all FK-scoped tables (Transaction, TapEvent, RentPayment, StudentBlock, etc.) to the new code at rotation time, or
- Keep the old code as a valid PK in `class_economies` (mark non-joinable) and use the alias purely for routing

Right now neither is implemented, so code rotation is not safe to expose in the UI.

**Required SQL template for safe rotation:**
```sql
-- Create alias
INSERT INTO class_join_code_aliases (old_code, current_join_code, rotated_at)
VALUES ('ABC123', 'DEF456', CURRENT_TIMESTAMP);

-- Backfill all FK-scoped tables
UPDATE transaction    SET join_code = 'DEF456' WHERE join_code = 'ABC123';
UPDATE tap_events     SET join_code = 'DEF456' WHERE join_code = 'ABC123';
UPDATE rent_payments  SET join_code = 'DEF456' WHERE join_code = 'ABC123';
-- ... all other scoped tables ...

-- Update primary key last
UPDATE class_economies SET join_code = 'DEF456' WHERE join_code = 'ABC123';
```

---

## P1: Remaining `teacher_id` as Class Scope Filter in Read Paths

**What's wrong:**
The admin mutation routes are gated, but several read paths still use `teacher_id` without `join_code`, leaking cross-period data for teachers with multiple sections.

| Location | Issue |
|---|---|
| `admin.py:2410` | `RentSettings.query.filter_by(teacher_id=teacher_id, block=current_block)` — no `join_code` |
| `admin.py:1125` | `InsurancePolicy` filtered by `teacher_id` only — returns all periods |
| `admin.py:9804-9823` | RentSettings, InsurancePolicy, PayrollFine in diagnostics/export route, filtered by `teacher_id` only |

**Fix:** Replace `filter_by(teacher_id=...)` with `filter_by(join_code=current_join_code)` on all three paths, and add cross-period isolation tests.

---

## P1: Backfill Conflict Detection Not Implemented

**What's wrong:**
`implementation_plan.md` defines three conflict conditions that should halt or warn during backfill, but the migration script (`comprehensive_legacy_migration.py`) checks none of them:

1. Same `join_code` owned by multiple `teacher_id` values in TeacherBlock
2. Would create an admin membership where a student membership already exists (XOR violation)
3. Multiple distinct admins inferred from transactions with none in TeacherBlock

The script uses `INSERT ... ON CONFLICT DO NOTHING` and `DISTINCT` but picks arbitrarily when multiple teacher_ids exist for the same join_code.

**Fix:** Add a `validate_backfill_safety()` pre-flight function to the migration script that detects and reports each conflict type before modifying any data.

---

## P2: Archived ClassEconomy Blocks All Access Instead of Read-Only

**What's wrong:**
The access matrix says archived economies allow read-only access. The actual code in `check_membership_access()` returns `False` immediately when `economy.status == 'archived'`, blocking all access including reads. This means a teacher who archives a class loses all visibility into it permanently.

**Fix:**
```python
# In check_membership_access():
if economy.status == 'archived':
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        return False, None, economy, "This class is archived and read-only"
    # Allow reads through
```

Add an "Archived" banner to the admin dashboard template for affected economies, and define who (if anyone) can reactivate an archived class.

---

## P2: `actor_membership_id` Can Be None Without Any Warning

**What's wrong:**
Three code paths set `actor_membership_id` conditionally to `None`, silently dropping audit trail coverage:

- `api.py:1040` — `redemption_tx.actor_membership_id = membership.id if membership else None`
- `api.py:1257` — uses a GET param that is not verified against membership
- `admin.py:1248` — `admin_membership_map.get(join_code)` can return `None` for edge cases

A transaction with `actor_membership_id = NULL` is not attributable to any actor, which defeats the purpose of the ledger immutability/audit anchor.

**Fix:** At minimum, log a warning when `actor_membership_id` resolves to `None`. Better: make these paths fail loudly post-auth — if a user passed the membership gate, their membership should always be resolvable.

---

## P2: TeacherBlock Fallback Has No Feature Flag or Removal Timeline

**What's wrong:**
The spec says `TeacherBlock` and `teacher_id` are "UX and audit artifacts only," but there is no removal timeline, no feature flag gating the fallback, and no criteria for when removal becomes safe. Without a flag:
- Cannot measure whether the fallback is still being exercised in production
- Cannot roll back to it quickly post-migration if something breaks
- The "artifacts only" claim is not enforceable

**Minimal fix:**
```python
# Wrap every legacy bootstrap call:
if app.config.get('USE_LEGACY_TB_FALLBACK', True):
    # legacy TeacherBlock path
    current_app.logger.warning("Legacy TB fallback invoked for join_code=%s", join_code)
```

When the log rate reaches zero for two weeks post-migration, removal is safe to schedule.

---

## P2: StoreItem Null Join_Code Is Undocumented Behavior

**What's wrong:**
`student.py:2539` contains:
```python
or_(StoreItem.join_code == None, StoreItem.join_code == join_code)
```

This allows items with no `join_code` to appear in every class period. This may be intentional ("global store items") but it is undocumented, untested, and is the one remaining `join_code IS NULL` read path after the fallback removal sweep.

**Fix:** Either document and test the behavior explicitly ("NULL join_code = global item visible to all periods"), or convert all existing null-join_code items to period-specific and remove the OR clause.

---

## P3: Observer Role and `pending` Status Are Schema-Only, Not Implemented

**Observer role:**
Fully defined in `access_matrix.md` (aggregated stats only, no student PII). In practice:
- No routes implement an observer-only view
- No PII redaction logic exists for the observer path
- An observer membership would hit 403 on every admin view
- Only two generic API endpoints allow `role='observer'` in `allowed_roles`

**Decision required:** Implement (define stats-only endpoint + PII redaction + template branch) or remove the role from schema for v2.0 and defer.

**`pending` ClassMembership status:**
The field exists and the schema allows `'pending'`, but no route creates or processes a pending membership. The approval workflow, use case, and expiry rules are all undefined.

**Decision required:** Define the co-teacher invite flow it presumably enables, or drop the `pending` status from the schema before shipping.

---

## P3: Global Balance Properties Are Dead Code

**What's wrong:**
`Student.checking_balance`, `Student.savings_balance`, and `Student.total_earnings` still exist as model properties that aggregate across ALL transactions for a student (all join_codes). All routes now use `get_checking_balance(join_code=...)` helpers, so these properties are not called from any live path — but they still return incorrect cross-period values if called.

**Fix:** Add a deprecation warning to each property or remove them entirely. The summer migration is the right cleanup window.

---

## P3: `system_admin.py` Routes Unaudited for Multi-Tenancy

**What's wrong:**
The v2 checklist and progress log have no entry for auditing `system_admin.py`. Sysadmin likely has legitimate cross-tenant access (by design), but the following should be explicitly documented:
- Which views are intentionally unscoped (all teachers, all transactions for diagnostics)
- Which should still respect class boundaries (individual student detail)
- Whether sysadmin views redact student PII or expose it

**Fix:** Do a route-by-route audit of `system_admin.py`, document intended access scope for each, and add tests for any boundaries that must be enforced.

---

*Generated from a combined code and spec audit conducted on 2026-02-20.*

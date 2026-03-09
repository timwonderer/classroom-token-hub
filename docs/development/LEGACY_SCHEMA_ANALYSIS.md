# Legacy and Deprecated Database Schema Analysis

**Date:** 2026-03-08  
**Database:** classroom_economy (PostgreSQL)  
**Purpose:** Document deprecated tables and legacy columns for potential cleanup

---

## Executive Summary

This document identifies database structures that are either:
1. **Deprecated** - No longer used by application logic, safe to remove
2. **Legacy** - Marked as legacy in comments but still actively used
3. **Intentional Null** - Nullable by design, not deprecated

---

## 1. Deprecated Tables

### `deletion_requests`

**Status:** ✅ SAFE TO DROP (if confirmed no data needs preservation)

**Current State:**
- Table exists with 0 rows
- Model class exists in `app/models.py` (lines 866-892)
- Only referenced for cleanup in `app/routes/admin.py:674`

**Original Purpose:**
- Store teacher account deletion requests
- Approval workflow for sysadmin-approved deletions

**Why Deprecated:**
The deletion workflow changed from async request/approval to immediate self-service deletion:

```python
# Current implementation in app/routes/admin.py:9564
def deletion_requests():
    """Teacher-managed account deletion.
    
    Deletion executes immediately after timed confirmation gate checks.
    """
    # ... validation logic ...
    _hard_delete_teacher_account_scope(admin_id)
    db.session.delete(admin)
    db.session.commit()
    # No DeletionRequest record created
```

**Cleanup Recommendation:**
1. ✅ Drop table: `DROP TABLE deletion_requests;`
2. ✅ Remove model from `app/models.py`
3. ✅ Remove cleanup reference in `admin.py:674`
4. ✅ Update CHANGELOG.md

---

## 2. Legacy Columns (Still In Use)

### `students.first_half_hash` and `students.second_half_hash`

**Status:** ⚠️ LEGACY BUT ACTIVE - DO NOT REMOVE

**Current State:**
- Both columns are nullable: `character varying | YES`
- Marked as "Legacy/compat hash value" in model comments
- **Actively used in 20+ locations** across codebase

**Purpose:**
- `first_half_hash`: Hash of `FirstInitial + DOBSum` (e.g., "S2025")
- `second_half_hash`: Hash of DOB sum alone (backward compatibility)

**Active Usage:**
- Student claiming flow (`app/routes/student.py:663-691`) - verifying student credentials match roster seat
- Student-initiated account reuse during claim (`app/routes/student.py:709`) - when the same student claims a second class, link to existing account instead of creating a duplicate
- Student matching in roster uploads
- **NOT used for recovery** - recovery uses `reset_code` + `join_code` (see `app/routes/recovery.py`)
- **NOT used for duplicate detection** - that's `dedupe_key` in `teacher_blocks`
- **Security note:** This does not grant teacher-to-teacher lookup or visibility. A teacher can only access students scoped to their own class context.

**Example Usage:**
```python
# app/routes/student.py:706-709
# Use first_half_hash for matching — it stays set even after dob_sum is cleaned up
matched_seat = Seat.query.filter_by(
    first_half_hash=matched_seat.first_half_hash
).first()
```

**Why Still Needed:**
Despite being marked "legacy," these columns serve critical functions:
1. Claim credential verification - matching student input against roster seat during first-time setup
2. Student-initiated account reuse across classes - when the same student claims from a 2nd/3rd teacher, it links their own existing account
3. Persistent identifier - remains set after `dob_sum_hash` is cleared post-claim
4. **Note:** Recovery uses `reset_code` + `join_code`, not these hashes
5. **Note:** Duplicate detection uses `dedupe_key`, not these hashes

**Cleanup Recommendation:**
❌ **DO NOT REMOVE** - Update documentation to reflect active use, remove misleading "legacy" comment

---

## 3. Intentionally Nullable Columns (Not Deprecated)

### `feature_settings.join_code`

**Status:** ✅ WORKING AS DESIGNED

**Current State:**
- Column is nullable by design: `character varying | YES`
- Documented in model docstring (lines 2489-2509)

**Purpose:**
```python
class FeatureSettings(db.Model):
    """
    Per-period/block feature toggle settings for a teacher.
    
    If block is NULL, settings apply as global defaults for the teacher.
    Period-specific settings override global defaults.
    """
    join_code = db.Column(db.String(20), nullable=True, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global defaults
```

**Design Pattern:**
- `join_code = NULL, block = NULL`: Global teacher defaults
- `join_code = 'ABC123', block = 'Period1'`: Period-specific settings

**Cleanup Recommendation:**
✅ **NO ACTION NEEDED** - This is correct implementation

---

## 4. Other Legacy Indicators

### Admin (teachers) table

**Legacy Columns:**
```sql
username character varying(80) | YES  -- Legacy plaintext username (deprecated)
```

**Status:** ⚠️ MIGRATION PATH ACTIVE

**Current State:**
- Column exists for backward compatibility
- Modern system uses:
  - `username_hash` (hashed authentication)
  - `username_lookup_hash` (indexed search)
  - `teacher_public_id` (public display identifier)
  - `public_id` (URL-safe unique identifier)

**Usage:**
- When legacy `username` is set, validator backfills modern fields
- Template updated (2026-03-08) to prefer `teacher_public_id`

**Cleanup Recommendation:**
⏳ **DEFERRED** - Keep for migration compatibility until confirmed all teachers have modern identifiers

---

## Migration Strategy

### Phase 1: Immediate (Low Risk)

1. **Drop `deletion_requests` table**
   ```sql
   DROP TABLE IF EXISTS deletion_requests CASCADE;
   ```

2. **Remove model class**
   - Delete `DeletionRequest`, `DeletionRequestType`, `DeletionRequestStatus` from `app/models.py`
   - Remove import from `app/routes/admin.py:44`
   - Remove cleanup call from `app/routes/admin.py:674`

3. **Update documentation**
   - Remove references from `docs/technical-reference/database_schema.md`
   - Add entry to CHANGELOG.md

### Phase 2: Documentation Fixes (No Schema Changes)

1. **Update misleading comments**
   - `students.first_half_hash`: Remove "Legacy" label, document as "Primary claim hash"
   - `students.second_half_hash`: Update to "Backward-compatible DOB hash"

2. **Verify `feature_settings.join_code = NULL` is documented**
   - Confirm docstring explains global defaults pattern
   - Add examples to schema docs if missing

### Phase 3: Future Consideration (Requires Data Migration)

1. **Phase out `teachers.username`**
   - Audit: Confirm all teachers have `teacher_public_id` populated
   - If confirmed: Create migration to drop column
   - Timeline: 6+ months after audit

---

## Database Commands for Investigation

### Check for data in deletion_requests
```sql
SELECT COUNT(*) FROM deletion_requests;
-- Result: 0 rows (confirmed empty)
```

### Check legacy username usage
```sql
SELECT 
    COUNT(*) AS total,
    COUNT(username) AS legacy_username,
    COUNT(teacher_public_id) AS modern_id
FROM teachers;
```

### Check feature_settings with NULL join_code
```sql
SELECT 
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE join_code IS NULL) AS global_defaults,
    COUNT(*) FILTER (WHERE join_code IS NOT NULL) AS period_specific
FROM feature_settings;
```

---

## Summary Table

| Structure | Status | Action | Priority | Risk |
|-----------|--------|--------|----------|------|
| `deletion_requests` table | Deprecated | Drop | High | Low |
| `DeletionRequest` model | Deprecated | Remove code | High | Low |
| `students.first_half_hash` | Mislabeled as legacy | Update docs | Medium | None |
| `students.second_half_hash` | Mislabeled as legacy | Update docs | Medium | None |
| `feature_settings.join_code` | Intentional NULL | No action | N/A | None |
| `teachers.username` | Migration path | Future cleanup | Low | Medium |

---

## Next Steps

1. **Confirm with stakeholders:**
   - No historical deletion_requests data needs preservation
   - All active teachers have been migrated to modern identifiers

2. **Create migration:**
   ```bash
   flask db migrate -m "Drop deprecated deletion_requests table"
   ```

3. **Clean up code:**
   - Remove model classes
   - Remove imports and references
   - Update documentation

4. **Update CHANGELOG.md:**
   ```markdown
   ### Removed
   - Dropped deprecated `deletion_requests` table (teacher deletion now immediate)
   - Removed `DeletionRequest`, `DeletionRequestType`, `DeletionRequestStatus` models
   ```

---

**Last Updated:** 2026-03-08  
**Reviewed By:** Development Team  
**Status:** Analysis Complete, Awaiting Approval for Phase 1 Cleanup

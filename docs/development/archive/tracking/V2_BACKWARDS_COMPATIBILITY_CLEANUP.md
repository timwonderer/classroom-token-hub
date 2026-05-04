# V2.0 Backwards Compatibility Cleanup Guide

**Date:** 2026-03-08  
**Last Reviewed:** 2026-04-25  
**Branch:** codex/v2.0  
**Context:** Fresh database launch - no legacy data, no v1.x compatibility needed
**Execution Status:** Deferred until current runtime stabilization recovers from full-suite baseline (`619 passed, 123 failed, 1 skipped` as of 2026-04-25)

---

## Executive Summary

Since v2.0 is launching on a **fresh database with zero legacy data**, we can safely remove all backwards compatibility code, legacy fallbacks, and migration shims. This document identifies all such code for cleanup.

**Impact:** Simpler codebase, reduced complexity, no unnecessary fallback paths

**2026-04-25 Note:** This remains the cleanup authority, but broad removals listed below are intentionally deferred while launch-critical stabilization is still in progress.

---

## 1. Admin (Teacher) Model - Legacy Username System

### Current State (REMOVE):

**File:** `app/models.py:2197`
```python
class Admin(db.Model):
    username = db.Column(db.String(80), unique=True, nullable=True)  # Legacy plaintext username (deprecated)
```

**File:** `app/models.py:2235-2251` - Legacy username validator
```python
@validates('username')
def _normalize_legacy_username(self, key, value):
    """Backfill hashed auth fields when legacy plaintext usernames are assigned."""
    # ... 17 lines of backwards compatibility logic
```

**File:** `app/routes/admin.py:254-268` - Legacy username lookup
```python
def _find_admin_by_auth_username(username: str):
    # ...
    # Migration-only fallback for legacy records that have not been hashed yet.
    return Admin.query.filter(
        Admin.username == normalized,
        Admin.username_lookup_hash.is_(None),
        Admin.username_hash.is_(None),
    ).first()
```

### V2.0 Clean State:

**Remove entirely:**
- ❌ `Admin.username` column
- ❌ `@validates('username')` decorator and method
- ❌ Legacy fallback in `_find_admin_by_auth_username()`

**Keep only:**
- ✅ `username_hash` (for secure authentication)
- ✅ `username_lookup_hash` (for indexed lookups)
- ✅ `teacher_public_id` (for display)
- ✅ `public_id` (for URLs)

**Migration:**
```python
# Create migration to drop Admin.username column
flask db migrate -m "Remove legacy username column from teachers table"
```

---

## 2. Student Model - Legacy Hash Labels

### Current State (MISLEADING):

**File:** `app/models.py:354-355`
```python
first_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Hash of "FirstInitial + DOBSum" (e.g., "S2025")
second_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Legacy/compat hash value
```

**Comment says "Legacy/compat"** but these are ACTIVELY USED for:
- Claim verification
- Cross-teacher account linking

### V2.0 Clean State:

**Update comments to remove misleading "legacy" label:**
```python
first_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Claim credential hash (first_initial + dob_sum)
second_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Backward-compatible DOB hash (dob_sum only)
```

**No code removal needed** - columns are actively used

---

## 3. TeacherBlock Model - Legacy DOB Compatibility Shim

### Current State (REMOVE):

**File:** `app/models.py:333-338`
```python
@property
def dob_sum(self):
    """Legacy compatibility shim for older fixture/setup code."""
    return getattr(self, "_legacy_dob_sum", None)

@dob_sum.setter
def dob_sum(self, value):
    self._legacy_dob_sum = value
```

### V2.0 Clean State:

**Remove entire property:**
- ❌ `@property def dob_sum(self)`
- ❌ `@dob_sum.setter`

**Reasoning:** `dob_sum` is cleared after claim for privacy. No code should be setting/getting this property in production.

---

## 4. StudentTeacher Model - Legacy admin_id Alias

### Current State (REMOVE):

**File:** `app/models.py:766`
```python
# Transitional alias for legacy call sites that still use admin_id.
admin_id = sa.orm.synonym('teacher_id')
```

### V2.0 Clean State:

**Remove synonym:**
```python
class StudentTeacher(db.Model):
    student_id = db.Column(...)
    teacher_id = db.Column(...)
    # NO admin_id synonym
```

**Update all references:**
```bash
# Find and replace any uses of .admin_id with .teacher_id
grep -r "\.admin_id" app/
```

---

## 5. Student Model - Legacy Profile Migration Flag

### Current State (REMOVE):

**File:** `app/models.py:381-382`
```python
# Track if student has completed the legacy profile migration
has_completed_profile_migration = db.Column(db.Boolean, default=False)
```

### V2.0 Clean State:

**Remove column entirely:**
- ❌ `has_completed_profile_migration` column
- ❌ All references to this flag in routes/logic

**Migration:**
```python
flask db migrate -m "Remove legacy profile migration flag from students"
```

---

## 6. Balance Service - Legacy Calculation Comments

### Current State (MISLEADING):

**File:** `app/services/balance_service.py:87`
```python
# 3. Batch fetch TOTAL EARNINGS (legacy calculation logic compatibility)
```

### V2.0 Clean State:

**Update comment to remove "legacy" reference:**
```python
# 3. Batch fetch TOTAL EARNINGS (sum of all income transactions)
```

**No code changes needed** - logic is current

---

## 7. Student Balance Methods - Legacy Fallback Logic

### Current State (REMOVE):

**File:** `app/models.py:510-524`
```python
# Legacy fallback: derive posted as (all non-void) - (pending).
# This handles cases where BalanceCache doesn't exist yet.
all_non_void = db.session.query(func.sum(Transaction.amount)).filter(
    # ...
).scalar() or Decimal('0.00')

pending_fallback = db.session.query(func.sum(Transaction.amount)).filter(
    # ...
).scalar() or Decimal('0.00')

posted = all_non_void - pending_fallback
```

### V2.0 Clean State:

**With fresh database, BalanceCache will ALWAYS exist:**

**Simplify to:**
```python
def get_checking_balance(self, join_code, teacher_id):
    cache = BalanceCache.query.filter_by(
        student_id=self.id,
        join_code=join_code,
        account_type='checking'
    ).first()
    
    if not cache:
        # Should never happen in v2.0, but handle gracefully
        return Decimal('0.00')
    
    # Posted balance directly from cache
    return _quantize_currency(cache.posted_balance)
```

**Remove:**
- ❌ Legacy fallback to summing transactions
- ❌ "if not cache, calculate from scratch" logic

**Reasoning:** BalanceCache is created atomically with first transaction

---

## 8. Main Routes - Deprecated Legacy Hall Pass Routes

### Current State (REMOVE):

**File:** `app/routes/main.py:165-180`
```python
# -------------------- HALL PASS LEGACY TERMINAL/QUEUE (DEPRECATED) --------------------

@main_bp.route('/hallpass-terminal')
def hallpass_terminal():
    """Deprecated legacy route kept for compatibility."""
    flash("This feature has been moved.", "info")
    return redirect(url_for('main.index'))

@main_bp.route('/hallpass-queue')
def hallpass_queue():
    """Deprecated legacy route kept for compatibility."""
    flash("This feature has been moved.", "info")
    return redirect(url_for('main.index'))
```

### V2.0 Clean State:

**Remove entire section:**
- ❌ `/hallpass-terminal` route
- ❌ `/hallpass-queue` route

**Reasoning:** No legacy links pointing to these routes in v2.0

---

## 9. Auth Helpers - Deprecated Parameters

### Current State (REMOVE):

**File:** `app/auth.py:314`
```python
def get_admin_student_query(include_unassigned=True):
    """
    include_unassigned (bool): [DEPRECATED] No longer used. Kept for backward compatibility.
    """
```

### V2.0 Clean State:

**Remove parameter:**
```python
def get_admin_student_query():
    """Get SQLAlchemy query for students owned by current admin."""
    # Remove include_unassigned parameter entirely
```

**Update all call sites:**
```bash
# Find all uses
grep -r "get_admin_student_query" app/

# Update from:
get_admin_student_query(include_unassigned=False)
# To:
get_admin_student_query()
```

---

## 10. Scheduled Tasks - Legacy Join Code Backfill

### Current State (REMOVE):

**File:** `app/scheduled_tasks.py:147`
```python
"Skipping legacy join_code backfill in nightly maintenance; "
```

### V2.0 Clean State:

**Remove entire backfill logic** if it exists in nightly tasks

**Search for:**
```bash
grep -A 10 "legacy join_code backfill" app/scheduled_tasks.py
```

---

## 11. CLI Commands - Legacy Placeholder Handling

### Current State (REVIEW):

**File:** `app/cli_commands.py:21, 37`
```python
LEGACY_PLACEHOLDER_FIRST_NAME = "[Legacy]"

if seat.first_name == LEGACY_PLACEHOLDER_FIRST_NAME:
    # Handle legacy placeholder
```

### V2.0 Clean State:

**Remove if not needed for fixtures:**
- Review usage in CLI commands
- If only for migrating old data → **REMOVE**
- If used in test fixtures → **KEEP**

---

## 12. Database Comments - Nullable "for existing records"

### Current State (MISLEADING):

**File:** `app/models.py:2213`
```python
created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=True)  # Nullable for existing records
```

### V2.0 Clean State:

**Make NOT NULL and remove comment:**
```python
created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
```

**Migration:**
```python
flask db migrate -m "Make Admin.created_at NOT NULL (no legacy data)"
```

---

## Priority Cleanup Order

### Phase 1: High Priority (Clean Breaks)
1. ✅ Remove `Admin.username` column and all fallback logic
2. ✅ Remove `has_completed_profile_migration` column
3. ✅ Remove `StudentTeacher.admin_id` synonym
4. ✅ Remove legacy hall pass routes (`/hallpass-terminal`, `/hallpass-queue`)
5. ✅ Remove `TeacherBlock.dob_sum` property shim

### Phase 2: Medium Priority (Comment Cleanup)
6. ✅ Update `first_half_hash` / `second_half_hash` comments to remove "legacy" label
7. ✅ Update balance service comments to remove "legacy" references
8. ✅ Make `Admin.created_at` NOT NULL

### Phase 3: Low Priority (Parameter Cleanup)
9. ✅ Remove `include_unassigned` parameter from `get_admin_student_query()`
10. ✅ Review and remove CLI legacy placeholder handling (if safe)

---

## Testing After Cleanup

After removing backwards compatibility code:

```bash
# 1. Run full test suite
pytest tests/

# 2. Check for any references to removed code
grep -r "admin_id" app/ | grep -v teacher_id
grep -r "has_completed_profile_migration" app/
grep -r "legacy" app/ | grep -i username

# 3. Run migration
flask db migrate -m "V2.0 backwards compatibility cleanup"
flask db upgrade

# 4. Verify database constraints
psql classroom_economy -c "\d teachers"
psql classroom_economy -c "\d students"
```

---

## Code Removal Summary

| Item | File | Lines | Action |
|------|------|-------|--------|
| `Admin.username` column | models.py | 2197 | DROP COLUMN |
| `@validates('username')` | models.py | 2235-2251 | DELETE METHOD |
| Legacy username lookup | admin.py | 262-268 | DELETE CODE |
| `TeacherBlock.dob_sum` property | models.py | 333-338 | DELETE PROPERTY |
| `StudentTeacher.admin_id` | models.py | 766 | DELETE SYNONYM |
| `has_completed_profile_migration` | models.py | 382 | DROP COLUMN |
| Legacy hall pass routes | main.py | 165-180 | DELETE ROUTES |
| `include_unassigned` param | auth.py | 314 | REMOVE PARAMETER |
| Legacy balance fallback | models.py | 510-524 | SIMPLIFY LOGIC |
| Misleading "legacy" comments | multiple | various | UPDATE COMMENTS |

---

## Benefits of Cleanup

1. **Simpler codebase** - 200+ lines of dead code removed
2. **Clearer intent** - No confusing "legacy" comments on active code
3. **Better performance** - No unnecessary fallback checks
4. **Easier debugging** - Fewer code paths to trace
5. **Confident refactoring** - No fear of breaking old migrations

---

## Migration Script Template

```python
"""V2.0 backwards compatibility cleanup

Revision ID: xxxxxxxxx
Revises: yyyyyyyy
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Phase 1: Column removals
    op.drop_column('teachers', 'username')
    op.drop_column('students', 'has_completed_profile_migration')
    
    # Phase 2: Make NOT NULL (safe since fresh DB)
    op.alter_column('teachers', 'created_at', nullable=False)

def downgrade():
    # For fresh DB launch, downgrade not supported
    raise NotImplementedError("V2.0 clean launch - no downgrade path")
```

---

**Last Updated:** 2026-04-25  
**Status:** Deferred pending runtime stabilization  
**Next Steps:** Re-validate this cleanup set after failing-suite stabilization, then execute as a bounded post-stabilization wave

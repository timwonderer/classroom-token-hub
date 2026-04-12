# Table Consolidation Analysis: Student-Related Tables

**Date:** 2026-03-08  
**Database:** classroom_economy (PostgreSQL)  
**Scope:** Students, TeacherBlocks, StudentBlocks, StudentTeacher, Seats

---

## Executive Summary

The system has **5 student-related tables** that may appear redundant but serve distinct purposes in a multi-tenant, multi-period architecture:

1. **`teacher_blocks`** - Unclaimed roster seats (pre-claim state)
2. **`students`** - Student accounts (post-claim state)
3. **`student_blocks`** - Per-period student settings
4. **`student_teachers`** - Student-teacher ownership mapping
5. **`seats`** - Join-code scoped user identity (new v2.0 architecture)

**Key Finding:** These tables have **intentional separation of concerns** and cannot be trivially consolidated without breaking the multi-period isolation model.

---

## Table Purposes & Cardinality

### 1. `teacher_blocks` (Roster Seats)
**Purpose:** Pre-claim roster entries uploaded by teachers  
**Cardinality:** 1 seat per student per period per teacher  
**Lifecycle:** Created during roster upload → Claimed by student → Becomes mostly read-only

**Unique Columns:**
```
- dob_sum_hash (cleared after claim for privacy)
- last_name_hash_by_part (cleared after claim for privacy)
- is_claimed (boolean status flag)
- claimed_at (timestamp)
- dedupe_key (cross-teacher duplicate detection - deterministic hash of join_code_id|name|dob)
```

**Why It Exists:**
- Enables **join-code based claiming** (students don't need to know teacher name)
- Stores **temporary PII hashes** for claim matching that are cleared post-claim
- Maintains **roster integrity** even after student claims
- Links to `identity_profiles` for display purposes

**Consolidation Risk:** ❌ **Cannot merge with `students`** - serves completely different lifecycle stage

---

### 2. `students` (Student Accounts)
**Purpose:** Post-claim student accounts with credentials and class-linked state  
**Cardinality:** 1 record per claimed student identity, linked to one or more class memberships  
**Lifecycle:** Created during claim → Exists only while at least one class link remains

**Unique Columns:**
```
- Authentication: username_hash, passphrase_hash, pin_hash
- Claiming: first_half_hash, second_half_hash (for claim verification and student-initiated account reuse)
- Recovery: reset_code, reset_code_expires_at (actual recovery uses code + join_code)
- Profile: has_completed_setup, has_completed_profile_migration
- References: internal_reference, opaque_reference
- Insurance: insurance_plan, insurance_last_paid
- Features: second_factor_type, second_factor_enabled
```

**Why It Exists:**
- Central **authentication** and **credential storage**
- **Same-student identity reuse** across active class claims (student-initiated)
- **Account recovery** via `reset_code` + `join_code` (NOT via hashes)
- **No global student state:** student existence is class-linked and should be removed when their final class link is deleted
- **DB-enforced invariant:** migration `1adc6456ab0e` adds deferred constraint triggers to reject commits where a `students` row has no `student_teachers` link
- **Claim verification** via `first_half_hash` (matches seat during claim)
- **Student-initiated account reuse** via `first_half_hash` (finds the same student's existing account when they claim a second class)
- **Security boundary:** This does not allow teacher-to-teacher student lookup; class access remains join-code/class scoped.

**Consolidation Risk:** ❌ **Cannot merge with `teacher_blocks`** - different lifecycle stage and cardinality (blocks are per-period seats; students are claimed accounts)

---

### 3. `student_blocks` (Per-Period Settings)
**Purpose:** Per-student, per-period behavioral state  
**Cardinality:** 1 record per student per period  
**Lifecycle:** Created when student joins period → Active while enrolled

**Unique Columns:**
```
- tap_enabled (period-specific tap in/out toggle)
- done_for_day_date (daily lock-out state)
- rent_hall_passes (period-specific hall pass accounting)
- period (explicitly stores period identifier)
- seat_id (links to v2.0 Seat architecture)
```

**Why It Exists:**
- Stores **period-specific behavioral flags** (tap enabled/disabled varies by class)
- Tracks **daily state** per period (done for day is class-specific)
- Enables **per-class feature toggles** (student may be tapped out in Period 1 but not Period 2)

**Consolidation Potential:** ⚠️ **Possible merge candidate** - Could potentially merge into `students` table

**But Consider:**
- `students` table is already large (44 columns)
- Period-specific state would create sparse data (NULLs for single-period students)
- Clean separation of concerns (global vs period-specific)

---

### 4. `student_teachers` (Ownership Mapping)
**Purpose:** Many-to-many relationship between students and teachers  
**Cardinality:** 1 record per (student, teacher) pair  
**Lifecycle:** Created when student starts with teacher → Deleted when relationship ends

**Unique Columns:**
```
- teacher_id (which teacher owns this student)
- join_code (which class this relationship ties to)
```

**Why It Exists:**
- Supports **multi-teacher scenarios** (student has Period 1 with Teacher A, Period 2 with Teacher B)
- Enables **teacher-scoped queries** (`get_admin_student_query()`)
- Provides **join_code context** for ownership lookups
- Simple join table for many-to-many relationship

**Consolidation Risk:** ❌ **Cannot eliminate** - pure relational join table required for M:N relationship

---

### 5. `seats` (V2.0 Architecture)
**Purpose:** Join-code scoped identity boundary (new unified architecture)  
**Cardinality:** 1 record per student per join_code  
**Lifecycle:** Created in v2.0+ → Gradually replacing student-centric models

**Unique Columns:**
```
- public_id (external-facing identifier)
- user_id (links to unified users table)
- join_code (class isolation)
- student_id (transitional bridge to legacy students table)
```

**Why It Exists:**
- **V2.0 architecture** - unified identity model across students/teachers/sysadmins
- **Join-code scoping** as first-class concern
- **Transitional bridge** to gradually migrate away from `students` table
- Enables **cleaner multi-tenancy** isolation

**Consolidation Risk:** ⏭️ **Future direction** - Eventually replaces `students` table entirely

---

## Column Overlap Analysis

### Shared Columns Across Tables

| Column | teacher_blocks | students | student_blocks | Reason |
|--------|----------------|----------|----------------|---------|
| `join_code` | ✅ | ✅ | ✅ | Multi-tenancy: Each table needs class isolation |
| `block` / `period` | ✅ | ✅ | ✅ | Period identifier (names differ for historical reasons) |
| `student_id` | ✅ (FK) | ✅ (PK) | ✅ (FK) | Relational linking |
| `identity_id` | ✅ | ✅ | ❌ | Display identity (shared via relationship) |
| `first_name` + `last_initial` | ✅ | ✅ | ❌ | Denormalized for performance (PII encrypted) |
| `salt` | ✅ | ✅ | ❌ | Each needs own salt for hashing |
| `first_half_hash` | ✅ | ✅ | ❌ | Claim verification + student-initiated account reuse |
| `dedupe_key` | ✅ | ❌ | ❌ | Duplicate detection during roster upload |

**Analysis:** These overlaps are **intentional denormalization** for:
1. **Performance** - Avoid joins on encrypted PII fields
2. **Multi-tenancy** - Each table independently scoped by `join_code`
3. **Lifecycle stages** - Pre-claim vs post-claim data
4. **Duplicate detection** - `dedupe_key` prevents same student in same class
5. **Claim verification** - `first_half_hash` matches credentials during claim

---

## Data Flow & Lifecycle

```
ROSTER UPLOAD
    ↓
teacher_blocks (unclaimed seats)
    - dob_sum_hash, last_name_hash_by_part (temp PII)
    - first_half_hash, join_code
    - is_claimed = FALSE
    
STUDENT CLAIMS
    ↓
students (account created; class-linked, non-global)
    - Copies: first_name, last_initial, identity_id
    - Adds: username_hash, passphrase_hash
    - Generates: internal_reference, opaque_reference
    ↓
teacher_blocks.is_claimed = TRUE
teacher_blocks.student_id = students.id
teacher_blocks.dob_sum_hash = NULL (privacy)
teacher_blocks.last_name_hash_by_part = NULL (privacy)
    ↓
student_blocks (period settings)
    - tap_enabled, done_for_day_date
    - rent_hall_passes
    ↓
student_teachers (ownership)
    - Links student to teacher
    - Stores join_code context
    - If final class link is removed, student record must be deleted (forbidden to leave orphan/global student state)
```

---

## Consolidation Options

### Option 1: Merge `student_blocks` into `students`
**Feasibility:** ⚠️ Technically possible but adds complexity

**Pros:**
- Reduces table count by 1
- Eliminates some joins

**Cons:**
- `students` already has 44 columns
- Period-specific data becomes sparse (NULL for single-period students)
- Loses clean separation of account-level state vs period-specific state
- Requires unique constraint change: `(student_id, period)` vs just `(student_id)`

**Recommendation:** ❌ **Not Recommended** - Complexity increase outweighs benefits

---

### Option 2: Merge `teacher_blocks` into `students`
**Feasibility:** ❌ Impossible due to cardinality mismatch

**Why It Fails:**
- `teacher_blocks`: 1 row per (teacher, period, student)
- `students`: claimed student identity row linked to class memberships (non-global)
- A student claimed by Teacher A in Period 1 AND Teacher B in Period 2 would need 2 rows
- Violates single-identity principle

---

### Option 3: Eliminate `student_teachers`
**Feasibility:** ❌ Breaks multi-teacher scenarios

**Why It Fails:**
- Required for many-to-many relationship
- Student can have multiple teachers (different periods)
- Teacher needs to query "my students" efficiently
- No other table cleanly stores this M:N relationship

---

### Option 4: Accelerate Migration to `seats` (V2.0)
**Feasibility:** ✅ Long-term strategic direction

**What This Means:**
- Gradually phase out `students` table
- Move authentication to `users` table
- Use `seats` as primary join-code scoped identity
- `student_blocks` becomes `seat_settings` or gets absorbed into `seats`

**Timeline:** 6-12 months

---

## Current Table Metrics

```sql
-- Check row counts
SELECT 
    'teacher_blocks' AS table_name, COUNT(*) AS row_count FROM teacher_blocks
UNION ALL SELECT 'students', COUNT(*) FROM students
UNION ALL SELECT 'student_blocks', COUNT(*) FROM student_blocks
UNION ALL SELECT 'student_teachers', COUNT(*) FROM student_teachers
UNION ALL SELECT 'seats', COUNT(*) FROM seats;
```

**Current Database:**
```
table_name       | row_count
-----------------|-----------
teacher_blocks   | 2
students         | 0
student_blocks   | 0
student_teachers | 0
seats            | 0
```

With empty tables in new DB, this is the **perfect time** to consider architecture changes!

---

## Recommendations

###  **Keep Current Architecture** (Short Term)
**Why:**
- Clean separation of concerns
- Well-tested multi-tenancy model
- Performance-optimized with intentional denormalization
- Complexity of consolidation outweighs benefits

### ⏭️ **Plan V2.0 Migration** (Long Term)
**Target State:**
```
users (authentication)
  ↓
seats (join-code scoped identity)
  ↓
seat_settings (replaces student_blocks)
  ↓
seat_teachers (replaces student_teachers)
```

**Benefits:**
- Unified identity model (students, teachers, sysadmins)
- First-class join-code scoping
- Cleaner multi-tenancy
- Reduced table count (4 → 3 in student domain)

**Migration Path:**
1. ✅ `seats` table already exists (transitional)
2. Add `users` table for unified authentication
3. Gradually migrate `students` → `users` + `seats`
4. Rename `student_blocks` → `seat_settings`
5. Update all queries to use `seats` instead of `students`
6. Drop `students` table after full migration

---

## Immediate Actions
✅ **PHASE 3 PURGE COMPLETE** (2026-04-12)

### ✅ **Executed:**
1. Dropped `is_teacher_shadow` and `shadow_for_admin_id` from `Students` table.
2. Dropped `username` from `Teachers` and `SystemAdmins` tables.
3. Dropped orphaned `actor_membership_id` columns from `UserCredentials` and `WebAuthnCredentials`.

Since database is fresh with no legacy data:

### ✅ **Safe to Do Now:**
1. Add better documentation to model docstrings explaining why each table exists
2. Add comments in migrations explaining separation of concerns
3. Update schema documentation with this analysis

### ⚠️ **Requires Planning:**
1. Design `users` table structure for V2.0
2. Create migration plan for `students` → `users` + `seats`
3. Update application code to use `seats` as primary identity reference

### ❌ **Do Not Do:**
1. Merge `student_blocks` into `students` (adds complexity)
2. Merge `teacher_blocks` into `students` (breaks cardinality)
3. Eliminate `student_teachers` (required for M:N relationship)

---

## Conclusion

What appears to be "redundant" tables is actually **intentional architectural separation** for:

1. **Lifecycle stages:** Pre-claim (teacher_blocks) vs Post-claim (students)
2. **Scope:** Class-linked claimed identity (students) vs Period-specific runtime state (student_blocks)
3. **Relationships:** Many-to-many mapping (student_teachers)
4. **Performance:** Denormalized joins for encrypted PII
5. **Future architecture:** Gradual migration to seats-based model

**Recommendation:** Maintain current separation, plan long-term V2.0 migration to `seats`-based architecture.

---

**Last Updated:** 2026-04-12  
**Status:** Phase 3 Hardening Complete  
**Next Steps:** Plan V2.1 Identity-Model Convergence (Post-Launch)

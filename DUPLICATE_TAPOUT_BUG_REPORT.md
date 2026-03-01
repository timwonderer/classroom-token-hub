---
roles: [teacher, student, developer]
Audience: mixed-audience
---
# P0 Bug Report: Duplicate Auto-Tap-Out Events Causing Payroll Overpayment
> **Note:** This page is relevant to multiple audiences because it covers system-wide information applicable to all roles.



**Date:** 2026-02-10
**Severity:** P0 - Critical Financial Bug
**Status:** Fixed
**Affected Student:** ID 357 (Matthew V.)

---

## Executive Summary

A race condition in the auto-tap-out enforcement logic caused duplicate attendance records, resulting in a student receiving ~$6000 instead of ~$15-20 for a single 75-minute work session. The bug allowed multiple "Daily limit reached" tap-out events to be created simultaneously, and payroll counted each duplicate pair as a separate session.

---

## Root Cause Analysis

### The Bug

The `check_and_auto_tapout_if_limit_reached()` function in `app/routes/api.py` had **no idempotency check**. When called multiple times simultaneously (or in quick succession), it would:

1. Query for the latest "active" TapEvent
2. Calculate if daily limit was reached
3. Create a new "inactive" tap-out event
4. **BUT**: Multiple concurrent requests could all see the same "active" event before commits happened

### Why It Happened

The function is called from **multiple sources**:

1. **Student browser polling** `/student-status` endpoint (every 1-2 seconds)
2. **Scheduled job** running hourly to check all active students
3. **Admin dashboard** when teacher views active students
4. **Manual check endpoint** when teacher manually checks limits

If a student's browser was polling rapidly while the scheduled job ran, or if they had multiple browser tabs open, all these calls would race to create tap-out events.

### The Impact

- Student ID 357 had **20+ duplicate tap-out events** created at the same timestamp (Feb 6, 2026, 1:14 PM PST)
- Each duplicate created a valid active→inactive pair in the attendance records
- Payroll calculation in `calculate_unpaid_attendance_seconds()` counted each pair as a separate session
- Result: **~$6000 payment** for 75 minutes of work (should be ~$15-20 at $0.25/min)

---

## The Fix

### Code Changes

**File:** `app/routes/api.py`
**Function:** `check_and_auto_tapout_if_limit_reached()` (lines 2599-2633)

Added an **idempotency check** before creating tap-out events:

```python
# IDEMPOTENCY CHECK: Check if we already created a daily limit tap-out today
# This prevents duplicate tap-outs from race conditions (multiple browser tabs, scheduled job, etc.)
existing_limit_tapout = TapEvent.query.filter(
    TapEvent.student_id == student.id,
    TapEvent.period == period_upper,
    TapEvent.status == "inactive",
    TapEvent.timestamp >= start_of_day_utc,
    TapEvent.timestamp < end_of_day_utc,
    TapEvent.reason.like(f"Daily limit%"),  # Matches "Daily limit (X.Xh) reached"
    TapEvent.is_deleted == False
).first()

if existing_limit_tapout:
    current_app.logger.debug(
        f"Skipping duplicate auto-tap-out for student {student.id} in {period_upper} - "
        f"daily limit tap-out already exists at {existing_limit_tapout.timestamp}"
    )
    continue  # Skip creating duplicate
```

### How It Works

Before creating a new daily limit tap-out event, the code now checks if one already exists for:
- Same student
- Same period
- Same day (Pacific timezone)
- Same reason pattern ("Daily limit%")
- Not deleted

If one exists, it skips creating a duplicate.

---

## Remediation Steps

### 1. Clean Up Existing Duplicates

Use the cleanup script to soft-delete duplicate records:

```bash
# Preview what would be cleaned up for student 357
python cleanup_duplicate_tapouts.py --student-id 357 --dry-run

# Actually clean up the duplicates (after reviewing preview)
python cleanup_duplicate_tapouts.py --student-id 357 --execute
```

### 2. Reverse the Incorrect Payroll

You'll need to manually adjust the student's balance:

```sql
-- Check student's current balance
SELECT checking_balance, savings_balance
FROM student_block
WHERE student_id = 357 AND join_code = '<JOIN_CODE>';

-- Find the incorrect payroll transaction
SELECT * FROM transaction
WHERE student_id = 357
  AND type = 'payroll'
  AND timestamp >= '2026-02-06'::date
  AND timestamp < '2026-02-07'::date;

-- Create a reversal transaction (adjust amount as needed)
-- This should be done through the admin interface or via a script
```

**Recommended approach:**
1. Calculate what the CORRECT payroll should have been (~$15-20)
2. Calculate the overpayment (~$5980-5985)
3. Create a manual adjustment transaction to reverse the overpayment

### 3. Verify No Other Affected Students

Run the cleanup script for all students to find other potential victims:

```bash
# Check all students for duplicates
python cleanup_duplicate_tapouts.py --all --dry-run

# If other students are affected, clean them up
python cleanup_duplicate_tapouts.py --all --execute
```

---

## Testing

### Manual Testing

1. **Create a student with daily limit set to 1.25 hours (75 minutes)**
2. **Have student tap in and work past the limit**
3. **Open multiple browser tabs** and let them poll `/student-status`
4. **Trigger the scheduled job** while tabs are open
5. **Verify:** Only ONE "Daily limit reached" tap-out event is created
6. **Run payroll** and verify correct amount paid

### Regression Test

Create a test in `tests/test_tap_flow.py`:

```python
def test_auto_tapout_prevents_duplicates_from_race_condition(client, app):
    """
    Test that duplicate auto-tap-out events are NOT created
    when check_and_auto_tapout_if_limit_reached is called multiple times.
    """
    # Setup student with daily limit
    # Tap in student
    # Wait until over limit
    # Call check_and_auto_tapout_if_limit_reached() 5 times rapidly
    # Assert: Only ONE tap-out event created
    # Assert: Payroll calculates correct amount
```

---

## Prevention

### Code Review Checklist

When reviewing future changes to attendance/payroll:

- [ ] Does it create TapEvents?
- [ ] Could it be called concurrently?
- [ ] Is there an idempotency check?
- [ ] Is there a test for duplicate prevention?
- [ ] Are there tests for payroll calculation accuracy?

### Monitoring

Add alerting for:
- **Abnormally high payroll amounts** (e.g., >$100 for a single student in one period)
- **Duplicate TapEvents** (same student, period, timestamp, reason)
- **High TapEvent creation rate** (>10 events per student per minute)

### Documentation

Update:
- [ ] CHANGELOG.md
- [ ] docs/security/ (if needed)
- [ ] docs/development/KNOWN_ISSUES.md (if still any edge cases)

---

## Timeline

| Time | Event |
|------|-------|
| Feb 6, 2026 1:14 PM PST | Duplicate tap-out events created for student 357 |
| Feb 10, 2026 | Teacher runs payroll, discovers $6000 overpayment |
| Feb 10, 2026 | Bug investigated and root cause identified |
| Feb 10, 2026 | Fix implemented with idempotency check |
| Feb 10, 2026 | Cleanup script created |

---

## Related Issues

- Multi-tenancy scoping (already fixed in previous audit)
- Payroll calculation accuracy (working as designed - issue was duplicate data)
- Rate limiting on API endpoints (consider for `/student-status`)

---

## Recommendations

### Short Term (Do Now)

1. ✅ **Apply the fix** (already done)
2. 🔧 **Clean up duplicates** for affected student(s)
3. 💰 **Reverse incorrect payroll** via manual adjustment
4. 🧪 **Add regression test**

### Medium Term (This Week)

1. **Add database unique constraint** on (student_id, period, timestamp, reason) to prevent duplicates at DB level
2. **Add rate limiting** on `/student-status` endpoint (max 1 request per 2 seconds per student)
3. **Add payroll anomaly detection** that alerts when a student would receive >$100 in single payroll
4. **Audit other scheduled jobs** for similar race condition risks

### Long Term (Next Sprint)

1. **Implement event sourcing** for attendance to ensure exactly-once semantics
2. **Add distributed locking** (Redis) for critical operations like auto-tap-out
3. **Create financial reconciliation report** that compares expected vs actual payroll
4. **Add end-to-end payroll accuracy tests** with duplicate prevention scenarios

---

## Lessons Learned

1. **Always add idempotency checks** for operations that can be called concurrently
2. **Test for race conditions** explicitly, especially for financial operations
3. **Monitor for anomalies** in financial calculations
4. **Add database constraints** where possible to enforce data integrity at the lowest level
5. **Batch operations carefully** - the scheduled job should use locking to prevent overlap with API calls

---

## Conclusion

This was a critical financial bug caused by a race condition in the auto-tap-out logic. The fix adds proper idempotency checking to prevent duplicate events. With cleanup of existing duplicates and reversal of incorrect payroll, the system should return to correct operation.

**Estimated Time to Fix:**
- Code fix: ✅ Complete
- Cleanup script: ✅ Complete
- Clean up duplicates: 10 minutes
- Reverse payroll: 15 minutes
- Testing: 30 minutes
- **Total: ~1 hour**

**Risk of Recurrence:** Low (after fix applied and tested)

---

**Report Author:** Claude Code
**Date:** February 10, 2026
**Session:** claude/investigate-system-issue-SGfWn

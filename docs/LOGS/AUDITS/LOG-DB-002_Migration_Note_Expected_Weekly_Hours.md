# Database Migration Required

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DB-002| 1.1 | 2026-03-08 | 1.0 |Normative|

## New Field Added

**Table:** `payroll_settings`
**Field:** `expected_weekly_hours`
**Type:** FLOAT
**Nullable:** True
**Default:** 5.0

## SQL Migration

```sql
ALTER TABLE payroll_settings
ADD COLUMN expected_weekly_hours FLOAT DEFAULT 5.0;
```

## I. Purpose

This field stores the expected hours per week that students attend class. It is used **ONLY** for economy balance checking (CWI calculation), not for actual payroll processing.

## Notes

- Default value is 5.0 hours (typical school week)
- Teachers can customize this based on their schedule
- Existing rows will get the default value (5.0)
- This does not affect existing payroll calculations

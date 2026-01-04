---
title: Teacher Students and Join Codes
category: diagnostics
roles: [teacher]
related:
  - diagnostics/teacher-onboarding
  - diagnostics/teacher-attendance-payroll
---

# Students and Join Codes

## If a student cannot claim an account, check these first
- The join code matches the correct class period.
- The student's first initial, last name, and date of birth match the roster.
- The seat for that join code has not already been claimed.

## If join codes look wrong or missing
- Each block has its own join code; shared teachers still have separate periods.
- Legacy students may require the Claim Students workflow.
- Use Backfill Join Codes when prompted to repair legacy transactions.

## If CSV uploads fail
- Required columns: first_name, last_name, date_of_birth, block.
- Date of birth must match the expected format in the template.
- Duplicate rows can create claim conflicts.

## This is expected when...
- Manual student creation generates a new join code and seat.

## Quick evidence to collect
- The join code, block, and the student's exact roster data.
- The upload error message or row that failed.

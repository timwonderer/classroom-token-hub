---
title: Teacher Attendance and Payroll
category: diagnostics
roles: [teacher]
related:
  - diagnostics/teacher-students
  - diagnostics/teacher-transactions-banking
---

# Attendance and Payroll

## If payroll does not run or looks wrong, check these first
- Payroll is enabled in Feature Settings for the class period.
- There are tap events in the attendance log for that period.
- Pay rates and schedule are configured in Payroll Settings.

## If attendance history looks wrong
- The attendance log is append-only; it does not support edits.
- Hall pass actions create tap-out and tap-in entries.
- Class context matters: join codes isolate attendance by period.

## This is expected when...
- Payroll history only shows runs that were manually triggered.
- Economy Health uses expected weekly hours from payroll settings.

## This cannot happen unless...
- Payroll transactions appear without a payroll run (only manual payments do that).

## Quick evidence to collect
- The period, date range, and the affected student(s).
- The last payroll run time shown on the payroll page.

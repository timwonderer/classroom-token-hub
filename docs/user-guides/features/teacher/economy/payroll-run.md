---
title: Run Payroll
category: features
subcategory: teacher-economy
roles: [teacher]
description: Run payroll, review previews, and confirm payments.
keywords: [payroll, run payroll, paychecks]
related:
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Run Payroll

## Overview
Running payroll allows you to pay students their earned wages based on their recorded work time in the Attendance Log.

## Step-by-Step Instructions

### Executing a Payroll Run
1. Navigate to **Economy > Payroll** in the teacher sidebar.
2. Review the preview list of students and their calculated pay.
3. If everything looks correct, select **Run Payroll**.
4. Confirm the run to deposit the funds into student accounts.

## What a Run Pays
Payroll pays **finished work sessions**: time from a student's clock-in to their clock-out. Each session is paid once, in full, by the first payroll run after the student clocks out.

- **Students still working are paid next time.** If you run payroll while a student is clocked in, that session is not included. It is paid in full, including the time before this run, by the next run after they clock out.
- **Nothing to pay yet.** If no student has a finished, unpaid session, the run is refused with "Nothing to pay yet". Nothing is recorded, and you can run it again once students have clocked out.
- **Automatic payroll** works the same way. If payday arrives while nothing is finished, it waits and pays within the hour after the first clock-out.
- **Sessions end at the end of the day** even if a student forgets to clock out, so no work waits more than a day to become payable.

The preview shows exactly what a run would pay right now. A student's unpaid time also includes a session in progress, so it can be larger than the preview.

## Important Notes
> [!NOTE]
> **After running:** Check the **Payroll History** tab to confirm totals and spot-check transactions for a few students.

> [!TIP]
> **If the preview looks wrong:** Verify the attendance taps and pay rates for the specific students, then return and refresh the preview page.

## Related guides
- [Payroll Settings](payroll-settings.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)

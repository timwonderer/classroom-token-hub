---
title: Teacher Hall Pass
category: diagnostics
roles: [teacher]
related:
  - diagnostics/teacher-store
  - diagnostics/teacher-attendance-payroll
---

# Hall Passes

## If passes cannot be approved, check these first
- Hall pass is enabled for the class period.
- The pass is still pending (approved and rejected passes cannot be re-approved).
- The student has hall passes remaining for standard reasons.

## If hall pass tracking looks wrong
- The queue shows approved passes that have not left yet.
- Terminal scans move passes from approved to left, then returned.
- Office, Summons, or Done for the day do not deduct passes.

## This is expected when...
- A pass number is generated only upon approval.
- Hall pass actions create tap-out/tap-in attendance events.

## Quick evidence to collect
- Pass ID, status, and student name.
- Whether the terminal was used or the action was taken in the admin UI.

---
title: Hall Pass
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Work the four-tab pass queue, set the out limit, configure pass types, and share the Office Verification link.
keywords: [hall pass, pending, issued, out, history, out limit, pass types, queue limit, office verification, QR]
related:
  - user-guides/features/teacher/classroom/hall-pass-setup
  - user-guides/diagnostics/teacher/hall-pass
  - user-guides/features/teacher/classroom/attendance-approvals
---

# Hall Pass

## Overview

**Classroom > Hall Pass** opens **Hall Pass Management**. A pass moves through four states, and the page gives each one its own tab: a student **requests**, you **approve**, they **leave**, they **return**. You touch the pass three times, not once.

## Step-by-step instructions

### The queue settings bar

Above the tabs sits a compact settings row:

- **Hall Pass Granting** — the master switch. Off means students cannot request passes at all.
- **Out Limit** — how many students may be out at once (1–50).
- **Configure Pass Types** — opens the separate setup page covered below.

Changes here save as you make them; a green **Saved!** badge confirms it.

### Working the four tabs

| Tab | What is in it | What you do |
| --- | --- | --- |
| **Pending** | Requests waiting on you, showing student, reason, request time, and period | **Approve** or **Reject** |
| **Issued** | Approved passes where the student has not left yet | **Left Class** when they go |
| **Out** | Students currently out, showing when they left | **Returned** when they come back |
| **History** | Everything, filtered | Read |

Empty states are distinct so you can tell them apart at a glance: *No pending requests*, *No issued passes are waiting*, *No one is currently out*.

**History** filters on **Type**, **Start Date**, and **End Date**, then **Apply**. Results show Date/Time, Student, Period, Type, Status, and Duration, paginated. Before you filter it reads *Select filters and click Apply to view history*.

### Configuring pass types

**Configure Pass Types** opens **Hall Pass Configuration**, a separate page with its own master switch, a list of destinations, and per-destination limits.

That page controls the destinations and per-destination limits students see. [Hall Pass Configuration](hall-pass-setup.md) covers the setup fields.

### Office Verification

**Office Verification** opens a public page staff can use to check whether a pass is genuine, without needing an account. **Regenerate QR** issues a fresh link and invalidates the old one — use it if the link has been shared beyond the people you meant to give it to.

## Important notes

> [!WARNING]
> **Pass type configuration is class-scoped.** Save while the intended class is active, then reload the setup page to confirm the saved destinations.

> [!IMPORTANT]
> **Out Limit is enforced.** The **Left Class** button becomes unavailable once the configured number of students are out. Mark a student **Returned** to open a place.

> [!NOTE]
> **Approving is not the same as sending.** An approved pass sits in **Issued** until you mark **Left Class**. That is what starts the duration clock, and the History tab's Duration column measures from there — not from approval.

> [!TIP]
> Mark **Returned** as students come back rather than at the end of the period. The Out tab is the only place that shows who is currently unaccounted for, and it is only trustworthy if it is current.

## Related guides

- [Hall Pass Configuration](hall-pass-setup.md)
- [Attendance and Approvals](attendance-approvals.md)
- [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md)

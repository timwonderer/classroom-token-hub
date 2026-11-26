---
title: Support Tickets
category: features
subcategory: teacher-settings
roles: [teacher]
description: Submit a support ticket to the Classroom Token Hub team, use your active class seat, and read the My Tickets list.
keywords: [support, ticket, help, bug, feature request, my tickets, escalate, report a problem, contact support]
related:
  - user-guides/features/teacher/classroom/student-issues
  - user-guides/features/student/support/report-issues
  - user-guides/diagnostics/teacher
---

# Support Tickets

## Overview

**Support** at the bottom of the teacher sidebar opens **Help & Support**. The page is in two halves: a form for raising a ticket with the Classroom Token Hub team, and a **My Tickets** list of what you have already sent.

This form is for problems *you* hit as a teacher. It is not the route for a student's problem — see the note below.

## Step-by-step instructions

### Before you start

You need at least one class. Without one the page tells you so and refuses to submit; create a class first.

### Filling in the form

1. In the teacher sidebar, select **Support**.
2. The form shows your active class. Every ticket belongs to your seat in that class, including reports about a problem you encountered as a teacher. Switch class before opening the form if needed.
3. Your seat and class references identify the ticket to support. The class name is shared only if you select its checkbox.
4. **Issue Type** (required) — *General Support*, *Bug / Error*, or *Feature Request*.
5. **Title** (required, 200 characters).
6. **What happened?** (required, 2000 characters). The useful version names the page, what you did, and what appeared.
7. **What did you expect to happen?** (optional, 1000 characters). Worth filling in for anything ambiguous — it is the difference between a bug report and a feature request.
8. **Page URL** (optional). The path where it happened, like `/admin/students`.
9. Optionally select **I give permission to include the class name**. It starts unchecked. Your written report, page URL, IP address, and browser details are sent to support; this form does not automatically attach balances, transactions, or roster notes.
10. Select the submit button. It disables itself and shows *Submitting…* so a slow connection cannot send the ticket twice.

You get a confirmation that the ticket went to system administration, and the page reloads with it in the list.

### Reading My Tickets

**My Tickets** shows your most recent 20, newest first, filtered to your active class seat. Switching classes changes the list.

Each entry shows the title you gave it, the saved class label and class reference, the submitted date, the category, the first 220 characters of your description, and a status badge.

The statuses a ticket moves through are **Open**, **Teacher review**, **Escalated to dev**, **Dev resolved**, **Teacher final review**, and **Closed**. See the caution below about how they are displayed.

## Important notes

> [!IMPORTANT]
> **A student's problem has to start with the student.** You cannot open a ticket on a student's behalf from here. The student raises it from their own account, and it then reaches you for review — that queue is covered in [Student Issues](../classroom/student-issues.md). Only after that can it be escalated to the support team.

> [!CAUTION]
> **An exact resubmission only creates one ticket.** If the form submits twice with every field identical — a double-click, or a browser retry after a slow connection — only one ticket is created. Changing anything, including just the description, makes it a new ticket even if you reuse the same title.

> [!NOTE]
> **The status badge's colour tracks the status**, and the wording is spaced out and capitalised (an escalated ticket reads *Escalated To Dev*, not a raw database value).

> [!NOTE]
> **There are no replies on this page.** My Tickets shows what you sent and where it has got to, not any response. Support replies arrive by whatever contact route your account is set up with.

> [!TIP]
> Fill in **Page URL** even when it feels obvious. It is the single most useful field for reproducing a problem, and it costs one copy-paste from your address bar.

## Related guides

- [Student Issues](../classroom/student-issues.md)
- [Report a Problem (Student)](../../student/support/report-issues.md)
- [Teacher Diagnostics](../../../diagnostics/teacher.md)

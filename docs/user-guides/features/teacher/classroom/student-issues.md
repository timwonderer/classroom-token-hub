---
title: Student Issues Queue
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Manage and resolve student-reported issues and disputes.
keywords: [issues, reports, support, student, resolution, escalate]
related:
  - user-guides/features/student/support/report-issues
  - user-guides/diagnostics/teacher-announcements-issues
---

# Student Issues Queue

## Overview
The Issue Resolution System allows you to manage student disputes, bug reports, and transaction errors in a structured way. Instead of scattered emails or verbal complaints, all issues are tracked, tied to specific records, and auditable.

## Step-by-Step Instructions

### Triaging and Reviewing Issues
1. Navigate to **Classroom > Student Issues** in the teacher sidebar.
2. Issues appear in one of three tabs: **Pending** (new), **Resolved** (closed), or **Escalated** (sent to Sysadmin).
3. Click on any issue card in the Pending tab to view the student's description, the issue category, and a snapshot of their balance at the time of the report.

### Resolving Issues
1. From the issue detail view, determine the appropriate action based on the student's claim.
2. **Void Transaction:** If the student legitimately points out an incorrect charge, click "Void Transaction" to refund the amount and automatically resolve the issue.
3. **Manual Adjustment:** If you need to fix a balance without voiding a specific record, go to the student's detail page via the provided link, adjust their money, and then return to the issue to mark it **Resolved**.
4. **Deny Issue:** If the student's report is invalid, select "Deny / No Action" and provide a reason.

### Escalating Technical Bugs
1. If the issue is a platform bug (e.g., negative balance glitches, broken buttons), click **Escalate to Developer**.
2. Provide a diagnostic note explaining your observations.
3. Check "Student eligible for bug reward" if you want the student to receive a bonus for finding a legitimate bug.
4. The issue will move to the Escalated tab for Sysadmin review.

## Important Notes
> [!NOTE]
> **Not a chat system:** This system is not designed for back-and-forth messaging. Students submit a report once, and you respond by resolving it or escalating it. If you need a conversation, speak with the student in class.

## Related Guides
- [Student Perspective: Reporting Issues](../../student/support/report-issues.md)
- [Diagnostics: Announcements & Issues](../../../diagnostics/teacher/announcements-issues.md)

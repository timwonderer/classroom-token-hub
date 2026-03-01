---
title: Student Issues Queue
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Manage and resolve student-reported issues and disputes.
keywords: [issues, reports, support, student, resolution, escalate]
related:
  - user-guides/features/student/reporting-issues/report-issues
  - user-guides/diagnostics/teacher-announcements-issues
Audience: teacher-facing
---

# Student Issues Queue

The Issue Resolution System allows you to manage student disputes, bug reports, and errors in a structured way. Instead of scattered emails or verbal complaints, all issues are tracked, tied to specific records, and auditable.

## Where to work
Go to **Classroom > Student Issues**.

---

## Triage Workflow

Issues appear in one of three tabs based on their status:

1.  **Pending:** New issues waiting for your review.
2.  **Resolved:** Issues you have closed or fixed.
3.  **Escalated:** Issues you have sent to the System Administrator (Developer) for technical review.

### Reviewing an Issue

Click on any issue card to see the full details:

- **Student Description:** What the student says happened.
- **Category:** The type of issue (e.g., "Transaction Error", "Login Issue").
- **Related Record:** Direct link to the transaction, tap event, or store purchase in question.
- **Context Snapshot:** A snapshot of the student's balance and ledger at the time they submitted the report (useful for debugging balance disputes).

---

## Resolution Actions

You have several tools to resolve issues directly from the issue detail page:

### 1. Void Transaction
If a student reports an incorrect charge or duplicate transaction:

- Click **Void Transaction**.
- This marks the original transaction as void and refunds the amount.
- The issue is automatically marked as **Resolved**.

### 2. Manual Adjustment
If you need to fix a balance without voiding a specific transaction:

- Go to the student's detail page (link provided in the issue).
- Use **Manage Money** to credit/debit the correct amount.
- Return to the issue and mark it as **Resolved**.

### 3. Deny Issue
If the student is incorrect or the report is invalid:

- Select **Deny / No Action**.
- Provide a reason (visible to the student).
- The issue is marked as **Resolved** (Closed).

---

## Escalating to System Admin (Developer)

If an issue seems to be a technical bug (e.g., "I clicked buy but didn't get the item", "My balance is negative $1,000,000"):

1.  Click **Escalate to Developer**.
2.  **Reason:** Explain why you think this is a bug.
3.  **Diagnostic Note:** Add any details you observed.
4.  **Share Class Name:** (Optional) Check this to allow the developer to see your class name for easier debugging. Otherwise, they only see an anonymous ID.
5.  **Student Reward:** Check **"Student eligible for bug reward"** if you want the student to receive a bonus for finding a legitimate bug.

**What happens next?**

- The issue moves to the **Escalated** tab.
- The System Admin reviews it.
- When resolved, you will see the admin's notes and the final status.

---

## Student Communication

Students see the status of their issues on their **Help & Support** page.

- **Pending:** "Teacher Review"
- **Resolved:** "Resolved" (They can see your resolution note)
- **Escalated:** "Elevated" -> "Developer Review"

**Note:** This system is not a chat. Students submit once, and you respond by resolving or escalating. If you need a back-and-forth conversation, speak with the student in class.

---

## Related Guides
- [Student Perspective: Reporting Issues](/docs/user-guides/features/student/reporting-issues/report-issues)
- [Diagnostics: Announcements & Issues](/docs/user-guides/diagnostics/teacher-announcements-issues)

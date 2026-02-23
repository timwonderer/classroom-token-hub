---
title: Account Recovery
category: features
subcategory: teacher-settings
roles: [teacher]
description: Step-by-step instruction guide for the teacher account recovery workflow.
keywords: [account recovery, teacher, TOTP, student-assisted, recovery code, reset]
related:
  - user-guides/diagnostics/teacher-login
---

# Teacher Account Recovery — Instruction Guide

Teacher accounts use a student-assisted recovery method instead of email or phone verification. This guide walks through every phase of the recovery workflow.

---

## Part 1 — Set Up Recovery (One-Time Prerequisite)

Before recovery can be used, you must register your date of birth. This is a one-time action. Accounts created before this feature was introduced will see a **Setup Account Recovery** prompt on the dashboard.

**Where to work:** Go to **Settings > Account Recovery**, or follow the prompt on your dashboard.

**Steps:**
1. Select your date of birth using the date picker.
2. Click **Save & Enable Recovery**.
3. A confirmation message appears: *Recovery setup complete!*

Your date of birth is processed into a one-way hash and stored securely. The original value cannot be retrieved from the stored hash.

> **If you skip this step**, self-service recovery will not be available. You will need to contact your system administrator if you lose access.

---

## Part 2 — Self-Service Recovery (Student-Assisted)

Use this flow when you cannot log in and need to reset your username and TOTP authenticator. You must have completed Part 1 first.

### Phase 1 — Initiate the Recovery Request

1. Navigate to the **Account Recovery** page.
   - From the login page, look for the recovery link, or go directly to `/admin/recover`.
2. In the **Student Usernames** field, enter one student username from **each class period** you teach, separated by commas.
   - Example: `swift_eagle, silver_fox, bright_comet`
   - You must include at least one student from every active period. Missing any period will block the request.
3. Select your **Date of Birth** using the date picker.
4. Click **Verify Identity**.

On success, a recovery request is created that expires in **5 days**. You are redirected to the Recovery Status page.

> **Rate limit:** This step is limited to 5 attempts per hour to prevent brute-force attacks on your date of birth.

### Phase 2 — Students Generate Recovery Codes

Each student you named must log in and generate a 6-digit recovery code.

1. Ask each selected student to log in to their account.
2. Each student navigates to their **Account** or recovery section and generates their code.
3. Collect the 6-digit code from each student in person or over a secure channel.

The Recovery Status page shows how many students have verified so far. All selected students must generate codes before you can proceed.

### Phase 3 — Enter Recovery Codes and New Username

1. Go to the **Recovery Status** page (`/admin/recovery-status`).
2. Once all students show as verified, click **Reset Credentials**.
3. On the Reset Credentials page, enter:
   - Each student's **6-digit recovery code** in the corresponding field.
   - Your desired **new username**.
4. Click **Submit**.

> **Security note:** Any failed submission (wrong code, wrong count, or invalid format) immediately invalidates **all** codes. Your students must generate new codes before you can try again.

### Phase 4 — Scan New TOTP QR Code

If the codes match, a new TOTP QR code is displayed.

1. Open your authenticator app (Google Authenticator, Authy, or similar).
2. Scan the QR code, or manually enter the secret shown below it.
3. A 6-digit TOTP code appears in your authenticator app.

### Phase 5 — Confirm and Complete

1. Enter the **6-digit TOTP code** from your authenticator app into the confirmation field.
2. Click **Confirm Reset**.
3. On success, you see: *Your account has been successfully reset! Please log in with your new username and TOTP.*
4. Log in using your new username and the TOTP codes from your newly registered authenticator.

---

## Saving and Resuming Partial Progress

If you cannot collect all student codes at once, you can save progress and resume later.

**To save progress:**
1. On the Reset Credentials page, enter the codes you have so far and your desired new username.
2. Click **Save Progress**.
3. A **6-digit resume PIN** is displayed. Write it down and keep it safe.

**To resume:**
1. Navigate to `/admin/resume-credentials`.
2. Enter your 6-digit resume PIN.
3. Your saved codes and username are restored. Continue collecting the remaining codes and submit.

> The recovery request expires in 5 days from creation. Saved progress is also lost when the request expires.

---

## Part 3 — System Admin-Assisted Recovery

If you did not set up recovery (Part 1 was never completed), or if you need help, a system administrator can reset your TOTP secret directly.

**What the system admin does:**
1. Navigates to the system admin portal.
2. Goes to **Manage Teachers** and locates your account.
3. Clicks **Reset TOTP** on your account row.
4. A new QR code is generated and provided to you.

**What you do:**
1. Scan the QR code in your authenticator app.
2. Log in with your existing username and the new TOTP codes.

Contact your system administrator if self-service recovery is not available to you.

---

## Security Details

| Detail | Value |
|---|---|
| Recovery request validity | 5 days |
| Failed code attempt | Invalidates **all** codes immediately |
| Initiation rate limit | 5 attempts per hour |
| Reset steps rate limit | 10 attempts per hour |
| Date of birth storage | One-way HMAC hash (not reversible) |

---

## Troubleshooting

**"You must select at least one student from each of your active periods."**
Add one username from the missing period(s) listed in the error and resubmit.

**"Unable to verify your identity."**
The date of birth entered does not match the stored hash. Verify you selected the correct date.

**"All codes have been invalidated."**
A wrong code was entered. Ask all selected students to regenerate their codes, then return to Phase 3.

**"You already have an active recovery request."**
An unexpired request already exists. Check the Recovery Status page or wait for it to expire before starting a new one.

**"Teacher account not configured for recovery."**
Your account does not have a date of birth on file. Contact your system administrator for a TOTP reset (Part 3).

**Recovery request expired before completion.**
Start a new recovery request from the beginning. Recovery requests expire after 5 days.

---

## Related guides
- [Teacher Login Diagnostics](/docs/user-guides/diagnostics/teacher-login)

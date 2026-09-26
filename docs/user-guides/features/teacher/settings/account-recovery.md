---
title: Account Recovery
category: features
subcategory: teacher-settings
roles: [teacher]
description: How student-assisted teacher account recovery works, and how to run it if you lose access.
keywords: [account recovery, teacher recovery, recovery codes, resume pin, lost access, totp reset]
related:
  - user-guides/diagnostics/teacher/login
  - user-guides/features/teacher/settings/passkey
---

# Account Recovery

## Overview

Classroom Token Hub does not store your email address, phone number, or date of birth. That means there is no reset link to send you. Instead, your students vouch for you.

If you lose access, you name one student from each class you teach. Those students log in, confirm their own passphrase, and each receives a **6-digit recovery code**. You collect the codes from them in person and enter all of them together to reset your credentials.

There is nothing to configure in advance. Recovery is active on your account by default.

## Step-by-step instructions

### The "Setup Account Recovery" banner

If your dashboard shows an **Action Required: Setup Account Recovery** banner, select **Setup Now**. The page explains that recovery runs on your class context and the student verification workflow, and that no extra personal information is needed. Select **Confirm & Return to Dashboard** to dismiss it.

Nothing is collected. The banner is an acknowledgement, not a form.

### Security requirement: at least 3 claimed students in every class

Student-assisted recovery works only when **every class you teach has at least 3 students who have claimed their accounts**.

Recovery randomly selects 2 students in each class to confirm it is you. If a class had only 2 students, anyone who knew that class would know exactly who gets picked. Requiring 3 keeps the selection unpredictable. Until every class reaches 3, recovery cannot start for your account at all.

The Student Management page warns you while the active class is below 3. Have students claim their accounts early in the term, before you might need recovery.

### Recovering your account

You do this from the login page, not from inside the app.

1. Go to the teacher login page and choose **Account Recovery**.
2. For each class you teach, enter rows of **Join Code** and **Student Username** from that class, one student per row. Use **+ Add another row** to add rows. How many students per class depends on how many classes you teach: 6 for one class, 3 each for two, 2 each for three, and 1 each for four or more. If a class has fewer students with claimed accounts than that, enter all of them. Each student username can be used only once, even if that student is in more than one of your classes.
3. Select **Verify Identity**.

Every class must be included and every entry must check out. If anything is wrong, recovery does not start and the page does not say which entry failed. The students you enter only prove you know your classes; they are not the students who help you next.

### What happens next

Classroom Token Hub randomly selects 2 students in each class. They see a recovery prompt in the app. You are not told who they are, and they stay the same for this recovery attempt, which lasts five days.

A selected student enters their own passphrase and gets a 6-digit code that lasts 30 minutes. Students are told to hand over a code only in person, while you are with the class. One code per class is enough.

See [Verify a Teacher Recovery Request](../../student/account/verify-teacher-recovery.md) for the student's view.

### Entering the codes

On the **Account recovery** page, save one code for each class as you collect it. The page confirms a code was received but never says whether it is correct. When every class has a code, enter your new username and select **Submit complete code set**. You get one overall result. If it fails, collect fresh codes for every class and try again.

### Saving your progress

Select **Get a PIN to resume later** to receive a 6-digit **Resume PIN**, shown **once**. Write it down immediately.

To come back later: go to the teacher login page, choose **Resume Recovery**, and enter the PIN. Codes you already saved stay accepted.

## Important notes

> [!WARNING]
> **One wrong code invalidates all of them.** If a code is mistyped, malformed, or you enter the wrong number of codes, every code in the request is destroyed and all of your students must verify again from scratch. Check each code carefully before submitting.

> [!IMPORTANT]
> **Codes must be handed over in person.** The whole point of the design is that someone who has stolen your password cannot also stand in your classroom. Do not ask students to text, email, or message you a code.

> [!IMPORTANT]
> **Recovery requests expire.** Both the request and the Resume PIN carry an expiry date shown on screen. Past that point you start over.

> [!WARNING]
> **Every class needs at least 3 students with claimed accounts.** This is a deliberate security requirement, not a setup step you can skip. If any class you teach has fewer than 3, recovery cannot start for your account. Check the Student Management page for each class.

> [!TIP]
> The most reliable time to run recovery is during class, when the selected students are in the room and can give you a code on the spot.

## Related guides

- [Verify a Teacher Recovery Request (Student)](../../student/account/verify-teacher-recovery.md)
- [Passkey and Login Security](passkey.md)
- [Login and Account Security Troubleshooting](../../../diagnostics/teacher/login.md)

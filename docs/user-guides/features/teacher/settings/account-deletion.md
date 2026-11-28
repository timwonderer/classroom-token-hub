---
title: Account Deletion
category: features
subcategory: teacher-settings
roles: [teacher]
description: Permanently delete your own teacher account and every class you own.
keywords: [account deletion, delete account, close account]
related:
  - user-guides/diagnostics/teacher/login
---

# Account Deletion

## Overview
You can permanently delete your own teacher account. Nobody reviews or approves it: deletion starts as soon as you finish the confirmation steps, and there is no grace period, archive or way to undo it.

Deleting your account deletes **every class you own**, along with its students, transactions and purchase history. A student account that also belongs to another teacher's class is kept; a student who exists only in your classes is deleted too.

To remove a single class instead, use **Class Tools > Delete Class**. Your account is not affected there.

## Step-by-Step Instructions

1. Export anything you still need. Nothing can be retrieved afterwards, not by you and not by support.
2. Open **Settings > Account Deletion** in the teacher sidebar.
3. Read the warning and select the delete button.
4. Complete the confirmation steps:
   - wait for the 30-second countdown;
   - type the confirmation phrase shown on screen by hand;
   - press and hold the button for ten seconds.

   You can back out at any point before the hold completes.
5. When deletion finishes you are signed out and returned to the sign-in page.

## Important Notes
> [!CAUTION]
> **This cannot be undone.** Your classes, students and records are permanently deleted the moment you confirm.

- **One thing is kept.** Each token transaction wrote a tamper-evident audit entry when it happened. Those entries cannot be edited or deleted by anyone. They hold identifiers and cryptographic digests, not names, credentials or readable transaction details.
- **Account deletion stays available while your sign-in is incomplete.** If the site is asking you to register a passkey or replace your authenticator app, you can still reach this page.
- **If deletion stops with an error,** your account, classes and records are kept. Deletion removes your passkeys from the passkey service first, so if it stopped after that step, your passkeys may no longer work. Sign in with your authenticator app instead, then try the deletion again later.

## Related guides
- [Login and Account Security Troubleshooting](../../../diagnostics/teacher/login.md)

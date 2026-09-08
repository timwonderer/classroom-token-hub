---
title: PIN vs Passphrase
category: features
subcategory: student-account
roles: [student]
description: Which of your two credentials each action asks for, why the app has both, and what to do if one stops working.
keywords: [PIN, passphrase, credentials, confirm, transfer, purchase, start work, recovery, security]
related:
  - user-guides/features/student/account/login-setup
  - user-guides/features/student/account/reset-recovery
  - user-guides/diagnostics/student/login
---

# PIN vs Passphrase

## Overview

You have two credentials, and the app asks for different ones in different places. That is deliberate, not a bug: your **PIN** is short and typed constantly, your **passphrase** is long and typed rarely.

The rule behind the split is roughly *how much damage could someone do*. Clocking in is annoying to undo. Emptying your checking account is not.

## Step-by-step instructions

### What each one is

| | PIN | Passphrase |
| --- | --- | --- |
| **Looks like** | 4–6 digits | At least four words, with numbers and symbols |
| **Typed** | Many times a day | A few times a term |
| **Job** | Proving it's still you at this device | Proving it's really you |

You set both when you first claim your account. See [Log In and First-Time Setup](login-setup.md).

### Which action asks for which

| What you're doing | What it asks for |
| --- | --- |
| Signing in | Username + **Passphrase** |
| **Start Work** | **PIN** |
| **Done for the day** | **PIN** |
| Using an item you already own | **PIN** |
| Buying something in the store | **Passphrase** |
| Moving money between checking and savings | **PIN** |
| Verifying your teacher's recovery request | **Passphrase** |
| Requesting a hall pass | Neither |
| Paying a rent bill | **Passphrase** |
| Buying insurance | **Passphrase** |
| Cancelling insurance | **Passphrase** |

The pattern worth remembering: **non-monetary or reversible actions use the PIN; account authentication and irreversible expense actions use the passphrase.** Hall-pass use is the exception among entitlements and uses the PIN.

### If one of them stops working

- **Passphrase rejected at sign-in.** Ask your teacher to reset it. They can do this from your student page without knowing your old one.
- **Passphrase rejected at a purchase or transfer.** Check capitalisation and spacing first — it is case-sensitive and the spaces between words count. If it is genuinely lost, see [Reset or Recover Your Account](reset-recovery.md).
- **You know both but the page keeps sending you back to sign in.** That is a session timeout, not a credential problem. Sign in again.

## Important notes

> [!WARNING]
> **Buying insurance asks for your passphrase.** The **Buy — $X** form commits you to a recurring premium only after the passphrase is verified. Cancelling remains confirmation-only because it stops renewal rather than taking a new payment.

> [!IMPORTANT]
> **Never tell anyone your passphrase, including someone claiming to be your teacher.** Your teacher never needs it. The one time they ask you to *use* it — verifying a recovery request — you type it into your own screen yourself and hand over a code instead. See [Verify a Teacher Recovery Request](verify-teacher-recovery.md).

> [!NOTE]
> **Sharing your PIN is not harmless.** Someone with your PIN can clock you out, mark you done for the day, and burn items you paid for. They cannot drain your balance, which is exactly why the passphrase exists.

> [!TIP]
> Pick a passphrase you can type from muscle memory rather than one you have to reconstruct. Four ordinary words in an order that means something to you beats one clever word with symbols wedged into it.

## Related guides

- [Log In and First-Time Setup](login-setup.md)
- [Reset or Recover Your Account](reset-recovery.md)
- [Verify a Teacher Recovery Request](verify-teacher-recovery.md)
- [Troubleshooting Login and Setup](../../../diagnostics/student/login.md)

---
title: Security: Passkeys and Authenticator App
category: features
subcategory: teacher-settings
roles: [teacher]
description: Register and delete passkeys, replace your authenticator app, and what to do when the site sends you to the Security page.
keywords: [passkey, security, login, authenticator, TOTP]
related:
  - user-guides/diagnostics/teacher/login
---

# Security: Passkeys and Authenticator App

## Overview
Every teacher account needs two things to use the site: at least one **passkey** and an **authenticator app** with a strong enough key. A passkey lets your device (fingerprint, face, PIN or a security key) sign you in without a password; the authenticator app gives you the six-digit codes you use to sign in with your username and to approve passkey changes.

The **Security** page has two tabs, **Passkeys** and **Authenticator app**.

## If you are sent to the Security page
If your account has no passkey, or your authenticator app uses a key that is too short, every page except Security, **Account Deletion** and sign out takes you to **Security** with a message that says what to do. Nothing is lost: finish the step below and your classes are right where you left them.

- **No passkey:** the **Passkeys** tab opens. Register one (below). You sign in again when it is done.
- **Authenticator key too short:** the **Authenticator app** tab opens. Replace your authenticator app (below). You sign in again when it is done.

If you have both problems you are asked for the passkey first, because a passkey is the proof that replacing the authenticator app needs.

## Step-by-Step Instructions

### Registering a passkey
1. Open **Settings > Security** in the teacher sidebar. The **Passkeys** tab is selected.
2. Select **Register New Passkey** and give it a name you will recognise, such as "work laptop".
3. Enter the current 6-digit code from your authenticator app when the box asks for it.
4. Follow your browser's prompt (Touch ID, Face ID, Windows Hello or a security key). You are signed out when it is done; sign in again.

### Deleting a passkey
1. On the **Passkeys** tab, find the passkey and select **Delete**, then confirm.
2. Enter the current 6-digit code from your authenticator app when the box asks for it. You are signed out when it is done.

You cannot delete your only passkey: add another one first. Deleting a passkey here does not remove it from your device; clear it in your device or password manager settings as well.

### Replacing your authenticator app
Use this when you get a new phone, or when the site tells you your authenticator key is too short. You need a registered passkey.
1. Open **Settings > Security** and select the **Authenticator app** tab.
2. Select **Replace authenticator app**.
3. Approve with one of your passkeys when your browser asks.
4. Scan the QR code with your new authenticator app, or type in the key shown. It appears only once.
5. Enter the 6-digit code from the new app and select **Confirm and replace**, then sign in again with the new app.

Your old authenticator keeps working until step 5 succeeds. If you cancel, enter a wrong code, or wait more than ten minutes, nothing changes. If you have no working passkey, use account recovery instead.

## Important Notes
> [!IMPORTANT]
> **Redundancy:** Register at least two passkeys (for example your phone and your main computer) so a broken device does not lock you out. If every passkey and your authenticator app become unavailable, account recovery is the only way back in.

> [!NOTE]
> After account recovery your account has a new authenticator app and no passkeys, so you are taken to the **Passkeys** tab to register one.

## Related guides
- [Login and Account Security Troubleshooting](../../../diagnostics/teacher/login.md)

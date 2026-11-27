---
title: Passkey and Login Security
category: features
subcategory: teacher-settings
roles: [teacher]
description: Manage passkeys and login security.
keywords: [passkey, security, login]
related:
  - user-guides/diagnostics/teacher/login
---

# Passkey and Login Security

## Overview
Passkeys offer a secure, passwordless way to authenticate your teacher account using your device's built-in biometrics or security pin.

## Step-by-Step Instructions

### Managing Passkeys
1. Navigate to **Settings > Passkey** in the teacher sidebar.
2. To add a new device (like a laptop or phone), select **Register New Passkey** and follow your browser's security prompts.
3. To remove access from an old or lost device, find it in the list of registered passkeys and click **Delete**.

### Replacing Your Authenticator App
Use this when you get a new phone or lose access to your authenticator app, as long as you still have a registered passkey.
1. In **Settings > Passkey**, find **Authenticator app** and select **Replace authenticator app**.
2. Approve with one of your passkeys when your browser asks.
3. Scan the QR code with your new authenticator app, or type in the key shown. It appears only once.
4. Enter the 6-digit code from the new app and select **Confirm and replace**, then sign in again.

Your old authenticator keeps working until step 4 succeeds. If you cancel, enter a wrong code, or wait more than ten minutes, nothing changes. If you have no working passkey, use account recovery instead.

## Important Notes
> [!IMPORTANT]
> **Redundancy:** Always attempt to register at least two passkeys (e.g., your phone and your primary computer) to ensure you are not locked out if one device breaks.

## Related guides
- [Login and Account Security Troubleshooting](../../../diagnostics/teacher/login.md)

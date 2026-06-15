---
title: Security and Access Management
category: features
subcategory: sysadmin
roles: [sysadmin]
description: Guide to managing security settings, passkeys, and administrator access.
keywords: [sysadmin, security, passkeys, totp, admins, 2fa, authentication]
---

# Security and Access Management

## Overview
Maintaining platform security is a critical sysadmin responsibility. This feature allows you to manage authentication (Passkeys and TOTP) for both yourself and other administrators to ensure secure access.

## Step-by-Step Instructions

### Registering a New Passkey
1. Navigate to **Manage Security** in the sidebar.
2. Select **Register New Passkey**.
3. Follow your browser's prompts to create and save the secure passkey to your device.

### Resetting Administrator 2FA (TOTP)
If another admin loses their authenticator app or device, they will be locked out and require a reset.
1. Verify the administrator's identity out-of-band (e.g., via a known phone number or in person).
2. Navigate to **Manage Admins** in the sidebar.
3. Locate their account in the admin list.
4. Select **Reset TOTP**. This clears their current 2FA settings and forces them to re-enroll on their next login.

### Revoking Administrator Access
1. Navigate to **Manage Admins**.
2. Locate the administrator.
3. Select **Delete** next to their name to revoke their access.

## Important Notes
> [!IMPORTANT]
> Currently, new admins must be added via direct database insertion or the command-line interface. They cannot be created via the web UI.

> [!TIP]
> Encourage all administrators to register at least two passkeys (e.g., a phone and a laptop) to prevent lockouts.

> [!CAUTION]
> Never share the Sysadmin Registration Phrase. If compromised, it must be rotated immediately via environment variables.

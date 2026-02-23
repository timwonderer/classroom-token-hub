---
title: Teacher Login and Account Security
category: diagnostics
roles: [teacher]
related:
  - user-guides/diagnostics/teacher-onboarding
  - user-guides/features/teacher/settings/account-recovery
---

# Login and Account Security

## If you cannot log in, check these first
- Username and TOTP code must match exactly.
- Your authenticator clock is accurate (time drift breaks TOTP).
- Too many attempts can trigger a short rate limit.

## If you lost access to your authenticator app
- Use the student-assisted recovery flow if you previously set up account recovery.
- See the full steps in [Teacher Account Recovery](/docs/user-guides/features/teacher/settings/account-recovery).
- If recovery was never set up, contact your system administrator for a TOTP reset.

## If you cannot sign up
- An invite code is required for first-time admin registration.
- Date of birth must be entered in the expected format on the signup form.

## This is expected when...
- Passkeys are optional and only available after initial signup.
- Recovery requests require student verification before credential reset.

## This cannot happen unless...
- You log in without TOTP unless a passkey is already configured.

## Quick evidence to collect
- The exact error message and the time shown on your authenticator app.
- Whether you are using the correct invite code.

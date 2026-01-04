---
title: Teacher Login and Account Security
category: diagnostics
roles: [teacher]
related:
  - diagnostics/teacher-onboarding
---

# Login and Account Security

## If you cannot log in, check these first
- Username and TOTP code must match exactly.
- Your authenticator clock is accurate (time drift breaks TOTP).
- Too many attempts can trigger a short rate limit.

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

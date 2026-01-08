# Release Notes - Version 1.5.0

**Release Date**: December 29, 2025  
**Focus**: Issue reporting lifecycle, security hardening, and operational polish

---

## Highlights

- Added issue reporting with escalation and resolution workflows for students and teachers
- Expanded issue reporting to attendance/tap events and transaction histories
- Shipped security remediation tooling and documented a comprehensive attack surface audit
- Standardized UTC timestamp formatting and improved admin command ergonomics
- Refreshed documentation structure and updated key dependencies

---

## New and Notable

### Issue Reporting and Resolution
- Added attendance issue reporting to help students and teachers flag and track issues.
- Implemented issue resolution and escalation workflows.
- Refined issue management and refreshed related UI flows.
- Expanded transaction issue reporting to all visible transaction rows on the Banking/Finances page.

### Security Remediation and Audit
- Disabled a vulnerable AI inference workflow after identifying a PromptPwnd prompt injection risk.
- Added remediation guidance, fixed workflow templates, and an SSH security setup script.
- Published a comprehensive attack surface audit with findings and recommendations.

### Privacy and Security Guardrails
- Removed `unsafe-eval` from the Content Security Policy to harden XSS protections.
- Added CSP allowances for `https://static.cloudflareinsights.com` and `worker-src 'self' blob:` to support analytics and Web Workers safely.
- Preserved privacy for issue resolution with opaque student references and teacher-controlled disclosure to sysadmins.

### Time Handling and Admin Quality
- Standardized UTC timestamp formatting for clearer audit trails.
- Fixed System Admin announcements form error by adding a custom `coerce` for `target_teacher`.
- Improved `flask create-sysadmin` to show a one-time TOTP QR code and secret, then clear the terminal.

### Documentation and Dependencies
- Reorganized documentation for improved navigation.
- Updated dependencies: `requests` 2.32.4 to 2.32.5, `markdown` 3.7 to 3.10, and `webfactory/ssh-agent` 0.9.0 to 0.9.1.

---

## Fixes

- Transaction issue reporting now covers all visible transactions on the Banking/Finances page.
- Issue resolution display now renders `developer_resolved` correctly in teacher view.
- Issue context snapshot now uses `get_checking_balance()` and `get_savings_balance()` for accuracy.
- Passkey authentication now includes the username parameter to avoid 500 errors.
- Passkey registration now extracts the credential ID from `{ token, error }` correctly.
- `time.tzset()` now guards for Windows compatibility.
- Admin signup now handles SQLite datetime strings safely.

---

## Upgrade Notes

1. Follow the standard deployment process (pull latest, install dependencies, run migrations if applicable).
2. Review the security remediation guidance in `docs/security/SECURITY_REMEDIATION_GUIDE.md`.
3. Validate any internal workflow references to AI inference jobs, as the vulnerable workflow is disabled.

---

## Testing and Validation

- No new release-specific test guidance provided; run the standard test suite for your environment.

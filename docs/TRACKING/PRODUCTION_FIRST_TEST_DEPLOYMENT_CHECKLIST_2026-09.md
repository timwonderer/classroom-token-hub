# Production First-Test Deployment Checklist

**Scope:** move the currently cleared production host from the v1/v2-empty state to the first controlled test deployment of the complete v2 application.

**This is not launch certification.** The goal is to prove that the full application can be installed, booted, migrated, and exercised on the production host under maintenance control.

## Current state

- [x] Production host inspected: `app-server` via the approved Tailscale/SSH path.
- [x] v1 application process stopped; `classroom-economy.service` and `gunicorn.service` disabled.
- [x] v1 database `classroom_db` dropped by explicit owner direction.
- [x] Empty v2 database `classroom_economy` dropped by explicit owner direction.
- [x] PostgreSQL service left installed and running.
- [x] Nginx transition redirect left active as a holding page.
- [ ] Old v1 checkout and old runtime configuration replaced by the approved v2 installation.

## 1. Release and authority gate

- [ ] Confirm the intended v2 deployment branch is the repository `main` branch.
- [ ] Confirm the exact 40-character v2 commit SHA to test.
- [ ] Confirm that SHA is an ancestor of the configured production release-lineage ref.
- [ ] Confirm the working tree and release SHA contain no unapproved local changes.
- [ ] Confirm migration head count is exactly one on the release artifact.
- [ ] Confirm migration safety checks pass on the release artifact.
- [ ] Record the SHA, branch, migration head, operator, verifier, and test window.

## 2. Production runtime preparation

- [ ] Put the domain in maintenance/holding mode and confirm the public maintenance response.
- [ ] Replace the v1 checkout with the approved v2 checkout at the exact release SHA.
- [ ] Create or refresh the v2 virtual environment using the pinned requirements.
- [ ] Install dependencies without changing the release artifact.
- [ ] Install the v2 systemd unit with an explicit protected environment source.
- [ ] Ensure the service uses the intended bind address, worker count, timeout, logging, and restart policy.
- [ ] Run `systemctl daemon-reload` and verify the unit does not start before configuration validation.

## 3. Production environment and secrets

Provision values through the approved secret-management path or a root-owned service environment file with mode `600`. Do not copy the local `.env` wholesale and do not commit or print values.

- [ ] `SECRET_KEY` — new, high-entropy, production-specific value.
- [ ] `ENCRYPTION_KEY` — production PII-encryption key with controlled custody.
- [ ] `PEPPER_KEY` — production lookup-HMAC key, independent from all other keys.
- [ ] `AUDIT_HMAC_KEY` — production audit-lineage key, independent from all other keys.
- [ ] `DATABASE_URL` — points only to the new v2 production database.
- [ ] `FLASK_ENV=production`.
- [ ] `FLASK_APP` — confirmed for the v2 entry point if required by CLI operations.
- [ ] `PASSWORDLESS_API_KEY` and `PASSWORDLESS_API_PUBLIC` — production pair.
- [ ] `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY` — production pair, registered for the production domains.
- [ ] `REDIS_URL` or the explicitly approved production rate-limit storage configuration.
- [ ] `CSRF_SECRET_KEY` if required by the production security configuration.
- [ ] `SUPPORT_EMAIL`, `MARKETING_SITE_URL`, `EXTERNAL_DOCS_BASE_URL`, and status/operations URLs.
- [ ] Required maintenance/status variables for the test window.
- [ ] Confirm no test, development, red-team, fallback, or local database values are present.
- [ ] Confirm the service identity can read the environment and no other identity can read it.
- [ ] Restart only after the environment completeness check passes.

## 4. Fresh database creation and migration

- [ ] Create one empty PostgreSQL database with the approved production owner.
- [ ] Confirm the database name and connection target do not resolve to a local, test, or legacy database.
- [ ] Confirm PostgreSQL version and required extensions match the migration rehearsal.
- [ ] Confirm no application service is writing to the database before migration.
- [ ] Run `flask db upgrade` using the exact release artifact and production `DATABASE_URL`.
- [ ] Confirm `flask db current` reports the expected single head.
- [ ] Run the repository migration validation evidence required by the release gate.
- [ ] Confirm the schema contains no v1-only database objects that v2 does not own.
- [ ] Record migration output and database revision in the transition record.

## 5. Application start and health checks

- [ ] Start the v2 service under maintenance mode.
- [ ] Confirm `systemctl is-active classroom-economy`.
- [ ] Confirm the service logs contain no missing-key, database, Redis, import, or migration errors.
- [ ] Confirm `/health` returns the expected healthy response.
- [ ] Confirm `/health/deep` reports the expected operational/integrity state.
- [ ] Confirm Nginx proxies to the v2 service only after local health passes.
- [ ] Confirm HTTPS certificate, host routing, and security headers.

## 6. Full-app first test

Use a real browser against the production test deployment while maintenance remains controlled until the critical paths pass.

- [ ] `/admin/login` renders and submits successfully.
- [ ] `/student/login` renders and submits successfully.
- [ ] Passwordless enrollment/authentication works with production credentials.
- [ ] Turnstile widget renders on every configured route and real verification succeeds.
- [ ] Teacher can create or access a class boundary.
- [ ] Student seat claim and student session work.
- [ ] Teacher current-class switching works.
- [ ] Student add-class and switch-class flows work.
- [ ] Class-scoped admin actions cannot cross the selected class boundary.
- [ ] Attendance, productivity, payroll, obligations, ledger, and store paths load and execute through their canonical routes.
- [ ] Required audit/lineage records are produced for protected mutations.
- [ ] Export and support/operations surfaces load without 500 responses.
- [ ] No PII appears in URLs, logs, errors, or browser-visible diagnostic output.
- [ ] Accessibility smoke checks cover the public, login, teacher, and student surfaces reached in this test.

## 7. Decision and rollback

- [ ] Independent verifier reviews service, database, browser, and security evidence.
- [ ] If migration or boot fails, keep maintenance active and stop; do not retry blindly.
- [ ] If the application fails after migration, choose approved fix-forward or restore based on evidence.
- [ ] Do not use `alembic downgrade` as automatic production recovery.
- [ ] Record exact SHA, database revision, health output, browser results, failures, and operator decision.
- [ ] Reopen traffic only after the test decision is explicitly recorded.

## Completion condition

The first test deployment is complete only when the exact v2 SHA is running from a fresh database, the required production integrations work, the named full-app browser paths have evidence, and the operator/verifier decision is recorded. A successful boot or targeted test alone is not launch certification.

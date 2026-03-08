---
title: Deployment Guide
category: operations
roles: [developer, teacher]
---

# Deployment Guide

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-006      | 1.1     | 2026-03-08     | 1.0        | Normative       |

This guide provides the current top-level deployment contract for v2.0 live-test readiness. Use it with:

- `SOP-DEP-022_V2_Live_Test_Runbook.md`
- `SOP-DEP-023_V2_Production_Transition_Runbook.md`

## Environment Variables

Required:

- `SECRET_KEY`
- `DATABASE_URL`
- `FLASK_ENV`
- `ENCRYPTION_KEY`
- `PEPPER_KEY`
- `CSRF_SECRET_KEY`

## Database Truth

- Dev and migration rehearsal DB:
  - use the team-configured v2 dev database
- Test DB:
  - use the team-configured PostgreSQL test database

## Standard Deploy Flow

1. Install dependencies.
2. Confirm branch and database target.
3. Run migration rehearsal or production transition checklist as appropriate.
4. Apply migrations with `flask db upgrade`.
5. Start the application server.
6. Run smoke checks.

## Maintenance Mode

Maintenance mode is persistent across code deploys and must be turned on and off intentionally. Use it during production transition and any migration that needs a protected validation window.

## Reset Warning

Do not use schema-drop reset instructions for live-test or production-like environments. Database reset remains a local-development escape hatch only.

## CI/CD

The deployment workflows are defined in the repo workflows. For v2.0 readiness, operator-owned runbooks take precedence over generic deployment steps.

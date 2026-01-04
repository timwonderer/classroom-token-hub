---
title: Architecture Guide
category: technical-reference
roles: [developer]
---

# Classroom Token Hub - Architecture Guide

Last Updated: 2026-01-03
Purpose: Describe the current system architecture, data boundaries, and core flows.

## What This Document Covers

- The runtime shape of the application (Flask app, blueprints, data stores).
- The boundary between roles (student, teacher, system admin).
- The data model patterns that must stay consistent (ledger, join codes, scoping).
- Where to look for deeper references (schema, API, timezone, economy spec).

## System Overview

Classroom Token Hub is a Flask web application with a server-rendered UI and a JSON API.
It models a classroom economy with attendance, payroll, store purchases, rent, insurance,
and hall passes. The system is designed for multi-class isolation using join codes.

High-level components:
- Flask app factory in `app/__init__.py`.
- Blueprints in `app/routes/` for role-specific pages and API endpoints.
- SQLAlchemy models in `app/models.py` with Alembic migrations.
- Jinja2 templates in `templates/` and static assets in `static/`.
- Background jobs in `app/scheduled_tasks.py`.

## Request and Data Flow

Typical request flow:
- Browser -> Flask route -> SQLAlchemy -> Jinja template or JSON response.
- Role checks happen in `app/auth.py` decorators.
- Financial changes always create `Transaction` rows.

Key flows:
- Attendance: tap in/out creates `TapEvent` rows, payroll converts those into `Transaction` rows.
- Store: purchases create `StudentItem` and `Transaction` rows, redemptions are state transitions.
- Hall passes: approvals generate a pass number and create attendance tap-out/tap-in records.
- Rent and insurance: settings are per teacher and per block, charges are recorded in transactions.

## Code Structure (Current)

```
classroom-economy/
- app/
  - __init__.py           # App factory, config, maintenance gate
  - auth.py               # Session and role guards
  - extensions.py         # db, migrate, csrf, limiter
  - models.py             # SQLAlchemy models
  - routes/               # Blueprints
    - admin.py
    - student.py
    - system_admin.py
    - main.py
    - api.py
    - docs.py
  - scheduled_tasks.py    # Periodic jobs
  - utils/                # Shared helpers
- templates/              # Jinja templates
- static/                 # CSS, JS, images
- migrations/             # Alembic migrations
- docs/                   # Documentation
```

## Data Model Highlights

- Multi-class isolation relies on `join_code` as the source of truth.
  - A student can be linked to multiple teachers via `StudentTeacher`.
  - Many records include `join_code` and/or `teacher_id` to scope data safely.
- The transaction ledger is append-only.
  - Use `is_void` to negate mistakes, do not delete historical transactions.
- Attendance uses `TapEvent` as the canonical time log.
  - Payroll is derived from tap events, not the other way around.
- Feature gating is per period via `FeatureSettings`.
  - Period settings override global settings for a teacher.

## Authentication and Sessions

- Students authenticate with username + PIN. A passphrase is required for purchases and transfers.
- Teachers and system admins authenticate with TOTP; passkeys are available after initial registration.
- System admins have elevated visibility across teachers.
- Session timeouts are enforced in `app/auth.py` to reduce stale sessions.
- Turnstile is used on the student login flow to reduce bot abuse.

## Multi-Tenancy and Scoping Rules

- `join_code` is the primary scoping key for all student-facing data.
- `teacher_id` is secondary and used for compatibility with legacy records.
- Helper functions in student routes select the active class context.
- When querying or writing financial data, include `join_code` whenever possible.

## Security and Privacy Controls

- PII is encrypted at rest using `ENCRYPTION_KEY` and helpers in `app/utils/encryption.py`.
- Credentials are hashed with a per-user salt and `PEPPER_KEY`.
- CSRF protection is enabled via Flask-WTF.
- Rate limits are enforced via Flask-Limiter.
- Maintenance mode can gate access at the app level with explicit bypass controls.

## Background Jobs

- `enforce_daily_limits_job`: auto-tap out students who exceed daily limits.
- `cleanup_expired_demo_sessions_job`: removes expired demo students and related data.

## Related References

- Database schema: `docs/technical-reference/database_schema.md`
- API reference: `docs/technical-reference/api_reference.md`
- Timezone handling: `docs/technical-reference/TIMEZONE_HANDLING.md`
- Economy spec: `docs/technical-reference/ECONOMY_SPECIFICATION.md`
- Diagnostics for user-visible behavior: `docs/diagnostics/student.md`, `docs/diagnostics/teacher.md`
- Development practices: `docs/development/DEVELOPMENT.md`

## Full Documentation

For the complete documentation set, visit:
https://github.com/timwonderer/classroom-economy/tree/main/docs

# Claude Development Guide for Classroom Token Hub

This document provides essential guidance for Claude (or any AI assistant) working on the Classroom Token Hub project. Following these guidelines ensures consistency, prevents common pitfalls, and maintains the project's high standards.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Critical Rules](#critical-rules)
3. [Architecture Patterns](#architecture-patterns)
4. [Database Migrations](#database-migrations)
5. [Documentation Standards](#documentation-standards)
6. [Testing Requirements](#testing-requirements)
7. [Security Principles](#security-principles)
8. [Multi-Tenancy Scoping](#multi-tenancy-scoping)
9. [Common Pitfalls](#common-pitfalls)
10. [Workflow Checklist](#workflow-checklist)

---

## Project Overview

**Classroom Token Hub** is an educational banking simulation platform for teaching financial literacy in classrooms. It's built with Flask, SQLAlchemy, PostgreSQL, and follows a multi-tenant architecture where:

- **Teachers** manage multiple class periods via join codes
- **Students** can be enrolled in multiple periods with different teachers
- **System Admins** oversee the entire platform

**Version:** 1.9.x - Active maintenance (see CHANGELOG.md)
**License:** PolyForm Noncommercial 1.0.0
**Python:** 3.10+
**Database:** PostgreSQL with Alembic migrations

---

## Critical Rules

### 🚨 MUST FOLLOW EVERY TIME

1. **ALWAYS read existing code before proposing changes**
   - Never suggest modifications to files you haven't read
   - Understand context before making changes

2. **ALWAYS scope database queries by `join_code`**
   - Every query for student data MUST be scoped to the current class period
   - See `.claude/rules/multi-tenancy.md` for detailed rules

3. **ALWAYS create a migration for database schema changes**
   - Never modify models without creating a migration
   - See `.claude/rules/database-migrations.md` for the complete workflow

4. **ALWAYS update documentation when adding features**
   - Update CHANGELOG.md for all changes
   - Update relevant user guides and technical docs
   - See `.claude/rules/documentation.md` for standards

5. **ALWAYS write tests for new features**
   - Minimum: happy path + error cases
   - Include multi-tenancy scoping tests
   - See `.claude/rules/testing.md` for requirements

6. **NEVER commit secrets or PII**
   - Use environment variables for sensitive data
   - Encrypt PII at rest using the encryption utilities

7. **NEVER skip CSRF protection**
   - All forms must include CSRF tokens
   - All POST/PUT/DELETE routes must validate CSRF

---

## Architecture Patterns

### Blueprint Structure

The application uses Flask Blueprints for modular organization:

```
app/
├── routes/
│   ├── admin.py          # Teacher/admin routes
│   ├── analytics.py      # Teacher analytics dashboard + APIs
│   ├── student.py        # Student routes
│   ├── system_admin.py   # System admin routes
│   ├── api.py            # API endpoints
│   ├── docs.py           # In-app documentation browser
│   ├── main.py           # Public/site routes
│   └── recovery.py       # Student recovery flow
├── auth.py               # Auth helpers and scoped access helpers
├── models.py             # SQLAlchemy models (55+ runtime models)
├── services/             # Service-layer modules
├── utils/                # Utility and domain helpers
├── scheduled_tasks.py    # Background scheduler jobs
└── __init__.py           # App factory
```

### Key Files

- `wsgi.py` - Application entry point
- `app/forms.py` - WTForms form definitions
- `app/auth.py` - Admin/student access helpers and auth/session utilities
- `app/payroll.py` - Payroll automation logic
- `app/services/balance_service.py` - Balance settlement/read helpers
- `app/utils/analytics_engine.py` - Analytics computation backend
- `app/scheduled_tasks.py` - Hourly and nightly background jobs

### Database Models

**55+ SQLAlchemy models** including:
- Identity and access: `Admin`, `SystemAdmin`, `User`, `IdentityProfile`, `Seat`
- Class scope: `ClassEconomy`, `ClassMembership`, `TeacherBlock`, `StudentTeacher`, `JoinCode`
- Student runtime: `Student`, `StudentBlock`, `Announcement`, `FeatureSettings`, `TeacherOnboarding`
- Financial and attendance: `Transaction` (with `transfer_correlation_id`), `BalanceCache`, `PayrollSettings`, `PayrollCache`, `BankingSettings`, `TapEvent`, `HallPassLog`
- Rent and insurance: `RentSettings`, `RentPayment`, `RentWaiver` (with `join_code`), `RentItem`, `InsurancePolicy`, `StudentInsurance`, `InsuranceClaim`
- Store: `StoreItem` (with `collective_goal_expires_at`), `StudentItem`, `StoreItemBlock`
- Support and observability: `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`, `ErrorLog`, `ErrorEvent`, `ActorRequestTrace`, `UserReport`
- Analytics: `AnalyticsAlert`, `AnalyticsSnapshot`, `AnalyticsEvent`

See `docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md` for full schema reference.

---

## Database Migrations

**See `.claude/rules/database-migrations.md` for complete workflow.**

### Quick Reference

```bash
# ALWAYS follow this sequence:

# 1. Modify the model in app/models.py
# 2. Generate migration
flask db migrate -m "Description of change"

# 3. Review the generated migration file
# 4. Test the migration
flask db upgrade

# 5. Test the downgrade
flask db downgrade

# 6. Re-upgrade for production
flask db upgrade

# 7. Run tests
pytest tests/
```

### Migration Naming Convention

- `add_<field>_to_<table>` - Adding columns
- `create_<table>` - New tables
- `remove_<field>_from_<table>` - Removing columns
- `rename_<old>_to_<new>_in_<table>` - Renaming
- `add_<table>_<relationship>_relationship` - Adding relationships

### Common Migration Mistakes (DON'T DO THIS)

❌ Modifying models without creating migrations
❌ Editing old migration files after they're merged
❌ Creating migrations with generic names like "update database"
❌ Skipping migration testing before committing
❌ Forgetting to add foreign key constraints

---

## Documentation Standards

**See `.claude/rules/documentation.md` for complete standards.**

### Files to Update for New Features

1. **CHANGELOG.md** - All changes, following Keep a Changelog format
2. **DEVELOPMENT.md** - Add to roadmap or mark as completed
3. **README.md** - Update if it affects installation/quick start
4. **User guides** in `docs/user-guides/` - If user-facing
5. **Technical reference** in `docs/ARCHITECTURE/` - For architecture changes

### Documentation Organization

```
docs/
├── README.md                          # Documentation index
├── INV-CORE-000_Core_Invariants.md    # Foundational invariants (top-level authority)
├── INV-CORE-001_Authority_Model.md    # Authority hierarchy
├── user-guides/                       # Teachers, students, sysadmins
│   ├── README.md
│   ├── teacher_manual.md
│   ├── student_guide.md
│   ├── sysadmin_manual.md
│   ├── diagnostics/
│   ├── features/
│   └── legal/
├── ARCHITECTURE/                      # System design and data models
│   ├── ARC-CORE-000_Architecture_Foundation.md
│   ├── IDENTITY/                      # Identity and account-recovery specs
│   ├── OPERATIONS/                    # Database schema, API, migration specs
│   └── SYSADMIN/                      # Sysadmin interface design
├── FEATURES/                          # Feature specifications
│   ├── INSURANCE/
│   ├── RENT/
│   ├── HALL_PASS/
│   ├── ANALYTICS/
│   ├── ECONOMY/
│   └── SUPPORT/
├── SECURITY/                          # Security audits and controls
│   ├── AUDITS/
│   ├── CONTROLS/
│   ├── INCIDENTS/
│   └── THREATS/
├── STANDARD_OPERATING_PROCEDURES/     # Deployment, database, doc procedures
│   ├── DEPLOYMENT/
│   └── DATABASE/
├── LOGS/                              # Audit logs and release notes
│   ├── AUDITS/
│   └── RELEASES/
└── AUDITS/                            # Privacy and compliance audits
```

---

## Testing Requirements

**See `.claude/rules/testing.md` for complete requirements.**

### Test Coverage Rules

- **Every new route** must have at least one test
- **Every new model** must have CRUD tests
- **Every bug fix** must have a regression test
- **Multi-tenancy** features must have scoping tests

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_teacher_recovery.py

# Run with coverage
pytest --cov=app tests/

# Run tests matching pattern
pytest -k "recovery"
```

### Test Structure

```python
def test_feature_name(client, app):
    """Test description explaining what this verifies."""
    # Setup: Create necessary data

    # Execute: Perform the action

    # Assert: Verify expected behavior

    # Cleanup: Usually handled by fixtures
```

---

## Security Principles

**See `.claude/rules/security.md` for complete guidelines.**

### Critical Security Rules

1. **PII Encryption**
   - All student names encrypted at rest
   - Use `encrypt_value()` and `decrypt_value()` from `hash_utils.py`

2. **Password Security**
   - All passwords salted AND peppered
   - Use `hash_password()` and `verify_password()` from `hash_utils.py`

3. **TOTP 2FA**
   - All admin accounts require TOTP
   - Never store TOTP secrets in plaintext

4. **CSRF Protection**
   - All forms include `{{ form.csrf_token }}`
   - All POST/PUT/DELETE routes validate CSRF

5. **Input Validation**
   - Always validate and sanitize user input
   - Use WTForms validators
   - Never trust client-side validation alone

6. **SQL Injection Prevention**
   - Always use SQLAlchemy ORM, never raw SQL
   - If raw SQL is absolutely necessary, use parameterized queries

---

## Multi-Tenancy Scoping

**See `.claude/rules/multi-tenancy.md` for complete rules.**

### The Golden Rule

**EVERY query involving student data MUST be scoped by `join_code`.**

### Critical Context

- A **teacher** may teach multiple class periods
- A **student** may be enrolled in multiple periods (different teachers or same teacher)
- Each class period has a unique `join_code`
- `join_code` is the ABSOLUTE source of truth for data isolation

### Examples of Proper Scoping

```python
# ✅ CORRECT - ownership helper + class scope
students = (
    get_admin_student_query()
    .join(ClassMembership, ClassMembership.student_id == Student.id)
    .filter(ClassMembership.join_code == current_join_code)
    .all()
)

# ✅ CORRECT - Transaction scoped by join_code
transactions = Transaction.query.filter_by(
    join_code=current_join_code
).all()

# ❌ WRONG - teacher ownership alone is not class scope
students = get_admin_student_query().all()
```

### Tables That MUST Be Scoped

- `Student` (via `ClassMembership` plus route-specific class checks)
- `Transaction`
- `TapEvent`
- `PayrollSettings`
- `RentSettings`
- `BankingSettings`
- `FeatureSettings`
- `InsurancePolicy` (via `InsurancePolicyBlock`)
- `StoreItem` (via `StoreItemBlock`)
- All student-related data

---

## Common Pitfalls

### 1. Database Migration Issues

**Problem:** Modifying models without creating migrations, or creating broken migrations.

**Solution:**
- Always use the migration workflow in `.claude/rules/database-migrations.md`
- Test migrations before committing
- Never edit old migrations after they're merged

### 2. Multi-Tenancy Data Leaks

**Problem:** Queries returning data from other class periods.

**Solution:**
- Always scope queries by `join_code`
- Add multi-tenancy tests for every student-related feature
- Review `.claude/rules/multi-tenancy.md` before any student data query

### 3. Inconsistent Documentation

**Problem:** Features added without updating docs.

**Solution:**
- Update CHANGELOG.md for EVERY change
- Update relevant docs in `docs/` directory
- Check `.claude/rules/documentation.md` for what to update

### 4. Missing Tests

**Problem:** Features or bug fixes without test coverage.

**Solution:**
- Write tests BEFORE or WITH feature implementation
- Every bug fix needs a regression test
- See `.claude/rules/testing.md` for requirements

### 5. Security Vulnerabilities

**Problem:** Forgetting CSRF, exposing PII, or weak authentication.

**Solution:**
- Review `.claude/rules/security.md` before ANY auth/data handling code
- Use the existing encryption and hashing utilities
- Never skip CSRF protection

---

## Workflow Checklist

### For New Features

- [ ] Read existing relevant code
- [ ] Create/update database models if needed
- [ ] Generate and test migration
- [ ] Implement feature with proper scoping
- [ ] Add CSRF protection if needed
- [ ] Write comprehensive tests
- [ ] Update CHANGELOG.md
- [ ] Update relevant documentation
- [ ] Run full test suite
- [ ] Commit with descriptive message

### For Bug Fixes

- [ ] Identify root cause
- [ ] Write regression test that fails
- [ ] Implement fix
- [ ] Verify test now passes
- [ ] Run full test suite
- [ ] Update CHANGELOG.md
- [ ] Document in relevant docs if needed
- [ ] Commit with descriptive message

### For Database Changes

- [ ] Modify model in `app/models.py`
- [ ] Generate migration: `flask db migrate -m "description"`
- [ ] Review generated migration file
- [ ] Test upgrade: `flask db upgrade`
- [ ] Test downgrade: `flask db downgrade`
- [ ] Re-upgrade: `flask db upgrade`
- [ ] Run tests: `pytest`
- [ ] Update docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md if needed
- [ ] Update CHANGELOG.md
- [ ] Commit migration with model changes

---

## Additional Resources

- **Detailed Rules:** See `.claude/rules/` directory for in-depth guidance
- **Project History:** `docs/LOGS/AUDITS/LOG-ARC-031_Project_History.md` for context and philosophy
- **Development Priorities:** `DEVELOPMENT.md` for roadmap and planned features
- **Security Audits:** `docs/SECURITY/` for past security reviews
- **Architecture:** `docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`

---

## Questions or Clarifications?

When uncertain about:
- **Architecture decisions** → Review `docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md`
- **Database design** → Review `docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md`
- **Multi-tenancy** → Review `docs/SECURITY/AUDITS/SEC-AUD-015_Multi_Tenancy_Audit.md`
- **Deployment** → Review `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md`
- **Invariants** → Review `docs/INV-CORE-000_Core_Invariants.md`

Always prefer reading existing code and documentation before making assumptions.

---

**Last Updated:** 2026-04-14
**For:** Claude Code and AI assistants working on Classroom Token Hub

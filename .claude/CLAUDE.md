# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Classroom Token Hub — a multi-tenant educational banking simulation. Flask + SQLAlchemy + PostgreSQL. Python 3.10+. License: PolyForm Noncommercial 1.0.0.

**Active branch:** `main` — all work merges here. This is the same branch that older documents
call `codex/v2.0` and then `CTH_v2.0`; both names are retired and no ref by either exists. The
v1 `main` that preceded it was renamed on 2026-09-07 to `main_legacy_v1.10.0`, which is now the
**single** ref carrying the v1 line — the separate `legacy_v1.10.0` branch no longer exists, and its
tip is contained in `main_legacy_v1.10.0`. If a tool, workflow, or instruction names `codex/v2.0` or `CTH_v2.0`, it is
stale and pointing at nothing — retarget it to `main` rather than creating the branch. Instructions
that say "never merge to `main`" describe the former v1 branch and no longer apply.

## Commands

```bash
# Run all tests (requires TEST_DATABASE_URL in .env pointing to a Postgres DB)
pytest

# Run a single test file
pytest tests/test_student_recovery.py

# Run tests matching a pattern
pytest -k "recovery"

# Run with coverage
pytest --cov=app tests/

# Database migrations
flask db heads          # Must show exactly 1 head
flask db current        # Note current revision before generating
flask db migrate -m "Add X to Y"
flask db upgrade
flask db downgrade <revision>   # Test rollback (bare form aborts: head is a merge point)
flask db upgrade        # Re-apply

# Start dev server
flask run

# Production entry point
gunicorn wsgi:app
```

Tests run against a real Postgres database (not SQLite). `conftest.py` drops and recreates the schema per session. Set `FEAT_BYPASS_AUDIT=1` to enable FEAT bypass mutation auditing.

## Architecture

### Identity Model (Constitutional — INV-ARC-019, DOM-IDEN-001)

```
User (users)              — global auth principal (login, credentials, recovery)
Seat (seats)              — class-local operational actor (ALL activity keys off seat_id)
IdentityProfile           — display-only name/identity, 1:1 with Seat
ClassEconomy (classes)    — isolation boundary; class_id (UUID) is canonical, join_code is public alias
```

**Resolution chain:** `User.id` → `Seat` (via `Seat.user_id`) → `IdentityProfile` (via `IdentityProfile.seat_id`)

**CanonicalContext** (`app/services/context_resolver.py`): Frozen dataclass with `user_id`, `class_id`, `seat_id`, `actor_role`. Accessing `join_code`, `teacher_id`, `student_id`, or `block` on it raises `AttributeError` by design.

**The v1 identity layer is gone.** `Student`, `Admin`, `TeacherBlock`, `StudentTeacher`, `ClassMembership`, `StudentBlock`, and `BalanceCache` exist neither as models nor as tables. Teacher authority lives on `User.user_role` plus `ClassEconomy.teacher_user_id`; sysadmin authority is `User.user_role == SYSADMIN`. Surviving mentions of "student"/"teacher" in the codebase are domain vocabulary (form labels, descriptions, log strings), not table references. Do not reintroduce these models.

### Mutation Model (FEAT Layer)

All state mutation goes through `app/feats/`. Routes must not call `db.session.add/commit` on domain models directly.

```
Route → FEAT (app/feats/) → Domain Services (app/services/) → commit
```

GET handlers must be pure — no DB writes (INV-ARC-007).

### Multi-Tenancy

Every query involving student/seat data MUST be scoped by `class_id`. `join_code` is acceptable as an ingress alias but must resolve to `class_id` before any authority-sensitive operation. Never scope by `teacher_id` alone. See `.claude/rules/multi-tenancy.md`.

### Blueprint Layout

| Blueprint | Prefix | File |
|-----------|--------|------|
| admin | `/admin` | `app/routes/admin.py` (~12K lines) |
| student | `/student` | `app/routes/student.py` (~4K lines) |
| analytics | `/admin/analytics` | `app/routes/analytics.py` |
| sysadmin | `/sysadmin` | `app/routes/system_admin.py` |
| api | `/api` | `app/routes/api.py` |
| recovery | `/recovery` | `app/routes/recovery.py` |
| main | `/` | `app/routes/main.py` |

### Key Services

- `app/services/context_resolver.py` — `resolve_canonical_context()`, the sole legal way to get identity in routes
- `app/services/ledger_balance_query_service.py` — balance reads, `get_available_balance(seat_id, class_id, account_type)`
- `app/services/identity_service.py` — identity resolution helpers
- `app/auth.py` — decorators (`admin_required`, `login_required`), session utilities
- `app/feats/base.py` — `feat_shell` decorator, `FEATContext` manager

### Test Helpers

Per SPEC-TEST-001, tests provision a whole classroom rather than assembling rows by hand.

- `tests/helpers/classroom_initializer.py` — `initialize(key, app)`, `initialize_as_teacher(...)`, `initialize_as_student(...)`. The canonical entry point; asserts DB invariants and canonical context on the way out
- `tests/helpers/canonical_classroom.py` — `provision_classroom()`, `login_teacher()`, `login_student()`; `ProvisionedClassroom` / `ProvisionedStudent` dataclasses
- `tests/helpers/canonical_session.py` — `set_canonical_context()` for direct session setup
- `tests/helpers/ledger.py` — `create_ledger_idempotent_transaction()`, `create_ledger_transfer_pair()`, `settle_ledger_balances()`, and other ledger seeding
- `tests/helpers/class_domain.py` — `enable_class_feature()` (bypasses the CWI enablement gate), settings updates, tap in/out
- Domain-specific: `attendance_domain.py`, `banking_domain.py`, `store_products.py`, `support_domain.py`

## Critical Rules

1. **Read before writing.** Never modify files you haven't read.
2. **Scope by `class_id`.** Every student/seat query needs class isolation. See `.claude/rules/multi-tenancy.md`.
3. **Mutate through FEATs.** No direct `db.session.add/commit` in routes. See `app/feats/base.py`.
4. **Migrations require idempotency helpers.** Copy helpers from `migrations/migration_template.py.mako`, wrap all CREATE ops in existence checks. See `.claude/rules/database-migrations.md`.
5. **CSRF on all forms.** Include `{{ form.csrf_token }}` in templates, validate on POST.
6. **Encrypt PII.** Use `PIIEncryptedType` for names. Use `hash_password()`/`verify_password()` from `app/hash_utils.py` (a named seam over werkzeug scrypt; credentials are not peppered).
7. **`class_id` is canonical, `join_code` is alias.** New domain queries must use `class_id`. `join_code` is only for ClassEconomy boundary lookups and user-facing display.
8. **`seat_id` is the activity anchor.** All activity records (transactions, attendance, hall passes) key off `seat_id`, not `student_id`.
9. **No GET side effects.** GET handlers must not write to the database.

## Documentation Hierarchy

Constitutional authority flows: `INV-CORE → INV-ARC → DOM → FEAT`

- `docs/INVARIANT/CORE/` — foundational invariants (highest authority)
- `docs/INVARIANT/ARCHITECTURE/` — architectural invariants (INV-ARC-019 governs identity)
- `docs/DOMAIN/` — domain authority specs (DOM-IDEN-001 governs identity/class binding)
- `docs/FEATURE-EXECUTION/` — FEAT contracts (execution-level, subordinate to above)
- `docs/TRACKING/` — migration status and audit tracking
- `.claude/rules/` — detailed development rules (testing, migrations, security, multi-tenancy, docs)

When specs and implementation disagree, the constitutional docs (`INV-*`, `DOM-*`) define the target state. Implementation is often in a transitional bridge state.

## Identity Migration: Complete

The v1→v2 identity migration has landed. `User`/`Seat`/`IdentityProfile`/`ClassEconomy` are the whole identity model:

- Credentials live on `users` only (`passphrase_hash`, `pin_hash`) — INV-ARC-019 §VI
- `ClassEconomy.teacher_user_id` is the canonical teacher-to-class linkage
- The claim flow binds a `User` to an existing `Seat`; it creates no separate student record
- `block`/`section`/`period` is display metadata only, never a scoping key. `Seat.block` is a read-through property onto `ClassEconomy.section` kept for legacy admin rendering

## Common Mistakes

- **`Seat.user_id` is a `User.id`**: it is not any kind of student id. A variable named `student` in this codebase is a `Seat`.
- **Teacher ownership ≠ class scope**: `ClassEconomy.teacher_user_id` alone returns data across all of that teacher's class periods. Always add `class_id`.
- **Using `join_code` for domain queries**: only `classes.join_code` is authoritative, and only at ingress. Filter domain tables by `class_id`.
- **Bypassing FEAT layer**: Adding `db.session.commit()` directly in a route handler. Wrap in a FEAT instead.
- **GET handlers with writes**: Reconciliation, interest posting, or lazy expiration in GET handlers violates INV-ARC-007.

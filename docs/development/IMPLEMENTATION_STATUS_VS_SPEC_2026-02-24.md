---
roles: [developer]
Audience: developer-facing
---
# Implementation Status vs Spec (2026-02-24)

Scope:
- `docs/development/HALL_PASS_FEATURE_SPEC.md`
- `docs/development/ADMIN_IDENTITY_HANDLING_SPEC.md`

Assessment legend:
- `MET`: Implemented and aligned.
- `PARTIAL`: Implemented but with caveat, legacy dependency, or incomplete enforcement.
- `GAP`: Not implemented per spec requirement.

## Hall Pass Feature Spec Status

### Summary
- Overall: `MET`
- Core flow is implemented (`request -> approve -> checkout -> checkin`) and tested.
- Core gap around terminal/queue deprecation has been closed with `410 Gone` guardrails.

### Requirement Matrix

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Canonical lifecycle statuses (`pending/approved/rejected/left/returned`) | MET | `app/models.py` (`HallPassLog.status`) | Status model matches spec. |
| Student primary flow (request, teacher approval, student checkout/checkin) | MET | `app/routes/api.py` (`/hall-pass/checkout`, `/hall-pass/checkin`, student request path in tap endpoint) | End-to-end path exists and is tested (`tests/test_hall_pass_checkout.py`). |
| Approval required before checkout | MET | `app/routes/api.py` (`checkout_hall_pass` checks `status == 'approved'`) | Explicit guard present. |
| Checkout/checkin create attendance side effects | MET | `app/routes/api.py` (`TapEvent` creation in checkout/checkin handlers) | Matches spec. |
| Queue/simultaneous limits per destination | MET | `app/routes/api.py` (`_check_simultaneous_pass_limit`, request-time queue checks) | Enforced both at request and checkout/terminal use. |
| Public verification uses rotatable token capability URL | MET | `app/routes/main.py` (`/verify/hallpass/<token>`), `app/routes/api.py` (`/hall-pass/verify-token/rotate`) | Token lookup and rotation present. |
| Public verification rate limiting | MET | `app/routes/main.py` (`@limiter.limit(\"60 per minute\")`) | Applied on verify route. |
| Public verify privacy constraints (no roster, scoped day window) | MET | `app/routes/main.py` (join-code selection, same-day filtering, minimal result shape) | Behavior aligns. |
| Terminal/queue not required for primary operation | MET | Primary student checkout/checkin routes exist | Terminal/queue legacy routes are disabled (`410 Gone`). |
| Terminal/queue endpoints deprecated and non-primary | MET | `app/routes/main.py` and `app/routes/api.py` legacy routes | Legacy terminal/queue surfaces now return `410 Gone`. |
| All hall-pass operations tenant scoped by class context | MET | Terminal lookup path removed from active use by deprecation | Previously global pass lookup is now disabled (`410 Gone`), removing cross-tenant exposure risk on that path. |
| Observability/audit minimums | PARTIAL | Some logging exists in key handlers | No unified audit/event schema for all required hall-pass events. |

### Hall Pass Gaps to Close

1. Add structured audit events for request/approve/reject/checkout/checkin/cancel/token-rotate.

## Admin Identity Handling Spec Status

### Summary
- Overall: `MET` (with minor operational follow-up)
- Auth hashing migration, teacher public ID generation, sysadmin display policy, and verify token usage are implemented.
- Teacher `display_name` is now encrypted at rest, with session-scoped decrypted caching for student/teacher sessions.

### Requirement Matrix

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Teacher auth username stored hashed (not plaintext) for new accounts | MET | `app/routes/admin.py` signup path, `scripts/create_admin.py` | New records use hash fields; legacy `username` retained nullable for migration only. |
| System admin auth username stored hashed (not plaintext) for new accounts | MET | `wsgi.py` `create-sysadmin`, `scripts/create_admin.py`, `app/routes/system_admin.py` | Hash + lookup hash + salt persisted. |
| Login lookup by hashed lookup with legacy fallback | MET | `app/routes/admin.py` `_find_admin_by_auth_username`; `app/routes/system_admin.py` `_find_sysadmin_by_auth_username` | Behavior matches migration strategy. |
| One-time migration prompt for legacy usernames | MET | `app/routes/admin.py` `/admin/username-migration`; `app/routes/system_admin.py` `/sysadmin/username-migration` | Forced redirect after login when hash fields absent. |
| Teacher no-student migration warning | MET | `app/routes/admin.py` (`no_recovery_warning`), template `templates/admin_username_migration.html` | Explicit warning present. |
| On migration confirm: hash/store + clear plaintext username | MET | `app/routes/admin.py`, `app/routes/system_admin.py` | `username_hash`/`lookup_hash` set, `username=None`. |
| Generate teacher public ID from 3-word preset list | MET | `app/utils/admin_identity.py`, `app/data/random_words.txt`, use in signup/migration/scripts | Unique generation with fallback suffix logic. |
| Generate teacher public token for hall pass verification URL | MET | `app/models.py` + admin signup/migration + rotate endpoint | Token generated and rotatable. |
| Student-facing display fallback to `teacher_public_id` when no display name | MET | `Admin.get_display_name()` in `app/models.py` | Implements fallback behavior. |
| Sysadmin always sees `teacher_public_id` | MET | `Admin.get_sysadmin_display_name()` and sysadmin route usage | Sysadmin-facing listings route through this method. |
| Teacher display name encrypted at rest | MET | `app/models.py` (`display_name = db.Column(PIIEncryptedType(...))`), migration `d2e4f6a8b0c1` | Converted to encrypted binary storage with backfill migration. |
| Session-scoped decrypted display-name cache (student/teacher) | MET | `app/utils/display_name_session.py`, `app/routes/admin.py`, `app/routes/student.py`, `app/__init__.py`, `app/auth.py` | Decrypt-once per session behavior implemented and cache cleared on logout/session invalidation paths. |
| CLI/admin operational paths avoid plaintext username persistence | MET | `wsgi.py`, `scripts/create_admin.py` | Updated to hashed creation. |
| Migration idempotency and rehearsal | MET | Migrations include existence checks; rehearsal run completed in prior execution | `b9c8d7e6f5a4`, `c1d2e3f4a5b7`. |

### Identity Follow-Ups

1. Add focused tests asserting session cache behavior directly (cache priming + cache clear on timeout/logout), although current full-suite regression coverage is passing.

## Test/Validation Snapshot

- Latest full suite run in this branch: `505 passed, 1 skipped`.
- This supports current behavior correctness, but does not by itself close the documented `GAP`/`PARTIAL` items above.

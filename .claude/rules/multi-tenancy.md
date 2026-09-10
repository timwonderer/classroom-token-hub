# Multi-Tenancy Scoping Rules

> **Not authoritative.** This file is operational guidance for agents. Normative authority lives only under `docs/INVARIANT/`, `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/SPEC/`, and `docs/STANDARD_OPERATING_PROCEDURES/`. Where this file conflicts with one of those, the normative document wins and this file is what gets corrected.

**CRITICAL:** This project had a P0 same-teacher multi-period data leak. Every read and
write touching seat-owned data must be scoped by `class_id`.

---

## The Golden Rules

1. **`class_id` is the class isolation key.** It is a UUID string, PK of `classes`.
2. **`seat_id` is the activity anchor.** Ledger, attendance, hall passes, and
   entitlements all key off `seat_id` — never off a user id.
3. **`join_code` is an ingress alias only.** It resolves to `class_id` at the boundary
   and is never a scoping key for a domain query.
4. **Teacher ownership is not class scope.** `classes.teacher_user_id` says who owns a
   class; it does not identify *which* class period a request is operating in.
5. **Balances are read from the ledger, never from a per-student row.**

---

## Runtime Model

```
User (users)              — global auth principal
Seat (seats)              — class-local actor; UNIQUE(user_id, class_id)
IdentityProfile           — display-only name, 1:1 with Seat
ClassEconomy (classes)    — the isolation boundary
```

```python
ClassEconomy            # __tablename__ = 'classes'
├── class_id            # String(36) UUID, PRIMARY KEY — the canonical scope key
├── class_public_id     # opaque external handle
├── join_code           # String(20), unique — public alias, ingress only
├── teacher_user_id     # FK users.id — ownership, NOT scope
├── section             # display metadata (what older docs called "block")
├── display_name
└── class_timezone      # NOT NULL, immutable once set

Seat                    # __tablename__ = 'seats'
├── id
├── public_id
├── user_id             # FK users.id
├── class_id            # FK classes.class_id
├── role                # 'student' | 'teacher'
├── claim_first_name_hash / claim_last_name_hash / roster_fingerprint
└── has_received_rent_exemption
```

`Seat.block` exists only as a read-through property onto `ClassEconomy.section`, for
legacy admin rendering. It is display metadata. Never scope by it.

### There is no v1 identity layer left

`Student`, `Admin`, `StudentBlock`, `ClassMembership`, `TeacherBlock`,
`StudentTeacher`, and `BalanceCache` **do not exist** — not as models, not as tables.
Neither do `Student.get_checking_balance()` / `get_savings_balance()`. If you find text
anywhere instructing you to use them, that text is stale; do not resurrect them.

Remaining `join_code` columns in the schema: `classes.join_code` (the alias itself) plus
two nullable legacy columns that no domain query filters on. Treat any new `join_code`
filter as a bug.

---

## Getting Class Context

### Student routes

```python
from app.services.context_resolver import resolve_canonical_context

context = resolve_canonical_context()          # CanonicalContext
class_id = context.class_id
seat_id = context.seat_id
```

`CanonicalContext` is a frozen dataclass carrying exactly `user_id`, `class_id`,
`seat_id`, `actor_role`. Its `__getattr__` **raises** on `join_code`, `teacher_id`,
`block`, `section`, and `student_id` — that is deliberate, not a gap to work around.

To get the seat object itself, `app/routes/student.py` provides
`_get_canonical_student_from_context()`, which returns a `Seat`.

### Admin routes

Class context is attached to `g` by the blueprint's before-request hook, and ownership
is re-verified per request:

```python
from flask import g
from app.services.class_configuration_query_service import verify_teacher_owns_class

canonical_context = getattr(g, "canonical_context", None)
class_id = (getattr(canonical_context, "class_id", None) or "").strip()
class_row = verify_teacher_owns_class(class_id, canonical_context.user_id)
if not class_row:
    abort(403)
```

Teachers holding no active class get a `BoundaryContext` (`user_id` + `actor_role`
only); accessing `class_id` or `seat_id` on it raises — resolve class selection first.
Sysadmins are *forbidden* from holding class context at all.

---

## Correct Scoping Patterns

### Pattern 1: Roster for the active class

```python
from app.models import Seat

seats = Seat.query.filter_by(class_id=class_id, role="student").all()
```

```python
# WRONG — teacher ownership spans every period they teach
seats = Seat.query.join(ClassEconomy).filter(
    ClassEconomy.teacher_user_id == user_id
).all()
```

### Pattern 2: Class-scoped ledger reads

```python
from app.models import Transaction, TransactionStatus

txns = (
    Transaction.query
    .filter(
        Transaction.seat_id == seat_id,
        Transaction.class_id == class_id,
        Transaction.status != TransactionStatus.VOID,
    )
    .order_by(Transaction.timestamp.desc())
    .all()
)
```

### Pattern 3: Balances

```python
from app.services.ledger_balance_query_service import (
    get_available_balance,
    get_available_balances,
)

checking = get_available_balance(seat_id, class_id, "checking")
checking, savings = get_available_balances(seat_id, class_id)
```

`get_available_balance` = posted (from `LedgerBalanceSnapshot.posted_balance_cents`,
with a summation fallback) + pending delta. All three arguments are mandatory; the
service raises rather than silently answering a narrower question — omitting
`account_type` would report zero for a seat that has money.

For rosters use `get_batch_balances_by_class_seat(pairs)` instead of looping.

### Pattern 4: Class-scoped settings

```python
settings = PayrollSettings.query.filter_by(class_id=class_id).first()
```

### Pattern 5: New records

Every new row in a class-scoped table carries both `seat_id` and `class_id`, and is
written through a FEAT — never `db.session.add` in a route.

---

## Tables That Must Be Class-Scoped

All 31 tables carrying a `class_id` column, notably:

`seats`, `identity_profiles`, `ledger_transaction`, `ledger_balance_snapshot`,
`attendance_sessions`, `hall_pass_logs`, `hall_pass_settings`, `payroll_settings`,
`payroll_cycle_completion`, `rent_settings`, `bill_cycles`, `insurance_policies`,
`insurance_claims`, `insurance_claim_productivity_dates`, `policy_versions`,
`policy_transitions`, `store_products`, `entitlement_events`, `pending_actions`,
`assessment_events`, `feature_settings`, `class_features`, `economic_engine`,
`announcements`, `student_recovery_codes`, `actor_request_trace`.

If you add a table holding seat-owned or class-owned state, it gets `class_id`.

---

## Common Mistakes

### `Seat.user_id` is a `User.id`

```python
# WRONG — there is no Student model; this compares unrelated id spaces
Seat.query.filter_by(user_id=student.id)

# CORRECT
Seat.query.filter_by(user_id=user.id, class_id=class_id).one_or_none()
```

### Scoping by teacher

`teacher_user_id` alone returns data across every period that teacher runs. That is the
exact shape of the original P0 leak. Always add `class_id`.

### Reaching for `join_code`

`join_code` belongs in three places only: the join/claim ingress flow, the
`ClassEconomy` boundary lookup that turns it into a `class_id`, and user-facing
display. Anywhere else it is a scoping bug.

### Trusting a client-supplied `class_id`

A `class_id` arriving in a form or query string is an assertion, not authority. Admin
writes must reconcile it against session context (`_admin_write_has_join_code_conflict`
in `app/routes/admin.py` exists for exactly this) and pass `verify_teacher_owns_class`.

---

## Session Checklist

- [ ] Class context resolved via `resolve_canonical_context()` / `g.canonical_context`
- [ ] Every seat-owned query filtered by `class_id`
- [ ] Admin writes re-verified with `verify_teacher_owns_class`
- [ ] New rows carry `seat_id` **and** `class_id`
- [ ] Balances read through `ledger_balance_query_service`
- [ ] No `join_code` outside ingress / boundary lookup / display
- [ ] No `teacher_user_id`-only scoping

---

**Last Updated:** 2026-09-09
**Critical Incident:** P0 same-teacher multi-period data leak

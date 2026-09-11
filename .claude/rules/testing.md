# Testing Requirements

> **Not authoritative.** This file is operational guidance for agents. Normative authority lives only under `docs/INVARIANT/`, `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/SPEC/`, and `docs/STANDARD_OPERATING_PROCEDURES/`. Where this file conflicts with one of those, the normative document wins and this file is what gets corrected.

**CRITICAL:** All new features and bug fixes must include tests. Untested code is broken code.

---

## The Golden Rules

1. **ALWAYS write tests for new features** (before or with implementation)
2. **ALWAYS write regression tests for bug fixes**
3. **ALWAYS test multi-tenancy scoping** for student-related features
4. **ALWAYS run full test suite before committing**
5. **NEVER skip tests because "it's a small change"**

---

## Test Coverage Requirements

### For New Features

**Minimum Required:**
- ✅ Happy path test (feature works as intended)
- ✅ Error handling test (feature fails gracefully)
- ✅ Multi-tenancy scoping test (if involves student data)
- ✅ Permission test (if involves authorization)

**Recommended:**
- Edge cases (boundary conditions, empty data, etc.)
- Integration tests (feature works with related features)
- Performance tests (for expensive operations)

### For Bug Fixes

**Required:**
- ✅ Regression test that would fail with the bug present
- ✅ Test that passes after fix is applied

### For Refactoring

**Required:**
- ✅ All existing tests still pass
- ✅ No decrease in coverage

---

## Test Structure

### File Organization

```
tests/
├── conftest.py                 # rebuilds the schema by running the real migration chain
├── helpers/                    # SPEC-TEST-001 classroom provisioning (see below)
├── dom/                        # per-domain invariant tests, mirrors docs/DOMAIN
├── test_*.py                   # feature and regression tests
└── ...
```

Tests run against a **real Postgres** database named by `TEST_DATABASE_URL`. There is
no SQLite path. `conftest.py` drops and recreates `public` and then runs `upgrade()`, so
migrations — including triggers and constraints — are live in every test.

### Test Naming Convention

```python
# Format: test_<feature>_<scenario>
def test_student_login_success(client, app):
    """Successful student login with valid credentials."""

def test_student_login_invalid_password(client, app):
    """Student login fails with a wrong passphrase."""
```

When a test exists to hold a named constitutional rule, put the rule id in the name so
a failure says which law broke:

```python
def test_INV_ARC_016__audit_events_cannot_be_updated(app, audit_row):
def test_J1__transfer_takes_an_exclusive_lock_on_the_seat_row(client, app):
```

---

## Provisioning a Classroom

**Do not hand-assemble rows.** Per SPEC-TEST-001, a test starts from a provisioned
classroom, which builds a consistent `User` + `Seat` + `ClassEconomy` +
`IdentityProfile` graph and asserts its own invariants.

```python
from tests.helpers.classroom_initializer import initialize_as_student

classroom, student = initialize_as_student("chemistry_p1", client, app)
class_id = classroom.class_id
seat_id = student.seat.id
user_id = student.user.id
```

| Helper | Use |
|--------|-----|
| `classroom_initializer.initialize(key, app)` | classroom only, nobody logged in |
| `classroom_initializer.initialize_as_teacher(key, client, app)` | teacher session established |
| `classroom_initializer.initialize_as_student(key, client, app)` | student session established |
| `canonical_session.set_canonical_context(...)` | set session context directly, no HTTP login |
| `ledger.create_ledger_idempotent_transaction(...)` | seed money |
| `ledger.create_ledger_transfer_pair(...)` / `settle_ledger_balances(...)` | ledger state |
| `class_domain.enable_class_feature(class_id=..., feature=...)` | turn on a feature; bypasses the CWI enablement gate |

---

## Common Test Patterns

### Pattern 1: Route testing

```python
def test_student_dashboard_displays_balance(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        create_ledger_idempotent_transaction(
            idempotency_key=f"seed:{student.seat.id}",
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            user_id=student.user.id,
            amount=Decimal("100.00"),
            account_type="checking",
            type="payroll",
            description="Test funding",
        )
        db.session.commit()

    response = client.get("/student/dashboard")
    assert response.status_code == 200
    assert b"100.00" in response.data
```

### Pattern 2: Mutation testing

State changes go through a FEAT, so drive the FEAT, not `db.session.add`:

```python
with FEATContext("FEAT-LED-000", idempotency_key=f"t:{seat_id}"):
    execute_account_transfer(
        seat_id=seat_id, class_id=class_id, user_id=user_id,
        amount=Decimal("5.00"), from_account="checking", to_account="savings",
    )
```

### Pattern 3: Multi-tenancy scoping

Two classes, one query, assert the other class is invisible:

```python
def test_transactions_scoped_by_class(client, app):
    first, alice = initialize_as_student("chemistry_p1", client, app)
    second, bob = initialize_as_student("chemistry_p2", client, app)

    with app.app_context():
        rows = Transaction.query.filter_by(class_id=first.class_id).all()
        assert all(r.class_id == first.class_id for r in rows)
        assert bob.seat.id not in {r.seat_id for r in rows}
```

Never assert scoping by `join_code` or by teacher ownership — see
`.claude/rules/multi-tenancy.md`.

### Pattern 4: Permission testing

```python
def test_student_cannot_access_admin_dashboard(client, app):
    initialize_as_student("chemistry_p1", client, app)
    response = client.get("/admin/dashboard")
    assert response.status_code in (302, 403)
```

### Pattern 5: Error handling

```python
def test_transfer_rejects_over_balance(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        with pytest.raises(InsufficientFunds):
            with FEATContext("FEAT-LED-000", idempotency_key="over"):
                execute_account_transfer(
                    seat_id=student.seat.id, class_id=classroom.class_id,
                    user_id=student.user.id, amount=Decimal("999.00"),
                    from_account="checking", to_account="savings",
                )
        db.session.rollback()
```

### Pattern 6: Asserting a property, not a coincidence

A passing test is not evidence until you have watched it fail. Before trusting a
regression test, remove the fix and confirm the test goes red. Locking is the classic
trap: a foreign key already takes `FOR KEY SHARE` on the parent row, so "something
locked it" is true with or without an explicit `with_for_update()`.

---


## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_teacher_recovery.py
```

### Run Specific Test Function

```bash
pytest tests/test_teacher_recovery.py::test_teacher_recovery_full_flow
```

### Run Tests Matching Pattern

```bash
pytest -k "recovery"  # Runs all tests with "recovery" in name
pytest -k "multi_tenancy"
```

### Run with Coverage

```bash
# Install coverage
pip install pytest-cov

# Run with coverage report
pytest --cov=app tests/

# Generate HTML coverage report
pytest --cov=app --cov-report=html tests/
# Open htmlcov/index.html in browser
```

### Run with Verbose Output

```bash
pytest -v  # Verbose mode
pytest -vv  # Very verbose mode
pytest -s  # Show print statements
```

### Run Only Failed Tests

```bash
pytest --lf  # Last failed
pytest --ff  # Failed first, then rest
```

---

## Test-Driven Development (TDD)

### Recommended Workflow

1. **Write failing test first**

```python
def test_new_feature_works(client, app):
    """Test new feature functionality."""
    # This test will fail because feature doesn't exist yet
    response = client.get('/new-feature')
    assert response.status_code == 200
    assert b'expected content' in response.data
```

2. **Run test - verify it fails**

```bash
pytest tests/test_new_feature.py::test_new_feature_works
# FAILED - as expected
```

3. **Implement minimum code to pass test**

```python
# In app/routes/student.py
@student_bp.route('/new-feature')
def new_feature():
    return render_template('new_feature.html', content='expected content')
```

4. **Run test - verify it passes**

```bash
pytest tests/test_new_feature.py::test_new_feature_works
# PASSED
```

5. **Refactor if needed**

Improve code quality while keeping tests passing.

6. **Add more tests for edge cases**

```python
def test_new_feature_handles_errors(client, app):
    """Test new feature error handling."""
    # ...
```

---

## Testing Checklist

### Before Every Commit

- [ ] All new features have tests
- [ ] All bug fixes have regression tests
- [ ] Multi-tenancy scoping tested (if applicable)
- [ ] Full test suite passes: `pytest`
- [ ] No decrease in coverage
- [ ] Tests follow naming conventions
- [ ] Tests have clear docstrings

### For New Features

- [ ] Happy path test
- [ ] Error handling test
- [ ] Permission test (if applicable)
- [ ] Multi-tenancy test (if involves students)
- [ ] Edge cases tested

### For Bug Fixes

- [ ] Test reproduces bug (fails before fix)
- [ ] Test passes after fix
- [ ] Related functionality still works

---

## Common Testing Mistakes

### MISTAKE 1: Not testing class isolation

```python
# BAD — proves nothing about isolation
def test_get_seats(client, app):
    assert Seat.query.count() > 0
```

```python
# GOOD — two classes exist, and only one is visible
def test_seats_scoped_by_class(client, app):
    first, _ = initialize_as_student("chemistry_p1", client, app)
    second, bob = initialize_as_student("chemistry_p2", client, app)

    seats = Seat.query.filter_by(class_id=first.class_id, role="student").all()
    assert bob.seat.id not in {s.id for s in seats}
```

### MISTAKE 2: Hand-assembling identity rows

```python
# BAD — bypasses the invariants the initializer exists to hold
seat = Seat(user_id=user.id, class_id=class_id)
db.session.add(seat)
```

```python
# GOOD
classroom, student = initialize_as_student("chemistry_p1", client, app)
```

### MISTAKE 3: Writing domain state directly

```python
# BAD — routes and tests alike must not post to the ledger by hand
db.session.add(Transaction(seat_id=seat_id, class_id=class_id, amount=50))
db.session.commit()
```

```python
# GOOD — go through the FEAT or the ledger helper
create_ledger_idempotent_transaction(idempotency_key=..., seat_id=..., class_id=..., ...)
```

### MISTAKE 4: Testing several things in one test

Split login, dashboard render, and transfer into three tests. When a compound test
fails, the failure names the workflow, not the defect.

### MISTAKE 5: Vague assertions

```python
# BAD
assert response.status_code == 200
```

```python
# GOOD — assert the balance actually moved
assert get_available_balance(seat_id, class_id, "checking") == Decimal("75.00")
assert get_available_balance(seat_id, class_id, "savings") == Decimal("25.00")
```

### MISTAKE 6: Trusting a green test you never saw fail

Especially for concurrency, locking, and trigger tests, where the database often
supplies incidental protection that makes a broken implementation look correct.

---

## Test Coverage Goals

### Current Status

- **55 test files**
- Coverage target: 80%+ for core features
- All routes should have at least one test

### Priority Areas

**Must Have 100% Coverage:**
- Authentication (login, logout, session management)
- Financial transactions (transfers, payroll, rent)
- Multi-tenancy scoping (all student data queries)
- Security features (encryption, CSRF, permissions)

**Should Have 80%+ Coverage:**
- Route handlers
- Model methods
- Utility functions
- Form validation

**Can Have Lower Coverage:**
- Template rendering (tested manually)
- Static file serving
- Error page rendering

---

## Quick Reference

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_teacher_recovery.py

# Run with coverage
pytest --cov=app tests/

# Run tests matching pattern
pytest -k "recovery"

# Run in verbose mode
pytest -v

# Run last failed tests
pytest --lf

# Show print statements
pytest -s
```

---

**Last Updated:** 2026-09-09
**Framework:** pytest with Flask test client, against real PostgreSQL
**Coverage Tool:** pytest-cov

The full suite takes over an hour. Run the narrowest selection that proves your change
(`pytest tests/test_x.py -q`, `pytest -k pattern`) while iterating; reserve the full
run for the end of a body of work.

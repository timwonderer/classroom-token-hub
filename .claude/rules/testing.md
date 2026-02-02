# Testing Requirements

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
├── conftest.py                 # Pytest fixtures and configuration
├── test_admin_routes.py        # Admin/teacher route tests
├── test_student_routes.py      # Student route tests
├── test_api_routes.py          # API endpoint tests
├── test_auth.py                # Authentication tests
├── test_payroll.py             # Payroll logic tests
├── test_models.py              # Model tests
├── test_teacher_recovery.py    # Account recovery tests
├── test_multi_tenancy.py       # Multi-tenancy scoping tests
└── ... (55 test files total)
```

### Test Naming Convention

```python
# Format: test_<feature>_<scenario>
def test_student_login_success(client, app):
    """Test successful student login with valid credentials."""

def test_student_login_invalid_password(client, app):
    """Test student login fails with wrong password."""

def test_student_login_missing_username(client, app):
    """Test student login fails with missing username."""
```

**Pattern:**
- Start with `test_`
- Use descriptive names
- One test per scenario
- Include docstring explaining what's tested

---

## Common Test Patterns

### Pattern 1: Route Testing

```python
def test_student_dashboard_displays_balance(client, app):
    """Test student dashboard shows current balance."""
    # Setup: Create teacher, student, and join code
    with app.app_context():
        teacher = Admin(username="teacher1", ...)
        db.session.add(teacher)
        db.session.flush()

        join_code = "ABC123"
        block = TeacherBlock(teacher_id=teacher.id, join_code=join_code)
        db.session.add(block)

        student = Student(username="student1", teacher_id=teacher.id, ...)
        db.session.add(student)

        student_block = StudentBlock(
            student_id=student.id,
            join_code=join_code,
            checking_balance=100.0
        )
        db.session.add(student_block)
        db.session.commit()

        # Login
        client.post('/student/login', data={
            'username': 'student1',
            'passphrase': 'test123'
        })

        # Execute: Access dashboard
        response = client.get('/student/dashboard')

        # Assert: Balance is displayed
        assert response.status_code == 200
        assert b'100.0' in response.data or b'$100' in response.data
```

### Pattern 2: Model Testing

```python
def test_student_model_creates_successfully(app):
    """Test Student model creates with required fields."""
    with app.app_context():
        student = Student(
            username="test_student",
            first_name="Test",
            last_initial="S",
            teacher_id=1,
            passphrase_hash="hashed_password"
        )
        db.session.add(student)
        db.session.commit()

        # Verify student was created
        retrieved = Student.query.filter_by(username="test_student").first()
        assert retrieved is not None
        assert retrieved.first_name == "Test"
        assert retrieved.last_initial == "S"
```

### Pattern 3: Multi-Tenancy Scoping

```python
def test_transaction_query_scoped_by_join_code(client, app):
    """Test transactions are properly scoped by join_code."""
    with app.app_context():
        # Setup: Create two class periods
        teacher = Admin(username="teacher1", ...)
        db.session.add(teacher)
        db.session.flush()

        # Period 1
        block1 = TeacherBlock(teacher_id=teacher.id, join_code="PERIOD1")
        db.session.add(block1)

        student1 = Student(username="student1", teacher_id=teacher.id, ...)
        db.session.add(student1)

        transaction1 = Transaction(
            student_id=student1.id,
            join_code="PERIOD1",
            amount=50.0,
            description="Period 1 transaction"
        )
        db.session.add(transaction1)

        # Period 2
        block2 = TeacherBlock(teacher_id=teacher.id, join_code="PERIOD2")
        db.session.add(block2)

        student2 = Student(username="student2", teacher_id=teacher.id, ...)
        db.session.add(student2)

        transaction2 = Transaction(
            student_id=student2.id,
            join_code="PERIOD2",
            amount=75.0,
            description="Period 2 transaction"
        )
        db.session.add(transaction2)

        db.session.commit()

        # Execute: Query transactions for PERIOD1 only
        period1_transactions = Transaction.query.filter_by(
            join_code="PERIOD1"
        ).all()

        # Assert: Only PERIOD1 transaction returned
        assert len(period1_transactions) == 1
        assert period1_transactions[0].join_code == "PERIOD1"
        assert period1_transactions[0].amount == 50.0
```

### Pattern 4: Permission Testing

```python
def test_student_cannot_access_admin_dashboard(client, app):
    """Test student cannot access teacher dashboard."""
    with app.app_context():
        # Setup: Create and login as student
        student = Student(username="student1", ...)
        db.session.add(student)
        db.session.commit()

        client.post('/student/login', data={
            'username': 'student1',
            'passphrase': 'test123'
        })

        # Execute: Try to access admin dashboard
        response = client.get('/admin/dashboard')

        # Assert: Redirected or forbidden
        assert response.status_code in [302, 403]
```

### Pattern 5: Error Handling

```python
def test_transfer_fails_with_insufficient_funds(client, app):
    """Test student transfer fails when balance is too low."""
    with app.app_context():
        # Setup: Student with $50 balance
        student = create_student_with_balance(50.0)

        # Login as student
        login_as_student(client, student)

        # Execute: Try to transfer $100 (more than balance)
        response = client.post('/student/transfer', data={
            'recipient_username': 'other_student',
            'amount': 100.0
        })

        # Assert: Transfer fails with error message
        assert response.status_code == 200  # Stays on page
        assert b'Insufficient funds' in response.data or b'not enough' in response.data
```

---

## Pytest Fixtures

### Using Fixtures

Fixtures are reusable test components defined in `conftest.py`:

```python
def test_with_fixtures(client, app, sample_teacher, sample_student):
    """Test using pre-defined fixtures."""
    # client: Flask test client
    # app: Flask app instance with context
    # sample_teacher: Pre-created teacher
    # sample_student: Pre-created student

    with app.app_context():
        # Your test code here
        pass
```

### Common Fixtures

```python
# In conftest.py

@pytest.fixture
def app():
    """Create and configure test app."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def sample_teacher(app):
    """Create a sample teacher."""
    with app.app_context():
        teacher = Admin(username="test_teacher", ...)
        db.session.add(teacher)
        db.session.commit()
        return teacher

@pytest.fixture
def sample_student(app, sample_teacher):
    """Create a sample student."""
    with app.app_context():
        student = Student(
            username="test_student",
            teacher_id=sample_teacher.id,
            ...
        )
        db.session.add(student)
        db.session.commit()
        return student
```

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

### ❌ MISTAKE 1: Not testing multi-tenancy

```python
# BAD: Doesn't test cross-period data isolation
def test_get_students(client, app):
    students = Student.query.all()
    assert len(students) > 0
```

```python
# GOOD: Tests join_code scoping
def test_get_students_scoped_by_join_code(client, app):
    # Create students in different periods
    student_period1 = create_student(join_code="PERIOD1")
    student_period2 = create_student(join_code="PERIOD2")

    # Query for PERIOD1 only
    students = Student.query.join(StudentBlock).filter(
        StudentBlock.join_code == "PERIOD1"
    ).all()

    # Assert only PERIOD1 student returned
    assert len(students) == 1
    assert students[0].id == student_period1.id
```

### ❌ MISTAKE 2: Testing multiple things in one test

```python
# BAD: Tests login, dashboard, and transfer in one test
def test_student_workflow(client, app):
    # Login
    response = client.post('/student/login', ...)
    assert response.status_code == 302

    # Check dashboard
    response = client.get('/student/dashboard')
    assert b'Balance' in response.data

    # Make transfer
    response = client.post('/student/transfer', ...)
    assert response.status_code == 200
```

```python
# GOOD: Separate tests for each scenario
def test_student_login_success(client, app):
    response = client.post('/student/login', ...)
    assert response.status_code == 302

def test_student_dashboard_displays_balance(client, app):
    login_as_student(client)
    response = client.get('/student/dashboard')
    assert b'Balance' in response.data

def test_student_transfer_success(client, app):
    login_as_student(client)
    response = client.post('/student/transfer', ...)
    assert response.status_code == 200
```

### ❌ MISTAKE 3: Not cleaning up database

```python
# BAD: Doesn't clean up, affects other tests
def test_create_student(app):
    student = Student(username="test")
    db.session.add(student)
    db.session.commit()
    # Missing cleanup
```

```python
# GOOD: Uses app fixture which handles cleanup
def test_create_student(app):
    with app.app_context():
        student = Student(username="test")
        db.session.add(student)
        db.session.commit()
        # Fixture automatically cleans up after test
```

### ❌ MISTAKE 4: Vague assertions

```python
# BAD: Not specific enough
def test_transfer(client, app):
    response = client.post('/student/transfer', ...)
    assert response.status_code == 200
```

```python
# GOOD: Specific assertions
def test_transfer_updates_balances(client, app):
    sender = create_student_with_balance(100.0)
    recipient = create_student_with_balance(50.0)

    login_as_student(client, sender)
    response = client.post('/student/transfer', data={
        'recipient_username': recipient.username,
        'amount': 25.0
    })

    # Verify transfer succeeded
    assert response.status_code == 200
    assert b'Transfer successful' in response.data

    # Verify balances updated
    sender_block = StudentBlock.query.filter_by(student_id=sender.id).first()
    recipient_block = StudentBlock.query.filter_by(student_id=recipient.id).first()

    assert sender_block.checking_balance == 75.0
    assert recipient_block.checking_balance == 75.0
```

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

**Last Updated:** 2025-12-13
**Test Count:** 55 files
**Framework:** pytest with Flask test client
**Coverage Tool:** pytest-cov

# Multi-Tenancy Scoping Rules

**CRITICAL:** This project had a P0 data leak where students in multiple class periods with the same teacher saw aggregated data across all periods. **ALWAYS scope by `join_code`.**

---

## The Golden Rules

1. **`join_code` is the ABSOLUTE source of truth** for class isolation
2. **EVERY query involving student data MUST be scoped by `join_code`**
3. **NEVER query by `teacher_id` alone** for student data
4. **ALWAYS test multi-tenancy scoping** for new features
5. **NEVER assume one student = one class period**

---

## Multi-Tenancy Context

### The Problem

**Without proper scoping:**
- A student enrolled in Period 1 and Period 2 with the same teacher would see:
  - Combined balances from both periods
  - Transactions from both periods
  - Attendance from both periods
  - Wrong payroll calculations

**This is a data leak and privacy violation.**

### The Solution

**`join_code` provides perfect isolation:**
- Each class period has a unique `join_code`
- All financial data is scoped by `join_code`
- All queries must filter by the current `join_code`

---

## Data Model Overview

### Core Tables

**Teacher/Admin:**
```python
Admin (teacher account)
├── id (primary key)
└── username

TeacherBlock (class periods)
├── id
├── teacher_id (FK to Admin)
├── join_code (unique per period)  # THE SOURCE OF TRUTH
├── block_name (e.g., "Period 1")
└── display_name
```

**Student:**
```python
Student
├── id
├── username
├── first_name (encrypted)
├── last_initial
└── teacher_id (DEPRECATED - DO NOT USE)

StudentBlock (student enrollment in specific period)
├── id
├── student_id (FK to Student)
├── join_code (FK to TeacherBlock.join_code)  # CRITICAL FOR SCOPING
├── checking_balance
├── savings_balance
└── is_active

StudentTeacher (many-to-many relationship)
├── student_id
└── teacher_id
```

**Financial Tables (ALL must have join_code):**
- `Transaction` - Has `join_code`
- `TapEvent` - Has `join_code`
- `PayrollSettings` - Has `join_code`
- `RentSettings` - Has `join_code`
- `RentPayment` - Has `join_code`
- `BankingSettings` - Has `join_code`
- `InsurancePolicyBlock` - Has `join_code`
- `StoreItemBlock` - Has `join_code`

---

## Correct Scoping Patterns

### Pattern 1: Get Students for Current Class Period

```python
# ✅ CORRECT - Scoped by join_code
def get_students_for_period(join_code):
    """Get all students enrolled in this specific class period."""
    students = Student.query.join(StudentBlock).filter(
        StudentBlock.join_code == join_code,
        StudentBlock.is_active == True
    ).all()
    return students

# ❌ WRONG - Not scoped, returns students from all periods
def get_students_for_teacher(teacher_id):
    """DO NOT USE - Returns students from ALL periods."""
    students = Student.query.filter_by(teacher_id=teacher_id).all()
    return students
```

### Pattern 2: Get Transactions for Current Period

```python
# ✅ CORRECT - Scoped by join_code
def get_period_transactions(join_code):
    """Get transactions for this class period only."""
    transactions = Transaction.query.filter_by(
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).all()
    return transactions

# ✅ CORRECT - Scoped by join_code AND student
def get_student_transactions(student_id, join_code):
    """Get student's transactions for specific period."""
    transactions = Transaction.query.filter_by(
        student_id=student_id,
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).all()
    return transactions

# ❌ WRONG - Not scoped, leaks across periods
def get_student_transactions_bad(student_id):
    """DO NOT USE - Returns transactions from ALL periods."""
    transactions = Transaction.query.filter_by(
        student_id=student_id
    ).all()
    return transactions
```

### Pattern 3: Get Student Balance

```python
# ✅ CORRECT - Get balance for specific period
def get_student_balance(student_id, join_code):
    """Get student's balance for specific class period."""
    student_block = StudentBlock.query.filter_by(
        student_id=student_id,
        join_code=join_code
    ).first()

    if not student_block:
        return None

    return {
        'checking': student_block.checking_balance,
        'savings': student_block.savings_balance
    }

# ❌ WRONG - No way to scope to specific period
def get_student_balance_bad(student_id):
    """DO NOT USE - Which period's balance?"""
    student = Student.query.get(student_id)
    # Student doesn't have balance - StudentBlock does!
    return None
```

### Pattern 4: Update Settings (Rent, Payroll, etc.)

```python
# ✅ CORRECT - Settings scoped to specific period
def update_payroll_settings(join_code, pay_rate):
    """Update payroll settings for this class period."""
    settings = PayrollSettings.query.filter_by(
        join_code=join_code
    ).first()

    if settings:
        settings.pay_rate = pay_rate
    else:
        settings = PayrollSettings(
            join_code=join_code,
            pay_rate=pay_rate
        )
        db.session.add(settings)

    db.session.commit()
    return settings

# ❌ WRONG - Settings by teacher_id affects all periods
def update_payroll_settings_bad(teacher_id, pay_rate):
    """DO NOT USE - Would apply to all periods."""
    # This pattern doesn't work for multi-period teachers
    pass
```

---

## Getting Current Class Context

### In Student Routes

```python
from app.routes.student import get_current_class_context

@student_bp.route('/dashboard')
@student_required
def dashboard():
    """Student dashboard scoped to current class period."""
    student_id = session.get('student_id')

    # Get current class context (includes join_code)
    context = get_current_class_context()
    if not context:
        return redirect(url_for('student.select_class'))

    join_code = context['join_code']

    # All queries must use this join_code
    student_block = StudentBlock.query.filter_by(
        student_id=student_id,
        join_code=join_code
    ).first()

    transactions = Transaction.query.filter_by(
        student_id=student_id,
        join_code=join_code
    ).limit(10).all()

    return render_template(
        'student_dashboard.html',
        student_block=student_block,
        transactions=transactions
    )
```

### In Admin/Teacher Routes

```python
from app.auth import get_admin_student_query, get_student_for_admin

@admin_bp.route('/students')
@admin_required
def students():
    """View students for current class period."""
    admin_id = session.get('admin_id')
    join_code = session.get('current_join_code')  # Selected period

    if not join_code:
        # Teacher must select a class period first
        return redirect(url_for('admin.select_class'))

    # Use scoped helper
    students_query = get_admin_student_query(admin_id, join_code)
    students = students_query.all()

    return render_template('admin_students.html', students=students)
```

---

## Scoped Helper Functions

**These are centralized in `app/auth.py`:**

### `get_admin_student_query(admin_id, join_code)`

Returns a filtered query for students accessible to this admin in this period.

```python
# Usage
students = get_admin_student_query(admin_id, join_code).all()

# Or with additional filters
active_students = get_admin_student_query(admin_id, join_code).filter(
    StudentBlock.is_active == True
).all()
```

### `get_student_for_admin(admin_id, student_id, join_code)`

Safely retrieves a student, ensuring the admin has access in this period.

```python
# Usage
student = get_student_for_admin(admin_id, student_id, join_code)
if not student:
    flash("Student not found or no access", "error")
    return redirect(url_for('admin.dashboard'))
```

**ALWAYS use these helpers instead of direct `Student.query` calls.**

---

## Common Multi-Tenancy Mistakes

### ❌ MISTAKE 1: Querying by teacher_id

```python
# WRONG - Returns students from ALL periods
students = Student.query.filter_by(teacher_id=teacher_id).all()
```

```python
# CORRECT - Scoped to specific period
students = Student.query.join(StudentBlock).filter(
    StudentBlock.join_code == join_code
).all()
```

### ❌ MISTAKE 2: Forgetting join_code on new transactions

```python
# WRONG - Transaction without join_code
transaction = Transaction(
    student_id=student_id,
    amount=50.0,
    description="Payroll"
)
db.session.add(transaction)
```

```python
# CORRECT - Always include join_code
transaction = Transaction(
    student_id=student_id,
    join_code=join_code,  # REQUIRED
    amount=50.0,
    description="Payroll"
)
db.session.add(transaction)
```

### ❌ MISTAKE 3: Assuming one student = one StudentBlock

```python
# WRONG - Returns first StudentBlock, might be wrong period
student_block = StudentBlock.query.filter_by(
    student_id=student_id
).first()  # Which period???
```

```python
# CORRECT - Specify the period
student_block = StudentBlock.query.filter_by(
    student_id=student_id,
    join_code=join_code  # SPECIFIC PERIOD
).first()
```

### ❌ MISTAKE 4: Using session student_id without join_code

```python
# WRONG - No period context
@student_bp.route('/balance')
def balance():
    student_id = session.get('student_id')
    # How do we know which period's balance to show?
    return "???"
```

```python
# CORRECT - Get current class context first
@student_bp.route('/balance')
def balance():
    context = get_current_class_context()
    join_code = context['join_code']
    student_id = session.get('student_id')

    student_block = StudentBlock.query.filter_by(
        student_id=student_id,
        join_code=join_code
    ).first()

    return render_template('balance.html', student_block=student_block)
```

---

## Testing Multi-Tenancy

### Required Test Pattern

```python
def test_transactions_scoped_by_join_code(client, app):
    """Test transactions are isolated by join_code."""
    with app.app_context():
        # Setup: Create teacher with two class periods
        teacher = Admin(username="teacher1", ...)
        db.session.add(teacher)
        db.session.flush()

        # Period 1
        block1 = TeacherBlock(
            teacher_id=teacher.id,
            join_code="PERIOD1",
            block_name="Period 1"
        )
        db.session.add(block1)

        student1 = Student(username="student1", ...)
        db.session.add(student1)
        db.session.flush()

        student_block1 = StudentBlock(
            student_id=student1.id,
            join_code="PERIOD1",
            checking_balance=100.0
        )
        db.session.add(student_block1)

        transaction1 = Transaction(
            student_id=student1.id,
            join_code="PERIOD1",
            amount=50.0,
            description="Period 1 transaction"
        )
        db.session.add(transaction1)

        # Period 2 (SAME student, different period)
        block2 = TeacherBlock(
            teacher_id=teacher.id,
            join_code="PERIOD2",
            block_name="Period 2"
        )
        db.session.add(block2)

        student_block2 = StudentBlock(
            student_id=student1.id,  # SAME STUDENT
            join_code="PERIOD2",
            checking_balance=200.0  # DIFFERENT BALANCE
        )
        db.session.add(student_block2)

        transaction2 = Transaction(
            student_id=student1.id,  # SAME STUDENT
            join_code="PERIOD2",
            amount=75.0,
            description="Period 2 transaction"
        )
        db.session.add(transaction2)

        db.session.commit()

        # Execute: Query for PERIOD1 only
        period1_transactions = Transaction.query.filter_by(
            student_id=student1.id,
            join_code="PERIOD1"
        ).all()

        # Assert: Only PERIOD1 transaction returned
        assert len(period1_transactions) == 1
        assert period1_transactions[0].amount == 50.0
        assert period1_transactions[0].join_code == "PERIOD1"

        # Execute: Query for PERIOD2 only
        period2_transactions = Transaction.query.filter_by(
            student_id=student1.id,
            join_code="PERIOD2"
        ).all()

        # Assert: Only PERIOD2 transaction returned
        assert len(period2_transactions) == 1
        assert period2_transactions[0].amount == 75.0
        assert period2_transactions[0].join_code == "PERIOD2"
```

---

## Legacy `teacher_id` Column

### Current Status

The `students.teacher_id` column is **DEPRECATED** and should not be used.

**Why it exists:**
- Legacy column from before multi-tenancy support
- Kept for backward compatibility during migration

**Why NOT to use it:**
- Doesn't support multiple teachers per student
- Doesn't distinguish between class periods
- Will cause data leaks for multi-period students

**Correct approach:**
- Use `StudentTeacher` table for teacher-student relationships
- Use `StudentBlock` table for period-specific data
- Use `join_code` for all scoping

### Migration Plan

1. ✅ All routes updated to use `StudentTeacher` and `StudentBlock`
2. ✅ All queries scoped by `join_code`
3. ✅ Tests verify multi-tenancy isolation
4. ⏳ **Future:** Remove `teacher_id` column entirely

**DO NOT** add new code that uses `students.teacher_id`.

---

## Session Management

### Student Sessions

```python
# When student logs in
session['student_id'] = student.id
session['user_type'] = 'student'

# When student selects class period
session['current_join_code'] = join_code

# Always check for current_join_code in routes
join_code = session.get('current_join_code')
if not join_code:
    return redirect(url_for('student.select_class'))
```

### Admin/Teacher Sessions

```python
# When teacher logs in
session['admin_id'] = admin.id
session['user_type'] = 'admin'

# When teacher selects class period
session['current_join_code'] = join_code

# Always check for current_join_code in routes
join_code = session.get('current_join_code')
if not join_code:
    return redirect(url_for('admin.select_class'))
```

---

## Quick Reference

### Correct Scoping Checklist

- [ ] Query includes `join_code` filter
- [ ] Using scoped helpers (`get_admin_student_query`, `get_student_for_admin`)
- [ ] Getting `join_code` from session or context
- [ ] Creating new records with `join_code`
- [ ] Tests verify period isolation
- [ ] NOT using `teacher_id` for scoping
- [ ] NOT assuming one student = one period

### Tables That MUST Be Scoped

**Financial:**
- `Transaction`
- `TapEvent`
- `PayrollSettings`
- `PayrollReward`
- `PayrollFine`
- `RentSettings`
- `RentPayment`
- `RentWaiver`
- `BankingSettings`

**Store & Insurance:**
- `StoreItemBlock`
- `InsurancePolicyBlock`
- `StudentInsurance`
- `InsuranceClaim`

**Student Data:**
- `StudentBlock` (the scoping table itself)
- Any query returning student data

---

**Last Updated:** 2025-12-13
**Critical Incident:** P0 same-teacher multi-period data leak (fixed 2025-11-29)
**Documentation:** `docs/security/CRITICAL_SAME_TEACHER_LEAK.md`

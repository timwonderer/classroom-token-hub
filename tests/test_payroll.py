import pytest
from app import app, db, Student, TapEvent, Transaction
from app.payroll import calculate_payroll
from datetime import datetime, timedelta, timezone

# Tolerance for floating point comparisons
FLOAT_TOLERANCE = 0.0001

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


@pytest.fixture
def test_teacher(client):
    """Fixture to create a test teacher for payroll tests."""
    from app.models import Admin
    teacher = Admin(username="test_teacher", totp_secret="s")
    db.session.add(teacher)
    db.session.commit()
    return teacher

def test_calculate_payroll(client):
    from app.models import Admin, TeacherBlock, Student
    
    # Create Teacher
    teacher = Admin(username="prof_payroll", totp_secret="s")
    db.session.add(teacher)
    db.session.commit()

    # Create a student
    student = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=b'salt',
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()
    
    # CRITICAL: Link Student to Teacher/Class for Payroll Scoping
    # Payroll now strictly requires a claimed TeacherBlock (join_code)
    tb = TeacherBlock(
        teacher_id=teacher.id,
        student_id=student.id,
        block="A",
        join_code="JOIN123",
        is_claimed=True,
        first_name="Test",
        last_initial="S",
        last_name_hash_by_part=['mock_hash'],
        first_half_hash='hash123',
        salt=b's',
        dob_sum=123
    )
    db.session.add(tb)
    db.session.commit()
    
    # Set TapEvent join_code to match
    join_code = "JOIN123"

    # Create TapEvents to simulate attendance
    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=60)
    tap_out_time = now - timedelta(minutes=30)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time, join_code=join_code)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time, join_code=join_code)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    # Calculate payroll
    students = [student]
    last_payroll_time = now - timedelta(days=1)
    payroll_summary = calculate_payroll(students, last_payroll_time)

    # Assert the payroll amount is correct
    # 30 minutes of attendance = 1800 seconds
    # 1800 seconds * ($0.25 / 60 seconds) = $7.50
    expected_payroll = 7.50
    assert student.id in payroll_summary
    assert payroll_summary[student.id] == expected_payroll

    # Test case with no attendance
    # NOTE: student2 intentionally has no StudentTeacher link and no TeacherBlock
    # to verify proper skipping behavior in calculate_payroll. Students without
    # these associations should be skipped during payroll processing.
    student2 = Student(first_name="Test2", last_initial="S", block="B", salt=b'salt2', has_completed_setup=True)
    db.session.add(student2)
    db.session.commit()
    # Need to link student2 to avoid skipping?
    # Actually if student2 has NO attendance, payroll is 0 anyway or empty dict.
    # But if no TeacherBlock, it is skipped even before checking attendance.
    # We want to verify that student2 is NOT in summary.
    
    students2 = [student2]
    payroll_summary2 = calculate_payroll(students2, last_payroll_time)
    assert student2.id not in payroll_summary2

    # Manual payments after the last payroll should clear projected pay for that student
    manual_time = now - timedelta(minutes=5)
    manual_tx = Transaction(student_id=student.id, amount=3, type="manual_payment", timestamp=manual_time, join_code=join_code)
    db.session.add(manual_tx)
    db.session.commit()

    post_manual_summary = calculate_payroll(students, last_payroll_time)
    assert post_manual_summary == {}


def test_get_pay_rate_for_block_default(test_teacher):
    """Test that get_pay_rate_for_block returns default rate when no settings exist."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND
    
    # Get pay rate when no settings exist - should return default
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    assert rate == DEFAULT_PAY_RATE_PER_SECOND
    assert isinstance(rate, float)


def test_get_pay_rate_for_block_block_specific(test_teacher):
    """Test that block-specific settings return correct float values."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create block-specific payroll settings
    # pay_rate is stored in database as $ per minute
    block_setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block="A",
        pay_rate=Decimal("0.50"),  # $0.50 per minute
        is_active=True
    )
    db.session.add(block_setting)
    db.session.commit()
    
    # Get pay rate for the block - should convert to per-second rate
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    
    # Expected: 0.50 / 60.0 = 0.008333...
    expected_rate = 0.50 / 60.0
    assert abs(rate - expected_rate) < FLOAT_TOLERANCE
    assert isinstance(rate, float)


def test_get_pay_rate_for_block_global_fallback(test_teacher):
    """Test that global settings fallback works correctly."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create global payroll settings (block=None)
    global_setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block=None,  # Global setting
        pay_rate=Decimal("0.30"),  # $0.30 per minute
        is_active=True
    )
    db.session.add(global_setting)
    db.session.commit()
    
    # Get pay rate for a block that doesn't have specific settings
    # Should fall back to global settings
    rate = get_pay_rate_for_block("B", teacher_id=test_teacher.id)
    
    # Expected: 0.30 / 60.0 = 0.005
    expected_rate = 0.30 / 60.0
    assert rate == expected_rate
    assert isinstance(rate, float)


def test_get_pay_rate_for_block_precedence(test_teacher):
    """Test that block-specific settings take precedence over global settings."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create global setting
    global_setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block=None,
        pay_rate=Decimal("0.25"),  # $0.25 per minute
        is_active=True
    )
    
    # Create block-specific setting (should take precedence)
    block_setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block="A",
        pay_rate=Decimal("0.75"),  # $0.75 per minute
        is_active=True
    )
    
    db.session.add_all([global_setting, block_setting])
    db.session.commit()
    
    # Block A should use block-specific rate
    rate_a = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    assert rate_a == 0.75 / 60.0
    
    # Block B should fall back to global rate
    rate_b = get_pay_rate_for_block("B", teacher_id=test_teacher.id)
    assert rate_b == 0.25 / 60.0


def test_get_pay_rate_for_block_per_minute_to_per_second_conversion(test_teacher):
    """Test that per-minute to per-second conversion is accurate."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create setting with exact value that's easy to verify
    setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block="A",
        pay_rate=Decimal("1.20"),  # $1.20 per minute
        is_active=True
    )
    db.session.add(setting)
    db.session.commit()
    
    # Get pay rate
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    
    # Expected: 1.20 / 60.0 = 0.02
    assert rate == 0.02
    assert isinstance(rate, float)


def test_get_pay_rate_for_block_json_serialization(test_teacher):
    """Test that the returned value works properly with JSON serialization."""
    import json
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create setting
    setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block="A",
        pay_rate=Decimal("0.45"),
        is_active=True
    )
    db.session.add(setting)
    db.session.commit()
    
    # Get pay rate
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    
    # Should be serializable to JSON without errors
    data = {"pay_rate": rate}
    json_str = json.dumps(data)
    assert json_str is not None
    
    # Deserialize and verify
    deserialized = json.loads(json_str)
    assert abs(deserialized["pay_rate"] - (0.45 / 60.0)) < FLOAT_TOLERANCE


def test_get_pay_rate_for_block_inactive_settings_ignored(test_teacher):
    """Test that inactive settings are ignored."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND
    from app.models import PayrollSettings
    from decimal import Decimal
    
    # Create an inactive setting
    inactive_setting = PayrollSettings(
        teacher_id=test_teacher.id,
        block="A",
        pay_rate=Decimal("0.99"),
        is_active=False  # Inactive
    )
    db.session.add(inactive_setting)
    db.session.commit()
    
    # Should fall back to default rate since the setting is inactive
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    assert rate == DEFAULT_PAY_RATE_PER_SECOND


def test_get_pay_rate_for_block_no_teacher_id(client):
    """Test that function returns default when no teacher_id is provided."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND
    
    # Call without teacher_id (and outside request context)
    rate = get_pay_rate_for_block("A", teacher_id=None)
    assert rate == DEFAULT_PAY_RATE_PER_SECOND
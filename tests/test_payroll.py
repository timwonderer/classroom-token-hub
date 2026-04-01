import pytest
from app import db, Student, TapEvent, Transaction
from app.payroll import calculate_payroll
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Tolerance for floating point comparisons
FLOAT_TOLERANCE = 0.0001

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
        last_name_hash_by_part=None,
        first_half_hash='hash123',
        salt=b's',
        dob_sum_hash=None
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


def test_calculate_payroll_ignores_other_class_manual_payment_anchor(client):
    from app.models import Admin, TeacherBlock, Student
    from tests.helpers.class_scope import create_class_scope

    teacher = Admin(username="prof_multiclass", totp_secret="s")
    db.session.add(teacher)
    db.session.commit()

    student = Student(
        first_name="Multi",
        last_initial="S",
        block="A,B",
        salt=b'salt',
        has_completed_setup=True,
    )
    db.session.add(student)
    db.session.flush()
    class_a = create_class_scope(
        teacher=teacher,
        join_code="PAYA01",
        student=student,
        block="A",
        display_name="A",
    )
    class_b = create_class_scope(
        teacher=teacher,
        join_code="PAYB01",
        student=student,
        block="B",
        display_name="B",
    )
    db.session.flush()

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher.id,
            student_id=student.id,
            block="A",
            join_code="PAYA01",
            class_id=class_a.class_id,
            is_claimed=True,
            first_name="Multi",
            last_initial="S",
            last_name_hash_by_part=None,
            first_half_hash='hash-a',
            salt=b's',
            dob_sum_hash=None,
        ),
        TeacherBlock(
            teacher_id=teacher.id,
            student_id=student.id,
            block="B",
            join_code="PAYB01",
            class_id=class_b.class_id,
            is_claimed=True,
            first_name="Multi",
            last_initial="S",
            last_name_hash_by_part=None,
            first_half_hash='hash-b',
            salt=b's',
            dob_sum_hash=None,
        ),
    ])

    now = datetime.now(timezone.utc)
    db.session.add_all([
        TapEvent(student_id=student.id, period="A", status="active", timestamp=now - timedelta(minutes=50), join_code="PAYA01"),
        TapEvent(student_id=student.id, period="A", status="inactive", timestamp=now - timedelta(minutes=40), join_code="PAYA01"),
        TapEvent(student_id=student.id, period="B", status="active", timestamp=now - timedelta(minutes=30), join_code="PAYB01"),
        TapEvent(student_id=student.id, period="B", status="inactive", timestamp=now - timedelta(minutes=15), join_code="PAYB01"),
        Transaction(student_id=student.id, amount=3, type="manual_payment", timestamp=now - timedelta(minutes=5), join_code="PAYA01"),
    ])
    db.session.commit()

    summary = calculate_payroll([student], now - timedelta(days=1), teacher_id=teacher.id)

    expected_class_b_only = Decimal("3.75")
    assert summary == {student.id: expected_class_b_only}


def test_get_pay_rate_for_block_default(test_teacher):
    """Test that get_pay_rate_for_block returns default rate when no settings exist."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND
    
    # Get pay rate when no settings exist - should return default
    rate = get_pay_rate_for_block("A", teacher_id=test_teacher.id)
    # Default is now Decimal
    from decimal import Decimal
    assert rate == DEFAULT_PAY_RATE_PER_SECOND
    assert isinstance(rate, Decimal)


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
    assert abs(float(rate) - expected_rate) < FLOAT_TOLERANCE
    assert isinstance(rate, Decimal)


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
    assert float(rate) == expected_rate
    assert isinstance(rate, Decimal)


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
    assert float(rate_a) == 0.75 / 60.0
    
    # Block B should fall back to global rate
    rate_b = get_pay_rate_for_block("B", teacher_id=test_teacher.id)
    assert abs(float(rate_b) - (0.25 / 60.0)) < FLOAT_TOLERANCE


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
    assert float(rate) == 0.02
    assert isinstance(rate, Decimal)


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
    
    # Should be serializable to JSON without errors (when converted)
    # Note: Standard json.dumps does not support Decimal, but our API uses custom encoders
    # For this test, verifying we can serialize it after conversion is sufficient
    data = {"pay_rate": float(rate)}
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


def test_get_cached_payroll_with_meta(client):
    """Test the caching logic for payroll."""
    from app.payroll import get_cached_payroll_with_meta
    from app.models import Admin, Student, TeacherBlock, PayrollCache, TapEvent
    from tests.helpers.class_scope import create_class_scope
    from datetime import datetime, timedelta, timezone
    
    # Setup Teacher
    teacher = Admin(username="prof_cache", totp_secret="s")
    db.session.add(teacher)
    db.session.commit()
    
    # Setup Student
    student = Student(first_name="CacheUser", last_initial="T", block="A", salt=b's', has_completed_setup=True)
    db.session.add(student)
    db.session.flush()
    class_economy = create_class_scope(
        teacher=teacher,
        join_code="CACHE1",
        student=student,
        block="A",
        display_name="A",
    )
    db.session.commit()
    
    # Link
    tb = TeacherBlock(
        teacher_id=teacher.id, student_id=student.id, block="A", join_code="CACHE1", is_claimed=True,
        class_id=class_economy.class_id,
        first_name="CacheUser", last_initial="T", last_name_hash_by_part=None, first_half_hash='h', salt=b's', dob_sum_hash=None
    )
    db.session.add(tb)
    db.session.commit()
    
    # Add Attendance (1 hour at default rate)
    now = datetime.now(timezone.utc)
    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=now-timedelta(hours=2), join_code="CACHE1")
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=now-timedelta(hours=1), join_code="CACHE1")
    db.session.add_all([tap_in, tap_out])
    db.session.commit()
    
    students = [student]
    last_payroll = now - timedelta(days=1)
    
    # 1. First Call: Cache Miss -> Calculation
    summary, updated_at = get_cached_payroll_with_meta(students, last_payroll, teacher_id=teacher.id, join_code="CACHE1")
    assert student.id in summary
    assert summary[student.id] > 0
    # Store initial values to compare later
    initial_amount = summary[student.id]
    initial_updated_at = updated_at
    
    # Verify Cache Entry Exists
    cache = PayrollCache.query.filter_by(class_id=class_economy.class_id).first()
    assert cache is not None
    assert cache.join_code == "CACHE1"
    assert str(student.id) in cache.cached_breakdown
    
    # 2. Second Call: Cache Hit (Verify Staleness)
    # Add more attendance events that SHOULD increase payroll if recalculated
    # Adding another 15 minutes
    tap_in2 = TapEvent(student_id=student.id, period="A", status="active", timestamp=now-timedelta(minutes=30), join_code="CACHE1")
    tap_out2 = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=now-timedelta(minutes=15), join_code="CACHE1")
    db.session.add_all([tap_in2, tap_out2])
    db.session.commit()
    
    # Call again - should still return OLD value (Cache Hit)
    summary_cached, updated_at_cached = get_cached_payroll_with_meta(students, last_payroll, teacher_id=teacher.id, join_code="CACHE1")
    # Value should be unchanged
    assert summary_cached[student.id] == initial_amount 
    # Timestamp should be unchanged
    assert updated_at_cached == initial_updated_at 
    
    # 3. Simulate Expiry -> Cache Miss -> Calculation
    # Force cache timestamp to be old (2 hours ago)
    cache.last_calculated_at = now - timedelta(hours=2)
    db.session.commit()
    
    # Call again - should Recalculate
    summary_fresh, updated_at_fresh = get_cached_payroll_with_meta(students, last_payroll, teacher_id=teacher.id, join_code="CACHE1")
    # Amount should increase due to new events
    assert summary_fresh[student.id] > initial_amount 
    # Timestamp should be newer
    assert updated_at_fresh > initial_updated_at

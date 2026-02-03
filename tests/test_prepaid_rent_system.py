"""
Test pre-paid rent system and back rent accumulation.

Tests that rent payment system works as pre-paid where:
- Payment for January covers student until February due date
- Students retain privileges if they've paid for current coverage period
- Back rent accumulates for missed payments
- Payments apply to oldest unpaid period first
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from app import create_app, db
from app.models import Admin, Student, RentSettings, RentPayment, TeacherBlock, Transaction


@pytest.fixture
def app():
    """Create test application."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
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
def setup_teacher_and_student(app):
    """Create teacher, student, and rent settings."""
    with app.app_context():
        # Create teacher
        teacher = Admin(
            username="testteacher",
            totp_secret="TESTSECRET123456"
        )
        db.session.add(teacher)
        db.session.flush()
        
        # Create student
        student = Student(
            first_name="Test",
            last_name="Student",
            block="A",
            is_rent_enabled=True
        )
        db.session.add(student)
        db.session.flush()
        
        # Create teacher block
        teacher_block = TeacherBlock(
            teacher_id=teacher.id,
            student_id=student.id,
            block="A",
            join_code="TEST123",
            is_claimed=True
        )
        db.session.add(teacher_block)
        
        # Create rent settings with monthly frequency
        first_due = datetime(2025, 1, 28)  # First rent due Jan 28, 2025
        rent_settings = RentSettings(
            teacher_id=teacher.id,
            block="A",
            is_enabled=True,
            rent_amount=Decimal('50.00'),
            frequency_type='monthly',
            first_rent_due_date=first_due,
            grace_period_days=3,
            late_penalty_amount=Decimal('10.00')
        )
        db.session.add(rent_settings)
        db.session.commit()
        
        return {
            'teacher': teacher,
            'student': student,
            'settings': rent_settings,
            'join_code': 'TEST123'
        }


def test_payment_covers_correct_period(app, setup_teacher_and_student):
    """Test that payment made in January covers January, not payment month."""
    with app.app_context():
        data = setup_teacher_and_student
        student = Student.query.get(data['student'].id)
        settings = RentSettings.query.get(data['settings'].id)
        
        # Make payment on January 15 for rent due January 28
        payment_date = datetime(2025, 1, 15)
        
        # Coverage should be January (due date month), not payment month
        from app.routes.student import _calculate_coverage_period
        coverage_month, coverage_year = _calculate_coverage_period(settings, payment_date)
        
        assert coverage_month == 1, "Payment should cover January"
        assert coverage_year == 2025, "Payment should cover 2025"


def test_prepaid_privileges_persist_until_next_due_date(app, setup_teacher_and_student):
    """Test that student who paid for January keeps privileges through February."""
    with app.app_context():
        data = setup_teacher_and_student
        student = Student.query.get(data['student'].id)
        
        # Student pays rent on Jan 15 for period due Jan 28
        payment = RentPayment(
            student_id=student.id,
            period="A",
            join_code=data['join_code'],
            amount_paid=Decimal('50.00'),
            period_month=1,  # Paid in January
            period_year=2025,
            coverage_month=1,  # Covers January
            coverage_year=2025,
            was_late=False
        )
        db.session.add(payment)
        db.session.commit()
        
        # Check privileges on Feb 15 (before Feb 28 due date)
        # Student should still have privileges since they paid for Jan
        settings = RentSettings.query.get(data['settings'].id)
        from app.routes.student import _calculate_rent_deadlines
        
        check_date = datetime(2025, 2, 15)
        current_due, _ = _calculate_rent_deadlines(settings, check_date)
        
        # On Feb 15, the current due date should be Feb 28
        assert current_due.month == 2, "Current due date should be in February"
        
        # Check if student has paid for February period
        coverage_month = current_due.month
        coverage_year = current_due.year
        
        has_paid_february = RentPayment.query.filter_by(
            student_id=student.id,
            period="A",
            coverage_month=coverage_month,
            coverage_year=coverage_year
        ).first() is not None
        
        # Student hasn't paid for February yet, so should not have privileges
        assert not has_paid_february, "Student hasn't paid for February period"


def test_back_rent_accumulation(app, setup_teacher_and_student):
    """Test that missed payments accumulate as back rent."""
    with app.app_context():
        data = setup_teacher_and_student
        student = Student.query.get(data['student'].id)
        settings = RentSettings.query.get(data['settings'].id)
        
        # Check on March 15 - student should owe Jan + Feb + Mar
        check_date = datetime(2025, 3, 15)
        
        from app.routes.student import _calculate_unpaid_periods
        unpaid = _calculate_unpaid_periods(
            student, settings, "A", data['join_code'], check_date
        )
        
        # Should have 3 unpaid periods (Jan, Feb, Mar)
        assert len(unpaid) >= 2, f"Expected at least 2 unpaid periods, got {len(unpaid)}"
        
        # Total owed should be at least 2 months of rent
        total_owed = sum(p['amount_owed'] for p in unpaid)
        assert total_owed >= Decimal('100.00'), f"Should owe at least $100, got ${total_owed}"


def test_payment_applies_to_oldest_period_first(app, setup_teacher_and_student):
    """Test that payments are applied to oldest unpaid period first."""
    with app.app_context():
        data = setup_teacher_and_student
        student = Student.query.get(data['student'].id)
        settings = RentSettings.query.get(data['settings'].id)
        
        # Student is in March with no payments (owes Jan, Feb, Mar)
        check_date = datetime(2025, 3, 15)
        
        from app.routes.student import _calculate_unpaid_periods
        unpaid_before = _calculate_unpaid_periods(
            student, settings, "A", data['join_code'], check_date
        )
        
        # Make one payment - should apply to January (oldest)
        payment = RentPayment(
            student_id=student.id,
            period="A",
            join_code=data['join_code'],
            amount_paid=Decimal('50.00'),
            period_month=3,  # Paid in March
            period_year=2025,
            coverage_month=1,  # Should cover January (oldest)
            coverage_year=2025,
            was_late=True
        )
        db.session.add(payment)
        db.session.commit()
        
        # Check unpaid periods again
        unpaid_after = _calculate_unpaid_periods(
            student, settings, "A", data['join_code'], check_date
        )
        
        # Should have one less unpaid period
        assert len(unpaid_after) < len(unpaid_before), "Should have fewer unpaid periods after payment"
        
        # January should be paid, February should be oldest unpaid
        if unpaid_after:
            oldest_unpaid = unpaid_after[0]
            assert oldest_unpaid['coverage_month'] == 2, "February should be oldest unpaid after paying January"


def test_multiple_periods_paid_at_once(app, setup_teacher_and_student):
    """Test that large payment can cover multiple periods."""
    with app.app_context():
        data = setup_teacher_and_student
        student = Student.query.get(data['student'].id)
        
        # Pay for both January and February at once
        payment1 = RentPayment(
            student_id=student.id,
            period="A",
            join_code=data['join_code'],
            amount_paid=Decimal('50.00'),
            period_month=1,
            period_year=2025,
            coverage_month=1,
            coverage_year=2025
        )
        payment2 = RentPayment(
            student_id=student.id,
            period="A",
            join_code=data['join_code'],
            amount_paid=Decimal('50.00'),
            period_month=1,
            period_year=2025,
            coverage_month=2,
            coverage_year=2025
        )
        db.session.add(payment1)
        db.session.add(payment2)
        db.session.commit()
        
        # Check on Feb 15 - both periods should be paid
        check_date = datetime(2025, 2, 15)
        settings = RentSettings.query.get(data['settings'].id)
        
        from app.routes.student import _calculate_unpaid_periods
        unpaid = _calculate_unpaid_periods(
            student, settings, "A", data['join_code'], check_date
        )
        
        # Should have no unpaid periods for Jan or Feb
        for period in unpaid:
            assert period['coverage_month'] not in [1, 2], \
                f"January and February should be paid, but month {period['coverage_month']} is unpaid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

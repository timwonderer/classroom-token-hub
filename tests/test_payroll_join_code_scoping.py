from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from decimal import Decimal
from app.extensions import db
from app.models import PayrollSettings, Admin, ClassEconomy
from app.payroll import get_pay_rate_for_block, get_daily_limit_seconds

def test_pay_rate_scoping_strictness(client):
    """
    Verify that payroll settings lookup is STRICTLY join_code scoped.
    Legacy teacher_id fallback should NOT occur in student context.
    """
    # Setup: Teacher with two classes (join codes)
    teacher = make_admin('teacher_strict', 'dummy_secret')
    # teacher.set_password('password') # Admin model doesn't have set_password or it's not needed here
    db.session.add(teacher)
    db.session.commit()
    
    # Create Class Economies
    class_a = ClassEconomy(join_code='CLASS-A', teacher_id=teacher.id, display_name='Class A', created_by_admin_id=teacher.id)
    class_b = ClassEconomy(join_code='CLASS-B', teacher_id=teacher.id, display_name='Class B', created_by_admin_id=teacher.id)
    db.session.add_all([class_a, class_b])
    db.session.commit()

    # 1. Global Teacher Default (should be IGNORED by strict join_code lookup)
    global_setting = PayrollSettings(
        teacher_id=teacher.id,
        block=None,
        join_code=None,
        pay_rate=Decimal('6.00') # $0.10/min
    )
    db.session.add(global_setting)
    
    # 2. Join Code Specific (Class A)
    # Rate: $0.50/min
    class_a_setting = PayrollSettings(
        teacher_id=teacher.id,
        block='Period 1',
        join_code='CLASS-A',
        pay_rate=Decimal('0.50') # $0.50/min
    )
    db.session.add(class_a_setting)
    
    db.session.commit()

    # --- Verification ---

    # Case A: Explicit Join Code (CLASS-A) should match Class A setting
    rate_a = get_pay_rate_for_block('Period 1', teacher_id=teacher.id, join_code='CLASS-A')
    assert round(rate_a * 60, 2) == Decimal('0.50'), "Should find CLASS-A setting"

    # Case B: Explicit Join Code (CLASS-B) 
    # CLASS-B has NO settings. 
    # STRICT BEHAVIOR: Should NOT fall back to global_setting ($0.10).
    # Should return default system rate ($0.25/min usually) or None if we change return type.
    # Current default in payroll.py is DEFAULT_PAY_RATE_PER_SECOND (~0.25/min)
    
    # NOTE: The implementation plan says "return default/None (do NOT fall back to teacher global)".
    # If we remove fallback, it should return the hardcoded default (0.25) not the teacher's global (0.10).
    rate_b = get_pay_rate_for_block('Period 1', teacher_id=teacher.id, join_code='CLASS-B')
    
    # 0.25 is standard default
    assert round(rate_b * 60, 2) == Decimal('0.25'), \
        f"Should return system default (0.25) when no class setting exists. Got {round(rate_b * 60, 2)}"

    # Case C: Missing Join Code in Student Context
    # Should raise error or behave predictably (depending on implementation choice).
    # For now, let's assume we pass None and it might behave like legacy (which we want to remove),
    # OR we explicitly fail it. 
    # Plan says: "In student context, join_code is mandatory".
    # We will enforce this by ensuring we don't use it without join_code in student routes.
    # At function level, if we pass None, it might still allow teacher-context usage (legacy admin tools).
    # BUT for this test we focus on cross-talk.
    
    pass 


def test_daily_limit_scoping_strictness(client):
    """
    Verify daily limit strict scoping.
    """
    teacher = make_admin('teacher_limit_strict', 'dummy_secret')
    # teacher.set_password('password')
    db.session.add(teacher)
    db.session.commit()
    
    class_x = ClassEconomy(join_code='CLASS-X', teacher_id=teacher.id, display_name='Class X', created_by_admin_id=teacher.id)
    db.session.add(class_x)
    db.session.commit()
    
    # Teacher Global Limit: 1 hour
    global_limit = PayrollSettings(
        teacher_id=teacher.id,
        block=None,
        join_code=None,
        settings_mode='simple',
        daily_limit_hours=1.0
    )
    db.session.add(global_limit)
    
    # Class X Specific Limit: 2 hours
    class_limit = PayrollSettings(
        teacher_id=teacher.id,
        block='Period 1',
        join_code='CLASS-X',
        settings_mode='simple',
        daily_limit_hours=2.0
    )
    db.session.add(class_limit)
    db.session.commit()
    
    # Verify Class X gets 2 hours
    limit_x = get_daily_limit_seconds('Period 1', teacher_id=teacher.id, join_code='CLASS-X')
    assert limit_x == 7200
    
    # Verify CLASS-Y (no specific limit) does NOT get teacher global limit
    # (Strict separation)
    limit_y = get_daily_limit_seconds('Period 1', teacher_id=teacher.id, join_code='CLASS-Y')
    assert limit_y is None, "Should NOT fall back to teacher global limit in strict mode"

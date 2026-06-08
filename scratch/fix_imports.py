import re
from pathlib import Path

files = [
    'tests/test_add_rent_waiver_route.py',
    'tests/test_admin_auth.py',
    'tests/test_admin_export_students_scoping.py',
    'tests/test_admin_help_support.py',
    'tests/test_admin_membership_gates.py',
    'tests/test_admin_payroll_manual_payment_invariants.py',
    'tests/test_admin_payroll_scoped_balances.py',
    'tests/test_admin_tenancy.py',
    'tests/test_analytics.py',
    'tests/test_announcements.py',
    'tests/test_api_admin_tap_scope.py',
    'tests/test_api_tenancy.py',
    'tests/test_backfill_transactions.py',
    'tests/test_banking_settings_class_scope.py',
    'tests/test_class_context_and_switching.py',
    'tests/test_class_deletion.py',
    'tests/test_class_deletion_audit_fixes.py',
    'tests/test_collective_goal_expiration.py',
    'tests/test_collective_goal_progress.py',
    'tests/test_core_invariants_smoke.py',
    'tests/test_dashboard_rendering.py',
    'tests/test_decimal_precision.py',
    'tests/test_decimal_type_errors.py',
    'tests/test_economy_api.py',
    'tests/test_economy_policy_mode.py',
    'tests/test_export_students_scoping.py',
    'tests/test_feature_flag_enforcement.py',
    'tests/test_feature_settings.py',
    'tests/test_flow_credential_reset.py',
    'tests/test_hall_pass_checkout.py',
    'tests/test_hall_pass_verify.py',
    'tests/test_identity_profile_centralization.py',
    'tests/test_insurance_class_scoping.py',
    'tests/test_insurance_security.py',
    'tests/test_insurance_snapshots.py',
    'tests/test_issue_payroll_display_fix.py',
    'tests/test_join_code_deletion_semantics.py',
    'tests/test_join_code_generation.py',
    'tests/test_navigation_integrity.py',
    'tests/test_payroll_settings_class_scope.py',
    'tests/test_redemption_audit_log.py',
    'tests/test_redemption_rejection.py',
    'tests/test_rent_display_dynamic.py',
    'tests/test_rent_item_types.py',
    'tests/test_rent_penalty_reversal.py',
    'tests/test_rent_privileges_overdue.py',
    'tests/test_rent_settings_class_scope.py',
    'tests/test_route_authorization_sweep.py',
    'tests/test_settings_fallback_removal.py',
    'tests/test_shared_student_attendance.py',
    'tests/test_shared_student_payroll.py',
    'tests/test_student_dashboard_rent.py',
    'tests/test_student_payroll_rate.py',
    'tests/test_student_recovery.py',
    'tests/test_student_scoped_earnings_display.py',
    'tests/test_teacher_recovery.py',
    'tests/test_teacher_student_flow.py',
    'tests/test_ticket_log_correlation_pack.py',
    'tests/test_void_transaction_rules.py'
]

# also need to fix class_scope.py
files.append('tests/helpers/class_scope.py')

for f in files:
    p = Path(f)
    if not p.exists(): continue
    content = p.read_text()
    
    # Remove TeacherBlock from app.models import
    content = re.sub(r"\bTeacherBlock\s*,\s*", "", content)
    content = re.sub(r",\s*TeacherBlock\b", "", content)
    
    # If the import line was `from app.models import TeacherBlock`, it becomes `from app.models import `
    content = re.sub(r"from app\.models import\s*\n", "", content)
    
    # Add the new import if TeacherBlock is used
    if "TeacherBlock" in content and "mock_teacher_block" not in content:
        # insert after first from app import
        new_import = "from tests.helpers.mock_teacher_block import TeacherBlock\n"
        if "from app.models import" in content:
            content = content.replace("from app.models import", new_import + "from app.models import", 1)
        else:
            content = new_import + content
            
    p.write_text(content)

print("Imports fixed.")

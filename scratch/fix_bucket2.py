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

remove_kwargs = [
    r"teacher_id=[^,]+,",
    r"is_claimed=[^,]+,",
    r"first_name=[^,]+,",
    r"last_initial=[^,]+,",
    r"last_name_hash_by_part=[^,]+,",
    r"dob_sum_hash=[^,]+,",
    r"salt=[^,]+,",
    r"first_half_hash=[^,]+,",
    r"identity_id=[^,]+,",
    r"class_label=[^,]+,"
]

for f in files:
    p = Path(f)
    if not p.exists(): continue
    content = p.read_text()
    
    # Replace TeacherBlock constructor with Seat
    # Note: we need to import Seat if it's not imported.
    if "TeacherBlock" in content:
        content = content.replace("TeacherBlock", "Seat")
    
    # We replaced the import, so Seat is now in the file but TeacherBlock might be everywhere.
    # Wait, earlier I removed TeacherBlock from the imports. Now we should add Seat to imports if not there.
    if "from app.models import" in content and "Seat" not in content:
        content = re.sub(r"(from app\.models import[^\n]+)", r"\1, Seat", content, count=1)
    
    for kwarg in remove_kwargs:
        content = re.sub(kwarg, "", content)
    
    # Remove trailing commas that might have been left if the kwarg was the last one before a parenthesis
    content = re.sub(r",\s*\)", ")", content)

    # Some kwargs might not have a comma if they were the last argument
    remove_kwargs_end = [k[:-1] + r"\s*\)" for k in remove_kwargs]
    for k in remove_kwargs_end:
        content = re.sub(k, ")", content)

    p.write_text(content)

print("Rewrote TeacherBlock to Seat in Bucket 2.")

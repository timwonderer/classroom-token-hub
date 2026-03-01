import os
import glob
import re

files = glob.glob('docs/**/*.md', recursive=True) + glob.glob('*.md')

# Manual fixes for complex renames and common issues in index and README files
fixes = {
    # Replace feature index links
    "features/teacher/classroom/index": "features/teacher/class-management/index",
    "features/teacher/economy/index": "features/teacher/economy-and-analytics/index",
    "features/teacher/bills/index": "features/teacher/rent/index",
    "features/teacher/settings/index": "features/teacher/account-customization/index",
    "features/student/account/index": "features/student/student-account-actions/index",
    "features/student/work/index": "features/student/starting-and-ending-work/index",
    "features/student/support/index": "features/student/reporting-issues/index",

    # Common nested files
    "features/teacher/classroom/announcements": "features/teacher/class-management/announcements",
    "features/teacher/classroom/attendance-approvals": "features/teacher/attendance-and-payroll/attendance-approvals",
    "features/teacher/classroom/attendance-corrections": "features/teacher/attendance-and-payroll/attendance-corrections",
    "features/teacher/classroom/class-setup": "features/teacher/class-management/class-setup",
    "features/teacher/classroom/dashboard-overview": "features/teacher/class-management/dashboard-overview",
    "features/teacher/classroom/hall-pass": "features/teacher/class-management/hall-pass",
    "features/teacher/classroom/student-issues": "features/teacher/student-issues/student-issues",
    "features/teacher/classroom/students-overview": "features/teacher/managing-students/students-overview",

    "features/teacher/economy/analytics": "features/teacher/economy-and-analytics/analytics",
    "features/teacher/economy/banking-interest": "features/teacher/banking/banking-interest",
    "features/teacher/economy/banking-overdraft": "features/teacher/banking/banking-overdraft",
    "features/teacher/economy/banking-settings": "features/teacher/banking/banking-settings",
    "features/teacher/economy/economy-health": "features/teacher/economy-and-analytics/economy-health",
    "features/teacher/economy/payroll-history": "features/teacher/attendance-and-payroll/payroll-history",
    "features/teacher/economy/payroll-run": "features/teacher/attendance-and-payroll/payroll-run",
    "features/teacher/economy/payroll-settings": "features/teacher/attendance-and-payroll/payroll-settings",
    "features/teacher/economy/store-items": "features/teacher/store/store-items",
    "features/teacher/economy/store-pricing": "features/teacher/store/store-pricing",
    "features/teacher/economy/store-redemptions": "features/teacher/store/store-redemptions",
    "features/teacher/economy/transactions": "features/teacher/banking/transactions",

    "features/teacher/bills/insurance-claims": "features/teacher/insurance/insurance-claims",
    "features/teacher/bills/insurance-enrollment": "features/teacher/insurance/insurance-enrollment",
    "features/teacher/bills/insurance-policies": "features/teacher/insurance/insurance-policies",
    "features/teacher/bills/rent-behaviors": "features/teacher/rent/rent-behaviors",
    "features/teacher/bills/rent-itemization": "features/teacher/rent/rent-itemization-2",
    "features/teacher/bills/rent-settings": "features/teacher/rent/rent-settings",
    "features/teacher/bills/rent-waivers": "features/teacher/rent/rent-waivers",

    "features/teacher/settings/account-deletion": "features/teacher/account-customization/account-deletion",
    "features/teacher/settings/account-recovery": "features/teacher/account-customization/account-recovery",
    "features/teacher/settings/feature-toggles": "features/teacher/system-features/feature-toggles",
    "features/teacher/settings/passkey": "features/teacher/account-customization/passkey",
    "features/teacher/settings/personalization": "features/teacher/account-customization/personalization",

    "features/student/account/dashboard-overview": "features/student/student-account-actions/dashboard-overview",
    "features/student/account/join-class": "features/student/student-account-actions/join-class",
    "features/student/account/login-setup": "features/student/student-account-actions/login-setup",
    "features/student/account/reset-recovery": "features/student/student-account-actions/reset-recovery",
    "features/student/account/switch-class": "features/student/student-account-actions/switch-class",

    "features/student/bills/insurance-claims": "features/student/insurance/insurance-claims",
    "features/student/bills/insurance-coverage": "features/student/insurance/insurance-coverage",
    "features/student/bills/rent-payments": "features/student/rent/rent-payments",

    "features/student/support/help-center": "features/student/reporting-issues/help-center",
    "features/student/support/report-issues": "features/student/reporting-issues/report-issues",

    "features/student/work/attendance-history": "features/student/starting-and-ending-work/attendance-history",
    "features/student/work/start-end-work": "features/student/starting-and-ending-work/start-end-work",
}

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    updated = False
    for old, new in fixes.items():
        # we try to replace both versions of links
        old_full = f"/docs/user-guides/{old}"
        new_full = f"/docs/user-guides/{new}"

        old_md = f"user-guides/{old}.md"
        new_md = f"user-guides/{new}.md"

        if old_full in content:
            content = content.replace(old_full, new_full)
            updated = True

        if old_md in content:
            content = content.replace(old_md, new_md)
            updated = True

    if updated:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)

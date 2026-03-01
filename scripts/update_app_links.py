import os
import glob
import re

ACTION_LOG_FILE = "docs/audits/documentation_action_log.md"

def log_action(action, file_path, details):
    with open(ACTION_LOG_FILE, "a") as f:
        f.write(f"- **{action}**: `{file_path}` - {details}\n")

mappings = {
    # Old links -> New links (without .md or /docs prefix if possible, but handle fully)
    "features/analytics/interpreting-analytics": "features/teacher/economy-and-analytics/interpreting-analytics",
    "features/banking/transferring-money": "features/student/banking/transferring-money",
    "features/banking/managing-banking": "features/teacher/banking/managing-banking",
    "features/rent/itemization-guide": "features/teacher/rent/itemization-guide",
    "features/rent/managing-rent": "features/teacher/rent/managing-rent",
    "features/payroll/running-payroll": "features/teacher/attendance-and-payroll/running-payroll",
    "features/store/creating-items": "features/teacher/store/creating-items",

    "features/teacher/classroom/announcements": "features/teacher/class-management/announcements",
    "features/teacher/classroom/attendance-approvals": "features/teacher/attendance-and-payroll/attendance-approvals",
    "features/teacher/classroom/attendance-corrections": "features/teacher/attendance-and-payroll/attendance-corrections",
    "features/teacher/classroom/class-setup": "features/teacher/class-management/class-setup",
    "features/teacher/classroom/dashboard-overview": "features/teacher/class-management/dashboard-overview",
    "features/teacher/classroom/hall-pass": "features/teacher/class-management/hall-pass",
    "features/teacher/classroom/student-issues": "features/teacher/student-issues/student-issues",
    "features/teacher/classroom/students-overview": "features/teacher/managing-students/students-overview",
    "features/teacher/classroom/index": "features/teacher/class-management/index",

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
    "features/teacher/economy/index": "features/teacher/economy-and-analytics/index",

    "features/teacher/bills/insurance-claims": "features/teacher/insurance/insurance-claims",
    "features/teacher/bills/insurance-enrollment": "features/teacher/insurance/insurance-enrollment",
    "features/teacher/bills/insurance-policies": "features/teacher/insurance/insurance-policies",
    "features/teacher/bills/rent-behaviors": "features/teacher/rent/rent-behaviors",
    "features/teacher/bills/rent-itemization": "features/teacher/rent/rent-itemization-2",
    "features/teacher/bills/rent-settings": "features/teacher/rent/rent-settings",
    "features/teacher/bills/rent-waivers": "features/teacher/rent/rent-waivers",
    "features/teacher/bills/index": "features/teacher/rent/index",

    "features/teacher/settings/account-deletion": "features/teacher/account-customization/account-deletion",
    "features/teacher/settings/account-recovery": "features/teacher/account-customization/account-recovery",
    "features/teacher/settings/feature-toggles": "features/teacher/system-features/feature-toggles",
    "features/teacher/settings/passkey": "features/teacher/account-customization/passkey",
    "features/teacher/settings/personalization": "features/teacher/account-customization/personalization",
    "features/teacher/settings/index": "features/teacher/account-customization/index",

    "features/student/account/dashboard-overview": "features/student/student-account-actions/dashboard-overview",
    "features/student/account/join-class": "features/student/student-account-actions/join-class",
    "features/student/account/login-setup": "features/student/student-account-actions/login-setup",
    "features/student/account/reset-recovery": "features/student/student-account-actions/reset-recovery",
    "features/student/account/switch-class": "features/student/student-account-actions/switch-class",
    "features/student/account/index": "features/student/student-account-actions/index",

    "features/student/banking/accounts-transfers": "features/student/banking/accounts-transfers",
    "features/student/banking/savings-interest": "features/student/banking/savings-interest",
    "features/student/banking/index": "features/student/banking/index",

    "features/student/bills/insurance-claims": "features/student/insurance/insurance-claims",
    "features/student/bills/insurance-coverage": "features/student/insurance/insurance-coverage",
    "features/student/bills/rent-payments": "features/student/rent/rent-payments",
    "features/student/bills/index": "features/student/rent/index",

    "features/student/store/browse-buy": "features/student/store/browse-buy",
    "features/student/store/redemption-status": "features/student/store/redemption-status",
    "features/student/store/index": "features/student/store/index",

    "features/student/support/help-center": "features/student/reporting-issues/help-center",
    "features/student/support/report-issues": "features/student/reporting-issues/report-issues",
    "features/student/support/index": "features/student/reporting-issues/index",

    "features/student/work/attendance-history": "features/student/starting-and-ending-work/attendance-history",
    "features/student/work/start-end-work": "features/student/starting-and-ending-work/start-end-work",
    "features/student/work/index": "features/student/starting-and-ending-work/index",
}

app_files = glob.glob('app/**/*.py', recursive=True) + glob.glob('templates/**/*.html', recursive=True) + glob.glob('docs/**/*.md', recursive=True)

for file_path in app_files:
    if "archive" in file_path or "audits" in file_path: continue

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        updated = False
        for old, new in mappings.items():
            if old in content:
                content = content.replace(old, new)
                updated = True

        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            log_action("Update", file_path, "Updated old doc links to new structure")
    except Exception as e:
        print(f"Skipping {file_path}: {e}")

print("App link updates complete.")

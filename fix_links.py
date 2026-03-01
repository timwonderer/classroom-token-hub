import re
import glob
import os

files = glob.glob('docs/**/*.md', recursive=True) + glob.glob('*.md')
mappings = {
    "/docs/user-guides/features/teacher/classroom/index": "/docs/user-guides/features/teacher/class-management/index",
    "/docs/user-guides/features/teacher/economy/index": "/docs/user-guides/features/teacher/economy-and-analytics/index",
    "/docs/user-guides/features/teacher/bills/index": "/docs/user-guides/features/teacher/rent/index",
    "/docs/user-guides/features/teacher/settings/index": "/docs/user-guides/features/teacher/account-customization/index",
    "/docs/user-guides/features/student/account/index": "/docs/user-guides/features/student/student-account-actions/index",
    "/docs/user-guides/features/student/work/index": "/docs/user-guides/features/student/starting-and-ending-work/index",
    "/docs/user-guides/features/student/store/index": "/docs/user-guides/features/student/store/index",
    "/docs/user-guides/features/student/banking/index": "/docs/user-guides/features/student/banking/index",
    "/docs/user-guides/features/student/bills/index": "/docs/user-guides/features/student/rent/index",
    "/docs/user-guides/features/student/support/index": "/docs/user-guides/features/student/reporting-issues/index",

    "/docs/user-guides/features/student/account/login-setup": "/docs/user-guides/features/student/student-account-actions/login-setup",
    "/docs/user-guides/features/student/work/start-end-work": "/docs/user-guides/features/student/starting-and-ending-work/start-end-work",
    "/docs/user-guides/features/student/store/browse-buy": "/docs/user-guides/features/student/store/browse-buy",
    "/docs/user-guides/features/student/banking/accounts-transfers": "/docs/user-guides/features/student/banking/accounts-transfers",
    "/docs/user-guides/features/student/bills/rent-payments": "/docs/user-guides/features/student/rent/rent-payments",
    "/docs/user-guides/features/student/support/help-center": "/docs/user-guides/features/student/reporting-issues/help-center",
}

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    updated = False
    for old, new in mappings.items():
        if old in content:
            content = content.replace(old, new)
            updated = True
    if updated:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)

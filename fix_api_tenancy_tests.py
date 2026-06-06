import re

file_path = "tests/test_api_tenancy.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace user_role="student" with user_role=UserRole.STUDENT
content = content.replace('user_role="student"', 'user_role=UserRole.STUDENT')

# Add import for UserRole if missing
if 'UserRole' not in content:
    content = content.replace('from app.models import (', 'from app.models import (\n    UserRole,')

with open(file_path, "w") as f:
    f.write(content)

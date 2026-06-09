import re

with open("app/routes/student.py", "r") as f:
    content = f.read()

# Replace get_current_join_code() logic
content = content.replace("return context['join_code'] if context else None", "return get_display_join_code(context.class_id) if context else None")

# Replace context['join_code'] or context.get('join_code')
content = re.sub(r"context\.get\('join_code'\)", "get_display_join_code(context.class_id)", content)
content = re.sub(r"context\['join_code'\]", "get_display_join_code(context.class_id)", content)

content = re.sub(r"class_context\.get\('join_code'\)", "get_display_join_code(class_context.class_id)", content)
content = re.sub(r"class_context\['join_code'\]", "get_display_join_code(class_context.class_id)", content)

# Also block, teacher_id
content = re.sub(r"context\.get\('block'\)", "''", content) # Block is rarely used internally in v2
content = re.sub(r"context\['block'\]", "''", content)
content = re.sub(r"context\.get\('teacher_id'\)", "None", content)
content = re.sub(r"context\['teacher_id'\]", "None", content)

# We need to make sure get_display_join_code is imported.
import_str = "from app.utils.join_code import get_display_join_code"
if import_str not in content:
    content = content.replace("from app.utils.time import (", import_str + "\nfrom app.utils.time import (")

with open("app/routes/student.py", "w") as f:
    f.write(content)

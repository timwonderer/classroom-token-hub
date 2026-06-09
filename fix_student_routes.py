import re

with open("app/routes/student.py", "r") as f:
    content = f.read()

# 1. Remove get_current_class_context definition
def_pattern = re.compile(r"def get_current_class_context\(\):.*?(?=\n\n\ndef )", re.DOTALL)
content = def_pattern.sub("", content)

# 2. Replace get_current_class_context() with resolve_canonical_context()
content = content.replace("get_current_class_context()", "resolve_canonical_context()")

# 3. Fix dict access to property access for CanonicalContext
content = re.sub(r"context\['class_id'\]", "context.class_id", content)
content = re.sub(r"context\.get\('class_id'\)", "context.class_id", content)
content = re.sub(r"class_context\['class_id'\]", "class_context.class_id", content)
content = re.sub(r"class_context\.get\('class_id'\)", "class_context.class_id", content)

content = re.sub(r"context\['seat_id'\]", "context.seat_id", content)
content = re.sub(r"context\.get\('seat_id'\)", "context.seat_id", content)
content = re.sub(r"class_context\['seat_id'\]", "class_context.seat_id", content)
content = re.sub(r"class_context\.get\('seat_id'\)", "class_context.seat_id", content)

# 4. Remove `if not context: return redirect(...)` and `if not class_context: return redirect(...)` 
# because error handlers now handle it.
# Actually, it's safer to just let them be, but `context` is never None anymore.
# We'll clean them up.
if_not_pattern = re.compile(r"^[ \t]*if not (?:class_)?context:\n[ \t]*return redirect.*?\n", re.MULTILINE)
content = if_not_pattern.sub("", content)

with open("app/routes/student.py", "w") as f:
    f.write(content)

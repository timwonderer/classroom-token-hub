import os

print("Realignment: Rewriting Routes")

routes = ["admin.py", "student.py", "api.py", "main.py", "recovery.py", "system_admin.py", "analytics.py", "docs.py"]
for r in routes:
    with open(f"app/routes/{r}", "w") as f:
        blueprint_name = r.replace(".py", "")
        if blueprint_name == 'main':
            f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__)
""")
        elif blueprint_name == 'api':
             f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__, url_prefix='/api')
""")
        elif blueprint_name == 'recovery':
             f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__, url_prefix='/recovery')
""")
        elif blueprint_name == 'system_admin':
             f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__, url_prefix='/system-admin')
""")
        elif blueprint_name == 'docs':
             f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__, url_prefix='/docs')
""")
        else:
            f.write(f"""from flask import Blueprint
{blueprint_name}_bp = Blueprint('{blueprint_name}', __name__)
""")

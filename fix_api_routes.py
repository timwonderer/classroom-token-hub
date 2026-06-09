import re

with open("app/routes/api.py", "r") as f:
    content = f.read()

# Replace get_current_class_context() with resolve_canonical_context()
content = content.replace("get_current_class_context()", "resolve_canonical_context()")
content = content.replace("from app.routes.student import get_current_class_context", "from app.services.context_resolver import resolve_canonical_context, ContextResolutionError")

# Fix dict access
content = re.sub(r"context\['class_id'\]", "context.class_id", content)
content = re.sub(r"context\.get\('class_id'\)", "context.class_id", content)
content = re.sub(r"context\['seat_id'\]", "context.seat_id", content)
content = re.sub(r"context\.get\('seat_id'\)", "context.seat_id", content)

content = re.sub(r"context\.get\('join_code'\)", "get_display_join_code(context.class_id)", content)
content = re.sub(r"context\['join_code'\]", "get_display_join_code(context.class_id)", content)

# Error handlers
error_handlers = """
@api_bp.errorhandler(ContextResolutionError)
def handle_api_context_resolution_error(e):
    from app.services.context_resolver import ContextForbidden, ContextMismatch
    if isinstance(e, (ContextForbidden, ContextMismatch)):
        return jsonify({"status": "error", "message": "Not Found", "error": "Not Found"}), 404
    return jsonify({"status": "error", "message": "Class context required", "error": "Class context required"}), 401
"""

content = content.replace("api_bp = Blueprint('api', __name__, url_prefix='/api')", "api_bp = Blueprint('api', __name__, url_prefix='/api')\n" + error_handlers)

with open("app/routes/api.py", "w") as f:
    f.write(content)

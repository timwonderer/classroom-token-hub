
from functools import wraps
from app.extensions import db
from app.models import OperationalEvent, AuditLog

def feat_shell(domain, level="INFO"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                db.session.commit()
                return result
            except Exception as e:
                db.session.rollback()
                raise e
        return wrapper
    return decorator

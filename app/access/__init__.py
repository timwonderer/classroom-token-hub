from app.access.scope import Scope
from app.access.scope_factory import (
    AccessScopeDenied,
    ResolvedStudentClassSwitch,
    resolve_scope,
    resolve_student_class_switch_scope,
)

__all__ = [
    "AccessScopeDenied",
    "ResolvedStudentClassSwitch",
    "Scope",
    "resolve_scope",
    "resolve_student_class_switch_scope",
]

from app.access.scope import Scope
from app.access.scope_factory import (
    AccessScopeDenied,
    ResolvedStudentClassSwitch,
    ResolvedStudentTeacherSwitch,
    resolve_scope,
    resolve_student_class_switch_scope,
    resolve_student_teacher_switch_scope,
)

__all__ = [
    "AccessScopeDenied",
    "ResolvedStudentClassSwitch",
    "ResolvedStudentTeacherSwitch",
    "Scope",
    "resolve_scope",
    "resolve_student_class_switch_scope",
    "resolve_student_teacher_switch_scope",
]

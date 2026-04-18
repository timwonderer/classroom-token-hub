from __future__ import annotations

from app.access.scope import Scope


class AccessPolicyDenied(Exception):
    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message

def assert_can_view_dashboard(scope: Scope) -> None:
    """Pure access decision for the student dashboard."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can view the student dashboard.",
        )


def assert_can_void_transaction(*, scope: Scope, transaction) -> None:
    """Pure access decision for admin transaction voids."""
    if scope.role != "teacher":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only teachers can void transactions from the admin surface.",
        )
    if transaction.teacher_id != scope.actor_id:
        raise AccessPolicyDenied(
            reason_code="foreign_teacher_scope",
            message="You do not have access to that transaction.",
        )
    if transaction.join_code and transaction.join_code != scope.join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that transaction.",
        )

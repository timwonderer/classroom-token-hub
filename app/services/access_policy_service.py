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


def assert_can_purchase_item(*, scope: Scope, teacher_id: int, join_code: str) -> None:
    """Pure access decision for student store purchases inside a class scope."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can purchase store items from the student surface.",
        )
    if scope.teacher_id != teacher_id:
        raise AccessPolicyDenied(
            reason_code="foreign_teacher_scope",
            message="You do not have access to that class store.",
        )
    if scope.join_code != join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class store.",
        )


def assert_can_pay_rent(*, scope: Scope, teacher_id: int, join_code: str) -> None:
    """Pure access decision for student rent-payment workflows inside a class scope."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can pay rent from the student surface.",
        )
    if scope.teacher_id != teacher_id:
        raise AccessPolicyDenied(
            reason_code="foreign_teacher_scope",
            message="You do not have access to that class rent workflow.",
        )
    if scope.join_code != join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class rent workflow.",
        )


def assert_can_process_claim(*, scope: Scope, enrollment, claim) -> None:
    """Pure access decision for admin insurance-claim processing."""
    if scope.role != "teacher":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only teachers can process insurance claims from the admin surface.",
        )
    enrollment_join_code = (enrollment.join_code or "").strip().upper() if enrollment and enrollment.join_code else None
    claim_join_code = (claim.join_code or "").strip().upper() if claim and claim.join_code else None
    if enrollment_join_code and scope.join_code != enrollment_join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance claim.",
        )
    if claim_join_code and scope.join_code != claim_join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance claim.",
        )


def assert_can_file_claim(*, scope: Scope, enrollment) -> None:
    """Pure access decision for student insurance-claim filing."""
    if scope.role != "student":
        raise AccessPolicyDenied(
            reason_code="forbidden_role",
            message="Only students can file insurance claims from the student surface.",
        )
    enrollment_join_code = (enrollment.join_code or "").strip().upper() if enrollment and enrollment.join_code else None
    if enrollment_join_code and scope.join_code != enrollment_join_code:
        raise AccessPolicyDenied(
            reason_code="foreign_class_scope",
            message="You do not have access to that class insurance policy.",
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

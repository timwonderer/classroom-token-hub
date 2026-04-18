from __future__ import annotations

from flask import session

from app.access.scope import Scope
from app.auth import get_current_student_seat, sync_student_session_context
from app.models import ClassEconomy, ClassMembership, TeacherBlock


class AccessScopeDenied(Exception):
    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _scope_from_runtime_seat(*, actor, selected_join_code: str | None) -> Scope | None:
    current_seat = get_current_student_seat()
    if not current_seat or current_seat.student_id != actor.id or not current_seat.join_code:
        return None
    if selected_join_code and current_seat.join_code != selected_join_code:
        return None

    class_row = None
    if current_seat.class_id:
        class_row = ClassEconomy.query.filter_by(class_id=current_seat.class_id).first()
    if not class_row:
        class_row = ClassEconomy.query.filter_by(join_code=current_seat.join_code).first()
    if not class_row:
        return None

    session["current_join_code"] = current_seat.join_code
    return Scope(
        class_id=class_row.class_id,
        join_code=current_seat.join_code,
        actor_id=actor.id,
        role="student",
        teacher_id=class_row.teacher_id,
        block=current_seat.block_identifier or current_seat.block,
        seat_id=current_seat.id,
    )


def _resolve_teacher_scope(*, actor, selected_join_code: str | None) -> Scope:
    normalized_join_code = (selected_join_code or session.get("current_join_code") or "").strip().upper() or None

    if normalized_join_code:
        membership = ClassMembership.query.filter_by(
            admin_id=actor.id,
            join_code=normalized_join_code,
            role="admin",
        ).first()
        if membership:
            class_row = ClassEconomy.query.filter_by(join_code=normalized_join_code).first()
            session["current_join_code"] = normalized_join_code
            return Scope(
                class_id=class_row.class_id if class_row else None,
                join_code=normalized_join_code,
                actor_id=actor.id,
                role="teacher",
                teacher_id=actor.id,
                block=class_row.display_name if class_row else None,
                seat_id=None,
            )

    membership = (
        ClassMembership.query.filter_by(admin_id=actor.id, role="admin")
        .filter(ClassMembership.join_code.isnot(None))
        .order_by(ClassMembership.join_code.asc())
        .first()
    )
    if membership and membership.join_code:
        class_row = ClassEconomy.query.filter_by(join_code=membership.join_code).first()
        session["current_join_code"] = membership.join_code
        return Scope(
            class_id=class_row.class_id if class_row else None,
            join_code=membership.join_code,
            actor_id=actor.id,
            role="teacher",
            teacher_id=actor.id,
            block=class_row.display_name if class_row else None,
            seat_id=None,
        )

    raise AccessScopeDenied(
        reason_code="no_admin_scope",
        message="No class selected. Please select a class to continue.",
    )


def resolve_scope(*, actor, selected_join_code: str | None = None, actor_role: str = "student") -> Scope:
    """Resolve a request-time scope for the current actor inside the selected class."""
    if actor is None:
        raise AccessScopeDenied(
            reason_code="missing_actor",
            message="No active actor is bound to this request.",
        )

    if actor_role == "teacher":
        return _resolve_teacher_scope(actor=actor, selected_join_code=selected_join_code)

    normalized_join_code = (selected_join_code or session.get("current_join_code") or "").strip().upper() or None
    scope = _scope_from_runtime_seat(actor=actor, selected_join_code=normalized_join_code)
    if scope is not None:
        return scope

    claimed_seats = (
        TeacherBlock.query.filter_by(student_id=actor.id, is_claimed=True)
        .order_by(TeacherBlock.id.asc())
        .all()
    )
    if not claimed_seats:
        raise AccessScopeDenied(
            reason_code="no_class_scope",
            message="No class selected. Please select a class to continue.",
        )

    active_seat = next(
        (seat for seat in claimed_seats if seat.join_code == normalized_join_code),
        None,
    )
    if active_seat is None:
        active_seat = claimed_seats[0]

    session["current_join_code"] = active_seat.join_code
    sync_student_session_context(actor, join_code=active_seat.join_code)

    class_row = None
    if active_seat.class_id:
        class_row = ClassEconomy.query.filter_by(class_id=active_seat.class_id).first()
    if not class_row:
        class_row = ClassEconomy.query.filter_by(join_code=active_seat.join_code).first()

    return Scope(
        class_id=class_row.class_id if class_row else active_seat.class_id,
        join_code=active_seat.join_code,
        actor_id=actor.id,
        role="student",
        teacher_id=class_row.teacher_id if class_row else active_seat.teacher_id,
        block=active_seat.block,
        seat_id=active_seat.id,
    )

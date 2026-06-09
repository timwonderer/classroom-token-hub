"""
Canonical Class Context Resolver for the v2 architecture.

This service establishes a strict context object anchored only on
user_id, class_id, and seat_id. It raises exceptions on failure
and never infers or reconstructs context.
"""

from dataclasses import dataclass
from typing import Optional

from flask import session
from app.extensions import db
from app.models import Seat, ClassEconomy


class ContextResolutionError(Exception):
    """Base class for all context resolution errors."""
    pass


class ContextNotEstablished(ContextResolutionError):
    """Raised when the requested context cannot be established (e.g. missing session keys)."""
    pass


class ContextForbidden(ContextResolutionError):
    """Raised when the actor is explicitly forbidden from holding class context (e.g. sysadmins)."""
    pass


class ContextMismatch(ContextResolutionError):
    """Raised when the requested context conflicts with the actor's authorized scope."""
    pass


@dataclass
class CanonicalContext:
    user_id: int
    class_id: str
    seat_id: int
    actor_role: str

    def __setattr__(self, name, value):
        forbidden_attrs = {"join_code", "teacher_id", "block", "section", "student_id"}
        if name in forbidden_attrs:
            raise AttributeError(f"Strict context invariant violation: cannot set {name}")
        super().__setattr__(name, value)

    def __getattr__(self, name):
        forbidden_attrs = {"join_code", "teacher_id", "block", "section", "student_id"}
        if name in forbidden_attrs:
            raise AttributeError(f"Strict context invariant violation: cannot access {name}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def resolve_canonical_context() -> CanonicalContext:
    """
    Establish the canonical class context for the current actor.
    
    Raises:
        ContextForbidden: If the actor is a system administrator.
        ContextNotEstablished: If no valid class_id or seat_id is found.
        ContextMismatch: If the seat does not belong to the class, or the user does not own the seat.
    """
    if session.get("is_system_admin"):
        raise ContextForbidden("System administrators cannot possess Class Context.")

    user_id = session.get("user_id")
    class_id = session.get("current_class_id")
    seat_id = session.get("current_seat_id")

    if not user_id or not class_id or not seat_id:
        raise ContextNotEstablished("Missing user_id, class_id, or seat_id in session.")

    try:
        user_id = int(user_id)
        seat_id = int(seat_id)
    except (ValueError, TypeError):
        raise ContextNotEstablished("Invalid format for user_id or seat_id.")

    seat = db.session.get(Seat, seat_id)
    if not seat:
        raise ContextNotEstablished("Seat not found.")

    if getattr(seat, "claimed_at", None) is None:
        raise ContextNotEstablished("Seat is not claimed.")

    if seat.class_id != class_id:
        raise ContextMismatch(f"Seat {seat_id} does not belong to class {class_id}.")

    if seat.user_id != user_id:
        raise ContextMismatch(f"User {user_id} does not own seat {seat_id}.")

    return CanonicalContext(
        user_id=user_id,
        class_id=class_id,
        seat_id=seat_id,
        actor_role=seat.role,
    )

from __future__ import annotations

from app.extensions import db
from app.models import Announcement, Seat
from app.utils.canonical_temporal_resolver import utc_now


def _require_teacher_seat(seat_id: int, class_id: str) -> None:
    if not Seat.query.filter_by(id=seat_id, class_id=class_id, role="teacher").first():
        raise ValueError("Announcement writer must be a teacher seat in this class.")


def _require_announcement_in_class(announcement: Announcement, acting_seat_id: int) -> None:
    # The row's own class is the boundary; the acting seat must teach that class.
    _require_teacher_seat(acting_seat_id, announcement.class_id)


def create_class_announcement(
    *,
    created_by_seat_id: int,
    class_id: str,
    title: str,
    message: str,
    priority: int,
    is_active: bool,
    expires_at,
) -> Announcement:
    _require_teacher_seat(created_by_seat_id, class_id)
    announcement = Announcement(
        created_by_seat_id=created_by_seat_id,
        class_id=class_id,
        title=title,
        message=message,
        priority=priority,
        is_active=is_active,
        expires_at=expires_at,
    )
    db.session.add(announcement)
    db.session.flush()
    return announcement


def update_class_announcement(
    announcement: Announcement,
    *,
    acting_seat_id: int,
    title: str,
    message: str,
    priority: int,
    is_active: bool,
    expires_at,
) -> Announcement:
    _require_announcement_in_class(announcement, acting_seat_id)
    announcement.title = title
    announcement.message = message
    announcement.priority = priority
    announcement.is_active = is_active
    announcement.expires_at = expires_at
    announcement.updated_at = utc_now()
    db.session.flush()
    return announcement


def delete_class_announcement(announcement: Announcement, *, acting_seat_id: int) -> None:
    _require_announcement_in_class(announcement, acting_seat_id)
    db.session.delete(announcement)
    db.session.flush()

"""Layout presentation contracts shared by fixture states.

``layout_admin.html`` / ``layout_student.html`` consume view models that the
real builders produce (``app.services.identity.builders``). Fixtures build them
through the same builders from fixed, fictional display data, so the
authenticated shell renders as it does for a signed-in user without a session
or database.
"""

from __future__ import annotations

from app.models import ClassFeature
from app.services.identity.builders import (
    build_admin_layout_context_view,
    build_student_layout_context_view,
)
from app.utils.display_metadata import DisplayMetadata

CLASS_ID = "00000000-0000-4000-8000-0000000a11y1"
JOIN_CODE = "A11YTEST"
CLASS_NAME = "Chemistry Period 1"
TIMEZONE = "America/Los_Angeles"


def admin_layout(*, current_page: str = "") -> dict:
    class_context = {
        "class_id": CLASS_ID, "class_identifier": CLASS_NAME, "join_code": JOIN_CODE,
        "class_timezone": TIMEZONE,
    }
    return {
        "admin_layout_view": build_admin_layout_context_view("Alex Teacher", class_context),
        "admin_available_classes": [
            {"class_id": CLASS_ID, "class_identifier": CLASS_NAME, "is_current": True},
            {"class_id": "00000000-0000-4000-8000-0000000a11y2", "class_identifier": "Period 3", "is_current": False},
        ],
        "admin_feature_settings": ClassFeature.defaults_dict(),
        "current_page": current_page,
    }


def student_layout(*, current_page: str = "", features: dict | None = None) -> dict:
    metadata = DisplayMetadata(
        context_key="a11y-fixture", user_id=None, seat_id=None, class_id=CLASS_ID, actor_role="student",
        join_code=JOIN_CODE, class_display_name=CLASS_NAME, class_identifier=CLASS_NAME,
        class_timezone=TIMEZONE, section=None, actor_first_name="Sam", actor_last_name="Student",
        actor_full_name="Sam Student", student_first_name="Sam", student_last_name="Student",
        student_full_name="Sam Student", teacher_first_name="Alex", teacher_last_name="Teacher",
        teacher_display_name="Alex Teacher", teacher_note=None,
    )
    settings = {**ClassFeature.defaults_dict(), **(features or {})}
    return {
        "student_layout_view": build_student_layout_context_view(metadata),
        "available_classes": [
            {"class_id": CLASS_ID, "class_identifier": CLASS_NAME, "teacher_name": "Alex Teacher",
             "is_current": True},
        ],
        "feature_settings": settings,
        "current_page": current_page,
    }

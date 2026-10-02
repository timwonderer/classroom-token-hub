"""Page view model for the notice about work recorded before the first payroll setting.

DOM-PROD-001 §XV.6 (owner rulings 2026-10-01). The condition is composed here
from the domains that own each part, and nowhere else:

1. no payroll setting exists — the payroll settings service (DOM-POL-001 §VI.2);
2. a claimed student seat has work — the attendance query service (DOM-PROD-001 §XIII.7);
3. the class's teacher has not dismissed it — Class Configuration (DOM-CLASS-001 §VII.1).

Pure reads (INV-ARC-007): building the view never records anything. The route
passes the result to the template; neither reconstructs the condition.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.attendance_service import class_has_claimed_student_work
from app.services.class_configuration_query_service import get_unpaid_work_notice_acknowledged_at
from app.services.payroll.settings import class_has_payroll_settings

# Where the dismissal form may send the teacher back to. A closed set: the form
# names a page, never a URL.
RETURN_PAGES = {"dashboard": "admin.dashboard", "payroll": "admin.payroll"}


@dataclass(frozen=True)
class UnpaidWorkNoticeView:
    """Everything the template needs to render the notice for one class."""

    class_id: str


def build_unpaid_work_notice_view(class_id: str) -> UnpaidWorkNoticeView | None:
    """The notice for ``class_id`` if it applies now, else None.

    Cheapest test first: once a class has a payroll setting the notice can
    never apply again, so nothing else is read.
    """
    if not class_id:
        return None
    if class_has_payroll_settings(class_id):
        return None
    if get_unpaid_work_notice_acknowledged_at(class_id) is not None:
        return None
    if not class_has_claimed_student_work(class_id):
        return None
    return UnpaidWorkNoticeView(class_id=class_id)

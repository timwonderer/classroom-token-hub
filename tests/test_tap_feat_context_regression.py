"""Tapping in must not nest one FEAT context inside another.

``/api/tap`` carried ``@requires_feat_context("FEAT-PROD-001")`` while the
function it calls, ``record_attendance_session``, carries the same decorator.
Every tap therefore opened FEAT-PROD-001 twice and died on the nesting guard
(INV-ARC-000 §VIII.2), so no student could start or stop work at all.

The suite missed it because no test drove the HTTP route — attendance coverage
reached the FEAT function directly, where there is only one context to open.
"""

from __future__ import annotations

from app.models import AttendanceSession
from tests.helpers.attendance_domain import tap_in_student
from tests.helpers.classroom_initializer import initialize_as_student


def test_tap_in_succeeds_through_the_http_route(client, app):
    """The route is the ingress the student actually uses; it must not 500."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    response = tap_in_student(client, pin="1234")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["active"] is True

    with app.app_context():
        rows = AttendanceSession.query.filter_by(
            target_seat_id=student.seat.id,
            class_id=classroom.class_id,
        ).all()
    assert [row.status for row in rows] == ["active"]


def test_tap_out_succeeds_through_the_http_route(client, app):
    """Stopping work runs the same nesting path and was equally broken."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    assert tap_in_student(client, pin="1234").status_code == 200
    response = client.post(
        "/api/tap",
        json={"action": "tap_out", "pin": "1234", "reason": "done"},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["active"] is False

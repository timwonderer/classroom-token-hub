"""Student detail rent status follows the class rent feature and recorded charges.

Regression: the page used to call every student a "Renter", always showed the
Rent tab, and derived "overdue" from a hard-coded 5th-of-month due date even when
the class had rent disabled.
"""
import re

from tests.helpers.canonical_classroom import login_teacher, provision_classroom
from tests.helpers.class_domain import enable_class_feature


def _detail_html(client, public_id):
    roster = client.get("/admin/students").get_data(as_text=True)
    match = re.search(rf'href="(/admin/students/{re.escape(public_id)}\?nav=[^"]+)"', roster)
    assert match, f"roster did not link to seat {public_id}"
    detail = client.get(match.group(1).replace("&amp;", "&"))
    assert detail.status_code == 200
    return detail.get_data(as_text=True)


def test_rent_disabled_class_shows_no_rent_status(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)
        public_id = classroom.students[0].seat.public_id

    html = _detail_html(client, public_id)
    assert "Housing:" not in html
    assert 'id="housing-tab"' not in html
    assert "Rent Information" not in html


def test_rent_enabled_class_reports_recorded_charges_only(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        login_teacher(client, classroom)
        public_id = classroom.students[0].seat.public_id

    html = _detail_html(client, public_id)
    assert "Housing:" not in html
    assert 'id="housing-tab"' in html
    # No assessment exists, so there is no due date or overdue claim to show.
    assert "No rent has been charged to this student yet." in html
    assert "Past due" not in html


def test_rent_tab_shows_recorded_assessment_due_date(app, client):
    from datetime import datetime, timedelta, timezone

    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import BillCycle, ObligationAssessment

    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="rent")
        seat = classroom.students[0].seat
        now_utc = datetime.now(timezone.utc)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="detail-rent:assessment"):
            cycle = BillCycle(
                class_id=classroom.class_id, internal_ref="rent:monthly", cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(cycle)
            db.session.flush()
            db.session.add(ObligationAssessment(
                correlation_id="detail-rent-assessment", seat_id=seat.id,
                class_id=classroom.class_id, obligation_type="RENT", event_type="ASSESSMENT",
                internal_ref="rent:monthly", bill_cycle_id=cycle.id, timestamp=now_utc,
            ))
        login_teacher(client, classroom)
        public_id = seat.public_id

    html = _detail_html(client, public_id)
    assert "No rent has been charged to this student yet." not in html
    due = re.search(r"Due Date:</td>\s*<td>([^<]*)</td>", html)
    assert due, "rent tab has no due date row"
    # A recorded assessment carries a real due date, formatted rather than N/A.
    assert re.fullmatch(r"[A-Z][a-z]+ \d{2}, \d{4}", due.group(1).strip()), due.group(1)

"""Roster names link to student detail, where the teacher reads the note.

Two students can share a display name. The link is how a teacher confirms which
seat a row refers to before acting on it (payroll credit, rent waiver, deletion).
"""
import re

from tests.helpers.canonical_classroom import login_teacher, provision_classroom


def _detail_href(html, public_id):
    match = re.search(rf'href="(/admin/students/{re.escape(public_id)}\?nav=[^"]+)"', html)
    return match.group(1).replace("&amp;", "&") if match else None


def test_payroll_manual_payment_names_link_to_detail_with_note(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        login_teacher(client, classroom)
        students = [(s.seat.public_id, s.first_name) for s in classroom.students]

    page = client.get("/admin/payroll")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for public_id, _first in students:
        assert _detail_href(html, public_id), f"payroll row for {public_id} has no detail link"
    # Opening detail must not discard the half-filled payment form.
    assert 'target="_blank" rel="noopener"' in html

    detail = client.get(_detail_href(html, students[0][0]))
    assert detail.status_code == 200
    assert "Teacher Notes:" in detail.get_data(as_text=True)


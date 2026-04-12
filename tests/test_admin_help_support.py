import pyotp

from app import db
from app.models import Admin, TeacherBlock, UserReport
from app.utils.auth_username import build_hashed_username_fields


def _login_admin(client):
    secret = pyotp.random_base32()
    auth_username = "teacher_help"
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(auth_username)
    admin = Admin(
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
        salt=salt,
        totp_secret=secret,
    )
    db.session.add(admin)
    db.session.flush()

    seat = TeacherBlock(
        teacher_id=admin.id,
        block="A",
        class_label="ELA",
        first_name="Student",
        last_initial="T",
        last_name_hash_by_part=["hash"],
        dob_sum_hash=None,
        salt=b"1234567890123456",
        first_half_hash="hashvalue",
        join_code="ELA123"
    )
    db.session.add(seat)
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": auth_username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_help_support_page_renders(client):
    _login_admin(client)

    response = client.get("/admin/help-support", follow_redirects=False)

    assert response.status_code == 200
    assert b"Submit Support Ticket" in response.data


def test_teacher_can_submit_class_scoped_support_ticket(client):
    _login_admin(client)

    response = client.post(
        "/admin/help-support",
        data={
            "join_code": "ELA123",
            "issue_category": "general",
            "title": "Roster sync issue",
            "description": "Student roster did not sync after update.",
            "expected_behavior": "Roster should sync immediately.",
            "page_url": "/admin/students",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"submitted directly to system administration" in response.data

    report = UserReport.query.filter_by(user_type="teacher", title="Roster sync issue").first()
    assert report is not None
    assert report.title == "Roster sync issue"
    assert report.report_type == "comment"
    assert report.description.startswith("SUPPORT_SCOPE|join_code=ELA123|class_label=ELA|category=general")

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.auth import ensure_admin_join_code, get_current_admin
from app.models import Admin, IdentityProfile, TeacherBlock


def test_admin_login_sets_session_identity(client):
    secret = pyotp.random_base32()
    admin = make_admin("teacher1", secret)
    db.session.add(admin)
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("is_admin") is True
        assert sess.get("admin_id") == admin.id
        assert "last_activity" in sess

    with client.application.test_request_context('/'):
        from flask import session

        session["is_admin"] = True
        session["admin_id"] = admin.id
        assert get_current_admin().id == admin.id


def test_admin_required_blocks_missing_identity(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.get("/admin/students", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers.get("Location", "")


def test_ensure_admin_join_code_falls_back_when_membership_table_missing(client, monkeypatch):
    admin = make_admin("teacher_fallback", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    identity = IdentityProfile(profile_type="student", first_name="Policy", last_initial="S")
    db.session.add(identity)
    db.session.flush()

    db.session.add(
        TeacherBlock(
            teacher_id=admin.id,
            block="A",
            class_label="Algebra",
            first_name="Policy",
            last_initial="S",
            identity_id=identity.id,
            last_name_hash_by_part=["hash"],
            dob_sum_hash=None,
            salt=b"1234567890123456",
            first_half_hash="fallback-seat",
            join_code="LEGACY123",
        )
    )
    db.session.commit()

    monkeypatch.setattr("app.auth._table_exists", lambda table_name: table_name != "class_memberships")

    with client.application.test_request_context("/"):
        from flask import session

        ensure_admin_join_code(admin.id)

        assert session["current_join_code"] == "LEGACY123"

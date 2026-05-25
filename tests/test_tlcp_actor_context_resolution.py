from flask import session

from app import db
from app.models import ClassEconomy, Student
from app.services.tlcp import resolve_actor_context
from app.utils.helpers import generate_anonymous_code
from tests.helpers.v2_fixtures import make_admin, make_sysadmin


def test_resolve_actor_context_student_session(app):
    admin = make_admin("tlcp_student_admin", "secret-admin")
    db.session.add(admin)
    db.session.flush()
    admin_id = admin.id

    class_row = ClassEconomy(join_code="TLCP-STUDENT", teacher_id=admin_id)
    db.session.add(class_row)
    db.session.flush()
    class_id = class_row.class_id
    join_code = class_row.join_code

    student = Student(
        first_name="TLCP",
        last_initial="S",
        block="A",
        join_code=join_code,
        class_id=class_id,
        salt=b"1234567890123456",
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()
    student_id = student.id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        session["student_id"] = student_id
        session["current_join_code"] = join_code
        session["current_class_id"] = class_id

        context = resolve_actor_context()

    assert context is not None
    assert context["actor_type"] == "student"
    assert context["actor_id"] == student_id
    assert context["actor_opaque_id"] == generate_anonymous_code(f"student_issue:{student_id}")
    assert context["class_id"] == class_id


def test_resolve_actor_context_admin_session(app):
    admin = make_admin("tlcp_admin_actor", "secret-admin-actor")
    db.session.add(admin)
    db.session.flush()
    admin_id = admin.id

    class_row = ClassEconomy(join_code="TLCP-ADMIN", teacher_id=admin_id)
    db.session.add(class_row)
    db.session.flush()
    join_code = class_row.join_code
    class_id = class_row.class_id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/admin/dashboard", method="GET"):
        session["is_admin"] = True
        session["admin_id"] = admin_id
        session["current_join_code"] = join_code

        context = resolve_actor_context()

    assert context is not None
    assert context["actor_type"] == "teacher"
    assert context["actor_id"] == admin_id
    assert context["actor_opaque_id"] == generate_anonymous_code(f"teacher:{admin_id}")
    assert context["class_id"] == class_id


def test_resolve_actor_context_sysadmin_session(app):
    sysadmin = make_sysadmin("tlcp_sysadmin_actor", "secret-sysadmin-actor")
    db.session.add(sysadmin)
    db.session.flush()
    sysadmin_id = sysadmin.id
    db.session.commit()
    db.session.remove()

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        session["is_system_admin"] = True
        session["sysadmin_id"] = sysadmin_id

        context = resolve_actor_context()

    assert context is not None
    assert context["actor_type"] == "sysadmin"
    assert context["actor_id"] == sysadmin_id
    assert context["actor_opaque_id"] == generate_anonymous_code(f"sysadmin:{sysadmin_id}")
    assert context["class_id"] is None

from datetime import datetime, timezone

from app.extensions import db
from app.models import Admin, ClassEconomy, Issue, IssueCategory, Student
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_set_current_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = Admin(username="gate_admin_a", totp_secret="secret-a")
    admin_b = Admin(username="gate_admin_b", totp_secret="secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    create_class_scope(
        teacher=admin_b,
        join_code="GATE001",
        teacher_block_teacher=admin_a,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin_a.id)
    response = client.post("/admin/current-class", json={"join_code": "GATE001"})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_delete_join_code_requires_membership_even_if_teacherblock_exists(client):
    admin_a = Admin(username="delete_gate_a", totp_secret="secret-a")
    admin_b = Admin(username="delete_gate_b", totp_secret="secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    create_class_scope(
        teacher=admin_b,
        join_code="DELG001",
        teacher_block_teacher=admin_a,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin_a.id)
    response = client.post("/admin/join-code/delete", json={"join_code": "DELG001"})
    assert response.status_code == 403
    assert db.session.get(ClassEconomy, "DELG001") is not None


def test_delete_join_code_requires_confirmation(client):
    admin = Admin(username="confirm_admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="CONF001")
    db.session.commit()

    _login_admin(client, admin.id)

    # 1. Missing confirmation -> 400
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001"})
    assert response.status_code == 400
    assert b"Confirmation failed" in response.data

    # 2. Wrong confirmation -> 400
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001", "confirm_join_code": "WRONG"})
    assert response.status_code == 400

    # 3. Correct confirmation -> 200
    response = client.post("/admin/join-code/delete", json={"join_code": "CONF001", "confirm_join_code": "CONF001"})
    assert response.status_code == 200
    assert db.session.get(ClassEconomy, "CONF001") is None


def test_issues_queue_respects_current_join_code_membership_scope(client):
    admin = Admin(username="issues_gate_admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    student = Student(first_name="Gate", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="ISSGA1")
    create_class_scope(teacher=admin, join_code="ISSGB1")

    category = IssueCategory(
        name=f"Issue Gate Category {datetime.now(timezone.utc).isoformat()}",
        category_type="transaction",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()

    db.session.add_all([
        Issue(
            student_id=student.id,
            student_first_name=student.first_name,
            student_last_initial=student.last_initial,
            opaque_student_reference="opaque-issue-gate-a",
            teacher_id=admin.id,
            join_code="ISSGA1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Issue for class A",
        ),
        Issue(
            student_id=student.id,
            student_first_name=student.first_name,
            student_last_initial=student.last_initial,
            opaque_student_reference="opaque-issue-gate-b",
            teacher_id=admin.id,
            join_code="ISSGB1",
            category_id=category.id,
            issue_type="transaction",
            student_explanation="Issue for class B",
        ),
    ])
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "ISSGA1"

    response = client.get("/admin/issues")
    assert response.status_code == 200
    assert b"Issue for class A" in response.data
    assert b"Issue for class B" not in response.data

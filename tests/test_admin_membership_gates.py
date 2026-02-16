from datetime import datetime, timezone

from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Issue, IssueCategory, Student, TeacherBlock


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

    db.session.add(ClassEconomy(join_code="GATE001", status="active", created_by_admin_id=admin_b.id))
    db.session.add(ClassMembership(join_code="GATE001", admin_id=admin_b.id, role="admin", status="active"))
    # Stale/legacy seat should not grant access without ClassMembership
    db.session.add(TeacherBlock(
        teacher_id=admin_a.id,
        block="A",
        join_code="GATE001",
        is_claimed=False,
        first_name="Legacy",
        last_initial="X",
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b"salt",
        first_half_hash="hash",
    ))
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

    db.session.add(ClassEconomy(join_code="DELG001", status="active", created_by_admin_id=admin_b.id))
    db.session.add(ClassMembership(join_code="DELG001", admin_id=admin_b.id, role="admin", status="active"))
    db.session.add(TeacherBlock(
        teacher_id=admin_a.id,
        block="A",
        join_code="DELG001",
        is_claimed=False,
        first_name="Legacy",
        last_initial="Y",
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b"salt",
        first_half_hash="hash",
    ))
    db.session.commit()

    _login_admin(client, admin_a.id)
    response = client.post("/admin/join-code/delete", json={"join_code": "DELG001"})
    assert response.status_code == 403
    assert db.session.get(ClassEconomy, "DELG001") is not None


def test_issues_queue_respects_current_join_code_membership_scope(client):
    admin = Admin(username="issues_gate_admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    student = Student(first_name="Gate", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add_all([
        ClassEconomy(join_code="ISSGA1", status="active", created_by_admin_id=admin.id),
        ClassEconomy(join_code="ISSGB1", status="active", created_by_admin_id=admin.id),
        ClassMembership(join_code="ISSGA1", admin_id=admin.id, role="admin", status="active"),
        ClassMembership(join_code="ISSGB1", admin_id=admin.id, role="admin", status="active"),
    ])

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

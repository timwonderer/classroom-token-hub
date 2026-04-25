from datetime import datetime, timezone

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import (
    Admin,
    ClassEconomy,
    Issue,
    IssueCategory,
    PayrollSettings,
    StoreItem,
    Student,
    StudentTeacher,
    TeacherBlock,
)
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_set_current_class_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("gate_admin_a", "secret-a")
    admin_b = make_admin("gate_admin_b", "secret-b")
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
    class_row = ClassEconomy.query.filter_by(join_code="GATE001").first()
    response = client.post("/admin/current-class", json={"class_id": class_row.class_id})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_delete_join_code_requires_membership_even_if_teacherblock_exists(client):
    admin_a = make_admin("delete_gate_a", "secret-a")
    admin_b = make_admin("delete_gate_b", "secret-b")
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
    admin = make_admin("confirm_admin", "secret")
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
    admin = make_admin("issues_gate_admin", "secret")
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


def test_add_individual_student_requires_current_class_context(client):
    admin = make_admin("student_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STUG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_student_count = db.session.query(Student).count()
    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Casey",
            "last_name": "Guard",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Student).count() == initial_student_count


def test_add_individual_student_creates_single_teacher_block_for_new_student(client):
    admin = make_admin("student_single_tb_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="SING001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "SING001"

    initial_student_count = Student.query.count()
    initial_link_count = StudentTeacher.query.filter_by(teacher_id=admin.id).count()
    initial_block_count = TeacherBlock.query.filter_by(teacher_id=admin.id, block="A").count()

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Indivuniq",
            "last_name": "Guarduniq",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert Student.query.count() == initial_student_count + 1
    assert StudentTeacher.query.filter_by(teacher_id=admin.id).count() == initial_link_count + 1
    assert TeacherBlock.query.filter_by(teacher_id=admin.id, block="A").count() == initial_block_count + 1

    linked_seats = TeacherBlock.query.filter_by(teacher_id=admin.id, block="A").filter(TeacherBlock.student_id.isnot(None)).all()
    assert len(linked_seats) == 1
    assert linked_seats[0].is_claimed is False
    assert linked_seats[0].join_code == "SING001"
    assert linked_seats[0].dob_sum_hash is not None
    assert linked_seats[0].last_name_hash_by_part


def test_add_manual_student_creates_single_teacher_block_for_new_student(client):
    admin = make_admin("manual_single_tb_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="MANU001",
        block="B",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "MANU001"

    initial_student_count = Student.query.count()
    initial_link_count = StudentTeacher.query.filter_by(teacher_id=admin.id).count()
    initial_block_count = TeacherBlock.query.filter_by(teacher_id=admin.id, block="B").count()

    response = client.post(
        "/admin/student/add-manual",
        data={
            "first_name": "Manualuniq",
            "last_name": "Seatuniq",
            "dob": "2010-03-04",
            "block": "B",
            "username": "",
            "pin": "",
            "passphrase": "",
            "hall_passes": "3",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert Student.query.count() == initial_student_count + 1
    assert StudentTeacher.query.filter_by(teacher_id=admin.id).count() == initial_link_count + 1
    assert TeacherBlock.query.filter_by(teacher_id=admin.id, block="B").count() == initial_block_count + 1

    linked_seats = TeacherBlock.query.filter_by(teacher_id=admin.id, block="B").filter(TeacherBlock.student_id.isnot(None)).all()
    assert len(linked_seats) == 1
    assert linked_seats[0].is_claimed is False
    assert linked_seats[0].join_code == "MANU001"
    assert linked_seats[0].dob_sum_hash is not None
    assert linked_seats[0].last_name_hash_by_part


def test_add_individual_student_uses_selected_class_join_code_when_block_has_other_scope(client):
    admin = make_admin("student_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="OLDA001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    create_class_scope(
        teacher=admin,
        join_code="NEWA001",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "NEWA001"

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Scoped",
            "last_name": "Student",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    linked_seat = (
        TeacherBlock.query
        .filter_by(teacher_id=admin.id, block="A")
        .filter(TeacherBlock.student_id.isnot(None))
        .order_by(TeacherBlock.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert linked_seat.join_code == "NEWA001"


def test_add_individual_student_create_new_class_section_mints_new_join_code(client):
    admin = make_admin("student_new_class_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="CURRA01",
        block="A",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "CURRA01"

    initial_class_count = ClassEconomy.query.count()

    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Brand",
            "last_name": "Newclass",
            "dob": "2011-02-03",
            "block_select": "__CREATE_NEW__",
            "block": "B",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert ClassEconomy.query.count() == initial_class_count + 1

    linked_seat = (
        TeacherBlock.query
        .filter_by(teacher_id=admin.id, block="B")
        .filter(TeacherBlock.student_id.isnot(None))
        .order_by(TeacherBlock.id.desc())
        .first()
    )
    assert linked_seat is not None
    assert linked_seat.join_code != "CURRA01"
    assert ClassEconomy.query.filter_by(join_code=linked_seat.join_code).first() is not None

    teacher_student_seat = TeacherBlock.query.filter_by(
        teacher_id=admin.id,
        join_code=linked_seat.join_code,
        is_teacher=True,
    ).first()
    assert teacher_student_seat is not None
    assert teacher_student_seat.class_label == "B"

    with client.session_transaction() as sess:
        assert sess["current_join_code"] == linked_seat.join_code


def test_admin_students_surfaces_teacher_shadow_claim_dob(client):
    admin = make_admin("teacher_shadow_info_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(
        teacher=admin,
        join_code="SHADOW1",
        block="B",
        teacher_block_teacher=admin,
        teacher_block_claimed=False,
    )
    db.session.commit()

    from app.routes.admin import _ensure_teacher_student_seat

    _ensure_teacher_student_seat(admin.id, "SHADOW1", "B")
    db.session.commit()

    _login_admin(client, admin.id)

    response = client.get("/admin/students")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "Join Code for B" in html
    assert "Teacher S." in html
    assert "Claim DOB: 01/01/2001" in html


def test_store_create_requires_current_class_context(client):
    admin = make_admin("store_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STOG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_store_item_count = db.session.query(StoreItem).count()
    response = client.post(
        "/admin/store",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/store")
    assert db.session.query(StoreItem).count() == initial_store_item_count


def test_payroll_settings_requires_current_class_context(client):
    admin = make_admin("payroll_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="PAYG001")
    db.session.commit()

    _login_admin(client, admin.id)

    initial_settings_count = db.session.query(PayrollSettings).count()
    response = client.post(
        "/admin/payroll/settings",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    assert db.session.query(PayrollSettings).count() == initial_settings_count


def test_class_scoped_write_rejects_stale_session_join_code(client):
    admin = make_admin("stale_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="LIVE001")
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STALE999"

    initial_student_count = db.session.query(Student).count()
    response = client.post(
        "/admin/student/add-individual",
        data={
            "first_name": "Stale",
            "last_name": "Session",
            "dob": "2010-01-02",
            "block": "A",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/students")
    assert db.session.query(Student).count() == initial_student_count


def test_store_query_scope_does_not_implicitly_switch_session_context(client):
    admin = make_admin("query_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="STOREA1", block="A", create_claimed_teacher_block=True)
    create_class_scope(teacher=admin, join_code="STOREB2", block="B", create_claimed_teacher_block=True)
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "STOREA1"

    response = client.get("/admin/store?join_code=STOREB2")
    assert response.status_code == 200

    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "STOREA1"


def test_class_scoped_post_rejects_request_join_code_mismatch(client):
    admin = make_admin("mismatch_guard_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    create_class_scope(teacher=admin, join_code="PAYA01", block="A", create_claimed_teacher_block=True)
    create_class_scope(teacher=admin, join_code="PAYB02", block="B", create_claimed_teacher_block=True)
    db.session.commit()

    _login_admin(client, admin.id)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "PAYA01"

    initial_settings_count = db.session.query(PayrollSettings).count()
    response = client.post(
        "/admin/payroll/settings",
        data={
            "join_code": "PAYB02",
            "cwi_block": "B",
            "settings_mode": "simple",
            "simple_pay_rate": "15.0",
            "simple_frequency": "biweekly",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")
    assert db.session.query(PayrollSettings).count() == initial_settings_count

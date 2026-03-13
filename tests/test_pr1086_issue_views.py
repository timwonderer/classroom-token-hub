from datetime import datetime, timezone

from app import db
from app.hash_utils import get_random_salt
from app.models import (
    Admin,
    Issue,
    IssueCategory,
    IssueResolutionAction,
    Student,
    StudentTeacher,
    TeacherBlock,
)


def _issue_category():
    category = IssueCategory(
        name="General Support",
        category_type="general",
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()
    return category


def test_student_help_support_scopes_tickets_to_current_teacher(client):
    teacher = Admin(username="teacher_pr1086", totp_secret="secret")
    other_teacher = Admin(username="other_teacher_pr1086", totp_secret="secret")
    student = Student(
        first_name="Avery",
        last_initial="Q",
        block="A",
        salt=get_random_salt(),
        first_half_hash="student-pr1086-hash",
        dob_sum=2025,
    )
    db.session.add_all([teacher, other_teacher, student])
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.add(
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            class_label="ELA",
            first_name="Avery",
            last_initial="Q",
            last_name_hash_by_part=[],
            dob_sum=2025,
            salt=get_random_salt(),
            first_half_hash="seat-pr1086-hash",
            join_code="PR1086",
            is_claimed=True,
            student_id=student.id,
        )
    )

    category = _issue_category()

    included_issue = Issue(
        student_id=student.id,
        student_first_name=student.first_name,
        student_last_initial=student.last_initial,
        opaque_student_reference="opaque-student-pr1086-1",
        teacher_id=teacher.id,
        join_code="PR1086",
        class_label="ELA",
        category_id=category.id,
        issue_type="general",
        student_explanation="Included issue for current class context.",
        status=Issue.STATUS_TEACHER_REVIEW,
    )
    excluded_issue = Issue(
        student_id=student.id,
        student_first_name=student.first_name,
        student_last_initial=student.last_initial,
        opaque_student_reference="opaque-student-pr1086-2",
        teacher_id=other_teacher.id,
        join_code="PR1086",
        class_label="Other Class",
        category_id=category.id,
        issue_type="general",
        student_explanation="Excluded issue from another teacher.",
        status=Issue.STATUS_TEACHER_REVIEW,
    )
    db.session.add_all([included_issue, excluded_issue])
    db.session.flush()

    db.session.add_all([
        IssueResolutionAction(
            issue_id=included_issue.id,
            join_code="PR1086",
            action_type="manual_adjustment",
            action_description=None,
            performed_by_type="teacher",
            performed_by_id=teacher.id,
        ),
        IssueResolutionAction(
            issue_id=excluded_issue.id,
            join_code="PR1086",
            action_type="deny_issue",
            action_description="Should not appear for the current class context.",
            performed_by_type="teacher",
            performed_by_id=other_teacher.id,
        ),
    ])
    db.session.commit()

    now = datetime.now(timezone.utc).isoformat()
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_join_code"] = "PR1086"
        sess["login_time"] = now
        sess["last_activity"] = now

    response = client.get("/student/help-support", follow_redirects=True)

    assert response.status_code == 200
    assert b"Included issue for current class context." in response.data
    assert b"Excluded issue from another teacher." not in response.data
    assert b"(no summary provided)" in response.data
    assert b"Should not appear for the current class context." not in response.data


def test_admin_issue_queue_shows_only_canonical_closed_issues(client):
    teacher = Admin(username="admin_pr1086", totp_secret="secret")
    db.session.add(teacher)
    db.session.flush()

    category = _issue_category()

    canonical_closed = Issue(
        student_id=1,
        student_first_name="Jordan",
        student_last_initial="R",
        opaque_student_reference="opaque-admin-pr1086-1",
        teacher_id=teacher.id,
        join_code="PR1086A",
        class_label="ELA",
        category_id=category.id,
        issue_type="general",
        student_explanation="Canonical closed issue should render.",
        status=Issue.STATUS_CLOSED,
        closed_at=None,
    )
    legacy_closed = Issue(
        student_id=2,
        student_first_name="Taylor",
        student_last_initial="S",
        opaque_student_reference="opaque-admin-pr1086-2",
        teacher_id=teacher.id,
        join_code="PR1086A",
        class_label="ELA",
        category_id=category.id,
        issue_type="general",
        student_explanation="Legacy closed issue should stay hidden.",
        status="closed",
    )
    db.session.add_all([canonical_closed, legacy_closed])
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        sess["join_code"] = "PR1086A"
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.get("/admin/issues", follow_redirects=False)

    assert response.status_code == 200
    assert b"Canonical closed issue should render." in response.data
    assert b"Legacy closed issue should stay hidden." not in response.data
    assert b"N/A" in response.data

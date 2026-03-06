from datetime import timedelta

from app import db
from app.models import (
    Admin,
    ActorRequestTrace,
    ErrorEvent,
    IssueCategory,
    JoinCode,
    Student,
    TeacherBlock,
)
from app.utils.helpers import generate_anonymous_code
from app.utils.issue_helpers import create_issue
from app.utils.time import utc_now


def _create_student_issue_context():
    admin = Admin(username="teacher", totp_secret="base32secret3232")
    db.session.add(admin)
    db.session.flush()

    join_code = JoinCode(join_code_token="TLCP-JOIN", teacher_id=admin.id)
    db.session.add(join_code)
    db.session.flush()

    student = Student(
        first_name="Student",
        last_initial="S",
        block="A",
        join_code=join_code.join_code_token,
        join_code_id=join_code.join_code_id,
        salt=b"1234567890123456",
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()

    seat = TeacherBlock(
        teacher_id=admin.id,
        block="A",
        first_name="Student",
        last_initial="S",
        salt=b"1234567890123456",
        first_half_hash="seat-hash",
        join_code=join_code.join_code_token,
        join_code_id=join_code.join_code_id,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)

    category = IssueCategory(name="General TLCP", category_type="general", is_active=True)
    db.session.add(category)
    db.session.commit()

    return admin, student, join_code, category


def test_create_issue_attaches_correlation_pack_with_trace_and_error(app):
    admin, student, join_code, category = _create_student_issue_context()
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")

    db.session.add(
        ActorRequestTrace(
            actor_type="student",
            actor_opaque_id=actor_opaque_id,
            join_code_id=join_code.join_code_id,
            request_id="req-test-1",
            method="POST",
            endpoint="/store/buy",
            status_code=500,
            created_at=utc_now() - timedelta(minutes=20),
        )
    )
    db.session.add(
        ErrorEvent(
            request_id="req-test-1",
            actor_type="student",
            actor_opaque_id=actor_opaque_id,
            join_code_id=join_code.join_code_id,
            endpoint="/store/buy",
            method="POST",
            error_class="RuntimeError",
            error_message="purchase failed",
            correlation_version=1,
            created_at=utc_now() - timedelta(minutes=15),
        )
    )
    db.session.commit()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        issue = create_issue(
            student=student,
            teacher_id=admin.id,
            join_code=join_code.join_code_token,
            category_id=category.id,
            explanation="Something broke",
            expected_outcome="It should work",
            include_recent_error=True,
        )

    assert issue.correlation_pack is not None
    assert issue.correlation_pack.actor_opaque_id == actor_opaque_id
    assert len(issue.correlation_pack.request_trace_json) == 1
    assert issue.correlation_pack.request_trace_json[0]["request_id"] == "req-test-1"
    assert len(issue.correlation_pack.error_refs_json) == 1
    assert issue.correlation_pack.error_refs_json[0]["error_class"] == "RuntimeError"


def test_create_issue_can_skip_recent_error_refs(app):
    admin, student, join_code, category = _create_student_issue_context()
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")

    db.session.add(
        ErrorEvent(
            request_id="req-test-2",
            actor_type="student",
            actor_opaque_id=actor_opaque_id,
            join_code_id=join_code.join_code_id,
            endpoint="/store/buy",
            method="POST",
            error_class="RuntimeError",
            error_message="purchase failed",
            correlation_version=1,
            created_at=utc_now() - timedelta(minutes=5),
        )
    )
    db.session.commit()

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        issue = create_issue(
            student=student,
            teacher_id=admin.id,
            join_code=join_code.join_code_token,
            category_id=category.id,
            explanation="Something broke",
            include_recent_error=False,
        )

    assert issue.correlation_pack is not None
    assert issue.correlation_pack.error_refs_json == []


def test_authenticated_request_writes_trace_row(app, client):
    @app.route("/_tlcp_ping")
    def _tlcp_ping():
        return "ok"

    student = Student(
        first_name="Trace",
        last_initial="S",
        block="A",
        salt=b"1234567890123456",
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.commit()

    with client.session_transaction() as sess:
        now = utc_now().isoformat()
        sess["student_id"] = student.id
        sess["login_time"] = now
        sess["last_activity"] = now

    response = client.get("/_tlcp_ping")

    assert response.status_code == 200
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")
    trace = (
        ActorRequestTrace.query.filter_by(
            actor_type="student",
            actor_opaque_id=actor_opaque_id,
            endpoint="/_tlcp_ping",
        )
        .order_by(ActorRequestTrace.id.desc())
        .first()
    )
    assert trace is not None
    assert trace.method == "GET"
    assert trace.status_code == 200
    assert trace.request_id

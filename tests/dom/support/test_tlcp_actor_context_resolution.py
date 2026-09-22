from flask import session

from app import db
from app.models import User
from app.services.context_resolver import CanonicalContext, resolve_canonical_context
from app.services.tlcp import resolve_actor_context
from tests.helpers.support_domain import initialize_support_student, initialize_support_teacher


def test_DOM_SUP_001__resolve_actor_context_uses_student_canonical_context(app):
    client = app.test_client()
    classroom, student = initialize_support_student("chemistry_p1", client, app)
    canonical_context = CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )
    context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "student"
    assert "actor_id" not in context
    assert context["actor_public_id"] == student.seat.public_id
    assert context["class_id"] == classroom.class_id


def test_DOM_SUP_001__resolve_actor_context_uses_teacher_canonical_context(app):
    client = app.test_client()
    classroom = initialize_support_teacher("chemistry_p1", client, app)
    canonical_context = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )
    context = resolve_actor_context(canonical_context)

    assert context is not None
    assert context["actor_type"] == "teacher"
    assert "actor_id" not in context
    assert context["actor_public_id"] == classroom.teacher_seat.public_id
    assert context["class_id"] == classroom.class_id


def test_DOM_SUP_001__resolve_actor_context_sysadmin_session_returns_none(app):
    """Sysadmins are structurally forbidden from holding class context
    (INV-ARC-019), so every sysadmin request hits this ``context is None``
    path forever -- it must not also log an ERROR-level
    "missing canonical context" on every single one. Confirmed live:
    /sysadmin/dashboard, /sysadmin/login, /sysadmin/support etc. all logged
    TLCP-INVARIANT-VIOLATION on every hit before this endpoint set treated
    the whole sysadmin blueprint as no-context by design.

    This test previously asserted only ``context is None`` -- true before
    and after the fix, since resolve_actor_context always returned None for
    sysadmin -- and so never actually covered the log-noise defect.
    """
    from unittest.mock import patch

    sysadmin_id = 1

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        session["is_system_admin"] = True
        session["sysadmin_id"] = sysadmin_id
        session["user_id"] = sysadmin_id

        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert logged == []


def test_DOM_SUP_001__resolve_actor_context_ignores_every_sysadmin_endpoint(app):
    """The exemption is blueprint-wide, not a per-route allowlist entry --
    covers a second sysadmin endpoint to prove it isn't special-cased to
    just /sysadmin/dashboard.
    """
    from unittest.mock import patch

    with app.test_request_context("/sysadmin/support", method="GET"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert logged == []


def test_DOM_SUP_001__sysadmin_request_carrying_canonical_context_fails_closed(app):
    """The other half of the sysadmin/context matrix: sysadmin absent-context
    is expected (see the two tests above), but a sysadmin request that
    somehow DOES carry a CanonicalContext is not a legitimate class-scoped
    actor -- a sysadmin session should never produce one at all, so this
    would itself be a scope leak. It must fail closed (return None) and log
    an invariant violation, exactly like the teacher/student "context
    absent" cell does -- not be silently trusted as though sysadmin were
    class-scoped.
    """
    from unittest.mock import patch

    classroom = initialize_support_teacher("chemistry_p1", app.test_client(), app)
    leaked_context = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            result = resolve_actor_context(leaked_context)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert result is None
    assert any(
        "TLCP-INVARIANT-VIOLATION: sysadmin request unexpectedly carries canonical class context" in msg
        for msg in logged
    )


def test_DOM_SUP_001__resolve_actor_context_logs_missing_canonical_context(app):
    from unittest.mock import patch

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical context" in msg for msg in logged)


def test_DOM_SUP_001__resolve_actor_context_ignores_admin_signup_path(app):
    from unittest.mock import patch

    with app.test_request_context("/admin/signup", method="POST"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            context = resolve_actor_context(None)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert context is None
    assert logged == []


def test_DOM_SUP_001__student_login_does_not_require_canonical_context(app):
    """Symmetric with admin.login (already exempt): the student login page
    is loaded and posted to before any session/context exists, so it must
    not log an invariant violation either -- it previously wasn't in
    DEFAULT_PUBLIC_ENDPOINTS even though admin.login was.
    """
    from unittest.mock import patch

    client = app.test_client()
    with patch("app.services.tlcp.current_app.logger.error") as mock_error:
        response = client.get("/student/login")
        logged = [call.args[0] for call in mock_error.call_args_list]

    assert response.status_code == 200
    assert logged == []


def test_DOM_SUP_001__tips_api_does_not_require_canonical_context(app):
    from unittest.mock import patch

    client = app.test_client()
    with patch("app.services.tlcp.current_app.logger.error") as mock_error:
        response = client.get("/api/tips/teacher")
        logged = [call.args[0] for call in mock_error.call_args_list]

    assert response.status_code == 200
    assert logged == []


def test_DOM_SUP_001__resolve_actor_context_logs_missing_canonical_seat(app):
    from unittest.mock import patch
    from app.services.context_resolver import CanonicalContext

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        ctx = CanonicalContext(user_id=1, class_id="class-1", seat_id=1, actor_role="student")
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            with patch("app.services.tlcp.db.session.get", return_value=None):
                result = resolve_actor_context(ctx)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert result is None
    assert any("TLCP-INVARIANT-VIOLATION: missing canonical seat" in msg for msg in logged)

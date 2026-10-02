import pytest
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


def test_DOM_SUP_001__a_teacher_context_on_a_sysadmin_page_is_not_a_violation(app):
    """Until 2026-10-02 this test asserted the opposite: any canonical context
    on a sysadmin endpoint was logged as ``TLCP-INVARIANT-VIOLATION``. But a
    ``CanonicalContext`` is only ever resolved for a student or teacher
    principal -- the resolver refuses one to a sysadmin -- so that rule fired
    only for non-sysadmin principals who opened a sysadmin URL, and never for
    the case it named. The URL says what surface was requested, not who
    requested it (INV-ARC-019 §V, §XIII). The violation is now keyed on the
    sysadmin principal, on any surface:
    tests/dom/support/test_tlcp_surface_and_principal.py.
    """
    from unittest.mock import patch

    classroom = initialize_support_teacher("chemistry_p1", app.test_client(), app)
    teacher_context = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )

    with app.test_request_context("/sysadmin/dashboard", method="GET"):
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            result = resolve_actor_context(teacher_context)
            logged = [call.args[0] for call in mock_error.call_args_list]

    assert logged == []
    assert result is not None
    assert result["actor_type"] == "teacher"
    assert result["class_id"] == classroom.class_id


def _tlcp_violations(mock_error):
    return [
        call.args[0] for call in mock_error.call_args_list
        if "TLCP-INVARIANT-VIOLATION" in str(call.args[0])
    ]


# Requests that carry no class context by nature: probes, sign-in and sign-up
# pages, an unmatched URL, the capability-token verification page, a
# sysadmin page. Production logged 345 "missing canonical context" ERROR lines
# for requests like these in its first five hours (2026-09-27).
CONTEXT_FREE_PATHS = [
    "/health",
    "/health/status",
    "/",
    "/.git/config",
    "/student/login",
    "/admin/login",
    "/admin/signup",
    "/sysadmin/login",
    "/api/tips/teacher",
    "/verify/hallpass/not-a-real-token",
]


@pytest.mark.parametrize("path", CONTEXT_FREE_PATHS)
def test_DOM_SUP_001__a_request_without_class_context_is_not_a_violation(app, path):
    from unittest.mock import patch

    client = app.test_client()
    with patch("app.services.tlcp.current_app.logger.error") as mock_error:
        client.get(path)
        assert _tlcp_violations(mock_error) == [], path


def test_DOM_SUP_001__absent_context_records_nothing_even_when_signed_in(app):
    """TLCP no longer decides whether a route needed context: that is the
    admission decorators' job (see the next test). A signed-in session with no
    context is correlated as nothing, not classified."""
    from unittest.mock import patch

    with app.test_request_context("/student/help-support/submit-issue", method="POST"):
        session["user_id"] = 1
        with patch("app.services.tlcp.current_app.logger.error") as mock_error:
            assert resolve_actor_context(None) is None
            assert _tlcp_violations(mock_error) == []


def test_DOM_IDEN_006__a_contradictory_signed_in_context_is_still_refused_and_logged(client, caplog):
    """Removing the TLCP classification weakens nothing: a signed-in teacher
    whose seat pointer names another class is refused at admission, and the
    resolver records the contradiction itself."""
    import logging

    from app.feats.base import FEATContext
    from app.models import Seat
    from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

    other = initialize("ap_csp_p3", client.application)
    active = initialize_as_teacher("chemistry_p1", client, client.application)
    foreign_seat = Seat.query.filter_by(class_id=other.class_id, role="teacher").one()
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="tlcp:foreign-seat-pointer"):
        user = db.session.get(User, active.teacher_user.id)
        user.last_active_seat_id = foreign_seat.id
        db.session.flush()

    with caplog.at_level(logging.WARNING):
        response = client.get("/admin/students")

    assert response.status_code in (302, 401)
    assert "/admin/students" not in response.headers.get("Location", "")
    assert any(
        "Canonical seat pointer crosses class boundary" in record.getMessage()
        for record in caplog.records
    )


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

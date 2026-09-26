"""Regression tests for the second live-test round (findings 29, 31, 32).

Each asserts a behaviour that was broken on the deployed build and each was
confirmed to fail against that code before the fix landed. They are grouped
because they share a cause worth naming: in all three the mechanism was present
and correct, and something upstream of it made it unreachable.

  29  the approval route opened a FEAT context around a call that opens its own,
      so every approval raised FEATContextError and 500'd
  31  the blueprint feature gate ran before ``admin_required`` and answered an
      expired session with a bare 404 instead of a redirect to login
  32  the token-rotation fetch omitted X-CSRFToken, so Flask-WTF refused every
      rotation before the route ran
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import HallPassLog, HallPassSettings
from app.services.entitlement_service import grant_hall_passes
from app.services.hall_pass_request_queue import (
    PendingHallPassRequest,
    enqueue_hall_pass_request,
    get_pending_hall_pass_request,
)
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _seed_hall_pass_policy(class_id: str) -> None:
    """One IN_USE hall-pass policy with a single consuming destination.

    Hall-pass policy is append-only with at most one IN_USE row per class
    (DOM-POL-001 §VI.1), so the provisioned policy is retired rather than
    shadowed.
    """
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"hall_pass_policy:{class_id}"):
        predecessor = (
            HallPassSettings.query
            .filter_by(class_id=class_id, availability_state="IN_USE")
            .first()
        )
        if predecessor is not None:
            predecessor.availability_state = "RETIRED"
            db.session.flush()

        db.session.add(HallPassSettings(
            class_id=class_id,
            max_queue_limit=10,
            pass_type_payload=[
                {"pass_name": "Bathroom", "max_queue": 10, "consume_pass": True}
            ],
        ))
        db.session.flush()


def _pending_request(classroom, student, request_id="req-1"):
    return enqueue_hall_pass_request(PendingHallPassRequest(
        request_id=request_id,
        class_id=classroom.class_id,
        requested_by_seat_id=student.seat.id,
        destination="Bathroom",
        requested_at_utc=datetime(2026, 9, 21, 4, 0, tzinfo=timezone.utc),
    ))


# --------------------------------------------------------------------------
# 29 — hall-pass approval
# --------------------------------------------------------------------------

def test_teacher_can_approve_a_hall_pass_request(app, client):
    """The approval writes a HallPassLog row and answers 200.

    Against the shipped code this returned 500: the route opened
    ``FEATContext("FEAT-PROD-002")`` and then called ``record_hall_pass_log``,
    whose ``@requires_feat_context`` decorator OPENS a second context rather
    than asserting the first. Nesting is forbidden (INV-ARC-000 §VIII.2), so
    every approval raised FEATContextError — caught by neither handler.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _seed_hall_pass_policy(classroom.class_id)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"grant:{student.seat.id}"):
            grant_hall_passes(student.seat, 1, correlation_id="corr-grant-1")
        _pending_request(classroom, student)

    response = client.post("/api/hall-pass/request/req-1/approve")

    assert response.status_code == 200, response.data
    assert response.get_json()["status"] == "success"

    with app.app_context():
        logs = HallPassLog.query.filter_by(class_id=classroom.class_id).all()
        assert len(logs) == 1, "approval must write exactly one hall_pass_logs row"
        assert logs[0].requested_by_seat_id == student.seat.id
        assert logs[0].destination == "Bathroom"
        # The pass is consumed, so the log references the entitlement.
        assert logs[0].hall_pass_id is not None

    # The request leaves the queue only on a successful approval.
    assert get_pending_hall_pass_request("req-1") is None


def test_approval_without_an_available_pass_is_refused_as_a_client_error(app, client):
    """A seat holding no pass gets 400, not 500 — the ValueError path still works.

    Guards the fix: removing the route's context must not turn a legitimate
    domain refusal into a server error.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="hall_pass")
        _seed_hall_pass_policy(classroom.class_id)
        _pending_request(classroom, student, request_id="req-no-pass")

    response = client.post("/api/hall-pass/request/req-no-pass/approve")

    assert response.status_code == 400, response.data
    with app.app_context():
        assert HallPassLog.query.filter_by(class_id=classroom.class_id).count() == 0


# --------------------------------------------------------------------------
# 31 — expired session on a feature-gated admin page
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "/admin/rent-settings",
        "/admin/payroll",
        "/admin/hall-pass",
        "/admin/store",
        "/admin/banking",
        "/admin/insurance",
    ],
)
def test_signed_out_feature_page_redirects_to_login_not_404(app, client, path):
    """An unauthenticated request must reach ``admin_required``, which redirects.

    Against the shipped code the blueprint's feature gate ran first — before the
    view and therefore before ``admin_required`` — resolved UNRESOLVED because
    no canonical context existed yet, and returned a bare 9-byte "Not Found".
    The six pages a teacher uses most answered a timeout with a 404 while every
    other admin page correctly sent them to log in.
    """
    response = client.get(path)

    assert response.status_code != 404, (
        f"{path} answered a signed-out request with 404 instead of redirecting"
    )
    assert response.status_code in (301, 302), response.status_code
    assert "/admin/login" in response.headers.get("Location", "")


def test_feature_gate_still_runs_for_an_authenticated_request(app, client):
    """Mutation proof for the ordering fix: authentication does not disarm the gate.

    The fix defers the capability check when no canonical context exists yet.
    Were it written as "skip the gate", a signed-in teacher whose class has rent
    turned off would reach the rent page. Instead the gate must still evaluate
    and answer with its enforcement signal — which is how we know it ran at all,
    since the DISABLED branch deliberately renders 200.
    """
    initialize_as_teacher("chemistry_p1", client, app)

    response = client.get("/admin/rent-settings")

    signalled = (
        response.headers.get("X-Feature-Disabled")
        or response.headers.get("X-Feature-Unresolved")
    )
    assert signalled == "rent" or response.status_code == 404, (
        "the capability gate did not evaluate for an authenticated request; "
        f"status={response.status_code} headers={dict(response.headers)}"
    )


# --------------------------------------------------------------------------
# 32 — the rotate call must carry a CSRF token
# --------------------------------------------------------------------------

def test_verify_token_rotation_uses_the_csrf_aware_fetch_helper():
    """The rotate call must route through AppCore.csrfFetch.

    A plain ``fetch`` here sent no X-CSRFToken, so Flask-WTF rejected every
    rotation with 400 before the route ran and the verification link could never
    be rotated — the documented remedy for a leaked link. Asserted against the
    template because the test suite runs with ``WTF_CSRF_ENABLED=False``
    (conftest.py), so no request-level test can observe this defect at all.
    """
    from pathlib import Path

    source = Path("templates/admin_hall_pass.html").read_text(encoding="utf-8")
    rotate_calls = [
        line for line in source.split("\n")
        if "hall-pass/verify-token/rotate" in line
    ]
    assert rotate_calls, "the rotate call site disappeared; update this test"
    for line in rotate_calls:
        assert "csrfFetch" in line, (
            "the token-rotation call must use AppCore.csrfFetch, which attaches "
            f"X-CSRFToken; found a bare fetch: {line.strip()}"
        )


def test_rotation_failure_is_not_reported_as_a_network_error():
    """A server that answered must not be described as unreachable.

    The 400 came back as an HTML error page; an unguarded ``r.json()`` threw and
    landed in ``.catch()``, which announced "Failed to contact the server" —
    sending the operator toward the wrong diagnosis and training them to retry.
    """
    from pathlib import Path

    source = Path("templates/admin_hall_pass.html").read_text(encoding="utf-8")
    assert "Failed to contact the server" not in source, (
        "a refusal the server sent is being reported as a connectivity failure"
    )
    # The handler must consult the response status before parsing a body.
    assert "if (!r.ok)" in source or "r.ok ?" in source, (
        "the rotate handler must check response.ok before treating the reply as JSON"
    )

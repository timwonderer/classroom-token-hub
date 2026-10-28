"""A correlation pack keeps the requests that explain a ticket, and shows their outcome.

Support ticket #13 (2026-10-27): a student's Store purchases were refused with
"Incorrect passphrase". The pack held seven `403` purchase attempts, but the
ticket page had no status column, so the refusals read as ordinary requests.
Meanwhile the dashboard's 10-second `/api/student-status` poll filled the
per-actor trace cap, so a few minutes of idling pushed real requests out of
`actor_request_trace` before a ticket could freeze them (DOM-SUP-001 §VI:
"relevant request trace entries").
"""
from app import db
from app.feats.base import FEATContext
from app.models import ActorRequestTrace, Issue, IssueCategory, TicketCorrelationPack
from app.services.tlcp import persist_request_trace
from app.utils.opaque_refs import make_opaque_ref
from tests.dom.interpretation.helpers import create_sysadmin
from tests.helpers.canonical_classroom import login_teacher
from tests.helpers.classroom_initializer import initialize
from tests.helpers.operation_routes import seed_sysadmin_session
from tests.helpers.support_domain import initialize_support_student, seed_support_issue_categories


def _context(seat, endpoint):
    return {"actor_type": seat.role, "actor_public_id": seat.public_id,
            "class_id": seat.class_id, "method": "GET", "endpoint": endpoint}


def test_DOM_SUP_001__successful_status_poll_is_not_recorded_but_its_failure_is(client):
    seat = initialize("chemistry_p1", client.application).students[0].seat
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:noise"):
        persist_request_trace(_context(seat, "/api/student-status"), "poll-ok", 200)
        persist_request_trace(_context(seat, "/api/student-status"), "poll-failed", 500)
        persist_request_trace(_context(seat, "/student/shop"), "shop", 200)

    recorded = {row.request_id for row in ActorRequestTrace.query.filter_by(actor_public_id=seat.public_id)}
    assert recorded == {"poll-failed", "shop"}


def test_DOM_SUP_001__polling_cannot_evict_a_refused_purchase_from_the_ticket(
        client, app, tlcp_trace_enabled):
    """Ticket #13 replayed: refused purchase, then more than a cap's worth of polling."""
    classroom, _student = initialize_support_student("chemistry_p1", client, app)
    db.session.commit()  # the production trace writer has its own connection
    refused = client.post("/api/purchase-item", json={
        "policy_uuid": "any-product", "passphrase": "not-the-passphrase", "quantity": 1})
    assert refused.status_code == 403
    for _ in range(25):  # above DEFAULT_TRACE_LIMIT
        assert client.get("/api/student-status").status_code == 200

    seed_support_issue_categories()
    category = (IssueCategory.query.filter_by(category_type="general", is_active=True)
                .order_by(IssueCategory.id).first())
    submitted = client.post("/student/help-support/submit-issue", data={
        "category_id": category.id, "explanation": "Purchases keep failing.",
        "expected_outcome": "I can buy the item."})
    assert submitted.status_code == 302

    issue = Issue.query.filter_by(student_explanation="Purchases keep failing.").one()
    trace = TicketCorrelationPack.query.filter_by(issue_id=issue.id).one().request_trace_json
    assert {"endpoint": "/api/purchase-item", "status_code": 403} in [
        {"endpoint": row["endpoint"], "status_code": row["status_code"]} for row in trace]
    assert all(row["endpoint"] != "/api/student-status" for row in trace)

    # The sysadmin sees the refusal, not just that a purchase was attempted.
    login_teacher(client, classroom)
    ref = make_opaque_ref("issue", issue.id)
    escalated = client.post(f"/admin/issues/{ref}/escalate",
                            data={"escalation_reason": "Needs developer investigation"})
    assert escalated.status_code == 302
    sysadmin = create_sysadmin("ticket13_viewer")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="ticket13_viewer")
    page = client.get(f"/sysadmin/issues/{ref}").get_data(as_text=True)
    assert '<th scope="col">Status</th>' in page
    assert "<td><code>403</code></td>" in page


def test_DOM_SUP_001__a_trace_past_its_ttl_never_reaches_a_ticket(client):
    """The TTL holds in the snapshot itself, not only when cleanup happens to run."""
    from app.services.tlcp import DEFAULT_TRACE_TTL_DAYS, create_ticket_correlation_pack
    from tests.helpers import temporal

    seat = initialize("chemistry_p1", client.application).students[0].seat
    now = temporal.now()
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:ttl"):
        for request_id, created_at in (
            ("expired", temporal.shifted(now, hours=-24 * (DEFAULT_TRACE_TTL_DAYS + 1))),
            ("recent", temporal.shifted(now, hours=-1)),
        ):
            db.session.add(ActorRequestTrace(
                actor_type=seat.role, actor_public_id=seat.public_id, class_id=seat.class_id,
                request_id=request_id, method="GET", endpoint="/student/shop",
                status_code=200, created_at=created_at,
            ))
        db.session.flush()

    pack = create_ticket_correlation_pack(
        issue_id=0, actor_type=seat.role, actor_public_id=seat.public_id,
        class_id=seat.class_id, ticket_created_at=now, include_recent_error=False,
    )
    assert [row["request_id"] for row in pack["request_trace_json"]] == ["recent"]

"""Ancillary request traces follow the lifetime of their canonical seat/class."""
from app import db
from app.feats.base import FEATContext, generate_correlation_id
from app.models import ActorRequestTrace, Seat
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize


def _trace(seat, request_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"trace:{request_id}"):
        trace = ActorRequestTrace(actor_type=seat.role, actor_public_id=seat.public_id,
                                  class_id=seat.class_id, request_id=request_id,
                                  method="GET", endpoint="/student/dashboard", status_code=200)
        db.session.add(trace)
        db.session.flush()
        return trace.id


def test_class_destruction_deletes_traces_and_spares_sibling(client):
    from app.routes.admin import _hard_delete_class_scope
    first = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    deleted_ids = [_trace(first.teacher_seat, "teacher-a"),
                   _trace(first.students[0].seat, "student-a")]
    kept_id = _trace(sibling.students[0].seat, "student-b")
    _hard_delete_class_scope(
        class_id=first.class_id,
        canonical_context=CanonicalContext(user_id=first.teacher_user.id,
            class_id=first.class_id, seat_id=first.teacher_seat.id, actor_role="teacher"),
        correlation_id=generate_correlation_id(), idempotency_key="trace:destroy-class",
    )
    db.session.expire_all()
    assert ActorRequestTrace.query.filter(ActorRequestTrace.id.in_(deleted_ids)).count() == 0
    assert db.session.get(ActorRequestTrace, kept_id) is not None


def test_seat_deletion_deletes_only_its_traces(client):
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    deleted_id = _trace(seat, "deleted-seat")
    kept_id = _trace(classroom.teacher_seat, "retained-seat")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:destroy-seat"):
        from app.services.classroom_setup import delete_seat_with_profile
        delete_seat_with_profile(db.session.get(Seat, seat.id))
        db.session.flush()
    db.session.expire_all()
    assert ActorRequestTrace.query.filter_by(id=deleted_id).count() == 0
    assert db.session.get(ActorRequestTrace, kept_id) is not None


def test_late_request_trace_cannot_recreate_deleted_seat_context(client):
    from app.services.tlcp import persist_request_trace
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    context = {"actor_type": seat.role, "actor_public_id": seat.public_id,
               "class_id": seat.class_id, "method": "POST", "endpoint": "/student/delete"}
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:late-delete"):
        Seat.query.filter_by(id=seat.id).delete(synchronize_session=False)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:late-write"):
        persist_request_trace(context, "late-request", 302)
    assert ActorRequestTrace.query.filter_by(request_id="late-request").count() == 0


def test_trace_writer_rejects_wrong_class_and_preserves_valid_context(client):
    from app.services.tlcp import persist_request_trace
    first = initialize("chemistry_p1", client.application)
    sibling = initialize("ap_csp_p3", client.application)
    seat = first.students[0].seat
    context = {"actor_type": seat.role, "actor_public_id": seat.public_id,
               "class_id": sibling.class_id, "method": "GET", "endpoint": "/student/dashboard"}
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:scope"):
        persist_request_trace(context, "wrong-class", 200)
        context["class_id"] = first.class_id
        persist_request_trace(context, "valid-class", 200)
    assert ActorRequestTrace.query.filter_by(request_id="wrong-class").count() == 0
    assert ActorRequestTrace.query.filter_by(request_id="valid-class").count() == 1


def test_account_destruction_removes_seat_then_orphan_user_and_traces(client):
    from app.models import User
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    deleted_id = _trace(seat, "deleted-user")
    kept_id = _trace(classroom.teacher_seat, "remaining-teacher")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:destroy-user"):
        from app.utils.student_deletion import remove_student_from_teacher_scope
        remove_student_from_teacher_scope(seat.id, classroom.teacher_user.id)
    db.session.expire_all()
    assert ActorRequestTrace.query.filter_by(id=deleted_id).count() == 0
    assert db.session.get(ActorRequestTrace, kept_id) is not None


def test_INV_ARC_021__support_holds_seat_public_id_without_foreign_key(client):
    """Support references seats by public ID only; deletion is explicit (DOM-SUP-001 §X)."""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    for table in ("issues", "actor_request_trace"):
        referred = {fk["referred_table"] for fk in inspector.get_foreign_keys(table)}
        assert "seats" not in referred, f"{table} must not hold a foreign key into Identity"


def test_deleting_an_unclaimed_seat_removes_its_earlier_tickets_and_traces(client):
    from app.models import Issue
    from app.services.classroom_setup import delete_seat_with_profile
    from app.utils.issue_helpers import create_issue
    from tests.helpers.support_domain import seed_support_issue_categories
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    other = classroom.students[1].seat
    seed_support_issue_categories()
    from app.models import IssueCategory
    category = IssueCategory.query.first()
    issue = create_issue(seat, seat.user_id, classroom.class_id, category.id, "Earlier claimant's report",
                         "Expected outcome", correlation_id="support:earlier-claimant",
                         idempotency_key="support:earlier-claimant")
    issue_id = issue.id
    kept_issue = create_issue(other, other.user_id, classroom.class_id, category.id, "Classmate report",
                              "Expected outcome", correlation_id="support:classmate",
                              idempotency_key="support:classmate").id
    trace_id = _trace(seat, "earlier-claimant")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="support:unclaim-then-delete"):
        live = db.session.get(Seat, seat.id)
        live.user_id, live.claimed_at = None, None
        db.session.flush()
        delete_seat_with_profile(live)
        db.session.flush()
    db.session.expire_all()
    assert db.session.get(Issue, issue_id) is None
    assert ActorRequestTrace.query.filter_by(id=trace_id).count() == 0
    assert db.session.get(Issue, kept_issue) is not None

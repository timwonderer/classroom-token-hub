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
        Seat.query.filter_by(id=seat.id).delete(synchronize_session=False)
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


def test_database_rejects_trace_for_deleted_actor(client):
    import pytest
    from sqlalchemy.exc import IntegrityError
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat
    public_id, class_id = seat.public_id, seat.class_id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:remove-before-insert"):
        Seat.query.filter_by(id=seat.id).delete(synchronize_session=False)
    with pytest.raises(IntegrityError):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="trace:reject-late-insert"):
            db.session.add(ActorRequestTrace(
                actor_type="student", actor_public_id=public_id, class_id=class_id,
                request_id="invalid-late-insert", method="GET", endpoint="/student/dashboard",
            ))
            db.session.flush()

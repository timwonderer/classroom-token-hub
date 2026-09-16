"""Last-student destruction and teacher sign-in retention boundaries."""
from datetime import timedelta

from app import db
from app.feats.base import FEATContext, generate_correlation_id
from app.models import ClassEconomy, Seat, User
from app.services.teacher_lifecycle import destroy_stale_teacher, teacher_account_is_stale
from app.utils.canonical_temporal_resolver import utc_now
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _students(class_id):
    return [seat.id for seat in Seat.query.filter_by(class_id=class_id, role="student").all()]


def test_last_students_require_account_warning_then_destroy(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    user_id, class_id = classroom.teacher_user.id, classroom.class_id
    ids = _students(class_id)
    preview = client.post('/admin/students/deletion-preview', json={'student_ids': ids}).get_json()
    assert preview['class_deleted'] and preview['account_deleted']
    assert 'teacher account' in preview['warning']
    blocked = client.post('/admin/students/bulk-delete', json={
        'student_ids': ids, **valid_destruction_gate('DELETE STUDENTS')})
    assert blocked.status_code == 400
    assert db.session.get(User, user_id) is not None
    response = client.post('/admin/students/bulk-delete', json={
        'student_ids': ids, **valid_destruction_gate(preview['expected_phrase'])})
    assert response.status_code == 200
    assert response.get_json()['account_deleted']
    db.session.expire_all()
    assert db.session.get(User, user_id) is None
    assert db.session.get(ClassEconomy, class_id) is None
    with client.session_transaction() as session:
        assert 'user_id' not in session


def test_last_students_delete_only_target_class_when_sibling_exists(client, app):
    sibling = initialize('ap_csp_p3', app)
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    user_id, class_id, sibling_id = classroom.teacher_user.id, classroom.class_id, sibling.class_id
    ids = _students(class_id)
    preview = client.post('/admin/students/deletion-preview', json={'student_ids': ids}).get_json()
    assert preview['class_deleted'] and not preview['account_deleted']
    result = client.post('/admin/students/bulk-delete', json={
        'student_ids': ids, **valid_destruction_gate(preview['expected_phrase'])})
    assert result.status_code == 200
    db.session.expire_all()
    assert db.session.get(ClassEconomy, class_id) is None
    assert db.session.get(ClassEconomy, sibling_id) is not None
    assert db.session.get(User, user_id) is not None


def test_regular_student_delete_removes_seat_without_destroying_class(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat_id = _students(classroom.class_id)[0]
    result = client.post('/admin/student/delete', data={'seat_id': seat_id, 'confirmation': 'DELETE'})
    assert result.status_code == 302
    db.session.expire_all()
    assert db.session.get(Seat, seat_id) is None
    assert db.session.get(ClassEconomy, classroom.class_id) is not None


def test_student_delete_rejects_sibling_class_ids(client, app):
    sibling = initialize('ap_csp_p3', app)
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat_id = _students(sibling.class_id)[0]
    result = client.post('/admin/students/bulk-delete', json={
        'student_ids': [seat_id], **valid_destruction_gate('DELETE STUDENTS')})
    assert result.status_code == 404
    assert db.session.get(Seat, seat_id) is not None


def test_retention_uses_180_days_since_sign_in_or_30_since_creation():
    now = utc_now()
    teacher = User(user_role='teacher', created_at=now-timedelta(days=30))
    assert teacher_account_is_stale(teacher, now)
    teacher.created_at += timedelta(seconds=1)
    assert not teacher_account_is_stale(teacher, now)
    teacher.last_signed_in_at = now-timedelta(days=180)
    assert teacher_account_is_stale(teacher, now)
    teacher.last_signed_in_at += timedelta(seconds=1)
    assert not teacher_account_is_stale(teacher, now)
    teacher.user_role = 'student'
    assert not teacher_account_is_stale(teacher, now+timedelta(days=365))


def test_stale_account_destruction_reuses_all_class_teardown(client, app, monkeypatch):
    from app.services import teacher_lifecycle
    classroom = initialize('chemistry_p1', app)
    sibling = initialize('ap_csp_p3', app)
    user_id, class_ids = classroom.teacher_user.id, [classroom.class_id, sibling.class_id]
    now = utc_now()
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='stale:setup'):
        classroom.teacher_user.last_signed_in_at = now-timedelta(days=180)
    monkeypatch.setattr(teacher_lifecycle, 'utc_now', lambda: now)
    assert destroy_stale_teacher(user_id=user_id, correlation_id=generate_correlation_id(), idempotency_key='stale:destroy')
    db.session.expire_all()
    assert db.session.get(User, user_id) is None
    assert ClassEconomy.query.filter(ClassEconomy.class_id.in_(class_ids)).count() == 0


def test_fresh_sign_in_invalidates_stale_candidate(client, app):
    from app.services.teacher_lifecycle import record_teacher_sign_in
    classroom = initialize('chemistry_p1', app)
    user_id = classroom.teacher_user.id
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='signin:setup'):
        classroom.teacher_user.last_signed_in_at = utc_now()-timedelta(days=181)
    with FEATContext('FEAT-IDEN-001', idempotency_key='signin:success'):
        record_teacher_sign_in(user_id)
    assert not destroy_stale_teacher(user_id=user_id, correlation_id=generate_correlation_id(), idempotency_key='stale:recheck')
    assert db.session.get(User, user_id) is not None


def test_unclaimed_seats_count_against_last_student_deletion(client, app):
    from app.services.classroom_setup import create_student_seat_with_profile
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    ids = _students(classroom.class_id)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='last:pending'):
        pending = create_student_seat_with_profile(class_id=classroom.class_id,
            first_name='Pending', last_name='Student')
    preview = client.post('/admin/students/deletion-preview', json={'student_ids': ids}).get_json()
    assert not preview['class_deleted']
    response = client.post('/admin/students/bulk-delete', json={
        'student_ids': ids, **valid_destruction_gate('DELETE STUDENTS')})
    assert response.status_code == 200
    preview = client.post('/admin/students/deletion-preview', json={'student_ids': [pending.id]}).get_json()
    assert preview['account_deleted']
    blocked = client.post('/admin/pending-students/delete', json={'seat_id': pending.id})
    assert blocked.status_code == 400
    assert db.session.get(Seat, pending.id) is not None


def test_scheduled_sweep_deletes_never_signed_in_after_30_days(client, app, monkeypatch):
    from app.services import teacher_lifecycle
    from app.scheduled_tasks import SCHEDULED_JOB_SPECS
    classroom = initialize('chemistry_p1', app)
    user_id = classroom.teacher_user.id
    now = utc_now()
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='never:setup'):
        classroom.teacher_user.created_at = now-timedelta(days=30)
        classroom.teacher_user.last_signed_in_at = None
    monkeypatch.setattr(teacher_lifecycle, 'utc_now', lambda: now)
    job = next(job for job in SCHEDULED_JOB_SPECS if job.id == 'stale_teacher_accounts')
    assert job.trigger_kwargs == {'hours': 1}
    assert job.func() == 1
    assert db.session.get(User, user_id) is None
    assert job.func() == 0


def test_teacher_session_refresh_does_not_extend_retention(client, app):
    from app.auth import establish_teacher_session
    classroom = initialize('chemistry_p1', app)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='refresh:setup'):
        classroom.teacher_user.last_signed_in_at = utc_now()-timedelta(days=10)
    before = classroom.teacher_user.last_signed_in_at
    with app.test_request_context():
        establish_teacher_session(classroom.teacher_user)
    assert classroom.teacher_user.last_signed_in_at == before

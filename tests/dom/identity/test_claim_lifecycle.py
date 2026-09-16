"""Claim artifacts end at binding; provisioning never resolves existing names."""
import pytest

from app.extensions import db
from app.feats.identity_feat import bind_authenticated_student_to_class
from app.models import Seat, IdentityProfile
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def assert_claim_cleared(seat):
    assert seat.user_id is not None and seat.claimed_at is not None
    assert all(getattr(seat, field) is None for field in (
        'claim_first_name_hash', 'claim_last_name_hash', 'roster_fingerprint', 'dedupe_code'
    ))


def test_initial_claim_erases_artifacts(client):
    classroom = initialize('chemistry_p1', client.application)
    for student in classroom.students:
        assert_claim_cleared(student.seat)
        assert student.profile.first_name == student.first_name


def test_import_matching_claimed_name_creates_new_seat(client):
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    original = classroom.students[0]
    before = Seat.query.filter_by(class_id=classroom.class_id).count()
    response = client.post('/admin/upload-students', json={'students': [
        {'first_name': original.first_name, 'last_name': original.last_name, 'notes': 'New enrolment'},
    ]})
    assert response.status_code == 200, response.json
    assert response.json['created'] == 1
    db.session.expire_all()
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == before + 1
    assert_claim_cleared(db.session.get(Seat, original.seat.id))
    pending = Seat.query.filter_by(class_id=classroom.class_id, role='student', user_id=None).one()
    assert pending.claim_first_name_hash and pending.claim_last_name_hash
    assert IdentityProfile.query.filter_by(seat_id=pending.id).one().notes == 'New enrolment'
    # A subsequent upload is another new student, even beside an unclaimed namesake.
    repeated = client.post('/admin/upload-students', json={'students': [
        {'first_name': original.first_name, 'last_name': original.last_name},
    ]})
    assert repeated.status_code == 200 and repeated.json['created'] == 1
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == before + 2


@pytest.mark.parametrize('rows', [
    [{'first_name': 'New', 'last_name': 'Student'}, {'first_name': '', 'last_name': 'Invalid'}],
    [{'first_name': 'New', 'last_name': 'Student'}, {'first_name': 'new', 'last_name': 'student'}],
])
def test_invalid_batch_is_atomic(client, rows):
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    before = Seat.query.filter_by(class_id=classroom.class_id).count()
    response = client.post('/admin/upload-students', json={'students': rows})
    assert response.status_code == 400
    assert response.json['created'] == 0
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == before


def test_explicit_batch_codes_and_authenticated_binding(client):
    source = initialize('chemistry_p1', client.application)
    target = initialize_as_teacher('duplicate_names', client, client.application)
    response = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'New', 'last_name': 'Student', 'dedupe_code': code} for code in ['ONE', 'TWO']
    ]})
    assert response.status_code == 200, response.json
    assert response.json['created'] == 2
    result = bind_authenticated_student_to_class(
        user_id=source.students[0].user.id, join_code=target.join_code,
        first_name='New', last_name='Student', dedupe_code='ONE',
        correlation_id='corr_claim_lifecycle', idempotency_key='claim-lifecycle:bind',
    )
    assert result.success
    assert_claim_cleared(db.session.get(Seat, result.seat_id))
    pending = Seat.query.filter_by(class_id=target.class_id, dedupe_code='TWO').one()
    assert pending.claim_first_name_hash is not None


def test_name_edits_only_change_profiles(client):
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    student = classroom.students[0]
    identity = (student.seat.id, student.seat.public_id, student.user.id)
    response = client.post('/admin/student/edit', data={
        'seat_id': student.seat.id, 'first_name': 'Edited', 'last_name': 'Student',
    })
    assert response.status_code == 302
    db.session.expire_all()
    profile = IdentityProfile.query.filter_by(seat_id=identity[0]).one()
    assert (profile.first_name, profile.last_name) == ('Edited', 'Student')
    assert (profile.seat.id, profile.seat.public_id, profile.seat.user_id) == identity
    assert_claim_cleared(profile.seat)
    response = client.post('/admin/customizations', data={
        'first_name': 'Edited', 'last_name': 'Teacher',
    })
    assert response.status_code == 302
    db.session.expire_all()
    teacher = IdentityProfile.query.filter_by(seat_id=classroom.teacher_seat.id).one()
    assert (teacher.first_name, teacher.last_name) == ('Edited', 'Teacher')
    assert teacher.seat.user_id == classroom.teacher_user.id

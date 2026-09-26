"""Claim artifacts end at binding; provisioning never resolves existing names."""
import pytest

from app.extensions import db
from app.feats.identity_feat import bind_authenticated_student_to_class, resolve_seat_claim
from app.models import Seat, IdentityProfile, User
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher
from tests.helpers.canonical_classroom import login_student


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
    # Both unclaimed namesakes receive distinct system codes and stay claimable.
    db.session.expire_all()
    namesakes = Seat.query.filter_by(class_id=classroom.class_id, role='student', user_id=None).all()
    codes = {seat.dedupe_code for seat in namesakes}
    assert len(namesakes) == 2 and None not in codes and len(codes) == 2
    for seat in namesakes:
        claim = resolve_seat_claim(join_code=classroom.join_code, first_name=original.first_name,
                                   last_name=original.last_name, dedupe_code=seat.dedupe_code)
        assert claim.success and claim.seat_id == seat.id


@pytest.mark.parametrize('rows', [
    [{'first_name': 'New', 'last_name': 'Student'}, {'first_name': '', 'last_name': 'Invalid'}],
    [{'first_name': 'New', 'last_name': 'Student'}, {'first_name': 'Other', 'last_name': 'Student', 'notes': 7}],
])
def test_invalid_batch_is_atomic(client, rows):
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    before = Seat.query.filter_by(class_id=classroom.class_id).count()
    response = client.post('/admin/upload-students', json={'students': rows})
    assert response.status_code == 400
    assert response.json['created'] == 0
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == before


def test_batch_namesakes_get_system_codes_and_bind(client):
    source = initialize('chemistry_p1', client.application)
    target = initialize_as_teacher('duplicate_names', client, client.application)
    response = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'New', 'last_name': 'Student', 'dedupe_code': 'ONE'} for _ in range(2)
    ]})
    assert response.status_code == 200, response.json
    assert response.json['created'] == 2
    codes = [seat.dedupe_code for seat in Seat.query.filter(
        Seat.class_id == target.class_id, Seat.user_id.is_(None),
        Seat.claim_first_name_hash.isnot(None), Seat.dedupe_code.isnot(None),
    ).order_by(Seat.id)]
    # Client-supplied codes are ignored; the system assigns distinct ones.
    assert len(codes) >= 2 and len(set(codes)) == len(codes) and 'ONE' not in codes
    result = bind_authenticated_student_to_class(
        user_id=source.students[0].user.id, join_code=target.join_code,
        first_name='New', last_name='Student', dedupe_code=codes[-2],
        correlation_id='corr_claim_lifecycle', idempotency_key='claim-lifecycle:bind',
    )
    assert result.success
    assert_claim_cleared(db.session.get(Seat, result.seat_id))
    pending = Seat.query.filter_by(class_id=target.class_id, dedupe_code=codes[-1]).one()
    assert pending.claim_first_name_hash is not None


def test_add_class_route_actually_activates_the_new_class(client):
    """/student/add-class must commit the session-context switch, not just claim
    the seat.

    Reproduces a live-test report (2026-09-22): a student who joined a second
    class saw "You're in! This class is now your active class." but the
    switch never stuck -- the route set ``user.last_active_class_id`` /
    ``last_active_seat_id`` directly on the ORM object, outside any FEAT
    context, with no explicit commit. That write is discarded at request
    teardown -- the same shape as finding 53's passkey-commit bug -- so a
    fresh read (simulating the student's very next request) still shows the
    OLD class. The route now uses the same canonical
    ``switch_student_session_context`` helper the dedicated
    ``/student/switch-class/<class_id>`` route already uses correctly, under
    its own FEAT context.
    """
    # Ava Chen is claimed in chemistry_p1. duplicate_names is an unrelated
    # class (different teacher, no name collision) that gets a fresh,
    # unclaimed "Ava Chen" seat added to it via the ordinary roster-upload
    # path -- exactly the "same student, second class" shape being
    # reproduced, built the same way test_import_matching_claimed_name_
    # creates_new_seat above builds its own unclaimed-seat fixture.
    first_classroom, ava = initialize_as_student('chemistry_p1', client, client.application)
    second_classroom = initialize_as_teacher('duplicate_names', client, client.application)
    upload = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'Ava', 'last_name': 'Chen'},
    ]})
    assert upload.status_code == 200 and upload.json['created'] == 1

    # Switch the client's session back to Ava before she adds the class.
    login_student(client, ava)

    response = client.post('/student/add-class', data={
        'join_code': second_classroom.join_code,
        'first_name': 'Ava',
        'last_name': 'Chen',
        'dedupe_code': '',
    }, follow_redirects=False)

    assert response.status_code == 302, response.get_data(as_text=True)
    assert response.headers['Location'].endswith('/student/dashboard')

    new_seat = Seat.query.filter_by(
        class_id=second_classroom.class_id, user_id=ava.user.id,
    ).one()
    assert new_seat.claimed_at is not None

    # Force a genuinely fresh read -- an in-memory-only mutation would still
    # pass an assertion against the same, already-mutated Python object.
    db.session.expire_all()
    refreshed_user = db.session.get(User, ava.user.id)
    assert refreshed_user.last_active_class_id == second_classroom.class_id
    assert refreshed_user.last_active_seat_id == new_seat.id


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

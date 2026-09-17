"""Unclaim preserves the Seat and requires fresh claim proof."""
from decimal import Decimal

import pytest
from app import db
from app.feats.base import FEATContext
from app.feats.identity_feat import activate_student_credentials, bind_authenticated_student_to_class, resolve_seat_claim
from app.models import AttendanceSession, ClassEconomy, IdentityProfile, Seat, Transaction, User
from app.services.ledger_posting_service import create_pending_transaction
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _unclaim(client, seat, **changes):
    payload = dict(seat_id=seat.id, claim_generation=seat.claim_generation,
                   first_name='Fresh', last_name='Claim', dedupe_code='', confirmation='UNCLAIM')
    payload.update(changes)
    return client.post('/admin/student/unclaim', json=payload)


def _complete(seat_id, generation, username='unclaim-new-account'):
    return activate_student_credentials(seat_id=seat_id, user_id=None,
        claim_generation=generation, username=username, pin='4826', passphrase='new-passphrase7',
        correlation_id='corr_unclaim_setup', idempotency_key=f'unclaim:setup:{username}')


def test_unclaim_preserves_display_and_records_then_normal_claim_works(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    seat_id, user_id, public_id = seat.id, seat.user_id, seat.public_id
    profile = IdentityProfile.query.filter_by(seat_id=seat.id).one()
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='unclaim:history'):
        profile.notes = 'Teacher context stays with the seat'
        tx = create_pending_transaction(seat_id=seat.id, target_seat_id=seat.id,
            actor_seat_id=classroom.teacher_seat.id, class_id=classroom.class_id,
            mechanism='teacher', amount=Decimal('7.50'), account_type='checking',
            type='manual_payment', description='Existing seat funds')
        attendance = AttendanceSession(target_seat_id=seat.id, actor_seat_id=seat.id,
            class_id=classroom.class_id, status='active', reason_code='start_work')
        db.session.add(attendance); db.session.flush()
        ids = tx.id, attendance.id
    original_profile = profile.first_name, profile.last_name, profile.notes
    response = _unclaim(client, seat)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['account_deleted'] is True
    db.session.expire_all()
    assert db.session.get(User, user_id) is None
    seat = db.session.get(Seat, seat_id)
    assert (seat.user_id, seat.claimed_at, seat.public_id) == (None, None, public_id)
    assert (profile.first_name, profile.last_name, profile.notes) == original_profile
    assert db.session.get(Transaction, ids[0]).amount == Decimal('7.50')
    assert db.session.get(AttendanceSession, ids[1]).target_seat_id == seat_id
    claim = resolve_seat_claim(join_code=classroom.join_code, first_name='Fresh', last_name='Claim')
    assert claim.success and claim.seat_id == seat_id
    result = _complete(seat_id, claim.claim_generation)
    assert result.success
    db.session.refresh(seat)
    assert seat.user_id == result.user_id and seat.claimed_at is not None
    assert (seat.claim_first_name_hash, seat.claim_last_name_hash, seat.roster_fingerprint, seat.dedupe_code) == (None, None, None, None)
    assert db.session.get(Transaction, ids[0]).seat_id == seat_id


def test_unclaim_preserves_multi_class_user_and_allows_consolidation(client, app):
    sibling = initialize('ap_csp_p3', app)
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    old_user_id = seat.user_id
    sibling_seat = sibling.students[0].seat
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='unclaim:multi-class'):
        # Attach a second-class position to this principal.
        previous = sibling_seat.user_id
        sibling_seat.user_id = old_user_id
        db.session.flush()
        from app.utils.student_deletion import delete_user_if_orphaned
        delete_user_if_orphaned(previous)
    assert _unclaim(client, seat).get_json()['account_deleted'] is False
    assert db.session.get(User, old_user_id) is not None
    assert db.session.get(Seat, sibling_seat.id).user_id == old_user_id
    result = bind_authenticated_student_to_class(user_id=old_user_id,
        join_code=classroom.join_code, first_name='Fresh', last_name='Claim',
        correlation_id='corr_unclaim_bind', idempotency_key='unclaim:bind')
    assert result.success and result.seat_id == seat.id
    db.session.refresh(seat)
    assert seat.user_id == old_user_id


@pytest.mark.parametrize('changes', [dict(first_name=''), dict(last_name=''),
    dict(confirmation=''), dict(claim_generation=-1), dict(claim_generation=True), dict(seat_id=True), dict(seat_id='invalid')])
def test_invalid_unclaim_does_not_change_binding(client, app, changes):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    user_id = seat.user_id
    response = _unclaim(client, seat, **changes)
    assert response.status_code == 400
    db.session.refresh(seat)
    assert seat.user_id == user_id and seat.claim_generation == 0


def test_foreign_or_teacher_seat_cannot_be_unclaimed(client, app):
    sibling = initialize('ap_csp_p3', app)
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    assert _unclaim(client, sibling.students[0].seat).status_code == 404
    assert _unclaim(client, classroom.teacher_seat).status_code == 404


def test_stale_claim_session_and_unclaim_form_cannot_act_on_new_generation(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    old_generation = seat.claim_generation
    assert _unclaim(client, seat).status_code == 200
    assert not _complete(seat.id, old_generation).success
    claim = resolve_seat_claim(join_code=classroom.join_code, first_name='Fresh', last_name='Claim')
    assert _complete(seat.id, claim.claim_generation).success
    assert _unclaim(client, seat, claim_generation=old_generation).status_code == 400
    db.session.refresh(seat)
    assert seat.user_id is not None


def test_unclaim_last_student_keeps_class_and_teacher(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='unclaim:last-seat'):
        from app.utils.student_deletion import remove_student_from_teacher_scope
        for other in classroom.students[1:]:
            remove_student_from_teacher_scope(other.seat.id, classroom.teacher_user.id)
    assert _unclaim(client, seat).status_code == 200
    assert db.session.get(ClassEconomy, classroom.class_id) is not None
    assert db.session.get(User, classroom.teacher_user.id) is not None
    assert db.session.get(Seat, classroom.teacher_seat.id) is not None


def test_duplicate_claim_names_fail_without_changing_existing_pending_seat(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    first, second = (student.seat for student in classroom.students[:2])
    assert _unclaim(client, first).status_code == 200
    response = _unclaim(client, second, dedupe_code='B')
    assert response.status_code == 400
    db.session.refresh(second)
    assert second.user_id is not None


def test_unclaim_page_exposes_distinct_action_and_blank_required_names(client, app):
    initialize_as_teacher('chemistry_p1', client, app)
    html = client.get('/admin/students').get_data(as_text=True)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select('[data-bs-target="#unclaimStudentModal"]')
    assert soup.select('.delete-student')
    for name in ['unclaimFirstName', 'unclaimLastName']:
        field = soup.find(id=name)
        assert field.has_attr('required') and not field.get('value')
    assert soup.find(id='unclaimAcknowledged').has_attr('required')


def test_unclaim_revokes_previous_teacher_recovery_confirmation(client, app):
    from app.feats.teacher_recovery_feat import begin_attempt, select_class_recipients
    from app.services.recovery_service import get_recovery_request_by_id, list_recovery_codes_for_request
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    common = dict(correlation_id='unclaim-recovery', idempotency_key='unclaim:recovery')
    attempt = begin_attempt(pairs=[(classroom.join_code, s.username) for s in classroom.students], **common)
    assert attempt
    assert select_class_recipients(request_id=attempt['id'], attempt_nonce=attempt['nonce'], class_id=classroom.class_id, **common)
    selected = list_recovery_codes_for_request(attempt['id'])
    seat = db.session.get(Seat, selected[0].seat_id)
    assert _unclaim(client, seat).status_code == 200
    assert get_recovery_request_by_id(attempt['id']).status == 'pending'
    remaining = list_recovery_codes_for_request(attempt['id'])
    assert len(remaining) == 1 and remaining[0].seat_id == selected[1].seat_id


def test_unclaim_route_claim_stores_new_generation_and_rejects_stale_session(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    assert _unclaim(client, seat).status_code == 200
    with client.session_transaction() as session:
        session.clear()
    response = client.post('/student/claim-account', data=dict(
        join_code=classroom.join_code, first_name='Fresh', last_name='Claim'))
    assert response.status_code == 302 and '/create-username' in response.location
    with client.session_transaction() as session:
        assert session['onboarding_claim_generation'] == 1
        session['onboarding_claim_generation'] = 0
    response = client.get('/student/create-username')
    assert response.status_code == 302 and '/claim-account' in response.location


def test_duplicate_claim_names_are_distinguished_by_codes(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    first, second = (student.seat for student in classroom.students[:2])
    assert _unclaim(client, first, dedupe_code='A').status_code == 200
    assert _unclaim(client, second, dedupe_code='B').status_code == 200
    for seat, code in [(first, 'A'), (second, 'B')]:
        claim = resolve_seat_claim(join_code=classroom.join_code, first_name='Fresh',
            last_name='Claim', dedupe_code=code)
        assert claim.success and claim.seat_id == seat.id
    assert not resolve_seat_claim(join_code=classroom.join_code,
        first_name='Fresh', last_name='Claim').success

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
                   first_name='Fresh', last_name='Claim', confirmation='UNCLAIM')
    payload.update(changes)
    return client.post('/admin/student/unclaim', json=payload)


def _complete(seat_id, generation, username='unclaim-new-account'):
    return activate_student_credentials(seat_id=seat_id, user_id=None,
        claim_generation=generation, username=username, pin='4826', passphrase='new-passphrase7',
        correlation_id='corr_unclaim_setup', idempotency_key=f'unclaim:setup:{username}')


def test_unclaim_renames_the_seat_and_preserves_its_records_then_claim_works(client, app):
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
    original_notes = profile.notes
    response = _unclaim(client, seat)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['account_deleted'] is True
    db.session.expire_all()
    assert db.session.get(User, user_id) is None
    seat = db.session.get(Seat, seat_id)
    assert (seat.user_id, seat.claimed_at, seat.public_id) == (None, None, public_id)
    # The entered names become the display name as well as the claim key
    # (DOM-IDEN-005 §Explicit Unclaim v2.2). Notes and every other seat-owned
    # fact survive — that is what "preserve" protects, not a departed
    # claimant's name.
    assert (profile.first_name, profile.last_name) == ('Fresh', 'Claim')
    assert profile.notes == original_notes
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


def test_unclaim_page_asks_for_no_claim_code(client, app):
    initialize_as_teacher('chemistry_p1', client, app)
    html = client.get('/admin/students').get_data(as_text=True)
    assert 'unclaimDedupeCode' not in html and 'name="dedupe_code"' not in html


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


def test_duplicate_claim_names_are_distinguished_by_system_codes(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    first, second = (student.seat for student in classroom.students[:2])
    assert _unclaim(client, first).status_code == 200
    db.session.refresh(first)
    assert first.dedupe_code is None  # alone under these names
    # A client-sent code is ignored; the second unclaim codes both seats.
    assert _unclaim(client, second, dedupe_code='B').status_code == 200
    db.session.expire_all()
    first, second = db.session.get(Seat, first.id), db.session.get(Seat, second.id)
    assert first.dedupe_code and second.dedupe_code and first.dedupe_code != second.dedupe_code
    assert 'B' not in {first.dedupe_code, second.dedupe_code}
    for seat in (first, second):
        claim = resolve_seat_claim(join_code=classroom.join_code, first_name='Fresh',
            last_name='Claim', dedupe_code=seat.dedupe_code)
        assert claim.success and claim.seat_id == seat.id
    assert not resolve_seat_claim(join_code=classroom.join_code,
        first_name='Fresh', last_name='Claim').success


def test_unclaim_leaves_the_roster_name_and_the_claim_key_naming_one_person(client, app):
    """The invariant behind DOM-IDEN-005 §Explicit Unclaim v2.2.

    The teacher reads the roster; the student claims against the hashes. If the
    two diverge, the seat is claimable only under a name the teacher cannot see,
    and the teacher directs the student using the name on screen — so the claim
    fails for a reason neither of them can observe.

    Through v2.1 the entered names were written to the claim material alone
    ("preserve existing profile display names"), so unclaiming "Ava Chen" as
    "Robin Vale" left the roster showing Ava Chen and the seat claimable only as
    Robin Vale.
    """
    from app.services.roster_view_model import build_class_roster_view

    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    seat_id = seat.id
    previous_name = IdentityProfile.query.filter_by(seat_id=seat_id).one().full_name

    assert _unclaim(client, seat, first_name='Robin', last_name='Vale').status_code == 200
    db.session.expire_all()

    # What the teacher sees on the roster.
    roster = build_class_roster_view(
        class_id=classroom.class_id,
        teacher_user_id=classroom.teacher_user.id,
        recovery_min_students=3,
    )
    row = next(r for r in roster.unclaimed_seats if r.seat_id == seat_id)
    assert row.full_name == 'Robin Vale'
    assert previous_name not in row.full_name

    # What the student must type to claim it.
    claim = resolve_seat_claim(join_code=classroom.join_code, first_name='Robin', last_name='Vale')
    assert claim.success and claim.seat_id == seat_id

    # And the name the roster no longer shows no longer claims the seat.
    stale = resolve_seat_claim(
        join_code=classroom.join_code,
        first_name=classroom.students[0].first_name,
        last_name=classroom.students[0].last_name,
    )
    assert not (stale.success and stale.seat_id == seat_id)


def test_unclaim_keeps_notes_and_money_while_the_name_moves(client, app):
    """Renaming at unclaim is not a reset: the seat keeps what it accumulated."""
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    seat_id = seat.id
    profile = IdentityProfile.query.filter_by(seat_id=seat_id).one()
    with FEATContext('FEAT-TEST-SETUP', idempotency_key=f'unclaim:notes:{seat_id}'):
        profile.notes = 'Sits by the window; needs a charger'
        tx = create_pending_transaction(
            seat_id=seat_id, target_seat_id=seat_id, actor_seat_id=classroom.teacher_seat.id,
            class_id=classroom.class_id, mechanism='teacher', amount=Decimal('12.25'),
            account_type='checking', type='manual_payment', description='Earned before unclaim')
        db.session.flush()
        tx_id = tx.id

    assert _unclaim(client, seat, first_name='Robin', last_name='Vale').status_code == 200
    db.session.expire_all()

    profile = IdentityProfile.query.filter_by(seat_id=seat_id).one()
    assert (profile.first_name, profile.last_name) == ('Robin', 'Vale')
    assert profile.notes == 'Sits by the window; needs a charger'
    assert db.session.get(Transaction, tx_id).amount == Decimal('12.25')
    assert db.session.get(Transaction, tx_id).seat_id == seat_id

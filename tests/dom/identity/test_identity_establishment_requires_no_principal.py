"""Identity establishment is for someone nobody is signed in as (OPS-DB-001).

DOM-IDEN-005 §VII: an unauthenticated claim provisions a new User "because no
authenticated principal exists". On 2026-09-30 a browser signed in as one
student ran the claim for another seat: the claim verified, staged setup,
locked the class, and FEAT-IDEN-002 created a second User while the first one's
session stayed live. The workflow's premise was false and nothing checked it.

Operator ruling 2026-10-01 (DOM-IDEN-005 §VII): claim, credential setup, and
recovery setup require the *absence* of an authenticated principal. A browser
session that names anyone is refused before verification. The refusal infers
nothing about the people involved: CTH knows only that the session represents
someone.

Names below are the ones from the shared-Chromebook report. In the fixture,
"Maria" is roster student Ava (signed in) and "Francisco" is the seat a teacher
unclaimed and re-rostered under that name.
"""
from __future__ import annotations

import html

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import db
from app.models import Seat, User
from app.services import student_setup
from tests.dom.identity.helpers import (
    admin_generate_recovery_code,
    student_create_username,
    student_login,
    student_setup_pin_passphrase,
    student_verify_saved_username,
)
from tests.helpers.canonical_classroom import login_student, login_teacher
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.operation_routes import seed_sysadmin_session
# Imported at collection: it loads wsgi, which must happen before the app serves a request.
from tests.dom.operation.test_sysadmin_grafana_auth import _create_sysadmin_via_cli

SIGNED_IN = "We are having trouble determining who you are right now."
CANCELLED = "For your protection, this request was cancelled."
# The owner's copy, verbatim (operator decision on PR #1457).
REFUSAL_COPY = (
    ("h1", SIGNED_IN),
    ("p", CANCELLED),
    ("h2", "Why is this happening?"),
    ("p", "Your sign-in changed while this page was open, so we can't safely determine which account "
          "should complete this request. This can happen when you sign in to another account in a "
          "different tab or when someone else uses the same browser."),
    ("h2", "What can I do?"),
    ("p", "Return to the login page and sign in again. Before continuing, close any older Classroom "
          "Token Hub tabs that are still open."),
    ("a", "Return to login"),
)
ONBOARDING_KEYS = (
    'onboarding_seat_ref', 'onboarding_user_ref', 'onboarding_claim_generation',
    'recovery_setup_authorization', 'student_setup_token',
)
PASSPHRASE = "Surprised!Banana!2!You!"


def _session(client):
    with client.session_transaction() as sess:
        return dict(sess)


def _session_state(client):
    """The session minus the display-name cache (SPEC-DISPLAY-001 §VII: not authoritative).

    Every page rendered for a signed-in student fills that cache from a context
    processor; the refusal page is no different. Everything that carries
    identity, onboarding, or a flashed message must be untouched.
    """
    from app.utils.display_metadata import DISPLAY_METADATA_SESSION_KEY
    state = _session(client)
    state.pop(DISPLAY_METADATA_SESSION_KEY, None)
    return state


def _return_to_login(page):
    return next(a for a in page.find_all('a') if a.get_text(strip=True) == "Return to login")


def _assert_return_to_login_signs_out(client, page, logout_path, login_path):
    """The button ends the sign-in that caused the refusal and lands on that role's login page."""
    button = _return_to_login(page)
    assert button['href'] == logout_path
    response = client.get(button['href'])
    assert response.status_code == 302 and response.location.split('?')[0].endswith(login_path)
    # The principal is gone; admin logout leaves a stale nonce key, which names nobody.
    assert 'user_id' not in _session(client)
    landed = client.get(response.location)
    assert landed.status_code == 200


def _assert_return_to_login_posts_sign_out(client, page, logout_path, login_path):
    """A POST-only logout (sysadmin) is offered as a form carrying a CSRF token, not a link."""
    assert not [a for a in page.find_all('a') if a.get_text(strip=True) == "Return to login"]
    button = next(b for b in page.find_all('button') if b.get_text(strip=True) == "Return to login")
    form = button.find_parent('form')
    assert form['method'].lower() == 'post' and form['action'] == logout_path
    token = form.find('input', attrs={'name': 'csrf_token'})
    assert token is not None and token['value']
    response = client.post(form['action'], data={'csrf_token': token['value']})
    assert response.status_code == 302 and response.location.split('?')[0].endswith(login_path)
    assert 'user_id' not in _session(client)
    landed = client.get(response.location)
    assert landed.status_code == 200


def _sign_out_browser(client):
    with client.session_transaction() as sess:
        sess.clear()


def _claim(client, classroom, first='Francisco', last='Reyes'):
    return client.post('/student/claim-account', data=dict(
        join_code=classroom.join_code, first_name=first, last_name=last))


def _setup_records():
    return student_setup.client().dbsize()


def _body(response):
    return html.unescape(response.get_data(as_text=True))


def _assert_unlocked(class_id, seat_id):
    """A second connection can take both rows at once: the request left no lock behind."""
    with db.engine.connect() as other:
        try:
            other.execute(text("SELECT 1 FROM classes WHERE class_id = :c FOR UPDATE NOWAIT"), {"c": class_id})
            other.execute(text("SELECT 1 FROM seats WHERE id = :s FOR UPDATE NOWAIT"), {"s": seat_id})
        except OperationalError as exc:  # pragma: no cover - the failure being guarded
            pytest.fail(f"the refused request still holds a row lock: {exc.orig}")
        finally:
            other.rollback()


@pytest.fixture
def shared_chromebook(client, app, monkeypatch):
    """Maria is signed in; Francisco's seat in the same class is waiting to be claimed."""
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    maria, francisco_seat = classroom.students[0], classroom.students[1].seat
    unclaimed = client.post('/admin/student/unclaim', json=dict(
        seat_id=francisco_seat.id, claim_generation=francisco_seat.claim_generation,
        first_name='Francisco', last_name='Reyes', confirmation='UNCLAIM'))
    assert unclaimed.status_code == 200
    _sign_out_browser(client)
    login_student(client, maria)
    db.session.commit()

    calls = {"turnstile": 0, "resolve_seat_claim": 0}

    def turnstile(*args, **kwargs):
        calls["turnstile"] += 1
        return True

    import app.feats.identity_feat as identity_feat
    import app.routes.recovery as recovery_routes
    import app.routes.student as student_routes
    real_resolve = identity_feat.resolve_seat_claim

    def resolve_seat_claim(**kwargs):
        calls["resolve_seat_claim"] += 1
        return real_resolve(**kwargs)

    monkeypatch.setattr(student_routes, 'verify_turnstile_token', turnstile)
    monkeypatch.setattr(recovery_routes, 'verify_turnstile_token', turnstile)
    monkeypatch.setattr(identity_feat, 'resolve_seat_claim', resolve_seat_claim)
    return {"classroom": classroom, "maria": maria, "seat_id": francisco_seat.id, "calls": calls}


# ------------------------------------------------------------- claim entry

def test_OPS_DB_001__signed_in_claim_post_is_refused_before_any_effect(client, shared_chromebook):
    classroom, calls = shared_chromebook["classroom"], shared_chromebook["calls"]
    records_before = _setup_records()
    users_before = User.query.count()

    response = _claim(client, classroom)
    db.session.rollback()  # end any transaction the request left open, then look from outside

    assert calls == {"turnstile": 0, "resolve_seat_claim": 0}, "verification ran for a signed-in browser"
    assert _setup_records() == records_before, "a setup record was staged"
    session_after = _session(client)
    assert not [key for key in ONBOARDING_KEYS if key in session_after]
    assert session_after['user_id'] == shared_chromebook["maria"].user.id, "Maria stays signed in"
    assert User.query.count() == users_before
    assert response.status_code == 409
    assert SIGNED_IN in _body(response)


def test_OPS_DB_001__signed_in_claim_post_takes_no_row_lock(client, shared_chromebook):
    _claim(client, shared_chromebook["classroom"])
    # Deliberately no rollback here: a lock the request took would still be held.
    _assert_unlocked(shared_chromebook["classroom"].class_id, shared_chromebook["seat_id"])


def test_OPS_DB_001__signed_in_claim_page_renders_refusal_without_touching_the_session(client, shared_chromebook):
    before = _session_state(client)
    response = client.get('/student/claim-account')
    assert response.status_code == 200
    page = BeautifulSoup(response.data, 'html.parser')
    assert page.select_one('form') is None, "the claim form is not offered"
    shown = [(el.name, ' '.join(el.get_text(' ', strip=True).split()))
             for el in page.select_one('.auth-body').find_all(['h1', 'h2', 'p', 'a'])]
    assert shown == list(REFUSAL_COPY), "the page says exactly the owner's copy and nothing else"
    assert page.select_one('a[href="/student/add-class"]') is None
    assert _session_state(client) == before, "GET must not change the session"


def test_OPS_DB_001__return_to_login_signs_the_student_out(client, shared_chromebook):
    page = BeautifulSoup(client.get('/student/claim-account').data, 'html.parser')
    _assert_return_to_login_signs_out(client, page, '/student/logout', '/student/login')
    # Signed out, the claim is no longer refused.
    assert SIGNED_IN not in _body(client.get('/student/claim-account'))


def test_OPS_DB_001__full_incident_sequence_creates_no_second_user(client, shared_chromebook):
    """The production sequence, start to finish, while Maria is signed in."""
    classroom = shared_chromebook["classroom"]
    users_before = User.query.count()
    _claim(client, classroom)
    student_create_username(client, 'otter', follow_redirects=False)
    student_verify_saved_username(client)
    student_setup_pin_passphrase(
        client, pin="4826", confirm_pin="4826", passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=False)
    db.session.expire_all()
    assert db.session.get(Seat, shared_chromebook["seat_id"]).user_id is None
    assert User.query.count() == users_before


# ------------------------------------------------- every page of the workflow

@pytest.fixture
def mid_setup_then_signed_in(client, shared_chromebook):
    """Francisco began setup signed out; then the browser was signed in as Maria."""
    _sign_out_browser(client)
    response = _claim(client, shared_chromebook["classroom"])
    assert response.status_code == 302 and '/create-username' in response.location
    assert student_create_username(client, 'otter', follow_redirects=False).status_code == 302
    login_student(client, shared_chromebook["maria"])
    db.session.commit()
    assert 'student_setup_token' in _session(client)
    return shared_chromebook


@pytest.mark.parametrize('path', [
    '/student/claim-account', '/student/create-username', '/student/verify-username',
    '/student/setup-pin-passphrase', '/recovery/lookup',
])
def test_OPS_DB_001__every_workflow_page_refuses_a_signed_in_browser(client, mid_setup_then_signed_in, path):
    before = _session_state(client)
    response = client.get(path)
    assert response.status_code == 200
    assert SIGNED_IN in _body(response)
    assert _session_state(client) == before


def test_OPS_DB_001__recovery_entry_redirect_lands_on_the_refusal(client, shared_chromebook):
    response = client.get('/recovery/', follow_redirects=True)
    assert SIGNED_IN in _body(response)


@pytest.mark.parametrize('path, data', [
    ('/student/create-username', {'write_in_word': 'badger'}),
    ('/student/verify-username', {'saved_username': 'anything', 'retention_page_token': 'x'}),
    ('/student/setup-pin-passphrase', {'pin': '4826', 'confirm_pin': '4826', 'passphrase': PASSPHRASE,
                                       'confirm_passphrase': PASSPHRASE, 'retention_page_token': 'x'}),
])
def test_OPS_DB_001__workflow_posts_are_refused_mid_setup(client, mid_setup_then_signed_in, path, data):
    before = _session_state(client)
    response = client.post(path, data=data)
    assert response.status_code == 409
    assert SIGNED_IN in _body(response)
    assert CANCELLED in _body(response) and 'Return to login' in _body(response)
    assert _session_state(client) == before


def test_OPS_DB_001__in_flight_setup_cannot_complete_once_signed_in(client, mid_setup_then_signed_in):
    """A setup started signed out has no completion path after a sign-in."""
    users_before = User.query.count()
    student_verify_saved_username(client)
    student_setup_pin_passphrase(
        client, pin="4826", confirm_pin="4826", passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=False)
    db.session.expire_all()
    assert db.session.get(Seat, mid_setup_then_signed_in["seat_id"]).user_id is None
    assert User.query.count() == users_before


def test_OPS_DB_001__json_retention_check_is_refused_as_json(client, mid_setup_then_signed_in):
    response = client.post('/student/verify-username', data={'saved_username': 'x', 'retention_page_token': 'x'},
                           headers={'Accept': 'application/json'})
    assert response.status_code == 409
    assert response.is_json
    assert response.json['verified'] is False
    assert response.json['message'] == f"{SIGNED_IN} {CANCELLED}"
    assert response.json['redirect'] == '/student/logout', "the page script follows it and ends the sign-in"


# ------------------------------------------------------------- recovery entry

def test_OPS_DB_001__signed_in_recovery_does_not_consume_the_code(client, shared_chromebook):
    classroom, calls = shared_chromebook["classroom"], shared_chromebook["calls"]
    mia = classroom.students[2]
    _sign_out_browser(client)
    login_teacher(client, classroom)
    admin_generate_recovery_code(client, mia.seat.id)
    db.session.expire_all()
    code = db.session.get(User, mia.user.id).reset_code
    assert code
    _sign_out_browser(client)
    login_student(client, shared_chromebook["maria"])
    db.session.commit()
    records_before = _setup_records()

    response = client.post('/recovery/lookup', data={'reset_code': code})
    db.session.rollback()

    assert calls["turnstile"] == 0
    db.session.expire_all()
    mia_user = db.session.get(User, mia.user.id)
    assert mia_user.reset_code == code, "the code was consumed"
    assert mia_user.recovery_setup_nonce_hash is None
    assert _setup_records() == records_before
    assert not [key for key in ONBOARDING_KEYS if key in _session(client)]
    assert response.status_code == 409
    assert SIGNED_IN in _body(response)


# --------------------------------------------------- other principal kinds

def test_OPS_DB_001__teacher_session_is_refused(client, shared_chromebook):
    classroom = shared_chromebook["classroom"]
    _sign_out_browser(client)
    login_teacher(client, classroom)
    db.session.commit()
    page = BeautifulSoup(client.get('/student/claim-account').data, 'html.parser')
    assert SIGNED_IN in html.unescape(page.get_text(' '))
    response = _claim(client, classroom)
    assert response.status_code == 409
    assert shared_chromebook["calls"]["resolve_seat_claim"] == 0
    _assert_return_to_login_signs_out(client, page, '/admin/logout', '/admin/login')


def test_OPS_DB_001__sysadmin_session_is_refused(client, shared_chromebook):
    _sign_out_browser(client)
    sysadmin, _ = _create_sysadmin_via_cli("establishment_refusal")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="establishment_refusal")
    db.session.commit()
    page = BeautifulSoup(client.get('/student/claim-account').data, 'html.parser')
    assert SIGNED_IN in html.unescape(page.get_text(' '))
    response = _claim(client, shared_chromebook["classroom"])
    assert response.status_code == 409
    assert shared_chromebook["calls"]["resolve_seat_claim"] == 0
    _assert_return_to_login_posts_sign_out(client, page, '/sysadmin/logout', '/sysadmin/login')


def test_OPS_DB_001__sysadmin_json_refusal_redirects_to_the_sign_out_page(client, shared_chromebook):
    """A JSON caller follows ``redirect`` with a GET, which the POST-only sysadmin
    logout refuses with 405. It is sent back to the refusal page, whose GET
    renders the sign-out form."""
    _sign_out_browser(client)
    sysadmin, _ = _create_sysadmin_via_cli("establishment_refusal_json")
    seed_sysadmin_session(client, user_id=sysadmin.id, username="establishment_refusal_json")
    db.session.commit()
    response = client.post('/student/verify-username', data={'saved_username': 'x', 'retention_page_token': 'x'},
                           headers={'Accept': 'application/json'})
    assert response.status_code == 409 and response.is_json
    assert response.json['redirect'] == '/student/verify-username'
    page = BeautifulSoup(client.get(response.json['redirect']).data, 'html.parser')
    assert SIGNED_IN in html.unescape(page.get_text(' '))
    _assert_return_to_login_posts_sign_out(client, page, '/sysadmin/logout', '/sysadmin/login')


def test_OPS_DB_001__revoked_session_counts_as_signed_out(client, shared_chromebook):
    """A session whose nonce was rotated names nobody; it neither blocks nor survives."""
    from app.feats.base import FEATContext
    maria = shared_chromebook["maria"]
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:revoke-maria-session"):
        db.session.get(User, maria.user.id).current_session_nonce = 'rotated-elsewhere'
        db.session.flush()
    db.session.commit()
    response = client.get('/student/claim-account')
    assert response.status_code == 200
    assert SIGNED_IN not in _body(response)
    assert 'user_id' not in _session(client)


# --------------------------------------------- shared Chromebook, end to end

def test_OPS_DB_001__shared_chromebook_sign_out_then_claim(client, shared_chromebook):
    classroom, maria = shared_chromebook["classroom"], shared_chromebook["maria"]
    maria_before = db.session.get(User, maria.user.id)
    maria_snapshot = (maria_before.passphrase_hash, maria_before.pin_hash, maria_before.username_lookup_hash)
    maria_seats = {s.id for s in Seat.query.filter_by(user_id=maria.user.id)}

    refused = client.get('/student/claim-account')
    client.get(_return_to_login(BeautifulSoup(refused.data, 'html.parser'))['href'])
    assert 'user_id' not in _session(client)

    response = _claim(client, classroom)
    assert response.status_code == 302 and '/create-username' in response.location
    assert student_create_username(client, 'otter', follow_redirects=False).status_code == 302
    username = BeautifulSoup(client.get('/student/setup-pin-passphrase').data, 'html.parser').select_one(
        '[data-generated-username]').get_text(strip=True)
    assert student_verify_saved_username(client).status_code == 200
    finished = student_setup_pin_passphrase(
        client, pin="4826", confirm_pin="4826", passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=False)
    assert finished.status_code == 302 and finished.location.endswith('/student/setup-complete')

    db.session.expire_all()
    francisco_user_id = db.session.get(Seat, shared_chromebook["seat_id"]).user_id
    assert francisco_user_id is not None and francisco_user_id != maria.user.id
    maria_after = db.session.get(User, maria.user.id)
    assert (maria_after.passphrase_hash, maria_after.pin_hash, maria_after.username_lookup_hash) == maria_snapshot
    assert {s.id for s in Seat.query.filter_by(user_id=maria.user.id)} == maria_seats

    _sign_out_browser(client)
    login = student_login(client, username=username, passphrase=PASSPHRASE)
    assert login.status_code == 302 and '/student/login' not in login.location
    assert _session(client)['user_id'] == francisco_user_id


def test_OPS_DB_001__signed_out_recovery_still_works(client, shared_chromebook):
    classroom = shared_chromebook["classroom"]
    mia = classroom.students[2]
    _sign_out_browser(client)
    login_teacher(client, classroom)
    admin_generate_recovery_code(client, mia.seat.id)
    db.session.expire_all()
    code = db.session.get(User, mia.user.id).reset_code
    _sign_out_browser(client)
    response = client.post('/recovery/lookup', data={'reset_code': code})
    assert response.status_code == 302 and '/student/create-username' in response.location
    assert _session(client).get('onboarding_user_ref') == mia.user.id


# ------------------------------------------- FEAT-IDEN-005: one seat per class

def test_FEAT_IDEN_005__add_class_refuses_a_class_the_student_is_already_in(client, shared_chromebook):
    """INV-ARC-000: the capability check precedes the command, not a constraint at flush."""
    classroom, maria = shared_chromebook["classroom"], shared_chromebook["maria"]
    maria_seats = {s.id for s in Seat.query.filter_by(user_id=maria.user.id)}

    response = client.post('/student/add-class', data=dict(
        join_code=classroom.join_code, first_name='Francisco', last_name='Reyes'))

    assert response.status_code == 302
    db.session.expire_all()
    assert db.session.get(Seat, shared_chromebook["seat_id"]).user_id is None
    assert {s.id for s in Seat.query.filter_by(user_id=maria.user.id)} == maria_seats
    flashed = _session(client).get('_flashes') or []
    assert ('warning', "You're already in this class.") in flashed

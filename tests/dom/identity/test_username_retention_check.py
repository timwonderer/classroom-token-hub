"""Username retention check during student credential setup.

A student cannot finish setup by claiming they saved their username. They have
to type it back after it leaves the screen, and the server — not the page
script — decides whether it matches. The check adds no copy of the username
anywhere: not to the database, the logs, or a URL.
"""
from __future__ import annotations

import logging
import re

import pytest
from sqlalchemy import text
from bs4 import BeautifulSoup
from app.services import student_setup

from app import db
from app.models import Seat, User
from tests.dom.identity.helpers import (
    student_create_username,
    student_login,
    student_setup_pin_passphrase,
    student_verify_saved_username,
)
from tests.helpers.classroom_initializer import initialize_as_teacher

PASSPHRASE = "Surprised!Banana!2!You!"
MISMATCH = "That doesn&#39;t match your username. Check the copy you saved and try again."


def _unclaim(client, seat):
    return client.post('/admin/student/unclaim', json=dict(
        seat_id=seat.id, claim_generation=seat.claim_generation,
        first_name='Fresh', last_name='Claim', confirmation='UNCLAIM'))


@pytest.fixture
def claiming(client, app):
    """A student part-way through claiming a seat, with a username generated."""
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    seat = classroom.students[0].seat
    assert _unclaim(client, seat).status_code == 200
    with client.session_transaction() as sess:
        sess.clear()
    response = client.post('/student/claim-account', data=dict(
        join_code=classroom.join_code, first_name='Fresh', last_name='Claim'))
    assert response.status_code == 302 and '/create-username' in response.location
    assert student_create_username(client, 'otter', follow_redirects=False).status_code == 302
    username = BeautifulSoup(client.get('/student/setup-pin-passphrase').data, 'html.parser').select_one('[data-generated-username]').get_text(strip=True)
    return {"classroom": classroom, "seat_id": seat.id, "username": username}


def _session(client):
    with client.session_transaction() as sess:
        return dict(sess)


def _record(client):
    token = _session(client)['student_setup_token']
    import json
    return json.loads(student_setup.client().get(student_setup._key(token)))


def _replace_username(client, value):
    record = _record(client)
    from app.utils.encryption import _get_fernet
    student_setup._change(_session(client)['student_setup_token'], record['scope'],
        lambda row: row.update(username=_get_fernet().encrypt(value.encode()).decode()))


def _finish(client, **kwargs):
    return student_setup_pin_passphrase(
        client, pin="4826", confirm_pin="4826", passphrase=PASSPHRASE,
        confirm_passphrase=PASSPHRASE, follow_redirects=False, **kwargs)


def _seat_claimed(seat_id):
    db.session.expire_all()
    return db.session.get(Seat, seat_id).user_id is not None


# ---------------------------------------------------------------- presentation

def test_username_is_shown_with_copy_and_no_acknowledgement_checkbox(client, claiming):
    body = client.get('/student/setup-pin-passphrase').get_data(as_text=True)
    assert claiming["username"] in body
    assert 'data-copy-username' in body and 'Copy username' in body
    assert "does not keep a readable copy of your username" in body
    assert "I've saved my username" in body or "I&#39;ve saved my username" in body
    assert 'username-ack' not in body and 'I have written down my username' not in body
    # PIN and passphrase stay locked until the check passes.
    assert re.search(r'<fieldset id="setup-fields"[^>]*\bdisabled\b', body)


def test_username_is_stable_across_refresh_and_moving_between_states(client, claiming):
    for path in ('/student/setup-pin-passphrase', '/student/verify-username',
                 '/student/setup-pin-passphrase', '/student/setup-pin-passphrase'):
        assert client.get(path).status_code == 200
        assert student_setup.username(_record(client)) == claiming["username"]
    student_verify_saved_username(client, 'not-it')
    body = client.get('/student/setup-pin-passphrase').get_data(as_text=True)
    assert claiming["username"] in body, "Show my username again must reveal the same username"


def test_verification_surface_never_contains_the_username(client, claiming):
    username = claiming["username"]
    assert username not in client.get('/student/verify-username').get_data(as_text=True)
    mismatch = student_verify_saved_username(client, username + 'x')
    assert username not in mismatch.get_data(as_text=True)
    # The modal on the setup page renders no copy of the username inside it.
    body = client.get('/student/setup-pin-passphrase').get_data(as_text=True)
    dialog = re.search(r'<dialog id="retention-check-dialog".*?</dialog>', body, re.S).group(0)
    assert username not in dialog


# ---------------------------------------------------------------- verification

def test_correct_username_unlocks_setup_and_the_account_signs_in(client, claiming):
    response = student_verify_saved_username(client)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert claiming["username"] not in body, "after the check the username need not be shown again"
    assert 'Username saved and checked' in body
    assert not re.search(r'<fieldset id="setup-fields"[^>]*\bdisabled\b', body)

    response = _finish(client, verify_username=False)
    assert response.status_code == 302 and 'setup-complete' in response.location
    assert _seat_claimed(claiming["seat_id"])
    assert 'student_setup_token' not in _session(client)

    client.get('/student/logout')
    with client.session_transaction() as sess:
        sess.clear()
    login = student_login(client, username=claiming["username"], passphrase=PASSPHRASE)
    assert login.status_code == 302 and '/student/login' not in login.location


def test_json_check_reports_match_and_mismatch_without_the_username(client, claiming):
    miss = student_verify_saved_username(client, 'wrong-guess-00', as_json=True)
    assert miss.status_code == 200
    assert miss.get_json() == {
        "verified": False,
        "message": "That doesn't match your username. Check the copy you saved and try again.",
    }
    hit = student_verify_saved_username(client, as_json=True)
    assert hit.get_json() == {"verified": True}


@pytest.mark.parametrize("variant", [
    lambda u: u.upper(),                 # usernames are case-sensitive
    lambda u: u[:-1],                    # one character short
    lambda u: u + u[-1],                 # one character long
    lambda u: u.replace('-', ' ', 1),    # internal punctuation is significant
    lambda u: '',                        # nothing typed
])
def test_wrong_username_never_passes(client, claiming, variant):
    response = student_verify_saved_username(client, variant(claiming["username"]))
    assert response.status_code == 200
    assert not _record(client)['verified_page']
    assert _finish(client, verify_username=False).location.endswith('/student/setup-pin-passphrase')
    assert not _seat_claimed(claiming["seat_id"])


def test_match_uses_login_normalization(client, claiming):
    """Surrounding whitespace is trimmed at sign-in, so it is trimmed here too."""
    response = student_verify_saved_username(client, f"  {claiming['username']}\t")
    assert response.status_code == 200
    assert _record(client)['verified_page']


def test_repeated_wrong_attempts_do_not_add_up_to_a_pass(client, claiming):
    for attempt in range(1, 8):
        response = student_verify_saved_username(client, f'guess-{attempt}')
        assert MISMATCH in response.get_data(as_text=True)
        assert _record(client)['attempts'] == attempt
    assert not _record(client)['verified_page']
    assert not _seat_claimed(claiming["seat_id"])
    # And a correct answer still works after them.
    assert student_verify_saved_username(client).status_code == 200


def test_submitting_setup_without_the_check_fails_closed(client, claiming):
    response = _finish(client, verify_username=False)
    assert response.status_code == 302
    assert response.location.endswith('/student/setup-pin-passphrase')
    assert not _seat_claimed(claiming["seat_id"])
    from app.hash_utils import hash_username_lookup
    assert User.query.filter_by(
        username_lookup_hash=hash_username_lookup(claiming["username"])).first() is None


def test_navigation_alone_never_marks_the_check_passed(client, claiming):
    for path in ('/student/verify-username', '/student/setup-pin-passphrase',
                 '/student/create-username', '/student/verify-username'):
        client.get(path)
    assert not _record(client)['verified_page']


def test_a_replaced_setup_cookie_cannot_replay_its_verification(client, claiming):
    student_verify_saved_username(client)
    old_cookie = client.get_cookie('session').value
    old_token = _session(client)['student_setup_token']
    response = client.post('/student/claim-account', data=dict(
        join_code=claiming['classroom'].join_code, first_name='Fresh', last_name='Claim'))
    assert response.location.endswith('/student/create-username')
    assert student_create_username(client, 'badger', follow_redirects=False).status_code == 302
    assert not _record(client)['verified_page']
    assert student_setup.client().get(student_setup._key(old_token)) is None
    client.set_cookie('session', old_cookie)
    assert _finish(client, verify_username=False).location.endswith('/student/claim-account')
    assert not _seat_claimed(claiming['seat_id'])


# ---------------------------------------------------------------- stability (SPEC-IDEN-001 §V)

def _generation(client):
    record = _record(client)
    return student_setup.username(record), record['generation']


def test_resubmitting_a_source_word_does_not_regenerate_the_username(client, claiming):
    """Refresh, navigation, attempts, both states and a pass keep the same username."""
    first = _generation(client)
    for step in (
        lambda: client.get('/student/setup-pin-passphrase'),
        lambda: client.get('/student/setup-pin-passphrase'),
        lambda: client.get('/student/verify-username'),
        lambda: client.get('/student/create-username'),
        lambda: student_verify_saved_username(client, 'wrong-guess'),
        lambda: student_verify_saved_username(client, 'wrong-guess', as_json=True),
        lambda: student_verify_saved_username(client),
        lambda: client.get('/student/setup-pin-passphrase'),
    ):
        step()
        assert _generation(client) == first
    # Replaying a create request in this setup session is not a new generation.
    student_create_username(client, 'badger', follow_redirects=False)
    second = _generation(client)
    assert second == first


def test_a_collision_does_not_itself_generate_a_username(client, claiming):
    taken = claiming["classroom"].students[1].username
    _replace_username(client, taken)
    student_verify_saved_username(client, taken)
    assert _finish(client, verify_username=False).location.endswith('/student/create-username')
    assert student_setup.username(_record(client)) == taken
    client.get('/student/create-username')
    assert student_setup.username(_record(client)) == taken


def test_the_proof_is_not_derived_from_the_username(client, claiming):
    student_verify_saved_username(client)
    from app.hash_utils import hash_username_lookup
    assert hash_username_lookup(claiming["username"]) not in str(_session(client))


def test_a_second_tab_cannot_use_another_tabs_verification(client, claiming):
    from bs4 import BeautifulSoup
    def new_tab():
        soup = BeautifulSoup(client.get('/student/setup-pin-passphrase').data, 'html.parser')
        return soup.select_one('[name="retention_page_token"]')['value']
    first, second = new_tab(), new_tab()
    assert first != second
    verified = client.post('/student/verify-username', data={
        'saved_username': claiming['username'], 'retention_page_token': first,
    }, headers={'Accept': 'application/json'})
    assert verified.json == {'verified': True}
    payload = {'pin': '4826', 'confirm_pin': '4826', 'passphrase': PASSPHRASE,
               'confirm_passphrase': PASSPHRASE, 'retention_page_token': second}
    denied = client.post('/student/setup-pin-passphrase', data=payload)
    assert denied.location.endswith('/student/setup-pin-passphrase')
    assert not _seat_claimed(claiming['seat_id'])
    payload['retention_page_token'] = first
    assert client.post('/student/setup-pin-passphrase', data=payload).location.endswith('/student/setup-complete')


def test_refresh_after_verification_requires_a_new_check(client, claiming):
    student_verify_saved_username(client)
    body = client.get('/student/setup-pin-passphrase').get_data(as_text=True)
    assert re.search(r'<fieldset id="setup-fields"[^>]*\bdisabled\b', body)


def test_a_missing_server_attempt_fails_closed(client, claiming):
    student_setup.discard(_session(client)['student_setup_token'])
    response = student_verify_saved_username(client)
    assert response.location.endswith('/student/claim-account')
    assert _finish(client, verify_username=False).location.endswith('/student/claim-account')
    assert not _seat_claimed(claiming['seat_id'])


def test_a_proof_from_another_setup_session_is_not_inherited(client, app, claiming):
    student_verify_saved_username(client)
    other = app.test_client()
    with other.session_transaction() as sess:
        sess['onboarding_seat_ref'] = claiming['seat_id']
        sess['onboarding_claim_generation'] = _session(client)['onboarding_claim_generation'] + 1
        sess['student_setup_token'] = _session(client)['student_setup_token']
    response = other.post('/student/setup-pin-passphrase', data={'pin': '4826', 'passphrase': PASSPHRASE})
    assert '/claim-account' in response.location
    assert not _seat_claimed(claiming['seat_id'])


def test_expired_setup_session_fails_closed_at_the_check(client, claiming):
    with client.session_transaction() as sess:
        sess['onboarding_claim_generation'] = sess['onboarding_claim_generation'] + 1
    response = student_verify_saved_username(client, claiming["username"])
    assert response.status_code == 302 and '/claim-account' in response.location
    assert not _record(client)['verified_page']
    json_response = student_verify_saved_username(client, claiming["username"], as_json=True)
    assert json_response.status_code == 409 and json_response.get_json()["verified"] is False


def test_collision_handling_is_unchanged_and_requires_a_fresh_check(client, claiming):
    taken = claiming["classroom"].students[1].username
    _replace_username(client, taken)
    student_verify_saved_username(client, taken)
    response = _finish(client, verify_username=False)
    assert response.location.endswith('/student/create-username')
    assert not _seat_claimed(claiming["seat_id"])
    student_create_username(client, 'heron', follow_redirects=False)
    assert not _record(client)['verified_page']
    assert _finish(client, verify_username=False).location.endswith('/student/setup-pin-passphrase')


# ---------------------------------------------------------------- privacy

def test_the_username_reaches_no_log_url_or_database_row(client, claiming, caplog):
    username = claiming["username"]
    caplog.set_level(logging.DEBUG)
    locations = []
    for response in (
        client.get('/student/verify-username'),
        student_verify_saved_username(client, 'wrong-guess'),
        student_verify_saved_username(client, username, as_json=True),
        student_verify_saved_username(client),
        _finish(client, verify_username=False),
    ):
        locations.append(response.headers.get('Location') or '')
    assert _seat_claimed(claiming["seat_id"])
    assert not [loc for loc in locations if username in loc]
    from app.hash_utils import hash_username_lookup
    forbidden = (username, hash_username_lookup(username))
    leaked = [record.getMessage() for record in caplog.records
              if any(value in record.getMessage() for value in forbidden)]
    assert leaked == [], leaked
    assert any('username_retention_check outcome=verified' in r.getMessage() for r in caplog.records)

    tables = db.session.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")).scalars().all()
    holding = [
        table for table in tables
        if db.session.execute(text(
            f'SELECT 1 FROM "{table}" AS r WHERE r::text LIKE :needle LIMIT 1'),
            {"needle": f"%{username}%"}).first()
    ]
    assert holding == [], f"plaintext username persisted in {holding}"


# ---------------------------------------------------------------- paste boundary

def test_paste_guard_is_scoped_to_the_check_input(client, claiming):
    setup = client.get('/student/setup-pin-passphrase').get_data(as_text=True)
    assert setup.count('data-retention-check-input') == 1
    assert 'id="saved-username"' in setup and '<label class="form-label text-secondary" for="saved-username">' in setup
    login = client.get('/student/login').get_data(as_text=True)
    assert 'data-retention-check-input' not in login
    assert 'username_retention_check.js' not in login


# ---------------------------------------------------------------- cookie privacy

def test_onboarding_cookie_holds_no_plaintext_username(client, claiming):
    import base64
    import json
    import zlib

    raw = client.get_cookie('session').value
    payload = raw.lstrip('.').split('.')[0]
    data = base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4))
    if raw.startswith('.'):
        data = zlib.decompress(data)
    assert claiming["username"] not in json.dumps(json.loads(data))


def test_expired_volatile_attempt_cannot_activate_even_with_a_saved_cookie(client, claiming):
    student_verify_saved_username(client)
    token = _session(client)['student_setup_token']
    student_setup.client().expire(student_setup._key(token), 0)
    assert _finish(client, verify_username=False).location.endswith('/student/claim-account')
    assert not _seat_claimed(claiming['seat_id'])


def test_setup_http_responses_do_not_cache_the_username(client, claiming):
    for path in ('/student/setup-pin-passphrase', '/student/verify-username'):
        response = client.get(path)
        assert 'no-store' in response.cache_control
        assert response.headers['Referrer-Policy'] == 'same-origin'
    assert client.get('/student/login').headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_empty_answer_revokes_an_earlier_proof(client, claiming):
    student_verify_saved_username(client)
    response = client.post('/student/verify-username', data={
        'retention_page_token': client.retention_page_token, 'saved_username': '',
    })
    assert response.status_code == 200
    assert _finish(client, verify_username=False).location.endswith('/student/setup-pin-passphrase')
    assert not _seat_claimed(claiming['seat_id'])


@pytest.mark.parametrize('invalidate', ['expire', 'change_username'])
def test_feat_rechecks_consumed_proof_before_activation(client, claiming, monkeypatch, invalidate):
    from app.feats import identity_feat
    real_activate = identity_feat.activate_student_credentials
    def interrupted_activation(**kwargs):
        if invalidate == 'expire':
            student_setup.discard(kwargs['setup_token'])
        else:
            kwargs['username'] = 'different-unverified-username'
        result = real_activate(**kwargs)
        assert not result.success and result.error_code == 'INVALID_SETUP_STATE'
        return result
    monkeypatch.setattr(identity_feat, 'activate_student_credentials', interrupted_activation)
    response = _finish(client)
    assert response.status_code == 302
    assert not _seat_claimed(claiming['seat_id'])


def test_https_csrf_protected_verification_and_completion(client, claiming, monkeypatch):
    """Exercise both production HTTPS POSTs with CSRF and strict referrer checks."""
    from app import app
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_SSL_STRICT', True)
    origin = 'https://localhost'
    page = client.get('/student/setup-pin-passphrase', base_url=origin)
    assert page.headers['Referrer-Policy'] == 'same-origin'
    html = BeautifulSoup(page.data, 'html.parser')
    token = html.select_one('[name="retention_page_token"]')['value']
    csrf = html.select_one('[name="csrf_token"]')['value']
    checked = client.post('/student/verify-username', base_url=origin,
        headers={'Referer': origin + '/student/setup-pin-passphrase'}, data={
            'csrf_token': csrf, 'retention_page_token': token,
            'saved_username': claiming['username']})
    assert checked.status_code == 200
    assert b'Username saved and checked' in checked.data
    csrf = BeautifulSoup(checked.data, 'html.parser').select_one('[name="csrf_token"]')['value']
    finished = client.post('/student/setup-pin-passphrase', base_url=origin,
        headers={'Referer': origin + '/student/verify-username'}, data={
            'csrf_token': csrf, 'retention_page_token': token,
            'pin': '4826', 'confirm_pin': '4826',
            'passphrase': PASSPHRASE, 'confirm_passphrase': PASSPHRASE})
    assert finished.status_code == 302 and finished.location.endswith('/student/setup-complete')
    assert _seat_claimed(claiming['seat_id'])


@pytest.mark.parametrize('referrer', [None, 'https://untrusted.example/'])
def test_https_verification_still_rejects_missing_or_foreign_referrer(client, claiming, monkeypatch, referrer):
    """The policy repair must preserve strict HTTPS CSRF rejection."""
    from app import app
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_SSL_STRICT', True)
    html = BeautifulSoup(client.get('/student/setup-pin-passphrase', base_url='https://localhost').data, 'html.parser')
    response = client.post('/student/verify-username', base_url='https://localhost',
        headers={'Referer': referrer} if referrer else {}, data={
            'csrf_token': html.select_one('[name="csrf_token"]')['value'],
            'retention_page_token': html.select_one('[name="retention_page_token"]')['value'],
            'saved_username': claiming['username']})
    assert response.status_code == 400
    assert not _record(client)['verified_page']

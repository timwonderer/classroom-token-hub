"""Turnstile ingress coverage: student claim, teacher account creation
(signup steps 2/3), teacher account recovery, and student account
recovery.

Per operator direction (2026-09-23): Turnstile must sit on every
unauthenticated ingress that resolves guessable/enumerable data --
join_code+name, username availability, reset codes, join_code+username
pairs -- not just the two routes (student login, signup step 1) that
already had it. Two of those two were themselves found half-wired:
admin_signup.html/admin_signup_totp.html already received a
turnstile_site_key in some render calls with no macro import to render it
and no server-side check at all (the same "matches-nothing" shape this
project keeps finding elsewhere).

Existing tests across the suite (test_teacher_signup_staging.py,
test_canonical_auth_session.py, test_login_redirect.py) monkeypatch
verify_turnstile_token to True purely to get past the existing gates --
none of them assert the FALSE path actually blocks anything. These do,
for every new gate, by checking the underlying state never changed, not
just that a flash message appeared.

Amended 2026-09-23: three more gaps found by an explicit sweep (not just
the four flows named above) -- teacher login (/admin/login, widget was
rendering via the global turnstile_site_key context processor but nothing
ever verified it server-side), teacher resume-credentials (a bare 6-digit
PIN with no session precondition -- no widget and no server check at
all), and public hall-pass verification (/verify/hallpass/<token> resolves
a (join_code, first_name, last_name) match against a real roster -- no
widget and no server check, even though the URL token itself is
non-enumerable by design).
"""
from __future__ import annotations

from types import SimpleNamespace

import pyotp

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.teacher_signup_feat import read_signup
from app.models import Seat, TeacherSignupAttempt, User
from tests.dom.identity.helpers import admin_generate_recovery_code, student_lookup_recovery_code
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def test_student_claim_blocked_without_turnstile(client, monkeypatch):
    """/student/claim-account must not bind a seat when Turnstile fails."""
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    upload = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'New', 'last_name': 'Student'},
    ]})
    assert upload.status_code == 200 and upload.json['created'] == 1
    claimed_before = Seat.query.filter(
        Seat.class_id == classroom.class_id, Seat.user_id.isnot(None),
    ).count()

    monkeypatch.setattr('app.routes.student.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/student/claim-account', data={
        'join_code': classroom.join_code,
        'first_name': 'New',
        'last_name': 'Student',
        'dedupe_code': '',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    assert Seat.query.filter(
        Seat.class_id == classroom.class_id, Seat.user_id.isnot(None),
    ).count() == claimed_before

    # Sanity: the same request succeeds once Turnstile passes, proving the
    # fixture itself (join_code/name/unclaimed seat) was valid all along.
    monkeypatch.setattr('app.routes.student.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/student/claim-account', data={
        'join_code': classroom.join_code,
        'first_name': 'New',
        'last_name': 'Student',
        'dedupe_code': '',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/student/create-username')


def _drive_signup_step1(client, monkeypatch):
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/admin/signup', data=dict(
        signup_step='class_setup', class_display_name='Turnstile Test',
        section='Period Z', first_name='Turn', last_name='Stile',
        class_timezone='America/Los_Angeles', tos_agreed='true',
    ))
    assert response.status_code == 200
    with client.session_transaction() as sess:
        return sess['teacher_signup_nonce']


def test_signup_step2_username_blocked_without_turnstile(client, monkeypatch):
    """Step 1's Turnstile pass must not license unlimited step-2 attempts."""
    nonce = _drive_signup_step1(client, monkeypatch)

    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/admin/signup', data={'username': 'turnstile_teacher'})

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    assert b"Set Up Your Authenticator" not in response.data
    # prepare_totp() was never reached: the staged payload carries no secret.
    payload = read_signup(nonce)
    assert payload is not None and payload.get('totp_secret') is None
    assert User.query.count() == 0

    # Confirm the fixture is otherwise valid: passing Turnstile now advances
    # to the TOTP screen as normal.
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/admin/signup', data={'username': 'turnstile_teacher'})
    assert response.status_code == 200
    assert b"Set Up Your Authenticator" in response.data


def test_signup_step3_totp_blocked_without_turnstile(client, monkeypatch):
    """The actual account-creation commit must not fire when Turnstile fails,
    even with an otherwise-correct TOTP code.
    """
    nonce = _drive_signup_step1(client, monkeypatch)
    response = client.post('/admin/signup', data={'username': 'turnstile_teacher2'})
    assert response.status_code == 200
    payload = read_signup(nonce)
    secret = payload['totp_secret']

    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/admin/signup', data=dict(
        username='turnstile_teacher2', totp_code=pyotp.TOTP(secret).now(), tos_agreed='true',
    ))

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    assert User.query.count() == 0
    assert TeacherSignupAttempt.query.count() == 1  # staged attempt survives, not consumed

    # A correct TOTP with Turnstile passing now completes the account.
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/admin/signup', data=dict(
        username='turnstile_teacher2', totp_code=pyotp.TOTP(secret).now(), tos_agreed='true',
    ))
    assert response.status_code == 302 and response.location.endswith('/admin/login')
    assert User.query.count() == 1


def test_teacher_recovery_begin_blocked_without_turnstile(client, monkeypatch):
    """/admin/recover must not open a recovery attempt when Turnstile fails."""
    from app.models import RecoveryRequest

    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/admin/recover', data={
        'join_code[]': ['ABC123'], 'student_username[]': ['someone'],
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    assert RecoveryRequest.query.count() == 0


def test_student_recovery_lookup_blocked_without_turnstile(client, monkeypatch):
    """/recovery/lookup must not accept a reset code when Turnstile fails."""
    classroom = initialize('chemistry_p1', client.application)
    teacher = classroom.teacher_user
    teacher_seat = classroom.teacher_seat
    student_seat = classroom.students[0].seat

    with client.session_transaction() as sess:
        set_canonical_context(
            sess, user_id=teacher.id, class_id=classroom.class_id,
            seat_id=teacher_seat.id, role="admin",
        )
    admin_generate_recovery_code(client, student_seat.id)
    db.session.refresh(student_seat)
    linked_user = db.session.get(User, student_seat.user_id)
    reset_code = linked_user.reset_code
    assert reset_code

    with client.session_transaction() as sess:
        sess.clear()  # student is unauthenticated at this entry point

    monkeypatch.setattr('app.routes.recovery.verify_turnstile_token', lambda *a, **k: False)
    response = student_lookup_recovery_code(client, reset_code, follow_redirects=True)

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    db.session.refresh(linked_user)
    assert linked_user.reset_code == reset_code  # code was never consumed

    monkeypatch.setattr('app.routes.recovery.verify_turnstile_token', lambda *a, **k: True)
    response = student_lookup_recovery_code(client, reset_code, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/student/create-username')


def test_admin_login_blocked_without_turnstile(client, monkeypatch):
    """/admin/login must not establish a session when Turnstile fails, even
    with an otherwise-correct username and TOTP code. The widget was already
    rendering here (via the global turnstile_site_key context processor);
    nothing was ever verifying it server-side.
    """
    class _DummyField:
        def __init__(self, data):
            self.data = data

        def __call__(self, **_kw):
            return ""

    classroom = initialize("chemistry_p1", client.application)
    form = SimpleNamespace(
        validate_on_submit=lambda: True,
        username=_DummyField("teacher.alice"),
        totp_code=_DummyField("123456"),
        hidden_tag=lambda: "",
        submit=_DummyField(None),
    )
    monkeypatch.setattr("app.routes.admin.AdminLoginForm", lambda: form)
    monkeypatch.setattr(
        "app.routes.admin.find_canonical_user_by_auth_username",
        lambda *_args, **_kwargs: classroom.teacher_user,
    )
    monkeypatch.setattr("app.routes.admin.decrypt_totp", lambda _value: "secret")
    monkeypatch.setattr(
        "app.routes.admin.pyotp.TOTP",
        lambda _secret: SimpleNamespace(verify=lambda *_args, **_kwargs: True),
    )

    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/admin/login', follow_redirects=True)

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

    # Confirm the fixture is otherwise valid: passing Turnstile now logs in.
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/admin/login', follow_redirects=False)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get('user_id') == classroom.teacher_user.id


def test_resume_credentials_blocked_without_turnstile(client, monkeypatch):
    """/admin/resume-credentials must never call resume_attempt (the
    single most guessable secret on the recovery surface -- a bare 6-digit
    PIN with no session precondition) when Turnstile fails.
    """
    def _resume_attempt_must_not_be_called(**_kwargs):
        raise AssertionError("resume_attempt() must not run when Turnstile fails")

    monkeypatch.setattr(
        'app.feats.teacher_recovery_feat.resume_attempt',
        _resume_attempt_must_not_be_called,
    )
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: False)
    response = client.post('/admin/resume-credentials', data={'resume_pin': '123456'})

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    with client.session_transaction() as sess:
        assert 'recovery_request_id' not in sess

    # Confirm the fixture is otherwise valid: passing Turnstile now reaches
    # resume_attempt (which fails on this fake PIN for an unrelated reason --
    # the point is only that it was called at all, which the False path proved
    # it wasn't).
    monkeypatch.setattr(
        'app.feats.teacher_recovery_feat.resume_attempt',
        lambda **kwargs: {'id': 1, 'nonce': 'test-nonce'},
    )
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a, **k: True)
    response = client.post('/admin/resume-credentials', data={'resume_pin': '123456'}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/recovery-status')
    with client.session_transaction() as sess:
        assert sess.get('recovery_request_id') == 1


def test_hall_pass_verify_blocked_without_turnstile(client, monkeypatch):
    """/verify/hallpass/<token> must not run the (join_code, name) match
    when Turnstile fails, even though the token itself is non-enumerable.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    teacher = classroom.teacher_user
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"hp-token:{teacher.id}"):
        teacher.hall_pass_verify_token = "test-verify-token-12345"
        db.session.flush()

    with client.session_transaction() as sess:
        sess.clear()  # public, unauthenticated entry point

    monkeypatch.setattr('app.routes.main.verify_turnstile_token', lambda *a, **k: False)
    response = client.post(
        f'/verify/hallpass/{teacher.hall_pass_verify_token}',
        data={'join_code': classroom.join_code, 'first_name': 'Anyone', 'last_name': 'Atall'},
    )

    assert response.status_code == 200
    assert b"Security verification failed" in response.data
    # The real matching outcomes ("No hall pass record found", a name/status
    # table) must not appear -- proving the match logic never ran.
    assert b"No hall pass record found" not in response.data

    monkeypatch.setattr('app.routes.main.verify_turnstile_token', lambda *a, **k: True)
    response = client.post(
        f'/verify/hallpass/{teacher.hall_pass_verify_token}',
        data={'join_code': classroom.join_code, 'first_name': 'Anyone', 'last_name': 'Atall'},
    )
    assert response.status_code == 200
    assert b"Security verification failed" not in response.data
    # No such student exists, so real matching logic correctly reaches
    # "no match" -- proving Turnstile passing lets real logic execute.
    assert b"No hall pass record found" in response.data

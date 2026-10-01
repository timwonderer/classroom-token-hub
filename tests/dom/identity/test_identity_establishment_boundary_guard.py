"""Every entry into identity establishment is behind the signed-in refusal.

The refusal (DOM-IDEN-005 §VII, operator ruling 2026-10-01) is one gate keyed on
``IDENTITY_ESTABLISHMENT_ENDPOINTS``. A route added later that reads the
onboarding session, the setup store, or the claim/credential commands, but is
missing from that declaration, would reopen OPS-DB-001 with every existing test
still green. This guard makes the declaration complete by construction.

Structural guard, so it ships with its mutation proofs (SOP-TEST-003 §IX.A).
"""
from __future__ import annotations

import inspect
import pathlib
import textwrap

from app import app
from app.routes.identity_establishment import IDENTITY_ESTABLISHMENT_ENDPOINTS
from tests.guards.identity_establishment_detector import (
    establishment_touches,
    undeclared_establishment_endpoints,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _app_sources() -> dict[str, str]:
    sources = {}
    for path in (REPO_ROOT / 'app').rglob('*.py'):
        module = '.'.join(path.relative_to(REPO_ROOT).with_suffix('').parts)
        sources[module.removesuffix('.__init__')] = path.read_text(encoding='utf-8')
    return sources


def _views() -> dict[str, tuple[str, str]]:
    views = {}
    for endpoint, function in app.view_functions.items():
        function = inspect.unwrap(function)
        views[endpoint] = (function.__module__, function.__name__)
    return views


def test_every_view_touching_establishment_state_is_declared():
    assert undeclared_establishment_endpoints(
        _app_sources(), _views(), IDENTITY_ESTABLISHMENT_ENDPOINTS) == []


def test_every_declared_endpoint_exists():
    assert IDENTITY_ESTABLISHMENT_ENDPOINTS <= set(app.view_functions)


def test_the_gate_is_registered_on_the_app():
    from app.routes.identity_establishment import refuse_authenticated_identity_establishment
    assert refuse_authenticated_identity_establishment in app.before_request_funcs[None]


def test_detector_still_finds_the_real_workflow():
    """A rename of the keys, the store or the commands must not silently empty the guard."""
    touched = establishment_touches(_app_sources())
    views = _views()
    for endpoint in ('student.claim_account', 'student.create_username', 'student.verify_saved_username',
                     'student.setup_pin_passphrase', 'recovery.account_lookup'):
        assert views[endpoint] in touched, endpoint


def test_lawful_discards_are_quiet():
    """Sign-in, sign-out, unclaim and deletion clear establishment state; that is not entry."""
    touched = establishment_touches(_app_sources())
    views = _views()
    for endpoint in ('student.login', 'student.logout', 'student.setup_complete', 'student.add_class',
                     'admin.unclaim_student', 'admin.login', 'admin.logout'):
        if endpoint in views:
            assert views[endpoint] not in touched, (endpoint, touched.get(views[endpoint]))


# ------------------------------------------------------------- mutation proofs

_NEAR_MISS = textwrap.dedent('''
    from flask import session
    from app.routes.student import _get_credential_setup_state, _setup_record

    @student_bp.route('/resume-setup')
    def resume_setup():
        seat, user = _get_credential_setup_state()
        token, binding, record = _setup_record(seat, user)
        return render_template('student_pin_setup.html', username=None)

    @student_bp.route('/setup-progress')
    def setup_progress():
        return jsonify(started=session.get('onboarding_seat_ref') is not None)

    SEAT_REF = 'onboarding_seat_ref'

    @student_bp.route('/setup-progress-v2')
    def setup_progress_v2():
        return jsonify(started=SEAT_REF in session)

    @student_bp.route('/quick-claim', methods=['POST'])
    def quick_claim():
        from app.feats.identity_feat import resolve_seat_claim
        return jsonify(ok=resolve_seat_claim(join_code='', first_name='', last_name='').success)

    @student_bp.route('/setup-peek')
    def setup_peek():
        from app.services import student_setup
        return jsonify(alive=bool(student_setup.read(session.get('x'), None)))

    @student_bp.route('/sign-out-everywhere')
    def sign_out_everywhere():
        session.pop('onboarding_seat_ref', None)
        session.pop('student_setup_token', None)
        from app.services import student_setup
        student_setup.discard(None)
        return redirect('/')
''')

_NEAR_MISS_VIEWS = {
    'student.resume_setup': ('app.routes.experimental', 'resume_setup'),
    'student.setup_progress': ('app.routes.experimental', 'setup_progress'),
    'student.setup_progress_v2': ('app.routes.experimental', 'setup_progress_v2'),
    'student.quick_claim': ('app.routes.experimental', 'quick_claim'),
    'student.setup_peek': ('app.routes.experimental', 'setup_peek'),
    'student.sign_out_everywhere': ('app.routes.experimental', 'sign_out_everywhere'),
}


def test_mutation__undeclared_routes_reaching_setup_state_are_reported():
    sources = _app_sources()
    sources['app.routes.experimental'] = _NEAR_MISS
    offenders = undeclared_establishment_endpoints(sources, _NEAR_MISS_VIEWS, IDENTITY_ESTABLISHMENT_ENDPOINTS)
    flagged = {line.split(' ')[0] for line in offenders}
    # Through a helper in another module, a direct key read, a key held in a
    # module constant, the claim command, and the setup store.
    assert flagged == {'student.resume_setup', 'student.setup_progress', 'student.setup_progress_v2',
                       'student.quick_claim', 'student.setup_peek'}
    # Discarding state is lawful anywhere.
    assert 'student.sign_out_everywhere' not in flagged


def test_mutation__dropping_an_endpoint_from_the_declaration_is_reported():
    for endpoint in ('student.setup_pin_passphrase', 'recovery.account_lookup'):
        offenders = undeclared_establishment_endpoints(
            _app_sources(), _views(), IDENTITY_ESTABLISHMENT_ENDPOINTS - {endpoint})
        assert [line.split(' ')[0] for line in offenders] == [endpoint]

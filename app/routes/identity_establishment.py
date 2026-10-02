"""The unauthenticated identity-establishment workflow and its one boundary.

Claim (FEAT-IDEN-001), credential setup (FEAT-IDEN-002) and recovery setup
(FEAT-IDEN-004) establish an identity for someone who cannot sign in. Their
correctness premise is DOM-IDEN-005 §VII: the workflow provisions a new User
"because no authenticated principal exists". A browser session that names a
principal falsifies that premise, so the workflow requires its absence
(operator ruling 2026-10-01, incident OPS-DB-001).

The rule is categorical. It does not ask whether the signed-in principal
belongs to the class, owns the seat, or is the same person: CTH knows only that
the session represents someone, and infers nothing about the humans.

The workflow is declared here, once, and enforced by a single app-level
``before_request`` gate keyed on ``request.endpoint``. A route joins the
workflow by being listed, never by repeating a check. The structural guard in
``tests/dom/identity/test_identity_establishment_boundary_guard.py`` fails any
view that touches establishment state (the setup store, FEAT-IDEN-001/002
commands, the onboarding session keys) without being listed here.

``student.setup_complete`` is deliberately absent. It is the first page of the
authenticated runtime: ``login_required`` sends a just-set-up student to sign
in, and the sign-in returns them there. It reads no establishment state.
"""
from __future__ import annotations

from flask import jsonify, render_template, request, session, url_for

IDENTITY_ESTABLISHMENT_ENDPOINTS = frozenset({
    'student.claim_account',
    'student.create_username',
    'student.verify_saved_username',
    'student.setup_pin_passphrase',
    'recovery.landing',
    'recovery.account_lookup',
})

REFUSAL_HEADING = "We are having trouble determining who you are right now."
REFUSAL_CANCELLED = "For your protection, this request was cancelled."
SIGNED_IN_MESSAGE = f"{REFUSAL_HEADING} {REFUSAL_CANCELLED}"

# "Return to login" must end the sign-in that caused the refusal, or the next
# attempt is refused again. Each role's logout clears it and lands on that
# role's login page.
_SIGN_OUT_ENDPOINTS = {
    'student': 'student.logout',
    'teacher': 'admin.logout',
    'sysadmin': 'sysadmin.logout',
}


def _signed_in_user():
    """The principal this request's session names, as the boundary validated it.

    ``validate_canonical_session_nonce`` runs earlier in the same request and
    clears any session whose user is gone or whose nonce was rotated, so a
    revoked session reaches here naming nobody. Principal existence is step 1
    of DOM-IDEN-006 §VIII (the authenticated ``user_id``), not a full class
    context: a sysadmin, a classless teacher, or a student still choosing a
    class has no ``g.canonical_context`` yet is signed in all the same. No
    resolver call is added; the User row is already in the session identity
    map from the nonce check.
    """
    from app import db
    from app.models import User
    from app.utils.user_ids import session_user_id

    user_id = session_user_id(session)
    return db.session.get(User, user_id) if user_id is not None else None


def refuse_authenticated_identity_establishment():
    """Refuse every entry into the workflow while a principal is signed in.

    Runs before the view, so before Turnstile, seat resolution, any row lock
    and any setup-store write. It writes nothing: no session key, no flash.
    """
    if request.endpoint not in IDENTITY_ESTABLISHMENT_ENDPOINTS:
        return None
    user = _signed_in_user()
    if user is None:
        return None

    status = 200 if request.method in ('GET', 'HEAD') else 409
    role = getattr(user.user_role, 'value', user.user_role)
    return_to_login_url = url_for(_SIGN_OUT_ENDPOINTS.get(role, 'student.logout'))
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(verified=False, message=SIGNED_IN_MESSAGE, redirect=return_to_login_url), 409
    return render_template(
        'identity_establishment_signed_in.html',
        heading=REFUSAL_HEADING,
        cancelled=REFUSAL_CANCELLED,
        return_to_login_url=return_to_login_url,
    ), status

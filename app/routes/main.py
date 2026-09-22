"""
Main routes for Classroom Token Hub.

Contains public-facing utility routes including health checks, legal pages,
debug endpoints, and public hall pass verification.
"""

from app.hash_utils import normalize_lookup_text
from datetime import datetime, timezone
from types import SimpleNamespace
from flask import (
    Blueprint, redirect, url_for, jsonify, current_app,
    session, request,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, limiter
from app.models import User, UserRole
from app.utils.helpers import render_template_with_fallback as render_template, safe_redirect_target
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

# Create blueprint
main_bp = Blueprint('main', __name__)


def _marketing_site_redirect(page_filename: str = ''):
    """Redirect to a page on the published marketing site.

    The application does not serve that site. It is published from
    ``github-pages/`` to GitHub Pages and answers on its own host, so every
    marketing URL the app emits is an absolute redirect off this origin.
    """
    marketing_url = current_app.config['MARKETING_SITE_URL'].rstrip('/')
    return redirect(f"{marketing_url}/{page_filename}" if page_filename else marketing_url)


# -------------------- HOME AND LEGAL PAGES --------------------

@main_bp.route('/')
def home():
    """
    Smart root route:
    - If logged in as student -> Student Dashboard
    - If logged in as system admin -> admin dashboard
    - If logged in as sysadmin -> Sysadmin Dashboard
    - If not logged in -> Redirect to Marketing Site (classroomtokenhub.com)
    """
    # Check for user session and redirect accordingly
    from app.auth import get_current_user

    user = get_current_user()
    if user:
        role = getattr(user.user_role, "value", user.user_role)
        if role == 'sysadmin':
            return redirect(url_for('sysadmin.dashboard'))
        elif role == 'teacher':
            return redirect(url_for('admin.dashboard'))
        elif role == 'student':
            return redirect(url_for('student.dashboard'))
    else:
        return _marketing_site_redirect()


@main_bp.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.scalar(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        current_app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500


@main_bp.route('/health/status')
def health_status():
    """Return bounded capability and platform signals for status publication.

    Exactly one check is executed: `SELECT 1`, reported as the `database`
    platform signal (PASS/KNOWN or FAIL/UNAVAILABLE).

    Every other signal — the `login`, `attendance`, `payroll`, `roster` and
    `classroom_economy` capabilities, and the `background_jobs`,
    `external_integrations`, `monitoring_freshness` and
    `invariant_verification` platform signals — is emitted as
    UNKNOWN/UNAVAILABLE with `CHECK_NOT_REGISTERED`. That is the contract, not
    a gap: a capability reports UNKNOWN until a lawful read-only probe is
    registered for it, so the endpoint can never imply health it has not
    observed (INV-ARC-017: executed evidence is not the same as inferred
    coverage).

    This endpoint intentionally exposes no table counts, tenant data, raw
    errors, or internal diagnostics.
    """
    signals = []

    try:
        db.session.scalar(text('SELECT 1'))
        signals.append({"key": "database", "layer": "platform", "outcome": "PASS", "epistemic_state": "KNOWN", "diagnostic_code": "DATABASE_REACHABLE", "checked_at": datetime.now(timezone.utc).isoformat()})
    except SQLAlchemyError:
        signals.append({"key": "database", "layer": "platform", "outcome": "FAIL", "epistemic_state": "UNAVAILABLE", "diagnostic_code": "DATABASE_UNAVAILABLE", "checked_at": datetime.now(timezone.utc).isoformat()})
    for key in ("login", "attendance", "payroll", "roster", "classroom_economy"):
        signals.append({"key": key, "layer": "capability", "outcome": "UNKNOWN", "epistemic_state": "UNAVAILABLE", "diagnostic_code": "CHECK_NOT_REGISTERED", "checked_at": None})
    for key in ("background_jobs", "external_integrations", "monitoring_freshness", "invariant_verification"):
        signals.append({"key": key, "layer": "platform", "outcome": "UNKNOWN", "epistemic_state": "UNAVAILABLE", "diagnostic_code": "CHECK_NOT_REGISTERED", "checked_at": None})
    return jsonify({"observed_at": datetime.now(timezone.utc).isoformat(), "signals": signals}), 200


@main_bp.route('/privacy')
def privacy():
    """Redirect to the hosted Privacy & Data Handling Policy page."""
    return _marketing_site_redirect('privacy.html')


@main_bp.route('/terms')
def terms():
    """Redirect to the hosted Terms of Service page."""
    return _marketing_site_redirect('terms.html')


@main_bp.route('/district')
def district():
    """Redirect to the hosted district assurance brief page."""
    return _marketing_site_redirect('district.html')


@main_bp.route('/offline')
def offline():
    """Render the offline fallback page."""
    return render_template('offline.html')


@main_bp.route('/sw.js')
@limiter.exempt
def service_worker():
    """Serve the service worker file from the root scope.

    Exempt from rate limiting because browsers check this frequently
    for PWA updates and it's a static file that doesn't need protection.
    """
    return current_app.send_static_file('sw.js')


# -------------------- HALL PASS PUBLIC VERIFICATION (NO AUTH REQUIRED) --------------------

def _normalize_first_name(value):
    """Normalize first name: strip, NFKC, lowercase."""
    if not value:
        return ''
    return normalize_lookup_text(value, kind="name")


def _normalize_last_name(value):
    """Normalize last name: strip, NFKC, lowercase."""
    if not value:
        return ''
    return normalize_lookup_text(value, kind="name")


@main_bp.route('/verify/hallpass/<teacher_public_token>', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def verify_hall_pass(teacher_public_token):
    """
    External, capability-authorized hall-pass verification for office staff.

    Name comparison finds same-day entries within a resolved class; it does not
    resolve an economic actor or establish application authority.

    GET:  Show a form with class dropdown, first name, last name fields.
    POST: Verify whether a specific student has a valid hall pass for today.

    Designed per Hall Pass Public Verification Spec v1.0:
    - Reveals no roster
    - Reveals no multi-day history
    - Reveals no internal identifiers
    - Non-enumerable (token-based)
    - Rotatable
    """
    from app.models import AttendanceReasonCode, AttendanceSession, HallPassLog
    from app.services.class_configuration_query_service import get_all_classes_by_teacher, get_class_economy_by_join_code
    from app.services.identity_service import match_hall_pass_profiles
    from app.services.hall_pass_status_service import resolve_hall_pass_lifecycle_status

    _GENERIC_UNAVAILABLE = "Verification page not available."

    teacher_user = User.query.filter_by(hall_pass_verify_token=teacher_public_token).first()

    if not teacher_user:
        return render_template(
            'hall_pass_verify.html',
            unavailable=True,
            message=_GENERIC_UNAVAILABLE
        ), 404

    # SANCTIONED cross-class exception (INV-ARC-004 V.3): the hall-pass
    # verification page is the ONLY runtime surface allowed to span a teacher's
    # classes. It is token-authorized and read-only; the POST resolves the supplied join code to class_id
    # before reading profiles or activity in that class.
    classes_rows = sorted(get_all_classes_by_teacher(teacher_user.id), key=lambda c: (c.display_name or ""))
    def _class_display_label(class_row):
        label_parts = [part for part in (class_row.section, class_row.display_name) if part]
        return " - ".join(label_parts) if label_parts else class_row.join_code

    classes = []
    for c in classes_rows:
        classes.append({
            "join_code": c.join_code,
            "label": _class_display_label(c),
        })

    if request.method == 'GET':
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result=None
        )

    # ---- POST: verification attempt ----
    raw_first_name = request.form.get('first_name', '')
    raw_last_name = request.form.get('last_name', '')
    selected_join_code = request.form.get('join_code', '').strip().upper()

    first_name_norm = _normalize_first_name(raw_first_name)
    last_name_norm = _normalize_last_name(raw_last_name)

    # Reject malformed input uniformly
    if not first_name_norm or not last_name_norm or not selected_join_code:
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result={'outcome': 'no_match'}
        )

    selected_class_row = get_class_economy_by_join_code(selected_join_code)
    if not selected_class_row or selected_class_row.teacher_user_id != teacher_user.id:
        return render_template(
            'hall_pass_verify.html', unavailable=False, token=teacher_public_token,
            classes=classes, result={'outcome': 'no_match'},
        )
    selected_class_id = selected_class_row.class_id
    profiles = match_hall_pass_profiles(
        class_id=selected_class_id, first_name=raw_first_name, last_name=raw_last_name,
    )
    if len(profiles) != 1:
        return render_template(
            'hall_pass_verify.html', unavailable=False, token=teacher_public_token,
            classes=classes, result={'outcome': 'ambiguous' if profiles else 'no_match'},
        )
    matched_profile = profiles[0]

    public_temporal_context = SimpleNamespace(class_id=selected_class_id)
    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=public_temporal_context,
        primitive="evaluation_day_boundaries",
    )
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=public_temporal_context,
        primitive="current_time",
    )

    # Query today's hall pass records for this class scope.
    passes_query = HallPassLog.query.filter(
        HallPassLog.class_id == selected_class_id,
        HallPassLog.timestamp >= day_bounds.boundary_start_utc,
        HallPassLog.timestamp < day_bounds.boundary_end_utc,
    ).order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc())

    matched = passes_query.filter(
        HallPassLog.requested_by_seat_id == matched_profile["seat_id"]
    ).limit(2).all()

    if len(matched) == 0:
        result = {'outcome': 'no_match'}
    elif len(matched) > 1:
        result = {'outcome': 'ambiguous'}
    else:
        entry = matched[0]
        class_label = _class_display_label(selected_class_row)
        lifecycle = resolve_hall_pass_lifecycle_status(
            class_id=entry.class_id,
            seat_id=entry.requested_by_seat_id,
            hall_pass_id=entry.hall_pass_id,
            day_boundary_start_utc=day_bounds.boundary_start_utc,
            day_boundary_end_utc=day_bounds.boundary_end_utc,
        )
        left_row = lifecycle.left_row
        return_row = lifecycle.return_row
        status = lifecycle.status
        time_out_value = None
        elapsed_mins = None
        if left_row:
            time_out_value = left_row.timestamp
            if status == "left":
                elapsed = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=public_temporal_context,
                    primitive="time_since",
                    reference_time_utc=now_evaluation.canonical_now_utc,
                    start=left_row.timestamp,
                )
                elapsed_mins = elapsed.elapsed_seconds // 60

        return_time_value = None
        if return_row:
            return_time_value = return_row.timestamp

        result = {
            'outcome': 'match',
            'student_display': matched_profile['display_name'],
            'class_label': class_label,
            'destination': entry.destination,
            'time_out': time_out_value,
            'status': status,
            'elapsed_mins': elapsed_mins,
            'return_time': return_time_value,
        }

    return render_template(
        'hall_pass_verify.html',
        unavailable=False,
        token=teacher_public_token,
        classes=classes,
        result=result
    )


@main_bp.route('/switch-view')
def switch_view():
    """Switches the view between mobile and desktop."""
    view = request.args.get('view', 'mobile')
    next_url = request.args.get('next', url_for('main.home'))

    if view == 'desktop':
        session['force_desktop'] = True
    else:
        session.pop('force_desktop', None)

    return redirect(safe_redirect_target(next_url, url_for('main.home')))

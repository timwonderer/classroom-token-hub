"""
Main routes for Classroom Token Hub.

Contains public-facing utility routes including health checks, legal pages,
debug endpoints, and public hall pass verification.
"""

import unicodedata
from datetime import timezone

from flask import Blueprint, redirect, url_for, jsonify, current_app, session, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, limiter
from app.models import Admin
from app.utils.helpers import render_template_with_fallback as render_template, is_safe_url
from app.utils.time import utc_now, ensure_utc, normalize_for_db, get_timezone

# Create blueprint
main_bp = Blueprint('main', __name__)


# -------------------- HOME AND LEGAL PAGES --------------------

@main_bp.route('/')
def home():
    """
    Smart root route:
    - If logged in as student -> Student Dashboard
    - If logged in as admin -> Admin Dashboard
    - If logged in as sysadmin -> Sysadmin Dashboard
    - If not logged in -> Redirect to Marketing Site (classroomtokenhub.com)
    """
    # Check for user session and redirect accordingly
    if session.get('is_system_admin') and session.get('sysadmin_id'):
        return redirect(url_for('sysadmin.dashboard'))
    elif session.get('is_admin') and session.get('admin_id'):
        return redirect(url_for('admin.dashboard'))
    elif session.get('student_id'):
        return redirect(url_for('student.dashboard'))
    else:
        # Default: Redirect to marketing site
        # Use environment variable or default to the canonical domain
        marketing_url = current_app.config.get('MARKETING_SITE_URL', 'https://classroomtokenhub.com')
        return redirect(marketing_url)


@main_bp.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        current_app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500


@main_bp.route('/health/deep')
def health_check_deep():
    """
    Extended health check that validates critical system components.

    Checks:
    - Database connectivity
    - Student table accessibility
    - Admin table accessibility
    - Hall passes table accessibility (if accessible)

    Returns JSON with component status for detailed monitoring.
    Individual table checks that fail are logged but don't fail the entire check.
    """
    checks = {}
    overall_status = 'ok'

    # Check database connectivity
    try:
        db.session.execute(text('SELECT 1'))
        checks['database'] = 'connected'
    except SQLAlchemyError as e:
        current_app.logger.exception('Database connectivity check failed')
        checks['database'] = 'error'
        overall_status = 'degraded'

    # Check if student table is accessible
    try:
        student_count = db.session.execute(
            text('SELECT COUNT(*) FROM students')
        ).scalar()
        checks['students_table'] = 'accessible'
        checks['student_count'] = student_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Students table check failed: %s', str(e))
        checks['students_table'] = 'error'
        overall_status = 'degraded'

    # Check if admin table is accessible
    try:
        admin_count = db.session.execute(
            text('SELECT COUNT(*) FROM teachers')
        ).scalar()
        checks['admins_table'] = 'accessible'
        checks['admin_count'] = admin_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Admins table check failed: %s', str(e))
        checks['admins_table'] = 'error'
        overall_status = 'degraded'

    # Check if hall pass logs table is accessible (may fail due to RLS/tenant context)
    try:
        hall_pass_count = db.session.execute(
            text('SELECT COUNT(*) FROM hall_pass_logs')
        ).scalar()
        checks['hall_pass_logs_table'] = 'accessible'
        checks['hall_pass_count'] = hall_pass_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Hall pass logs table check failed: %s', str(e))
        checks['hall_pass_logs_table'] = 'not_accessible'
        # Don't mark as degraded - this might be expected due to RLS

    # Return 200 if at least database is working, 500 if database is down
    if checks.get('database') == 'connected':
        return jsonify({
            'status': overall_status,
            'checks': checks
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'error': 'Database connectivity failed',
            'checks': checks
        }), 500


@main_bp.route('/privacy')
def privacy():
    """Render the Privacy & Data Handling Policy page."""
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    """Render the Terms of Service page."""
    return render_template('tos.html')


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

def _get_school_timezone():
    """Return the configured school timezone or fall back to Pacific Time."""
    return get_timezone(current_app.config.get('DEFAULT_TIMEZONE'))


def _normalize_first_name(value):
    """Normalize first name: strip, NFKC, lowercase."""
    if not value:
        return ''
    return unicodedata.normalize('NFKC', value.strip().lower())


def _normalize_last_initial(value):
    """Normalize last initial: strip, uppercase, single alpha char."""
    if not value:
        return ''
    v = value.strip().upper()
    if len(v) == 1 and v.isalpha():
        return v
    return ''


@main_bp.route('/verify/hallpass/<teacher_public_token>', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def verify_hall_pass(teacher_public_token):
    """
    Public hall pass verification for office staff.

    GET:  Show a form with class dropdown, first name, last initial fields.
    POST: Verify whether a specific student has a valid hall pass for today.

    Designed per Hall Pass Public Verification Spec v1.0:
    - Reveals no roster
    - Reveals no multi-day history
    - Reveals no internal identifiers
    - Non-enumerable (token-based)
    - Rotatable
    """
    from app.models import TeacherBlock, HallPassLog

    _GENERIC_UNAVAILABLE = "Verification page not available."

    # Look up teacher by token
    teacher = Admin.query.filter_by(hall_pass_verify_token=teacher_public_token).first()

    if not teacher:
        return render_template(
            'hall_pass_verify.html',
            unavailable=True,
            message=_GENERIC_UNAVAILABLE
        ), 404

    # Get teacher's active classes (distinct join_codes with labels)
    # Use plain .distinct() (all columns) + Python deduplication for cross-DB compat
    classes_rows = (
        db.session.query(TeacherBlock.join_code, TeacherBlock.block, TeacherBlock.class_label)
        .filter(
            TeacherBlock.teacher_id == teacher.id,
            TeacherBlock.join_code.isnot(None),
        )
        .group_by(TeacherBlock.join_code, TeacherBlock.block, TeacherBlock.class_label)
        .order_by(TeacherBlock.block)
        .all()
    )
    # Build list: [{"join_code": ..., "label": ...}, ...]
    classes = []
    seen_codes = set()
    for row in classes_rows:
        if row.join_code and row.join_code not in seen_codes:
            seen_codes.add(row.join_code)
            label = row.class_label if row.class_label else row.block
            classes.append({"join_code": row.join_code, "label": label})

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
    raw_last_initial = request.form.get('last_initial', '')
    selected_join_code = request.form.get('join_code', '')

    first_name_norm = _normalize_first_name(raw_first_name)
    last_initial_norm = _normalize_last_initial(raw_last_initial)

    # Reject malformed input uniformly
    if not first_name_norm or not last_initial_norm or not selected_join_code:
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result={'outcome': 'no_match'}
        )

    # Validate selected join_code belongs to this teacher
    valid_code = any(c['join_code'] == selected_join_code for c in classes)
    if not valid_code:
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result={'outcome': 'no_match'}
        )

    # Determine today's date range in school timezone
    school_tz = _get_school_timezone()
    now_school = utc_now().astimezone(school_tz)
    today_start = now_school.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    today_start_utc = today_start.astimezone(timezone.utc)
    today_end_utc = today_end.astimezone(timezone.utc)

    # Normalize for DB comparison (handles SQLite naive datetime storage)
    today_start_db = normalize_for_db(today_start_utc)
    today_end_db = normalize_for_db(today_end_utc)

    # Query today's hall pass records for this join_code.
    # Only include actionable statuses (not pending/rejected).
    passes_query = HallPassLog.query.filter(
        HallPassLog.join_code == selected_join_code,
        HallPassLog.request_time >= today_start_db,
        HallPassLog.request_time <= today_end_db,
        HallPassLog.status.in_(['approved', 'left', 'returned'])
    ).order_by(HallPassLog.request_time.desc())

    # Filter in Python (first_name is PII-encrypted, can't filter in DB).
    # Stop at 2 matches: enough to distinguish unique vs ambiguous.
    matched = []
    for entry in passes_query.yield_per(100):
        student = entry.student
        if not student:
            continue
        stored_norm = _normalize_first_name(student.first_name)
        stored_initial = (student.last_initial or '').strip().upper()
        if stored_norm == first_name_norm and stored_initial == last_initial_norm:
            matched.append(entry)
        if len(matched) >= 2:
            # Ambiguous — stop early
            break

    if len(matched) == 0:
        result = {'outcome': 'no_match'}
    elif len(matched) > 1:
        result = {'outcome': 'ambiguous'}
    else:
        entry = matched[0]
        student = entry.student
        class_label = next((c['label'] for c in classes if c['join_code'] == selected_join_code), selected_join_code)

        # Format time_out in school timezone
        time_out_str = None
        elapsed_mins = None
        if entry.left_time:
            left_utc = ensure_utc(entry.left_time)
            left_local = left_utc.astimezone(school_tz)
            time_out_str = left_local.strftime('%I:%M %p').lstrip('0')

            # Compute elapsed minutes only for currently-out passes
            if entry.status == 'left':
                elapsed_mins = int((utc_now() - left_utc).total_seconds() // 60)

        return_time_str = None
        if entry.return_time:
            returned_utc = ensure_utc(entry.return_time)
            returned_local = returned_utc.astimezone(school_tz)
            return_time_str = returned_local.strftime('%I:%M %p').lstrip('0')

        result = {
            'outcome': 'match',
            'student_display': f"{student.first_name} {student.last_initial}.",
            'class_label': class_label,
            'destination': entry.reason,
            'time_out': time_out_str,
            'status': entry.status,
            'elapsed_mins': elapsed_mins,
            'return_time': return_time_str,
        }

    return render_template(
        'hall_pass_verify.html',
        unavailable=False,
        token=teacher_public_token,
        classes=classes,
        result=result
    )


# -------------------- DEBUG ROUTES --------------------

@main_bp.route('/debug/filters')
def debug_filters():
    """List all available Jinja2 filters for debugging."""
    return jsonify(list(current_app.jinja_env.filters.keys()))


@main_bp.route('/switch-view')
def switch_view():
    """Switches the view between mobile and desktop."""
    view = request.args.get('view', 'mobile')
    next_url = request.args.get('next', url_for('main.home'))

    if view == 'desktop':
        session['force_desktop'] = True
    else:
        session.pop('force_desktop', None)

    if not is_safe_url(next_url):
        return redirect(url_for('main.home'))

    return redirect(next_url)  # nosec # Safe: validated by is_safe_url()


@main_bp.route('/debug/admin-db-test')
def debug_admin_db_test():
    """
    Temporary route to confirm admin and invite codes tables are accessible.
    """
    try:
        admins = Admin.query.all()
        invite_codes_count = db.session.execute(text('SELECT COUNT(*) FROM teacher_invite_codes')).scalar()
        return jsonify({
            "admin_count": len(admins),
            "invite_codes_count": invite_codes_count,
            "status": "success"
        }), 200
    except Exception as e:
        current_app.logger.exception("Admin DB test failed")
        return jsonify({"status": "error", "message": "Admin DB test failed due to an internal error."}), 500

"""
Authentication and authorization utilities for Classroom Token Hub.

Contains session management helpers, authentication decorators, and timeout logic.
"""

import urllib.parse
from datetime import datetime, timedelta, timezone
from functools import wraps

import sqlalchemy as sa
from flask import session, flash, redirect, url_for, request, current_app, jsonify


# -------------------- SESSION CONFIGURATION --------------------

SESSION_TIMEOUT_MINUTES = 10


def _get_safe_next_path() -> str:
    """
    Return a safe relative path that can be used as a `next` parameter.

    Ensures the value is a same-site path without scheme or host to avoid
    open redirect vulnerabilities if used in a subsequent redirect.
    """
    # Start from the Flask path, which is already URL-decoded and does not
    # include the scheme or host for normal requests.
    raw_path = request.path or "/"

    # Normalize any backslashes to forward slashes to avoid browser quirks.
    raw_path = raw_path.replace("\\", "/")

    # Parse the path in case an attacker has tried to smuggle in a scheme
    # or netloc via malformed input.
    parsed = urllib.parse.urlparse(raw_path)

    # Only allow pure paths without scheme or netloc.
    if parsed.scheme or parsed.netloc:
        return "/"

    path = parsed.path or "/"

    # Disallow protocol-relative style (`//evil.com`) paths.
    if path.startswith("//"):
        return "/"

    # Ensure the path is absolute within this application.
    if not path.startswith("/"):
        path = "/" + path

    return path


# -------------------- AUTHENTICATION DECORATORS --------------------

def login_required(f):
    """
    Decorator to require student authentication for a route.

    Enforces a strict 10-minute timeout from login time for students.
    Also allows admins in view-as-student mode to access student routes.
    Redirects to student.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow access if admin is viewing as student
        if is_viewing_as_student():
            # Enforce 10-minute timeout for demo sessions even in admin view
            if session.get('is_demo'):
                login_time_str = session.get('login_time')

                if not login_time_str:
                    session.pop('student_id', None)
                    session.pop('login_time', None)
                    session.pop('last_activity', None)
                    session['view_as_student'] = False
                    session.pop('is_demo', None)
                    session.pop('demo_session_id', None)
                    flash("Demo session is invalid. Please start a new demo session.")
                    return redirect(url_for('admin.dashboard'))

                login_time = datetime.fromisoformat(login_time_str)
                if (datetime.now(timezone.utc) - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    demo_session_id = session.get('demo_session_id')

                    try:
                        if demo_session_id:
                            from app.extensions import db
                            from app.models import DemoStudent
                            from app.utils.demo_sessions import cleanup_demo_student_data

                            demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
                            if demo_session:
                                cleanup_demo_student_data(demo_session)
                                db.session.commit()
                            else:
                                db.session.rollback()
                    except Exception:
                        current_app.logger.exception(
                            "Failed to clean up expired demo session %s during auth check",
                            demo_session_id,
                        )

                    session.pop('student_id', None)
                    session.pop('login_time', None)
                    session.pop('last_activity', None)
                    session.pop('is_demo', None)
                    session.pop('demo_session_id', None)
                    session['view_as_student'] = False
                    flash("Demo session expired. Please start a new demo session.")
                    return redirect(url_for('admin.dashboard'))

            # Admins must also have a student context when bypassing login_required
            if 'student_id' not in session:
                session['view_as_student'] = False
                # Return JSON for API requests
                if request.path.startswith('/api/'):
                    return jsonify({"status": "error", "error": "No student context"}), 401
                flash("Select a student before viewing the student experience.")
                return redirect(url_for('admin.dashboard'))

            # Enforce demo session expiry for admins viewing as demo students
            if session.get('is_demo'):
                demo_session_id = session.get('demo_session_id')
                if not demo_session_id:
                    session['view_as_student'] = False
                    # Return JSON for API requests
                    if request.path.startswith('/api/'):
                        return jsonify({"status": "error", "error": "Demo session expired"}), 401
                    flash("Demo session expired. Start a new demo to continue.")
                    return redirect(url_for('admin.dashboard'))

                from app.models import DemoStudent  # Imported lazily to avoid circular import
                demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
                now = datetime.now(timezone.utc)

                expires_at = None
                if demo_session and isinstance(demo_session.expires_at, datetime):
                    if demo_session.expires_at.tzinfo is None:
                        # Treat naive timestamps as UTC to avoid shifting into earlier local time
                        expires_at = demo_session.expires_at.replace(tzinfo=timezone.utc)
                    else:
                        expires_at = demo_session.expires_at
                else:
                    # If missing/invalid, refresh expiry window to prevent false expirations mid-redirect
                    expires_at = now + timedelta(minutes=10)
                    if demo_session:
                        demo_session.expires_at = expires_at
                        from app.extensions import db
                        db.session.commit()

                if not demo_session or not demo_session.is_active or (expires_at and now > expires_at):
                    try:
                        if demo_session:
                            from app.extensions import db  # Imported lazily to avoid circular import
                            from app.utils.demo_sessions import cleanup_demo_student_data

                            cleanup_demo_student_data(demo_session)
                            db.session.commit()

                        session.pop('student_id', None)
                        session.pop('login_time', None)
                        session.pop('last_activity', None)
                        session.pop('is_demo', None)
                        session.pop('demo_session_id', None)
                        session['view_as_student'] = False
                        # Return JSON for API requests
                        if request.path.startswith('/api/'):
                            return jsonify({"status": "error", "error": "Demo session expired"}), 401
                        flash("Demo session expired. Start a new demo to continue.")
                        return redirect(url_for('admin.dashboard'))
                    except Exception:
                        current_app.logger.exception(
                            "Failed to clean up expired demo session %s during auth check",
                            demo_session_id,
                        )
                        session.pop('student_id', None)
                        session.pop('login_time', None)
                        session.pop('last_activity', None)
                        session.pop('is_demo', None)
                        session.pop('demo_session_id', None)
                        session['view_as_student'] = False
                        # Return JSON for API requests
                        if request.path.startswith('/api/'):
                            return jsonify({"status": "error", "error": "Demo session expired"}), 401
                        flash("Demo session expired. Start a new demo to continue.")
                        return redirect(url_for('admin.dashboard'))

            # Update admin's last activity
            session['last_activity'] = datetime.now(timezone.utc).isoformat()
            return f(*args, **kwargs)

        # Regular student authentication check
        if 'student_id' not in session:
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")

        # Enforce strict 10-minute timeout from login time
        login_time_str = session.get('login_time')
        if not login_time_str:
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Session is invalid. Please log in again."}), 401
            flash("Session is invalid. Please log in again.")
            return redirect(url_for('student.login'))

        login_time = datetime.fromisoformat(login_time_str)
        if (datetime.now(timezone.utc) - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Session expired. Please log in again."}), 401
            flash("Session expired. Please log in again.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")

        # Continue to update last_activity for other potential uses, but it no longer controls the timeout
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to admin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"Admin access attempt: session = {dict(session)}")
        if not session.get("is_admin"):
            flash("You must be an admin to view this page.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        admin = get_current_admin()
        if not admin:
            session.pop("is_admin", None)
            session.pop("admin_id", None)
            session.pop("last_activity", None)
            flash("Admin session is invalid. Please log in again.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        now = datetime.now(timezone.utc)
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.clear()
                flash("Admin session expired. Please log in again.")
                next_path = _get_safe_next_path()
                encoded_next = urllib.parse.quote(next_path, safe="")
                return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        session['last_activity'] = now.isoformat()
        ensure_admin_join_code(admin.id)
        return f(*args, **kwargs)
    return decorated_function


def system_admin_required(f):
    """
    Decorator to require system admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to sysadmin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_system_admin"):
            flash("System administrator access required.")
            return redirect(url_for('sysadmin.login', next=request.path))
        last_activity = session.get('last_activity')
        now = datetime.now(timezone.utc)
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if now - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.clear()
                flash("Session expired. Please log in again.")
                return redirect(url_for('sysadmin.login', next=request.path))
        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


# -------------------- HELPER FUNCTIONS --------------------

def get_logged_in_student():
    """
    Get the currently logged-in student from the session.

    Returns:
        Student: The logged-in Student object, or None if not logged in.
    """
    # Import here to avoid circular imports
    from app.models import Student
    return Student.query.get(session['student_id']) if 'student_id' in session else None


def get_current_admin():
    """Return the logged-in admin based on the session state."""
    if not session.get("is_admin"):
        return None
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    from app.models import Admin  # Imported lazily to avoid circular import
    return Admin.query.get(admin_id)


def ensure_admin_join_code(admin_id):
    """Ensure an admin has a current join code selected in session."""
    from app.models import TeacherBlock  # Imported lazily to avoid circular import

    if not admin_id:
        return

    join_code = session.get('current_join_code')
    if join_code:
        if TeacherBlock.query.filter_by(teacher_id=admin_id, join_code=join_code).first():
            return
        session.pop('current_join_code', None)

    teacher_block = (
        TeacherBlock.query
        .filter_by(teacher_id=admin_id)
        .filter(TeacherBlock.join_code.isnot(None))
        .order_by(TeacherBlock.block, TeacherBlock.join_code)
        .first()
    )
    if teacher_block and teacher_block.join_code:
        session['current_join_code'] = teacher_block.join_code


def get_admin_student_query(include_unassigned=True):
    """Return a Student query scoped to the current admin's ownership.

    System admins are allowed to see all students. Regular admins only see
    students linked to them via the StudentTeacher association table.
    
    CRITICAL SECURITY NOTE: We ONLY use the StudentTeacher table as the source of truth.
    The teacher_id column on Student is DEPRECATED and should NOT be used for scoping
    because it can contain stale data from deleted teachers or data migration issues.
    
    Args:
        include_unassigned (bool): [DEPRECATED] No longer used. Kept for backward compatibility.
    """
    from app.models import Student, StudentTeacher, DemoStudent  # Imported lazily to avoid circular import

    if session.get("is_system_admin"):
        demo_ids_subq = DemoStudent.query.with_entities(DemoStudent.student_id).subquery()
        return Student.query.filter(~Student.id.in_(demo_ids_subq))

    admin = get_current_admin()
    if not admin:
        return Student.query.filter(sa.text("0=1"))

    # Get student IDs that are explicitly linked to this admin via StudentTeacher table
    # This is the ONLY source of truth for student-teacher associations
    shared_student_ids = (
        StudentTeacher.query.with_entities(StudentTeacher.student_id)
        .filter(StudentTeacher.admin_id == admin.id)
        .subquery()
    )

    # SECURITY FIX: Only use StudentTeacher associations, NOT the deprecated teacher_id column
    # The old code used: sa.or_(Student.teacher_id == admin.id, Student.id.in_(shared_student_ids))
    # This caused multi-tenancy leaks when teacher_id had stale data
    demo_ids_subq = DemoStudent.query.with_entities(DemoStudent.student_id).subquery()
    return Student.query.filter(
        Student.id.in_(shared_student_ids),
        ~Student.id.in_(demo_ids_subq)
    )


def get_student_for_admin(student_id, include_unassigned=True):
    """Return a student the current admin can access, or None."""
    query = get_admin_student_query(include_unassigned=include_unassigned)
    return query.filter_by(id=student_id).first()


def is_viewing_as_student():
    """
    Check if the current user is an admin viewing as a student.

    Returns:
        bool: True if admin is in view-as-student mode, False otherwise.
    """
    return session.get("is_admin") and session.get("view_as_student", False)


def can_access_student_routes():
    """
    Check if the current user can access student routes.

    Returns True if:
    - User is a logged-in student, OR
    - User is an admin in view-as-student mode

    Returns:
        bool: True if user can access student routes, False otherwise.
    """
    return 'student_id' in session or is_viewing_as_student()


# -------------------- CLASS MEMBERSHIP AUTHORIZATION --------------------

def resolve_join_code(join_code):
    """
    Resolve a join code, following aliases if necessary.

    If the join_code is an old/rotated code, resolves to the current code.
    Returns None if the code doesn't exist in any form.

    Args:
        join_code: The join code to resolve

    Returns:
        tuple: (resolved_join_code, ClassEconomy) or (None, None) if not found
    """
    from app.models import ClassEconomy, ClassJoinCodeAlias

    # First, try direct lookup
    economy = ClassEconomy.query.get(join_code)
    if economy:
        return join_code, economy

    # Check if it's an old/aliased code
    alias = ClassJoinCodeAlias.query.filter_by(old_code=join_code).first()
    if alias:
        economy = ClassEconomy.query.get(alias.current_join_code)
        if economy:
            return alias.current_join_code, economy

    return None, None


def get_membership(join_code, admin_id=None, student_id=None):
    """
    Get a user's membership for a specific class economy.

    Args:
        join_code: The class economy's join code
        admin_id: The admin's ID (mutually exclusive with student_id)
        student_id: The student's ID (mutually exclusive with admin_id)

    Returns:
        ClassMembership: The membership record, or None if not found
    """
    from app.models import ClassMembership

    if not join_code:
        return None

    # Resolve the join code in case it's an alias
    resolved_code, economy = resolve_join_code(join_code)
    if not resolved_code:
        return None

    if admin_id:
        return ClassMembership.query.filter_by(
            join_code=resolved_code,
            admin_id=admin_id,
            status='active'
        ).first()
    elif student_id:
        return ClassMembership.query.filter_by(
            join_code=resolved_code,
            student_id=student_id,
            status='active'
        ).first()

    return None


def get_current_membership():
    """
    Get the current user's membership for their active class context.

    Automatically determines user type from session and uses current_join_code.

    Returns:
        ClassMembership: The membership record, or None if not found
    """
    join_code = session.get('current_join_code')
    if not join_code:
        return None

    if session.get('is_admin'):
        admin_id = session.get('admin_id')
        return get_membership(join_code, admin_id=admin_id)
    elif 'student_id' in session:
        student_id = session.get('student_id')
        return get_membership(join_code, student_id=student_id)

    return None


def check_membership_access(join_code, allowed_roles=None, require_active_economy=True):
    """
    Check if the current user has membership access to a class economy.

    This is the core authorization check for the join_code-centric architecture.

    Args:
        join_code: The class economy's join code to check access for
        allowed_roles: List of roles that are allowed (e.g., ['admin', 'student'])
                      If None, any active membership is sufficient
        require_active_economy: If True, also checks that the economy status is 'active'

    Returns:
        tuple: (is_allowed, membership, economy, error_message)
            - is_allowed: True if access is granted
            - membership: The ClassMembership record (or None)
            - economy: The ClassEconomy record (or None)
            - error_message: Human-readable error if access denied
    """
    from app.models import ClassEconomy, ClassMembership

    if not join_code:
        return False, None, None, "No class context specified"

    # Resolve the join code
    resolved_code, economy = resolve_join_code(join_code)
    if not economy:
        return False, None, None, "Class not found"

    # Check economy status if required
    if require_active_economy and economy.status != 'active':
        return False, None, economy, "This class is archived and read-only"

    # System admins have global access
    if session.get('is_system_admin'):
        return True, None, economy, None

    # Get the user's membership
    membership = None
    if session.get('is_admin'):
        admin_id = session.get('admin_id')
        membership = ClassMembership.query.filter_by(
            join_code=resolved_code,
            admin_id=admin_id,
            status='active'
        ).first()
    elif 'student_id' in session:
        student_id = session.get('student_id')
        membership = ClassMembership.query.filter_by(
            join_code=resolved_code,
            student_id=student_id,
            status='active'
        ).first()

    if not membership:
        return False, None, economy, "You do not have access to this class"

    # Check role if required
    if allowed_roles and membership.role not in allowed_roles:
        return False, membership, economy, f"This action requires one of these roles: {', '.join(allowed_roles)}"

    return True, membership, economy, None


def membership_required(allowed_roles=None, require_active_economy=True):
    """
    Decorator to require class membership for a route.

    Uses the 'join_code' from:
    1. Route kwargs (if present)
    2. Request args (if present)
    3. Session's current_join_code (fallback)

    Args:
        allowed_roles: List of roles that are allowed (e.g., ['admin'])
        require_active_economy: If True, requires economy status to be 'active'

    Usage:
        @app.route('/class/<join_code>/settings')
        @admin_required
        @membership_required(allowed_roles=['admin'])
        def class_settings(join_code):
            # membership is available via get_current_membership()
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get join_code from route, request args, or session
            join_code = kwargs.get('join_code') or request.args.get('join_code') or session.get('current_join_code')

            is_allowed, membership, economy, error = check_membership_access(
                join_code,
                allowed_roles=allowed_roles,
                require_active_economy=require_active_economy
            )

            if not is_allowed:
                if request.path.startswith('/api/'):
                    return jsonify({"status": "error", "error": error}), 403
                flash(error, "error")
                # Redirect based on user type
                if session.get('is_admin'):
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('student.select_class'))

            # Store membership in request context for use in route
            from flask import g
            g.current_membership = membership
            g.current_economy = economy

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_or_create_membership(join_code, admin_id=None, student_id=None, role=None):
    """
    Get existing membership or create a new one.

    This is used during class joining and roster operations.

    Args:
        join_code: The class economy's join code
        admin_id: The admin's ID (for admin/observer roles)
        student_id: The student's ID (for student role)
        role: The role to assign if creating ('admin', 'observer', 'student')

    Returns:
        tuple: (membership, created) - The membership and whether it was newly created
    """
    from app.models import ClassMembership, ClassEconomy
    from app.extensions import db

    # Resolve and validate join code
    resolved_code, economy = resolve_join_code(join_code)
    if not economy:
        return None, False

    # Determine role if not provided
    if not role:
        role = 'admin' if admin_id else 'student'

    # Check for existing membership
    existing = get_membership(resolved_code, admin_id=admin_id, student_id=student_id)
    if existing:
        return existing, False

    # Create new membership
    membership = ClassMembership(
        join_code=resolved_code,
        admin_id=admin_id,
        student_id=student_id,
        role=role,
        status='active'
    )
    db.session.add(membership)

    return membership, True


def get_actor_membership_id():
    """
    Get the current actor's membership ID for audit logging.

    This should be used when creating transactions or other audited records.

    Returns:
        int: The ClassMembership.id for the current user's active class, or None
    """
    membership = get_current_membership()
    return membership.id if membership else None

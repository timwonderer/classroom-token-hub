from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from datetime import timedelta
from datetime import timedelta
import secrets

from app.extensions import db
from app.models import Student, TeacherBlock
from app.auth import admin_required, get_student_for_admin
from app.utils.time import utc_now, ensure_utc
from app.extensions import limiter

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')
RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _recovery_rate_limit():
    """Use strict limits in runtime, relaxed limits in test environments."""
    if current_app.testing:
        return "1000 per minute"
    return "10 per minute"


def _generate_reset_code(length=8):
    """Generate an uppercase, unambiguous alphanumeric recovery code."""
    return ''.join(secrets.choice(RESET_CODE_ALPHABET) for _ in range(length))


# ----------------------------------------------------------------------
# TEACHER ROUTES
# ----------------------------------------------------------------------

@recovery_bp.route('/admin/generate-code/<int:student_id>', methods=['POST'])
@admin_required
def generate_reset_code(student_id):
    """
    Step 1 — Teacher Initiates Reset.

    System must:
      - Set student status -> to_be_claimed
      - Invalidate any existing reset_code
      - Generate new 8-character mixed alphanumeric reset_code
      - Set reset_code_expires_at = now + 10 minutes
      - Log reset event
    """
    # Verify scoping: admin must have access to this student
    student = get_student_for_admin(student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for('admin.students'))

    # Invalidate any existing reset_code, then generate new one
    code = _generate_reset_code(8)

    student.reset_code = code
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'

    db.session.commit()

    current_app.logger.info(
        f"Reset code generated for student {student.id} by admin {session.get('admin_id')}"
    )

    flash(f"Reset code generated for {student.first_name} {student.last_initial}. "
          f"Code: {code} — Expires in 10 minutes.", "success")
    return redirect(url_for('admin.student_detail', student_id=student.id))

# ----------------------------------------------------------------------
# STUDENT ROUTES — Single Recovery Flow
# ----------------------------------------------------------------------

@recovery_bp.route('/', methods=['GET'])
def landing():
    """Redirect to account recovery lookup (single flow)."""
    return redirect(url_for('recovery.account_lookup'))


@recovery_bp.route('/lookup', methods=['GET', 'POST'])
@limiter.limit(_recovery_rate_limit)
def account_lookup():
    """
    Step 2 — Student Enters Join Code + Reset Code.

    Validates:
      - reset_code exists
      - reset_code unexpired
      - student.recovery_status == to_be_claimed
      - join_code matches a claimed seat for this student

    On success: clears old credentials and redirects straight to username/credential
    setup. No PII re-entry is required — first name and last initial are managed by
    the teacher and remain unchanged through recovery.
      - join_code matches a claimed seat for this student

    On success: clears old credentials and redirects straight to username/credential
    setup. No PII re-entry is required — first name and last initial are managed by
    the teacher and remain unchanged through recovery.

    On failure: generic message, do not reveal student identity.
    """
    if request.method == 'POST':
        join_code = request.form.get('join_code', '').strip().upper()
        reset_code = request.form.get('reset_code', '').strip().upper()

        if not join_code or not reset_code:
            flash("Both fields are required.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Find candidate row by both reset_code and join_code to avoid collisions.
        linked_block = (
            TeacherBlock.query
            .join(Student, Student.id == TeacherBlock.student_id)
            .filter(
                TeacherBlock.join_code == join_code,
                Student.reset_code == reset_code,
            )
            .first()
        )
        student = db.session.get(Student, linked_block.student_id) if linked_block else None

        # Validate all conditions — use a single generic error for security
        valid = True

        if not student:
            valid = False
        elif not student.reset_code_expires_at or ensure_utc(student.reset_code_expires_at) < utc_now():
            valid = False
        elif student.recovery_status != 'to_be_claimed':
            valid = False

        if not valid:
            session.pop('recovery_student_id', None)
            flash("Invalid or expired recovery code.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Clear all credentials — forces fresh credential setup (username, PIN, passphrase).
        # first_name and last_initial are preserved; they are managed by the teacher.
        if linked_block and linked_block.is_claimed and linked_block.claimed_at is None:
            linked_block.claimed_at = utc_now()

        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False
        # Keep reset_code and recovery_status until setup_pin_passphrase completes.
        # Keep reset_code and recovery_status until setup_pin_passphrase completes.

        db.session.commit()

        current_app.logger.info(
            f"Recovery lookup succeeded for student {student.id}; credentials cleared."
        )
        current_app.logger.info(
            f"Recovery lookup succeeded for student {student.id}; credentials cleared."
        )

        # Set session for credential setup flow
        # Set session for credential setup flow
        session['claimed_student_id'] = student.id
        session.pop('recovery_student_id', None)

        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        flash("Recovery code verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/account_lookup.html')


@recovery_bp.route('/verify-identity', methods=['GET', 'POST'])
def verify_identity():
    """Deprecated — identity re-entry is no longer required for recovery.

    Redirects to account_lookup so students with bookmarked URLs land somewhere useful.
    """
    return redirect(url_for('recovery.account_lookup'))
    return render_template('student/recovery/account_lookup.html')


@recovery_bp.route('/verify-identity', methods=['GET', 'POST'])
def verify_identity():
    """Deprecated — identity re-entry is no longer required for recovery.

    Redirects to account_lookup so students with bookmarked URLs land somewhere useful.
    """
    return redirect(url_for('recovery.account_lookup'))

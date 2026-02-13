from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime, timedelta
import secrets

from app.extensions import db
from app.models import Student, TeacherBlock, StudentTeacher
from app.auth import admin_required, get_student_for_admin
from app.hash_utils import hash_hmac, get_random_salt
from app.utils.name_utils import hash_last_name_parts
from app.utils.claim_credentials import compute_primary_claim_hash
from app.utils.time import utc_now, ensure_utc
from app.extensions import limiter

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')


def _recovery_rate_limit():
    """Use strict limits in runtime, relaxed limits in test environments."""
    if current_app.testing:
        return "1000 per minute"
    return "10 per minute"


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
    code = secrets.token_hex(4).upper()  # 8-char hex string

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
      - reset_code unused
      - reset_code unexpired
      - student.recovery_status == to_be_claimed
      - join_code matches the student record

    On failure: generic message, do not reveal student identity.
    """
    if request.method == 'POST':
        join_code = request.form.get('join_code', '').strip().upper()
        reset_code = request.form.get('reset_code', '').strip().upper()

        if not join_code or not reset_code:
            flash("Both fields are required.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Find student by reset_code
        student = Student.query.filter_by(reset_code=reset_code).first()

        # Validate all conditions — use a single generic error for security
        valid = True

        if not student:
            valid = False
        elif not student.reset_code_expires_at or ensure_utc(student.reset_code_expires_at) < utc_now():
            valid = False
        elif student.recovery_status != 'to_be_claimed':
            valid = False
        else:
            # Verify join_code matches the student record
            linked_block = TeacherBlock.query.filter_by(
                student_id=student.id,
                join_code=join_code
            ).first()
            if not linked_block:
                valid = False

        if not valid:
            flash("Invalid or expired recovery code.", "error")
            return redirect(url_for('recovery.account_lookup'))

        # Success: store student_id in session for next step
        session['recovery_student_id'] = student.id
        # Scope the next step to the teacher context validated by join_code lookup.
        session['recovery_teacher_id'] = linked_block.teacher_id
        return redirect(url_for('recovery.verify_identity'))

    return render_template('student/recovery/account_lookup.html')


@recovery_bp.route('/verify-identity', methods=['GET', 'POST'])
@limiter.limit(_recovery_rate_limit)
def verify_identity():
    """
    Step 3 — Identity Re-Registration.

    Student re-enters first name, full last name, DOB.
    These replace existing identity metadata on the same student row.
    student_id remains unchanged. No new student record is created.
    Operation is atomic.

    Then proceeds to Step 4 — Credential Re-Establishment
    (normal credential setup: username, PIN, passphrase).
    """
    student_id = session.get('recovery_student_id')
    recovery_teacher_id = session.get('recovery_teacher_id')
    if not student_id:
        return redirect(url_for('recovery.account_lookup'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob')  # YYYY-MM-DD

        if not first_name or not last_name or not dob_str:
            flash("All fields are required.", "error")
            return redirect(url_for('recovery.verify_identity'))

        try:
            dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
            dob_sum = dob_date.month + dob_date.day + dob_date.year
        except ValueError:
            flash("Invalid Date of Birth format.", "error")
            return redirect(url_for('recovery.verify_identity'))

        student = db.session.get(Student, student_id)
        if not student:
            return redirect(url_for('recovery.account_lookup'))

        # --- Atomic identity rebinding ---

        # Update PII and rotate salt
        new_salt = get_random_salt()

        student.first_name = first_name
        student.last_initial = last_name[0].upper() if last_name else ''
        student.dob_sum = dob_sum
        student.salt = new_salt

        # Update hashes
        student.last_name_hash_by_part = hash_last_name_parts(last_name, new_salt)

        first_initial = first_name[0].upper()
        student.first_half_hash = compute_primary_claim_hash(first_initial, dob_sum, new_salt)
        student.second_half_hash = hash_hmac(str(dob_sum).encode(), new_salt)

        # Clear all credentials — forces full credential setup
        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False

        # Step 5 — Completion: clear recovery state, set status -> active
        student.reset_code = None
        student.reset_code_expires_at = None
        student.recovery_status = 'active'

        # Sync PII to TeacherBlock rows for this teacher only.
        teacher_block_query = TeacherBlock.query.filter_by(student_id=student.id)
        if recovery_teacher_id:
            teacher_block_query = teacher_block_query.filter_by(teacher_id=recovery_teacher_id)

        for teacher_block in teacher_block_query.all():
            teacher_block.first_name = student.first_name
            teacher_block.last_initial = student.last_initial
            teacher_block.last_name_hash_by_part = student.last_name_hash_by_part or []
            teacher_block.dob_sum = student.dob_sum or 0
            teacher_block.salt = new_salt
            teacher_block.first_half_hash = student.first_half_hash
            teacher_block.is_claimed = False
            teacher_block.claimed_at = None

        db.session.commit()

        current_app.logger.info(f"Account reclaimed for student {student.id}")

        # Set session for credential setup flow (Step 4)
        session['claimed_student_id'] = student.id
        session.pop('recovery_student_id', None)
        session.pop('recovery_teacher_id', None)

        flash("Identity verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))

    return render_template('student/recovery/identity_update.html')

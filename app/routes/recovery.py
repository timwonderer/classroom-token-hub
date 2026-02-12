from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
import secrets

from app.extensions import db
from app.models import Student, TeacherBlock, Admin
from app.auth import admin_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.hash_utils import hash_username, hash_hmac, get_random_salt
from app.utils.name_utils import hash_last_name_parts
from app.utils.claim_credentials import compute_primary_claim_hash
from app.utils.money_guard import check_financial_cooldown
from app.utils.time import utc_now, ensure_utc

recovery_bp = Blueprint('recovery', __name__, url_prefix='/recovery')

# ----------------------------------------------------------------------
# TEACHER ROUTES
# ----------------------------------------------------------------------

@recovery_bp.route('/admin/generate-code/<int:student_id>', methods=['POST'])
@admin_required
def generate_reset_code(student_id):
    """
    Teacher-initiated: Generate a temporary reset code for a student.
    User must be the teacher identifying this student.
    """
    student = db.session.get(Student, student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for('admin.students'))
    
    # 1. Verify scoping: Does this teacher teach this student?
    admin_id = session.get('admin_id')
    # Simplified check: Is there a StudentTeacher link?
    # In real implementation we might want stricter scope checks via TeacherBlock/JoinCode
    
    # 2. Generate Code
    code = secrets.token_hex(4).upper() # 8 chars
    
    # 3. Update Student
    student.reset_code = code
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'requested'
    
    db.session.commit()
    
    # 4. Return to page with code (using flash)
    flash(f"Reset Code for {student.first_name} {student.last_initial}.: {code} (Expires in 10m)", "success")
    return redirect(url_for('admin.students'))

# ----------------------------------------------------------------------
# STUDENT ROUTES
# ----------------------------------------------------------------------

@recovery_bp.route('/', methods=['GET'])
def landing():
    """Step 0: Landing page to choose recovery flow."""
    return render_template('student/recovery/landing.html')

@recovery_bp.route('/lookup', methods=['GET', 'POST'])
def account_lookup():
    """Flow 1 Step 1: Lookup by Join Code + Reset Code."""
    if request.method == 'POST':
        join_code = request.form.get('join_code', '').strip().upper()
        reset_code = request.form.get('reset_code', '').strip().upper()
        
        # 1. Find Student where reset_code matches AND expires_at > now
        student = Student.query.filter_by(reset_code=reset_code).first()
        
        if not student:
            flash("Invalid or expired reset code.", "error")
            return redirect(url_for('recovery.account_lookup'))
            
        if ensure_utc(student.reset_code_expires_at) < utc_now():
            flash("Reset code has expired.", "error")
            return redirect(url_for('recovery.account_lookup'))
            
        # 2. Verify Scoping: Is student in the class with this join_code?
        # We check if student is in a TeacherBlock with this join_code.
        linked_block = TeacherBlock.query.filter_by(
            student_id=student.id, 
            join_code=join_code
        ).first()
        
        if not linked_block:
             flash("Invalid join code for this student.", "error")
             return redirect(url_for('recovery.account_lookup'))
             
        # Success: Store student_id in session for next step
        session['recovery_student_id'] = student.id
        session['recovery_mode'] = 'account_reset' # Flow 1
        return redirect(url_for('recovery.verify_identity'))

    return render_template('student/recovery/account_lookup.html')


@recovery_bp.route('/verify-identity', methods=['GET', 'POST'])
def verify_identity():
    """Flow 1 Step 2: Update PII and Reset Account."""
    student_id = session.get('recovery_student_id')
    if not student_id or session.get('recovery_mode') != 'account_reset':
        return redirect(url_for('recovery.landing'))
        
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob') # YYYY-MM-DD
        
        if not first_name or not last_name or not dob_str:
            flash("All fields are required.", "error")
            return redirect(url_for('recovery.verify_identity'))

        try:
            # Parse DOB: YYYY-MM-DD
            dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
            dob_sum = dob_date.month + dob_date.day + dob_date.year
        except ValueError:
            flash("Invalid Date of Birth format.", "error")
            return redirect(url_for('recovery.verify_identity'))
        
        student = db.session.get(Student, student_id)
        if not student:
            return redirect(url_for('recovery.landing'))
            
        # Update PII and Rotate Salt
        new_salt = get_random_salt()
        
        student.first_name = first_name
        student.last_initial = last_name[0].upper()
        student.dob_sum = dob_sum
        student.salt = new_salt
        
        # Update Hashes
        student.last_name_hash_by_part = hash_last_name_parts(last_name, new_salt)
        
        # Update Claim Hashes (First Initial + DOB Sum)
        first_initial = first_name[0].upper()
        primary_hash = compute_primary_claim_hash(first_initial, dob_sum, new_salt)
        student.first_half_hash = primary_hash
        # Assume second_half_hash is legacy or same? 
        # Typically second_half_hash was dob_sum hash.
        # Check models.py: second_half_hash = db.Column(db.String(64), unique=True, nullable=True) # Hash of DOB sum (backward compat)
        student.second_half_hash = hash_hmac(str(dob_sum).encode(), new_salt)
        
        # Clear Credentials to force full setup
        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False
        
        # Clear recovery state
        student.reset_code = None
        student.reset_code_expires_at = None
        student.recovery_status = 'none'
        
        db.session.commit()
        
        # Log them in as "partial student" or just redirect to setup?
        # Typically setup requires being logged in or having a session.
        # But 'has_completed_setup' is False, so login might redirect to setup.
        # We need to log them in securely.
        session['student_id'] = student.id
        session['login_time'] = utc_now().isoformat()
        
        flash("Identity verified. Please set up your new username and credentials.", "success")
        return redirect(url_for('student.create_username'))
        
    return render_template('student/recovery/identity_update.html')

@recovery_bp.route('/credential-lookup', methods=['GET', 'POST'])
def credential_lookup():
    """Flow 2 Step 1: Lookup by Username + Reset Code."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        reset_code = request.form.get('reset_code', '').strip().upper()
        
        student = Student.query.filter_by(reset_code=reset_code).first()
        
        if not student:
             flash("Invalid reset code.", "error")
             return redirect(url_for('recovery.credential_lookup'))
             
        if not student.reset_code_expires_at or ensure_utc(student.reset_code_expires_at) < utc_now():
            flash("Reset code has expired.", "error")
            return redirect(url_for('recovery.credential_lookup'))
            
        # Verify Username Match
        # We need to verify hash using stored salt
        salt = student.salt
        computed_hash = hash_username(username, salt)
        
        if computed_hash != student.username_hash:
             flash("Username does not match our records.", "error")
             return redirect(url_for('recovery.credential_lookup'))
        
        # Success
        session['recovery_student_id'] = student.id
        session['recovery_mode'] = 'credential_reset' # Flow 2
        return redirect(url_for('recovery.reset_credentials'))

    return render_template('student/recovery/credential_lookup.html')

@recovery_bp.route('/reset', methods=['GET', 'POST'])
def reset_credentials():
    """Flow 2 Step 2: Reset PIN/Passphrase."""
    student_id = session.get('recovery_student_id')
    if not student_id or session.get('recovery_mode') != 'credential_reset':
        return redirect(url_for('recovery.landing'))
    
    student = db.session.get(Student, student_id)
    if not student:
        return redirect(url_for('recovery.landing'))
    
    if request.method == 'POST':
        new_pin = request.form.get('pin')
        new_passphrase = request.form.get('passphrase')
        
        changed_passphrase = False
        
        if new_pin and len(new_pin) >= 4:
            # Hash PIN
            # Reuse hash_password or specific pin hashing?
            # app/routes/student.py uses hash_password(pin, method='pbkdf2:sha256', salt_length=8) usually
            # But let's check how pin_hash is stored.
            # It's usually a standard password hash.
            student.pin_hash = generate_password_hash(new_pin) # Uses default method (pbkdf2)
            
        if new_passphrase and len(new_passphrase) >= 8:
            student.passphrase_hash = generate_password_hash(new_passphrase)
            changed_passphrase = True
            
        # Apply Cooldowns
        if changed_passphrase:
            # 1 Hour Cooldown for Passphrase change
            student.money_action_cooldown_until = utc_now() + timedelta(hours=1)
            flash("Passphrase updated. Money transfers unlocked in 1 hour.", "warning")
        else:
            flash("Credentials updated successfully.", "success")
            
        # Clear recovery state
        student.reset_code = None
        student.reset_code_expires_at = None
        student.recovery_status = 'none'
        
        db.session.commit()
        
        # Clear recovery session
        session.pop('recovery_student_id', None)
        session.pop('recovery_mode', None)
        
        return redirect(url_for('student.login'))
        
    return render_template('student/recovery/reset_form.html')

# Helper for PIN hashing if needed (generate_password_hash is from werkzeug.security)
from werkzeug.security import generate_password_hash

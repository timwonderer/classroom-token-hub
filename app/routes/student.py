"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import secrets
import uuid
import re
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Blueprint, redirect, url_for, flash, request, session, jsonify, current_app, has_app_context, has_request_context, g
from sqlalchemy import or_, func, select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import selectinload
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from dateutil.relativedelta import relativedelta

from app.extensions import db, limiter
from app.models import (
    Student, Transaction, TransactionStatus, TapEvent, StoreItem, StoreItemBlock, StudentItem,
    RentSettings, RentPayment, RentWaiver, InsurancePolicy, InsurancePolicyBlock, StudentInsurance, InsuranceClaim,
    BankingSettings, UserReport, FeatureSettings, Issue, IssueResolutionAction, _quantize_currency
)
from app.auth import (
    admin_required,
    login_required,
    get_logged_in_student,
    is_student_account_active,
    SESSION_TIMEOUT_MINUTES,
)
from app.forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, InsuranceClaimForm, StudentCompleteProfileForm,
    StudentConfirmMigratedUsernameForm,
)

# Import utility functions
from app.utils.helpers import generate_anonymous_code, is_safe_url, format_utc_iso, render_template_with_fallback as render_template
from app.utils.constants import THEME_PROMPTS
from app.utils.turnstile import verify_turnstile_token
from app.utils.demo_sessions import cleanup_demo_student_data
from app.utils.ip_handler import get_real_ip
from app.utils.claim_credentials import compute_primary_claim_hash, match_claim_hash
from app.utils.name_utils import hash_last_name_parts
from app.utils.overdraft import charge_overdraft_fee_if_needed, evaluate_overdraft_allowance
from app.utils.help_content import HELP_ARTICLES
from app.utils.store import process_expired_collective_goals
from app.hash_utils import hash_hmac, hash_username, hash_username_lookup
from app.attendance import get_all_block_statuses
from app.payroll import get_pay_rate_for_block
from app.utils.time import utc_now, ensure_utc, normalize_for_db, get_timezone, get_claim_period_bounds, UTC_MIN
from app.utils.insurance_eligibility import (
    evaluate_claim_transaction_eligibility,
    collect_reimbursed_source_tx_ids,
)
from app.utils.economy_rebalance import activate_due_rebalances
from app.utils.display_name_session import (
    get_teacher_display_name_cache,
    upsert_teacher_display_name_cache,
    clear_teacher_display_name_cache,
)
from app.services.tlcp import has_recent_error_for_actor

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')

# Tolerance used to match RentPayment rows with their Transaction rows.
# This guards against small timestamp drift without weakening ownership checks.
RENT_PAYMENT_MATCH_TOLERANCE_SECONDS = 300
TRANSFER_SUBMISSION_TOKEN_KEY = 'transfer_submission_token'
TRANSFER_SUBMISSION_TOKEN_LIMIT = 5

USERNAME_ADJECTIVES = [
    "brave", "clever", "curious", "daring", "eager", "fancy", "gentle", "honest", "jolly", "kind",
    "lucky", "mighty", "noble", "quick", "proud", "silly", "witty", "zesty", "sunny", "chill"
]


# -------------------- DATETIME HELPERS --------------------


def _generate_unique_student_username(seed_word, first_name, last_initial):
    """
    Generate a non-PII username by combining an adjective, a seed word,
    a random 4-digit number, and the student's initials.
    Includes a retry loop to ensure uniqueness against existing Student records.
    """
    initials = f"{first_name[0].upper()}{last_initial.upper()}"
    max_retries = 5

    for _ in range(max_retries):
        adjective = random.choice(USERNAME_ADJECTIVES)
        uniquifier = random.randint(1000, 9999)
        username = f"{adjective}{seed_word}{uniquifier}{initials}"

        # Check for collision in DB
        lookup_hash = hash_username_lookup(username)
        if not Student.query.filter_by(username_lookup_hash=lookup_hash).first():
            return username

    # Extremely rare collision limit reached
    current_app.logger.warning(f"Username collision retry limit reached for seed '{seed_word}'")
    # Final fallback attempt with higher entropy
    uniquifier = random.randint(10000, 99999)
    return f"{random.choice(USERNAME_ADJECTIVES)}{seed_word}{uniquifier}{initials}"


def _clear_expired_rent_perk_items(student_id, join_code=None, teacher_id=None, now=None):
    """Delete expired rent-granted StudentItem rows so stale perks disappear."""
    if not student_id:
        return 0

    now = now or utc_now()
    expired_query = db.session.query(StudentItem.id).join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.student_id == student_id,
        StudentItem.status == 'purchased',
        StudentItem.purchase_transaction_id.is_(None),
        StudentItem.uses_remaining.isnot(None),
        StudentItem.expiry_date.isnot(None),
        StudentItem.expiry_date <= now,
        StoreItem.is_rent_linked.is_(True),
    )

    if join_code:
        expired_query = expired_query.filter(StudentItem.join_code == join_code)
    if teacher_id:
        expired_query = expired_query.filter(StoreItem.teacher_id == teacher_id)

    expired_ids = [row.id for row in expired_query.all()]
    if not expired_ids:
        return 0

    deleted = StudentItem.query.filter(StudentItem.id.in_(expired_ids)).delete(synchronize_session=False)
    return int(deleted or 0)




# -------------------- PERIOD SELECTION HELPERS --------------------

def get_current_class_context():
    """Get the currently selected class context (join_code, teacher_id, block).

    CRITICAL: This function enforces proper multi-tenancy isolation by using
    join_code as the source of truth. Each join code represents a distinct
    class economy, even if they share the same teacher.

    Returns:
        dict with keys: join_code, teacher_id, block, seat_id
        None if no context available
    """
    if not has_request_context():
        return None

    if getattr(g, "_current_class_context_loaded", False):
        cached_context = getattr(g, "_current_class_context", None)
        return cached_context.copy() if isinstance(cached_context, dict) else cached_context

    from app.models import TeacherBlock

    student = get_logged_in_student()
    if not student:
        g._current_class_context = None
        g._current_class_context_loaded = True
        return None

    # Check if a join code is already selected in session
    current_join_code = session.get('current_join_code')

    # Get all claimed seats for this student
    claimed_seats = TeacherBlock.query.filter_by(
        student_id=student.id,
        is_claimed=True
    ).all()

    if not claimed_seats:
        g._current_class_context = None
        g._current_class_context_loaded = True
        return None

    # If no join code selected, default to first claimed seat
    if not current_join_code:
        first_seat = claimed_seats[0]
        current_join_code = first_seat.join_code
        # Store in session for future requests
        session['current_join_code'] = current_join_code

    # Find the seat matching current join code
    current_seat = next(
        (seat for seat in claimed_seats if seat.join_code == current_join_code),
        None
    )

    # If join code not found in student's seats, reset to first seat
    if not current_seat:
        current_seat = claimed_seats[0]
        session['current_join_code'] = current_seat.join_code

    # Return full class context
    context = {
        'join_code': current_seat.join_code,
        'teacher_id': current_seat.teacher_id,
        'block': current_seat.block,
        'seat_id': current_seat.id
    }
    g._current_class_context = context.copy()
    g._current_class_context_loaded = True
    return context.copy()


def _activate_rebalances_for_context(context=None):
    """Activate any due economy rebalances for the current (or given) class context."""
    if context is None:
        context = get_current_class_context()
    if context and context.get('teacher_id'):
        activate_due_rebalances(
            context['teacher_id'],
            block=(context.get('block') or '').strip().upper() or None,
        )
        db.session.commit()


def _issue_transfer_submission_token():
    """Create a one-time token for the transfer confirmation form."""
    token = secrets.token_urlsafe(32)
    existing_tokens = session.get(TRANSFER_SUBMISSION_TOKEN_KEY, [])
    if isinstance(existing_tokens, str):
        existing_tokens = [existing_tokens]
    elif not isinstance(existing_tokens, list):
        existing_tokens = []
    existing_tokens.append(token)
    session[TRANSFER_SUBMISSION_TOKEN_KEY] = existing_tokens[-TRANSFER_SUBMISSION_TOKEN_LIMIT:]
    return token


def _consume_transfer_submission_token(submitted_token):
    """Consume and validate a pending transfer submission token."""
    if not submitted_token:
        return False

    pending_tokens = session.get(TRANSFER_SUBMISSION_TOKEN_KEY, [])
    if isinstance(pending_tokens, str):
        pending_tokens = [pending_tokens]
    elif not isinstance(pending_tokens, list):
        pending_tokens = []

    for idx, expected_token in enumerate(pending_tokens):
        if secrets.compare_digest(expected_token, submitted_token):
            remaining_tokens = pending_tokens[:idx] + pending_tokens[idx + 1:]
            if remaining_tokens:
                session[TRANSFER_SUBMISSION_TOKEN_KEY] = remaining_tokens
            else:
                session.pop(TRANSFER_SUBMISSION_TOKEN_KEY, None)
            return True
    return False


def _prime_student_teacher_display_name_cache(student_id: int) -> None:
    """Cache decrypted teacher display names in session for this student session."""
    from app.models import TeacherBlock, Admin

    seats = TeacherBlock.query.filter_by(student_id=student_id, is_claimed=True).all()
    teacher_ids = sorted({seat.teacher_id for seat in seats if seat.teacher_id})
    if not teacher_ids:
        clear_teacher_display_name_cache()
        return

    cache_updates = {}
    for teacher in Admin.query.filter(Admin.id.in_(teacher_ids)).all():
        cache_updates[str(teacher.id)] = teacher.get_display_name()
    upsert_teacher_display_name_cache(cache_updates)


def get_rent_settings_for_context(context):
    """Return rent settings scoped to the current class context."""
    if not context:
        return None

    teacher_id = context.get('teacher_id')
    if not teacher_id:
        return None

    current_block = (context.get('block') or '').strip().upper()
    if current_block:
        settings = RentSettings.query.filter_by(
            teacher_id=teacher_id,
            block=current_block
        ).first()
        if settings:
            return settings

    return RentSettings.query.filter_by(teacher_id=teacher_id).first()


def get_current_teacher_id():
    """DEPRECATED: Get teacher_id from current class context.

    This function is maintained for backward compatibility but should be
    replaced with get_current_class_context() for proper multi-tenancy.
    """
    context = get_current_class_context()
    return context['teacher_id'] if context else None


def get_current_join_code():
    """Get the currently selected join code from class context.

    Join code is the absolute source of truth for class association.
    Returns None if no class context is available.
    """
    context = get_current_class_context()
    return context['join_code'] if context else None


def _insurance_next_payment_due(now_utc, charge_frequency):
    frequency = (charge_frequency or 'monthly').lower()
    if frequency == 'weekly':
        return now_utc + timedelta(days=7)
    if frequency == 'biweekly':
        return now_utc + timedelta(days=14)
    if frequency == 'semester':
        return now_utc + timedelta(days=7 * 16)
    return now_utc + timedelta(days=28)


def get_feature_settings_for_student():
    """
    Get feature settings for the currently logged-in student.

    Returns the merged feature settings for the student's current teacher/period context.
    Settings cascade: period-specific > global > system defaults.

    Returns:
        dict: Feature settings dictionary with enabled/disabled flags
    """
    student = get_logged_in_student()
    if not student:
        # Return defaults if no student logged in
        return FeatureSettings.get_defaults()

    context = get_current_class_context()
    if not context:
        return FeatureSettings.get_defaults()

    teacher_id = context.get('teacher_id')
    if not teacher_id:
        return FeatureSettings.get_defaults()

    current_block = (context.get('block') or '').strip().upper() or None

    # Try block-specific settings first
    if current_block:
        block_settings = FeatureSettings.query.filter(
            FeatureSettings.teacher_id == teacher_id,
            func.upper(FeatureSettings.block) == func.upper(current_block)
        ).first()
        if block_settings:
            return block_settings.to_dict()

    # Fall back to global settings for this teacher
    global_settings = FeatureSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None
    ).first()

    if global_settings:
        return global_settings.to_dict()

    # Return system defaults
    return FeatureSettings.get_defaults()


def is_feature_enabled(feature_name):
    """
    Check if a specific feature is enabled for the current student context.

    Args:
        feature_name: The feature to check (e.g., 'store', 'insurance', 'rent')

    Returns:
        bool: True if feature is enabled, False otherwise
    """
    if feature_name == 'rent':
        rent_settings = get_rent_settings_for_context(get_current_class_context())
        if rent_settings:
            return bool(rent_settings.is_enabled)

    settings = get_feature_settings_for_student()
    feature_key = f"{feature_name}_enabled"
    return settings.get(feature_key, True)  # Default to enabled


def calculate_scoped_balances(student: 'Student', join_code: str, teacher_id: int) -> tuple[Decimal, Decimal]:
    """Calculate checking and savings balances using the Ledger + Settlement model.
    
    This function:
    1. Triggers an eager settlement (if lock available) to ensure BalanceCache is up-to-date.
    2. Reads the posted balance from BalanceCache (O(1)).
    3. Adds any remaining pending transactions.
    
    Args:
        student (Student): Student object
        join_code (str): The join code for the current class context
        teacher_id (int): The teacher ID (kept for signature compatibility)
    
    Returns:
        tuple[Decimal, Decimal]: (checking_balance, savings_balance)
    """
    from app.models import BalanceCache, Transaction, TransactionStatus, _quantize_currency
    from app.utils.banking import settle_balances
    import logging
    
    logger = logging.getLogger(__name__)

    # Default to 0.00
    checking_balance = Decimal('0.00')
    savings_balance = Decimal('0.00')

    if not join_code:
        # Fallback for legacy calls without join_code (should be rare/non-existent)
        logger.warning(f"calculate_scoped_balances called without join_code for student {student.id}")
        return checking_balance, savings_balance

    # 1. Eager Settlement (Best Effort)
    try:
        settle_balances(student.id, join_code)
    except Exception as e:
        logger.warning(f"Eager settlement failed during read for student {student.id}: {e}")

    # 2. Read Posted Balance from Cache
    cache = BalanceCache.query.filter_by(student_id=student.id, join_code=join_code).first()
    if cache:
        checking_balance += Decimal(cache.posted_checking_balance_cents) / 100
        savings_balance += Decimal(cache.posted_savings_balance_cents) / 100
    else:
        # Legacy fallback for contexts not yet represented in BalanceCache.
        # Derive posted as (all non-void) - (pending) to avoid enum-label assumptions.
        all_checking = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.join_code == join_code,
            Transaction.account_type == 'checking',
            Transaction.is_void == False,
        ).scalar() or Decimal('0.00')
        pending_checking_fallback = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.join_code == join_code,
            Transaction.status == TransactionStatus.PENDING,
            Transaction.account_type == 'checking',
            Transaction.is_void == False,
        ).scalar() or Decimal('0.00')
        all_savings = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.join_code == join_code,
            Transaction.account_type == 'savings',
            Transaction.is_void == False,
        ).scalar() or Decimal('0.00')
        pending_savings_fallback = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.join_code == join_code,
            Transaction.status == TransactionStatus.PENDING,
            Transaction.account_type == 'savings',
            Transaction.is_void == False,
        ).scalar() or Decimal('0.00')
        posted_checking = all_checking - pending_checking_fallback
        posted_savings = all_savings - pending_savings_fallback
        checking_balance += posted_checking
        savings_balance += posted_savings

    # 3. Add Pending Transactions (aggregate in DB to avoid loading all rows)
    pending_checking = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.student_id == student.id,
        Transaction.join_code == join_code,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == 'checking',
        Transaction.is_void == False,
    ).scalar() or Decimal('0.00')

    pending_savings = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.student_id == student.id,
        Transaction.join_code == join_code,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == 'savings',
        Transaction.is_void == False,
    ).scalar() or Decimal('0.00')

    checking_balance += pending_checking
    savings_balance += pending_savings

    return _quantize_currency(checking_balance), _quantize_currency(savings_balance)


# -------------------- LEGACY PROFILE MIGRATION --------------------

@student_bp.before_request
def check_legacy_profile():
    """
    Check if logged-in student needs to complete legacy profile migration.
    
    Legacy students are those who:
    - have completed setup (has_completed_setup=True)
    - but are missing last_name_hash_by_part or dob_sum
    - and have not completed the migration (has_completed_profile_migration=False)
    """
    # Skip for non-student routes, login, logout, and profile completion itself
    excluded_endpoints = [
        'student.login', 'student.logout', 'student.complete_profile',
        'student.claim_account', 'student.create_username', 'student.setup_pin_passphrase',
        'student.demo_login', 'student.setup_complete', 'student.add_class',
        'student.migrate_username', 'student.confirm_migrated_username'
    ]
    
    # Skip if endpoint is None or not in student blueprint
    if not request.endpoint or not request.endpoint.startswith('student.'):
        return
    
    if request.endpoint in excluded_endpoints:
        return
    
    # Only check for logged-in students
    student = get_logged_in_student()
    
    if not student:
        return
    
    # Check if this is a legacy student needing profile migration
    needs_profile_migration = (
        student.has_completed_setup and
        not student.has_completed_profile_migration and
        (not student.last_name_hash_by_part or student.dob_sum is None)
    )
    
    if needs_profile_migration:
        return redirect(url_for('student.complete_profile'))

    # Check if this is a legacy student needing username migration
    if student.has_completed_setup and not student.username_migrated:
        return redirect(url_for('student.migrate_username'))


@student_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """
    One-time profile completion for legacy students missing last name and DOB.
    
    This route collects:
    - First name (editable, from existing)
    - Last name (new, required)
    - Date of birth (new, required)
    
    Then updates the student record with hashed values and regenerates credential hashes.
    """
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('student.login'))
    
    # Check if already completed migration
    if student.has_completed_profile_migration:
        flash("You have already completed your profile.", "info")
        return redirect(url_for('student.dashboard'))
    
    form = StudentCompleteProfileForm()
    
    # Handle form submission
    if form.validate_on_submit():
        step = request.form.get('step', 'confirm')
        
        # Get form data from WTForms
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()
        dob_month = form.dob_month.data
        dob_day = form.dob_day.data.strip()
        dob_year = form.dob_year.data.strip()
        
        # Validation
        if not all([first_name, last_name, dob_month, dob_day, dob_year]):
            flash("All fields are required.", "error")
            return redirect(url_for('student.complete_profile'))
        
        if not last_name:
            flash("Last name is required.", "error")
            return redirect(url_for('student.complete_profile'))
        
        try:
            month = int(dob_month)
            day = int(dob_day)
            year = int(dob_year)
            
            # Validate ranges
            current_year = utc_now().year
            if not (1 <= month <= 12):
                flash("Invalid month.", "error")
                return redirect(url_for('student.complete_profile'))
            if not (1 <= day <= 31):
                flash("Invalid day.", "error")
                return redirect(url_for('student.complete_profile'))
            # Students should be born between 1900 and (current year - 5) for elementary/middle school
            if not (1900 <= year <= current_year - 5):
                flash(f"Invalid year. Students should be born between 1900 and {current_year - 5}.", "error")
                return redirect(url_for('student.complete_profile'))
            
            # Validate that the date is real
            try:
                datetime(year, month, day)
            except ValueError:
                flash("Invalid date. Please check the month and day.", "error")
                return redirect(url_for('student.complete_profile'))
            
            # Calculate DOB sum
            dob_sum = month + day + year
            
        except (ValueError, TypeError):
            flash("Invalid date format.", "error")
            return redirect(url_for('student.complete_profile'))
        
        if step == 'confirm':
            # Show confirmation page
            month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            dob_display = f"{month_names[month]} {day}, {year}"
            current_year = utc_now().year
            max_birth_year = current_year - 5
            
            return render_template(
                'student_complete_profile.html',
                current_page='profile',
                page_title='Complete Profile',
                form=form,
                student=student,
                confirmed=True,
                max_birth_year=max_birth_year,
                confirm_data={
                    'first_name': first_name,
                    'last_name': last_name,
                    'dob_month': dob_month,
                    'dob_day': dob_day,
                    'dob_year': dob_year,
                    'dob_display': dob_display
                }
            )
        
        elif step == 'submit':
            # Final submission - update student record
            try:
                # Recalculate dob_sum for submit step (needed since it's only calculated in confirm step's try block)
                # This prevents NameError when submitting the form
                month = int(dob_month)
                day = int(dob_day)
                year = int(dob_year)
                dob_sum = month + day + year
                
                # Update first name (encrypted)
                student.first_name = first_name
                
                # Update last initial from last name (already validated to not be empty)
                student.last_initial = last_name[0].upper()
                
                # Calculate and store DOB sum
                student.dob_sum = dob_sum
                
                # Generate last_name_hash_by_part
                student.last_name_hash_by_part = hash_last_name_parts(last_name, student.salt)
                
                # Regenerate first_half_hash using first initial + dob_sum
                first_initial_char = first_name[0].upper() if first_name else ''
                student.first_half_hash = compute_primary_claim_hash(first_initial_char, dob_sum, student.salt)
                
                # Regenerate second_half_hash using just dob_sum
                dob_sum_str = str(dob_sum)
                student.second_half_hash = hash_hmac(dob_sum_str.encode('utf-8'), student.salt)
                
                # Mark migration as completed
                student.has_completed_profile_migration = True

                # Update all TeacherBlock entries for this student with new hashes
                from app.models import TeacherBlock
                teacher_blocks = TeacherBlock.query.filter_by(student_id=student.id).all()
                for block in teacher_blocks:
                    block.last_name_hash_by_part = student.last_name_hash_by_part
                    block.first_half_hash = student.first_half_hash
                    block.last_initial = student.last_initial

                # Post-migration PII cleanup: dob_sum and last_name_hash_by_part are no
                # longer needed on the student record now that hashes are propagated to
                # TeacherBlock. Mirrors the cleanup done in setup_pin_passphrase.
                student.dob_sum = None
                student.last_name_hash_by_part = None
                
                db.session.commit()
                
                flash("Profile completed successfully! Thank you.", "success")
                return redirect(url_for('student.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error completing profile for student {student.id}: {str(e)}")
                flash("An error occurred. Please try again.", "error")
                return redirect(url_for('student.complete_profile'))
    
    # GET request - show form
    current_year = utc_now().year
    max_birth_year = current_year - 5  # Students should be at least 5 years old
    
    return render_template(
        'student_complete_profile.html',
        current_page='profile',
        page_title='Complete Profile',
        form=form,
        student=student,
        confirmed=False,
        max_birth_year=max_birth_year
    )


# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
def claim_account():
    """
    PAGE 1: Claim Account - Verify identity using join code to begin setup.

    New join code-based flow:
    1. Student enters join code (identifies their teacher-period)
    2. Student enters name code + DOB sum
    3. System finds matching unclaimed seat in TeacherBlock
    4. Creates Student record (or finds existing if student has other classes)
    5. Links TeacherBlock seat to Student
    6. Creates StudentTeacher link
    """
    from app.models import TeacherBlock, StudentTeacher
    from app.utils.join_code import format_join_code

    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        join_code = format_join_code(form.join_code.data)
        first_initial = form.first_initial.data.strip().upper()
        last_name = form.last_name.data.strip()
        dob_input = form.dob_sum.data

        try:
            if isinstance(dob_input, str):
                dob_input = dob_input.strip()
                dob_input = datetime.strptime(dob_input, "%Y-%m-%d").date()
            dob_sum = dob_input.month + dob_input.day + dob_input.year
        except (ValueError, AttributeError, TypeError):
            flash("Please enter a valid birth date.", "claim")
            return redirect(url_for('student.claim_account'))

        # Find all unclaimed seats with this join code
        unclaimed_seats = TeacherBlock.query.filter_by(
            join_code=join_code,
            is_claimed=False
        ).all()

        if not unclaimed_seats:
            current_app.logger.warning(
                f"Claim attempt failed: No unclaimed seats for join_code={join_code}"
            )
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "claim")
            return redirect(url_for('student.claim_account'))

        # Try to find a matching seat
        from app.utils.name_utils import verify_last_name_parts

        matched_seat = None
        match_attempts = []  # Track why each seat didn't match

        for seat in unclaimed_seats:
            credential_matches, matched_primary, canonical_hash = match_claim_hash(
                seat.first_half_hash,
                first_initial,
                seat.last_initial,
                seat.dob_sum,
                seat.salt,
            )

            # Check last name with fuzzy matching
            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )

            # Track match details for debugging — deliberately omit raw dob_sum
            # values to prevent PII from persisting in application logs.
            dob_sum_matches = seat.dob_sum == dob_sum
            match_attempts.append({
                'seat_id': seat.id,
                'credential_matches': credential_matches,
                'last_name_matches': last_name_matches,
                'dob_sum_matches': dob_sum_matches,
            })

            if credential_matches and last_name_matches and dob_sum_matches:
                if canonical_hash and not matched_primary:
                    seat.first_half_hash = canonical_hash
                matched_seat = seat
                break

        if not matched_seat:
            # Log detailed match failure information
            current_app.logger.warning(
                f"Claim attempt failed for join_code={join_code}, "
                f"first_initial={first_initial}, with last_name from input. "
                f"Attempted {len(match_attempts)} seat(s). Match details: {match_attempts}"
            )
            flash("No matching account found. Please check your join code and credentials.", "claim")
            return redirect(url_for('student.claim_account'))

        # Check if this student already has an account (claiming from another teacher).
        # Use first_half_hash for matching — it stays set even after dob_sum is cleaned up
        # post-claim, so this lookup works regardless of cleanup state.
        existing_student = Student.query.filter_by(
            first_half_hash=matched_seat.first_half_hash
        ).first()

        if existing_student:
            # Student already exists - link this seat to existing student
            matched_seat.student_id = existing_student.id
            matched_seat.is_claimed = True
            matched_seat.claimed_at = utc_now()
            # Null out PII on the now-claimed seat — no longer needed for matching
            matched_seat.dob_sum = None
            matched_seat.last_name_hash_by_part = None

            # Create StudentTeacher link
            existing_link = StudentTeacher.query.filter_by(
                student_id=existing_student.id,
                admin_id=matched_seat.teacher_id
            ).first()

            if not existing_link:
                link = StudentTeacher(
                    student_id=existing_student.id,
                    admin_id=matched_seat.teacher_id
                )
                db.session.add(link)

            db.session.commit()

            # Student already completed setup in another class, redirect to login
            if existing_student.has_completed_setup:
                flash("This seat has been linked to your existing account. Please log in.", "claim")
                return redirect(url_for('student.login'))
            else:
                # Continue setup process
                session['claimed_student_id'] = existing_student.id
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)
                return redirect(url_for('student.create_username'))

        # New student - create Student record
        # Generate second_half_hash (DOB hash) for backward compatibility
        second_half_hash = hash_hmac(str(dob_sum).encode(), matched_seat.salt)

        new_student = Student(
            first_name=matched_seat.first_name,
            last_initial=matched_seat.last_initial,
            block=matched_seat.block,
            salt=matched_seat.salt,
            first_half_hash=matched_seat.first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=matched_seat.dob_sum,
            last_name_hash_by_part=matched_seat.last_name_hash_by_part,
            has_completed_setup=False,
            is_teacher=matched_seat.is_teacher,
        )
        db.session.add(new_student)

        try:
            db.session.flush()  # Get student ID
        except IntegrityError:
            # Handle duplicate first_half_hash - student already exists but wasn't found
            # by the deduplication logic above (edge case with different field combinations)
            db.session.rollback()

            # Look up the existing student directly by first_half_hash
            existing_by_hash = Student.query.filter_by(
                first_half_hash=matched_seat.first_half_hash
            ).first()

            if existing_by_hash:
                # Link this seat to the existing student
                matched_seat.student_id = existing_by_hash.id
                matched_seat.is_claimed = True
                matched_seat.claimed_at = utc_now()
                # Null out PII on the now-claimed seat
                matched_seat.dob_sum = None
                matched_seat.last_name_hash_by_part = None

                # Create StudentTeacher link if not exists
                existing_link = StudentTeacher.query.filter_by(
                    student_id=existing_by_hash.id,
                    admin_id=matched_seat.teacher_id
                ).first()

                if not existing_link:
                    link = StudentTeacher(
                        student_id=existing_by_hash.id,
                        admin_id=matched_seat.teacher_id
                    )
                    db.session.add(link)

                db.session.commit()

                if existing_by_hash.has_completed_setup:
                    flash("This seat has been linked to your existing account. Please log in.", "claim")
                    return redirect(url_for('student.login'))
                else:
                    session['claimed_student_id'] = existing_by_hash.id
                    session.pop('generated_username', None)
                    session.pop('theme_prompt', None)
                    session.pop('theme_slug', None)
                    return redirect(url_for('student.create_username'))
            else:
                # Unexpected state - constraint violation but no matching student found
                current_app.logger.error(
                    f"IntegrityError on first_half_hash but no matching student found. "
                    f"Seat ID: {matched_seat.id}, Hash: {matched_seat.first_half_hash[:16]}..."
                )
                flash("An error occurred while claiming your account. Please try again.", "danger")
                return redirect(url_for('student.claim_account'))

        # Link seat to student
        matched_seat.student_id = new_student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = utc_now()
        # Null out PII on the now-claimed seat — the student record carries dob_sum
        # through the setup flow; it will be nulled on the student record itself
        # after setup completes in setup_pin_passphrase.
        matched_seat.dob_sum = None
        matched_seat.last_name_hash_by_part = None

        # Create StudentTeacher link
        link = StudentTeacher(
            student_id=new_student.id,
            admin_id=matched_seat.teacher_id
        )
        db.session.add(link)
        db.session.commit()

        # Start setup flow
        session['claimed_student_id'] = new_student.id
        session.pop('generated_username', None)
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)

        return redirect(url_for('student.create_username'))

    return render_template('student_account_claim.html', form=form)


@student_bp.route('/create-username', methods=['GET', 'POST'])
def create_username():
    """PAGE 2: Create Username - Generate themed username."""
    # Only allow if claimed
    student_id = session.get('claimed_student_id')
    if not student_id:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student.claim_account'))
    student = db.session.get(Student, student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    # Assign a random theme prompt if not yet in session
    if 'theme_prompt' not in session:
        selected_theme = random.choice(THEME_PROMPTS)
        session['theme_slug'] = selected_theme['slug']
        session['theme_prompt'] = selected_theme['prompt']
    form = StudentCreateUsernameForm()
    if form.validate_on_submit():
        write_in_word = form.write_in_word.data.strip().lower()
        if not write_in_word.isalpha() or len(write_in_word) < 3 or len(write_in_word) > 12:
            flash("Please enter a valid word (3-12 letters, no numbers or spaces).", "setup")
            return redirect(url_for('student.create_username'))
        username = _generate_unique_student_username(write_in_word, student.first_name, student.last_initial)
        # Save username plaintext in session for display
        session['generated_username'] = username
        # Hash and store in DB; mark as using the new PII-free username format
        student.username_hash = hash_username(username, student.salt)
        student.username_lookup_hash = hash_username_lookup(username)
        student.username_migrated = True

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current_app.logger.error(f"IntegrityError during username creation for student {student_id}")
            flash("An error occurred while generating your username. Please try again.", "setup")
            return redirect(url_for('student.create_username'))

        # Clear theme prompt from session
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)


@student_bp.route('/setup-pin-passphrase', methods=['GET', 'POST'])
def setup_pin_passphrase():
    """PAGE 3: Setup PIN & Passphrase - Secure the account."""
    # Only allow if claimed and username generated
    student_id = session.get('claimed_student_id')
    username = session.get('generated_username')
    if not student_id or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student.claim_account'))
    student = db.session.get(Student, student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    form = StudentPinPassphraseForm()
    if form.validate_on_submit():
        pin = form.pin.data
        passphrase = form.passphrase.data
        if not pin or not passphrase:
            flash("PIN and passphrase are required.", "setup")
            return redirect(url_for('student.setup_pin_passphrase'))
        # Save credentials (store passphrase as hash)
        student.pin_hash = generate_password_hash(pin)
        student.passphrase_hash = generate_password_hash(passphrase)
        student.has_completed_setup = True
        if student.recovery_status == 'to_be_claimed':
            # Complete recovery only after credentials are successfully re-established.
            student.reset_code = None
            student.reset_code_expires_at = None
            student.recovery_status = 'active'

        # Post-claim PII cleanup: dob_sum and last_name_hash_by_part are no longer
        # needed on the student record after setup is complete. Clear them to minimise
        # the PII footprint. has_completed_profile_migration is set to True so the
        # legacy migration gate does not incorrectly redirect this student.
        student.dob_sum = None
        student.last_name_hash_by_part = None
        student.has_completed_profile_migration = True

        db.session.commit()
        # Clear session onboarding keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('student.setup_complete'))
    return render_template('student_pin_setup.html', username=username, form=form)


# -------------------- USERNAME MIGRATION --------------------

@student_bp.route('/migrate-username', methods=['GET', 'POST'])
def migrate_username():
    """One-time migration: let students with legacy DOB-embedded usernames pick a
    new theme word and receive a fresh username that uses a random 4-digit suffix
    instead of their date-of-birth sum.

    Accessible only to logged-in students whose username_migrated flag is False.
    """
    student_id = session.get('student_id')
    if not student_id:
        return redirect(url_for('student.login'))

    student = db.session.get(Student, student_id)
    if not student or not student.has_completed_setup:
        return redirect(url_for('student.login'))

    # Already migrated — nothing to do
    if student.username_migrated:
        return redirect(url_for('student.dashboard'))

    form = StudentCreateUsernameForm()

    if 'theme_prompt' not in session:
        selected_theme = random.choice(THEME_PROMPTS)
        session['theme_slug'] = selected_theme['slug']
        session['theme_prompt'] = selected_theme['prompt']

    if form.validate_on_submit():
        write_in_word = form.write_in_word.data.strip().lower()
        if not write_in_word.isalpha() or len(write_in_word) < 3 or len(write_in_word) > 12:
            flash("Please enter a valid word (3-12 letters, no numbers or spaces).", "migration")
            return redirect(url_for('student.migrate_username'))

        new_username = _generate_unique_student_username(write_in_word, student.first_name, student.last_initial)

        session['migration_username'] = new_username
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.confirm_migrated_username'))

    return render_template(
        'student_migrate_username.html',
        theme_prompt=session['theme_prompt'],
        form=form,
    )


@student_bp.route('/confirm-username-migration', methods=['GET', 'POST'])
def confirm_migrated_username():
    """Show the newly generated username to the student and, after they confirm
    they have written it down, commit the new hashes and mark migration complete.
    """
    student_id = session.get('student_id')
    new_username = session.get('migration_username')

    if not student_id or not new_username:
        return redirect(url_for('student.migrate_username'))

    student = db.session.get(Student, student_id)
    if not student or student.username_migrated:
        session.pop('migration_username', None)
        return redirect(url_for('student.dashboard'))

    form = StudentConfirmMigratedUsernameForm()

    if form.validate_on_submit():
        student.username_hash = hash_username(new_username, student.salt)
        student.username_lookup_hash = hash_username_lookup(new_username)
        student.username_migrated = True
        # Post-migration PII cleanup: dob_sum and last_name_hash_by_part are no longer
        # needed for account recovery or matching once the student has a new secure username.
        # This matches the cleanup behavior in standard account setup.
        student.dob_sum = None
        student.last_name_hash_by_part = None
        
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current_app.logger.error(f"IntegrityError during username migration for student {student_id}")
            session.pop('migration_username', None)
            flash("That username is no longer available. Please try the migration again.", "error")
            return redirect(url_for('student.migrate_username'))

        session.pop('migration_username', None)
        flash("Your username has been updated. Use your new username next time you log in.", "success")
        return redirect(url_for('student.dashboard'))

    return render_template(
        'student_confirm_migrated_username.html',
        username=new_username,
        form=form,
    )


# -------------------- ADD NEW CLASS --------------------

@student_bp.route('/add-class', methods=['GET', 'POST'])
@login_required
def add_class():
    """
    Allow logged-in students to add a new class by entering a join code.

    Each join_code is an independent scoped universe. Credentials entered here
    are matched against the *new* class's own unclaimed roster seat, which still
    carries its own verification hashes (dob_sum, last_name_hash_by_part).
    Those hashes are deleted from the seat after it is claimed.

    Note: The student's own account has no stored dob_sum or last_name_hash_by_part
    after their first claim completes (post-claim PII cleanup). This is intentional —
    we verify credentials against the target class's seat, not the student account.
    A name cross-check (encrypted first_name + last_initial) ensures the entered
    credentials correspond to a seat belonging to this student.
    """
    from app.models import TeacherBlock, StudentTeacher
    from app.utils.join_code import format_join_code
    from app.forms import StudentAddClassForm
    from app.utils.name_utils import verify_last_name_parts

    student = get_logged_in_student()
    form = StudentAddClassForm()

    def _is_safe_url(target: str) -> bool:
        """
        Wrapper around the shared is_safe_url helper to make the sanitizer
        explicit within this view. Ensures that only same-origin or relative
        URLs are treated as safe redirect targets.
        """
        try:
            return bool(target) and is_safe_url(target)
        except Exception:
            # In case the helper raises for malformed URLs, treat as unsafe.
            return False

    def _get_return_target(default_endpoint: str = 'student.dashboard'):
        """
        Return the safest place to redirect back to after add-class attempts.

        Prioritize an explicit `next` value, fall back to referrer, then dashboard.

        Security: All redirect targets are validated with _is_safe_url() and
        additionally restricted to internal, relative URLs (no scheme or host)
        to prevent open redirect vulnerabilities.
        """
        def _normalize_and_validate_internal_target(raw_target: str) -> str | None:
            """
            Ensure the target is an internal relative URL:
            - strip backslashes, which some browsers treat like slashes
            - disallow any scheme or netloc
            Returns the cleaned path if valid, otherwise None.
            """
            if not raw_target:
                return None
            # Normalize backslashes to reduce browser inconsistencies
            cleaned = raw_target.replace('\\', '')
            parsed = urlparse(cleaned)
            # Require relative URL: no scheme and no netloc
            if parsed.scheme or parsed.netloc:
                return None
            return cleaned

        # 1) Explicit next parameter (form or query string)
        next_url = request.form.get('next') or request.args.get('next')
        if next_url and _is_safe_url(next_url):
            internal_next = _normalize_and_validate_internal_target(next_url)
            if internal_next:
                return internal_next

        # 2) Referrer header, after validation
        ref_url = request.referrer
        if ref_url and _is_safe_url(ref_url):
            internal_ref = _normalize_and_validate_internal_target(ref_url)
            if internal_ref:
                return internal_ref

        # 3) Safe fallback: always use internal route
        return url_for(default_endpoint)

    if form.validate_on_submit():
        join_code = format_join_code(form.join_code.data)
        first_initial = form.first_initial.data.strip().upper()
        last_name = form.last_name.data.strip()
        dob_input = form.dob_sum.data

        # Parse DOB and calculate sum
        try:
            if isinstance(dob_input, str):
                dob_input = dob_input.strip()
                dob_input = datetime.strptime(dob_input, "%Y-%m-%d").date()
            dob_sum = dob_input.month + dob_input.day + dob_input.year
        except (ValueError, AttributeError, TypeError):
            flash("Invalid date of birth. Please enter a valid date.", "danger")
            return redirect(_get_return_target())  # nosec # Safe: validated by _is_safe_url() with same-origin check

        # Find all unclaimed seats with this join code
        unclaimed_seats = TeacherBlock.query.filter_by(
            join_code=join_code,
            is_claimed=False
        ).all()

        if not unclaimed_seats:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "danger")
            return redirect(_get_return_target())  # nosec # Safe: validated by _is_safe_url() with same-origin check

        # Verify credentials against the new class's own seat hashes (per-seat scoping).
        # The student's account does not store dob_sum or last_name_hash_by_part after
        # their initial claim completes. Verification uses the target seat's hashes only.
        matched_seat = None
        for seat in unclaimed_seats:
            credential_matches, matched_primary, canonical_hash = match_claim_hash(
                seat.first_half_hash,
                first_initial,
                seat.last_initial,
                seat.dob_sum,
                seat.salt,
            )

            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )

            # Cross-check: ensure the seat belongs to this authenticated student
            # (encrypted first_name + last_initial comparison).
            name_matches = (
                seat.first_name == student.first_name
                and seat.last_initial == student.last_initial
            )

            if credential_matches and last_name_matches and name_matches and seat.dob_sum == dob_sum:
                if canonical_hash and not matched_primary:
                    seat.first_half_hash = canonical_hash
                matched_seat = seat
                break

        if not matched_seat:
            flash("No matching seat found. Please verify your join code and credentials with your teacher.", "danger")
            return redirect(_get_return_target())  # nosec # Safe: validated by _is_safe_url() with same-origin check

        # Check if student is already linked to this teacher's block
        existing_link = StudentTeacher.query.filter_by(
            student_id=student.id,
            admin_id=matched_seat.teacher_id
        ).first()

        if existing_link:
            current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            new_block_check = matched_seat.block.strip().upper()
            if new_block_check in current_blocks:
                flash(f"You are already enrolled in Block {new_block_check}.", "warning")
                return redirect(_get_return_target())

        # Link the seat to the student and null out its PII (no longer needed post-claim)
        matched_seat.student_id = student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = utc_now()
        matched_seat.dob_sum = None
        matched_seat.last_name_hash_by_part = None

        # Create StudentTeacher link if it doesn't exist
        if not existing_link:
            link = StudentTeacher(
                student_id=student.id,
                admin_id=matched_seat.teacher_id
            )
            db.session.add(link)

        # Update student's block to include the new block if not already there
        current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        new_block = matched_seat.block.strip().upper()

        if new_block not in current_blocks:
            current_blocks.append(new_block)
            student.block = ','.join(sorted(current_blocks))

        try:
            db.session.commit()
            flash(f"Successfully added to Block {new_block}! You can now access this class from your dashboard.", "success")
            return redirect(_get_return_target())
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding class for student {student.id}: {str(e)}")
            flash("An error occurred while adding the class. Please try again or contact your teacher.", "danger")
            return redirect(_get_return_target())

    return render_template('student_add_class.html', form=form)


# -------------------- STUDENT DASHBOARD --------------------

@student_bp.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard with balance, attendance, transactions, and quick actions."""
    student = get_logged_in_student()

    # CRITICAL FIX v2: Use join_code as source of truth (not just teacher_id)
    # This properly isolates same-teacher, different-period classes
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.login'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']
    current_block = context['block']  # Get current class block

    expired_rent_perks_cleared = _clear_expired_rent_perk_items(
        student.id,
        join_code=join_code,
        teacher_id=teacher_id,
    )
    if expired_rent_perks_cleared:
        db.session.commit()

    _, _, hall_pass_reconciled = _ensure_rent_hall_pass_top_off(student, context)
    if hall_pass_reconciled:
        db.session.commit()

    apply_savings_interest(student)  # Apply savings interest if not already applied

    # CRITICAL FIX: Filter transactions by join_code (not just teacher_id)
    # This ensures Period A and Period B with same teacher are isolated
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code  # FIX: Use join_code for proper isolation
    ).order_by(Transaction.timestamp.desc()).all()

    # FIX: Filter student items by current teacher's store
    student_items = student.items.join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        StoreItem.teacher_id == teacher_id
    ).order_by(StudentItem.purchase_date.desc()).all()

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    # CRITICAL FIX: Calculate balances using join_code scoping
    # Sum only transactions for THIS specific class (join_code)
    from app.models import _quantize_currency
    
    checking_balance = _quantize_currency(sum(
        (tx.amount for tx in student.transactions
        if tx.account_type == 'checking' and not tx.is_void and tx.join_code == join_code),
        Decimal('0.00')
    ))
    savings_balance = _quantize_currency(sum(
        (tx.amount for tx in student.transactions
        if tx.account_type == 'savings' and not tx.is_void and tx.join_code == join_code),
        Decimal('0.00')
    ))
    # Calculate forecast interest using Decimal
    forecast_interest = _quantize_currency(savings_balance * Decimal('0.045') / Decimal('12'))

    # FIX: Only show tap in/out status for CURRENT class, not all classes
    # Get status for only the current block (not all blocks)
    period_states = get_all_block_statuses(student, join_code=join_code)
    # Filter to only current class block
    period_states = {current_block.upper(): period_states.get(current_block.upper(), {})}
    student_blocks = [current_block.upper()]  # Only current block

    # Convert Decimal values to float for JSON serialization
    for state in period_states.values():
        if 'projected_pay' in state and state['projected_pay'] is not None:
            state['projected_pay'] = float(state['projected_pay'])

    period_states_json = json.dumps(period_states, separators=(',', ':'))

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: state.get("projected_pay", 0)
        for blk, state in period_states.items()
    }

    # Compute total unpaid seconds and format as HH:MM:SS for display
    total_unpaid_seconds = sum(unpaid_seconds_per_block.values())
    hours, remainder = divmod(total_unpaid_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    total_unpaid_elapsed = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    student_name = student.full_name

    # Compute most recent deposit and insurance paid flag
    recent_deposit = student.recent_deposits[0] if student.recent_deposits else None

    # Track seen deposits in session to show notification only once
    if 'seen_deposit_ids' not in session:
        session['seen_deposit_ids'] = []

    # Only show deposit if it hasn't been seen yet
    if recent_deposit and recent_deposit.id not in session['seen_deposit_ids']:
        # Mark as seen
        session['seen_deposit_ids'].append(recent_deposit.id)
        session.modified = True
        # Keep only last 10 seen deposit IDs to prevent session bloat
        session['seen_deposit_ids'] = session['seen_deposit_ids'][-10:]
    else:
        # Don't show if already seen
        recent_deposit = None

    # Get student's active insurance policies (scoped to current class)
    context = get_current_class_context()
    teacher_id = context['teacher_id'] if context else None
    active_insurance = student.get_active_insurance(teacher_id)

    rent_status = None
    rent_settings = get_rent_settings_for_context(context)
    if rent_settings and rent_settings.is_enabled and student.is_rent_enabled:
        now = utc_now()
        timeline = _calculate_rent_timeline(rent_settings, now)
        due_date = timeline['due_date']
        grace_end_date = timeline['grace_end_date']
        coverage_due_date = timeline['coverage_due_date']
        upcoming_due_date = timeline['upcoming_due_date']
        preview_start_date = timeline['preview_start_date']
        rent_is_active = timeline['rent_is_active']
        is_preview_period = timeline['is_preview_period_candidate']

        rent_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]

        # Calculate coverage period for pre-paid system
        if is_preview_period:
            coverage_month = upcoming_due_date.month
            coverage_year = upcoming_due_date.year
            grace_end_date_for_status = upcoming_due_date + timedelta(days=rent_settings.grace_period_days)
        else:
            coverage_month = coverage_due_date.month if coverage_due_date else upcoming_due_date.month
            coverage_year = coverage_due_date.year if coverage_due_date else upcoming_due_date.year
            grace_end_date_for_status = (coverage_due_date + timedelta(days=rent_settings.grace_period_days)) if coverage_due_date else grace_end_date

        all_paid = True
        for period in rent_blocks:
            all_payments_for_period = RentPayment.query.filter(
                RentPayment.student_id == student.id,
                RentPayment.period == period,
                RentPayment.coverage_month == coverage_month,
                RentPayment.coverage_year == coverage_year,
                RentPayment.join_code == join_code
            ).all()

            payments = _filter_valid_rent_payments(all_payments_for_period, student.id, join_code)

            total_paid = sum(p.amount_paid for p in payments) if payments else Decimal('0.00')
            paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
            effective_rent_amount = _get_effective_rent_amount_for_coverage_period(
                rent_settings,
                payments,
                coverage_due_date,
                join_code=join_code,
            )
            late_fee = Decimal('0.00')
            if rent_is_active and now > grace_end_date_for_status and paid_by_grace < effective_rent_amount:
                late_fee = rent_settings.late_fee
            total_due = effective_rent_amount + late_fee if rent_is_active else Decimal('0.00')
            is_paid = total_paid >= total_due if rent_is_active else False

            if rent_is_active and not is_paid:
                all_paid = False
                break

        rent_status = {
            'is_active': rent_is_active,
            'is_paid': all_paid if rent_is_active else False,
            'is_preview': is_preview_period
        }

    tz = pytz.timezone('America/Los_Angeles')
    local_now = utc_now().astimezone(tz)
    # --- DASHBOARD DEBUG LOGGING ---
    current_app.logger.info(f"DASHBOARD DEBUG: Student {student.id} - Block states:")
    for blk, blk_state in period_states.items():
        active = blk_state.get("active")
        done = blk_state.get("done")
        seconds = blk_state.get("duration")
        current_app.logger.info(f"Block {blk} => DB Active={active}, Done={done}, Seconds (today)={seconds}, Total Unpaid Seconds={unpaid_seconds_per_block.get(blk, 0)}")


    # --- Calculate remaining session time for frontend timer ---
    login_time = datetime.fromisoformat(session['login_time'])
    expiry_time = login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    session_remaining_seconds = max(0, int((expiry_time - utc_now()).total_seconds()))

    # --- Get feature settings for this student ---
    feature_settings = get_feature_settings_for_student()

    # --- Check for pending recovery request ---
    from app.models import StudentRecoveryCode, RecoveryRequest
    pending_recovery_code = StudentRecoveryCode.query.join(
        RecoveryRequest
    ).filter(
        StudentRecoveryCode.student_id == student.id,
        StudentRecoveryCode.dismissed == False,
        StudentRecoveryCode.code_hash == None,  # Not yet verified
        RecoveryRequest.status == 'pending',
        RecoveryRequest.expires_at > utc_now()
    ).first()

    # --- Calculate weekly/monthly analytics ---
    from app.models import TapEvent
    now_utc = utc_now()
    week_start = now_utc - timedelta(days=now_utc.weekday())  # Monday of current week
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)



    # Days tapped in this week
    tap_events_this_week = TapEvent.query.filter(
        TapEvent.student_id == student.id,
        TapEvent.join_code == join_code,
        TapEvent.timestamp >= week_start,
        TapEvent.is_deleted == False
    ).all()

    # Calculate unique days and total minutes
    unique_days_tapped = len(set(ensure_utc(event.timestamp).date() for event in tap_events_this_week if event.status == 'active'))

    # Calculate total minutes this week
    total_minutes_this_week = 0
    active_sessions = {}  # Track active tap-in per period

    for event in sorted(tap_events_this_week, key=lambda e: e.timestamp):
        period = event.period
        event_ts = ensure_utc(event.timestamp)
        if event.status == 'active':
            active_sessions[period] = event_ts
        elif event.status == 'inactive' and period in active_sessions:
            duration = (event_ts - active_sessions[period]).total_seconds() / 60
            total_minutes_this_week += duration
            del active_sessions[period]

    # Add ongoing sessions (still active)
    for start_time in active_sessions.values():
        duration = (now_utc - start_time).total_seconds() / 60
        total_minutes_this_week += duration

    def _occurred_after(ts, start):
        ts_utc = ensure_utc(ts)
        return ts_utc is not None and ts_utc >= start

    # Earnings this week/month
    # FIX: Add null check to prevent decimal.InvalidOperation on corrupted data
    earnings_this_week = sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount > Decimal('0') and _occurred_after(tx.timestamp, week_start) and not tx.is_void),
        Decimal('0.00')
    )
    earnings_this_month = sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount > Decimal('0') and _occurred_after(tx.timestamp, month_start) and not tx.is_void),
        Decimal('0.00')
    )

    # Spending this week/month
    # FIX: Add null check to prevent decimal.InvalidOperation on corrupted data
    spending_this_week = abs(sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount < Decimal('0') and _occurred_after(tx.timestamp, week_start) and not tx.is_void),
        Decimal('0.00')
    ))
    spending_this_month = abs(sum(
        (tx.amount for tx in transactions
        if tx.amount is not None and tx.amount < Decimal('0') and _occurred_after(tx.timestamp, month_start) and not tx.is_void),
        Decimal('0.00')
    ))

    # Get active announcements for this student
    # Include: class-specific, system-wide, all students, and teacher's all classes
    from app.models import Announcement

    announcements = Announcement.query.filter(
        Announcement.is_active.is_(True),
        or_(
            Announcement.expires_at.is_(None),
            Announcement.expires_at > utc_now()
        ),
        or_(
            # Class-specific announcements
            Announcement.join_code == join_code,
            # System-wide announcements
            Announcement.audience_type == 'system_wide',
            # All students announcements
            Announcement.audience_type == 'all_students',
            # Teacher's all classes announcements
            (Announcement.audience_type == 'teacher_all_classes') & (Announcement.target_teacher_id == teacher_id)
        )
    ).order_by(Announcement.created_at.desc()).all()

    return render_template(
        'student_dashboard.html',
        student=student,
        session_remaining_seconds=session_remaining_seconds,
        student_blocks=student_blocks,
        period_states=period_states,
        period_states_json=period_states_json,
        checking_transactions=checking_transactions,
        savings_transactions=savings_transactions,
        student_items=student_items,
        recent_transactions=transactions[:5],  # Most recent 5 transactions
        now=local_now,
        forecast_interest=float(forecast_interest),
        recent_deposit=recent_deposit,
        active_insurance=active_insurance,
        rent_status=rent_status,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block={blk: float(pay or 0) for blk, pay in projected_pay_per_block.items()},
        student_name=student_name,
        total_unpaid_elapsed=total_unpaid_elapsed,
        feature_settings=feature_settings,
        # FIX: Pass scoped balances to template instead of using unscoped properties
        checking_balance=float(checking_balance),
        savings_balance=float(savings_balance),
        teacher_id=teacher_id,
        pending_recovery_code=pending_recovery_code,
        # Weekly/monthly analytics
        unique_days_tapped=unique_days_tapped,
        total_minutes_this_week=int(total_minutes_this_week),
        earnings_this_week=float(round(earnings_this_week, 2)),
        earnings_this_month=float(round(earnings_this_month, 2)),
        spending_this_week=float(round(spending_this_week, 2)),
        spending_this_month=float(round(spending_this_month, 2)),
        announcements=announcements,
    )


@student_bp.route('/payroll')
@login_required
def payroll():
    """Student payroll page with attendance record, productivity stats, and projected pay."""
    # Check if payroll feature is enabled
    if not is_feature_enabled('payroll'):
        flash("The payroll feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    current_block = (context.get('block') or '').upper()
    join_code = context.get('join_code')
    teacher_id = context.get('teacher_id')
    period_states = get_all_block_statuses(student, join_code=join_code)

    # Scope dashboard data to the selected class context only
    period_states = {current_block: period_states.get(current_block, {})}
    student_blocks = [current_block]

    # Determine the pay rate for the current block (per minute)
    pay_rate_per_second = get_pay_rate_for_block(current_block, teacher_id=teacher_id)
    pay_rate_per_minute = round(pay_rate_per_second * 60, 2)

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: round(state.get("projected_pay", 0), 2)
        for blk, state in period_states.items()
    }

    # Get all tap events grouped by block (scoped to the current class when available)
    # Limit to 20 most recent events to improve performance (template only displays 20)
    tap_query = TapEvent.query.filter_by(
        student_id=student.id,
        period=current_block,
        join_code=join_code
    )

    all_tap_events = tap_query.order_by(TapEvent.timestamp.desc()).limit(20).all()
    tap_events_by_block = {}
    for event in all_tap_events:
        # Normalize to the action labels used by the template
        event.action = 'start_work' if event.status == 'active' else 'stop_work'
        if event.period not in tap_events_by_block:
            tap_events_by_block[event.period] = []
        tap_events_by_block[event.period].append(event)

    return render_template(
        'student_payroll.html',
        student=student,
        student_blocks=student_blocks,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        period_states=period_states,
        all_tap_events=all_tap_events,
        tap_events_by_block=tap_events_by_block,
        pay_rate_per_minute=pay_rate_per_minute,
        pay_rate_table=[
            ("1 minute", pay_rate_per_minute),
            ("10 minutes", round(pay_rate_per_minute * 10, 2)),
            ("30 minutes", round(pay_rate_per_minute * 30, 2)),
            ("1 hour", round(pay_rate_per_minute * 60, 2)),
            ("2 hours", round(pay_rate_per_minute * 120, 2)),
            ("4 hours", round(pay_rate_per_minute * 240, 2)),
        ],
        now=utc_now()
    )


# -------------------- FINANCIAL TRANSACTIONS --------------------

@student_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer funds between checking and savings accounts."""
    # Check if banking feature is enabled
    if not is_feature_enabled('banking'):
        flash("The banking feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context (join_code, teacher_id, block)
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        payload = request.get_json(silent=True) if request.is_json else None
        payload = payload if isinstance(payload, dict) else {}

        def get_transfer_value(key):
            return payload.get(key) if request.is_json else request.form.get(key)

        submission_token = get_transfer_value("transfer_submission_token")
        if not _consume_transfer_submission_token(submission_token):
            message = "This transfer request has already been processed or expired. Please try again."
            if is_json:
                return jsonify(status="error", message=message), 409
            flash(message, "transfer_error")
            return redirect(url_for("student.transfer"))

        passphrase = get_transfer_value("passphrase")
        if not check_password_hash(student.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student.transfer"))

        from_account = get_transfer_value('from_account')
        to_account = get_transfer_value('to_account')
        # Convert form input to Decimal for precise financial calculation
        from app.models import _quantize_currency
        amount = _quantize_currency(get_transfer_value('amount'))

        # CRITICAL FIX: Calculate balances using join_code scoping
        checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)
        banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None

        if from_account == to_account:
            if is_json:
                return jsonify(status="error", message="Cannot transfer to the same account."), 400
            flash("Cannot transfer to the same account.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif amount <= Decimal('0'):
            if is_json:
                return jsonify(status="error", message="Amount must be greater than 0."), 400
            flash("Amount must be greater than 0.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'checking' and amount > checking_balance:
            message = "Insufficient checking funds."
            if is_json:
                return jsonify(status="error", message=message), 400
            flash(message, "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'savings' and amount > savings_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient savings funds."), 400
            flash("Insufficient savings funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        else:
            # CRITICAL FIX v2: Add BOTH teacher_id AND join_code for proper isolation
            _transfer_cid = str(uuid.uuid4())
            # Record the withdrawal side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=-amount,
                account_type=from_account,
                status=TransactionStatus.PENDING,
                type='Withdrawal',
                description=f'Transfer to {to_account}',
                transfer_correlation_id=_transfer_cid,
            ))
            # Record the deposit side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=amount,
                account_type=to_account,
                status=TransactionStatus.PENDING,
                type='Deposit',
                description=f'Transfer from {from_account}',
                transfer_correlation_id=_transfer_cid,
            ))
            try:
                db.session.commit()
                current_app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for student {student.id}"
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(
                    f"Transfer failed for student {student.id}: {e}", exc_info=True
                )
                if is_json:
                    return jsonify(status="error", message="Transfer failed."), 500
                flash("Transfer failed due to a database error.", "transfer_error")
                return redirect(url_for("student.transfer"))
            if is_json:
                return jsonify(status="success", message="Transfer completed successfully!")
            flash("Transfer completed successfully!", "transfer_success")
            return redirect(url_for('student.dashboard'))

    # CRITICAL FIX v2: Get transactions for display - strict join_code scoping.
    transactions = Transaction.query.filter(
        Transaction.student_id == student.id,
        Transaction.is_void == False,
        Transaction.join_code == join_code
    ).order_by(Transaction.timestamp.desc()).all()
    checking_transactions = [t for t in transactions if t.account_type == 'checking']
    savings_transactions = [t for t in transactions if t.account_type == 'savings']

    # Get banking settings for interest rate display
    settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    # Convert APY to decimal rate (e.g., 5% = 0.05)
    from app.models import _quantize_currency
    annual_rate = _quantize_currency(settings.savings_apy / Decimal('100')) if settings and settings.savings_apy is not None else Decimal('0.045')
    calculation_type = settings.interest_calculation_type if settings else 'simple'
    compound_frequency = settings.compound_frequency if settings else 'monthly'

    # Calculate forecast interest based on settings
    # CRITICAL FIX v3: Calculate BOTH checking and savings balances using join_code scoping
    checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)

    if calculation_type == 'compound':
        if compound_frequency == 'daily':
            periods_per_month = Decimal('30')
            rate_per_period = annual_rate / Decimal('365')
            # For Decimal exponentiation, convert to float, calculate, then back to Decimal
            forecast_interest = _quantize_currency(savings_balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        elif compound_frequency == 'weekly':
            periods_per_month = Decimal('4.33')
            rate_per_period = annual_rate / Decimal('52')
            forecast_interest = _quantize_currency(savings_balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        else:  # monthly
            forecast_interest = _quantize_currency(savings_balance * (annual_rate / Decimal('12')))
    else:
        # Simple interest: calculate only on principal (excluding interest earnings)
        principal = _quantize_currency(sum((tx.amount for tx in savings_transactions if tx.type != 'Interest' and 'Interest' not in (tx.description or '')), Decimal('0')))
        forecast_interest = _quantize_currency(principal * (annual_rate / Decimal('12')))

    # Calculate 12-month savings projection for graph
    projection_months = []
    projection_balances = []
    current_balance = savings_balance

    for month in range(13):  # 0 to 12 months
        projection_months.append(month)
        # Convert to float for JSON serialization in template
        projection_balances.append(float(current_balance))

        if month < 12:  # Don't calculate interest for the last point
            if calculation_type == 'compound':
                if compound_frequency == 'daily':
                    periods = Decimal('30')
                    rate = annual_rate / Decimal('365')
                    interest = _quantize_currency(current_balance * ((Decimal('1') + rate) ** periods - Decimal('1')))
                elif compound_frequency == 'weekly':
                    periods = Decimal('4.33')
                    rate = annual_rate / Decimal('52')
                    interest = _quantize_currency(current_balance * ((Decimal('1') + rate) ** periods - Decimal('1')))
                else:  # monthly
                    interest = _quantize_currency(current_balance * (annual_rate / Decimal('12')))
                current_balance = _quantize_currency(current_balance + interest)
            else:  # simple interest
                interest = _quantize_currency(savings_balance * (annual_rate / Decimal('12')))  # Simple interest on original principal
                current_balance = _quantize_currency(current_balance + interest)

    return render_template('student_transfer.html',
                         student=student,
                         transactions=transactions,
                         checking_transactions=checking_transactions,
                         savings_transactions=savings_transactions,
                         checking_balance=checking_balance,
                         savings_balance=savings_balance,
                         forecast_interest=forecast_interest,
                         settings=settings,
                         calculation_type=calculation_type,
                         compound_frequency=compound_frequency,
                         projection_months=projection_months,
                         projection_balances=projection_balances,
                         transfer_submission_token=_issue_transfer_submission_token())


def apply_savings_interest(student, annual_rate=Decimal('0.045')):
    """
    Apply savings interest for a student based on banking settings.
    Supports both simple and compound interest with configurable frequency.
    All time calculations are in UTC.
    """
    from app.models import BankingSettings, _quantize_currency

    now = utc_now()
    this_month = now.month
    this_year = now.year



    # Get banking settings for current teacher
    teacher_id = get_current_teacher_id()
    settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    if not settings:
        # Use default simple interest if no settings
        calculation_type = 'simple'
        compound_frequency = 'monthly'
    else:
        calculation_type = settings.interest_calculation_type or 'simple'
        compound_frequency = settings.compound_frequency or 'monthly'

    # Check if interest was already applied this month
    for tx in student.transactions:
        tx_timestamp = ensure_utc(tx.timestamp)
        if (
            tx.account_type == 'savings'
            and tx.description == "Monthly Savings Interest"
            and tx_timestamp
            and tx_timestamp.month == this_month
            and tx_timestamp.year == this_year
        ):
            return  # Interest already applied this month

    for tx in student.transactions:
        if tx.account_type != 'savings' or "Transfer" not in (tx.description or ""):
            continue
        tx_timestamp = ensure_utc(tx.timestamp)
        if tx_timestamp and tx_timestamp.date() == now.date():
            return

    # Calculate interest based on type
    if calculation_type == 'compound':
        # For compound interest, use current total balance (including previous interest)
        # Convert float balance to Decimal for arithmetic compatibility with Decimal rates
        balance = _quantize_currency(student.savings_balance)

        # Determine the rate based on compound frequency
        if compound_frequency == 'daily':
            # Daily compounding: rate = (1 + annual_rate/365)^365 - 1 ≈ annual_rate for small rates
            # For monthly payout with daily compounding: (1 + annual_rate/365)^30
            periods_per_month = Decimal('30')
            rate_per_period = annual_rate / Decimal('365')
            interest = _quantize_currency(balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        elif compound_frequency == 'weekly':
            # Weekly compounding: (1 + annual_rate/52)^4.33 (approx weeks per month)
            periods_per_month = Decimal('4.33')
            rate_per_period = annual_rate / Decimal('52')
            interest = _quantize_currency(balance * ((Decimal('1') + rate_per_period) ** periods_per_month - Decimal('1')))
        else:  # monthly
            # Monthly compounding
            monthly_rate = annual_rate / Decimal('12')
            interest = _quantize_currency(balance * monthly_rate)
    else:
        # Simple interest: only calculate on original deposits (not including previous interest)
        eligible_balance = Decimal('0')
        for tx in student.transactions:
            # FIX: Add null check to prevent decimal.InvalidOperation on corrupted data
            if tx.account_type != 'savings' or tx.is_void or tx.amount is None or tx.amount <= Decimal('0'):
                continue
            # Exclude interest transactions from principal calculation
            if tx.type == 'Interest' or 'Interest' in (tx.description or ''):
                continue
            available_at = ensure_utc(tx.date_funds_available)
            if available_at and (now - available_at).days >= 30:
                eligible_balance += _quantize_currency(tx.amount)

        monthly_rate = annual_rate / Decimal('12')
        interest = _quantize_currency((eligible_balance or Decimal('0')) * monthly_rate)

    if interest > Decimal('0'):
        # CRITICAL FIX v2: Add join_code to interest transactions
        # Interest must be scoped to specific class, not just teacher
        context = get_current_class_context()
        if context:
            interest_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=context['join_code'],  # CRITICAL: Add join_code for period isolation
                amount=interest,
                account_type='savings',
                status=TransactionStatus.PENDING,
                type='Interest',
                description="Monthly Savings Interest"
            )
            db.session.add(interest_tx)
            db.session.commit()


# -------------------- INSURANCE --------------------

@student_bp.route('/insurance', endpoint='student_insurance')
@login_required
def insurance_marketplace():
    """Insurance marketplace - browse and manage policies."""
    context = get_current_class_context()
    _activate_rebalances_for_context(context)

    # Check if insurance feature is enabled
    if not is_feature_enabled('insurance'):
        flash("The insurance feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context (join_code is source of truth)
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']
    join_code = context['join_code']
    current_block = (context.get('block') or '').strip().upper()
    now_utc = utc_now()

    visible_policy_ids = (
        db.session.query(InsurancePolicy.id)
        .filter(InsurancePolicy.teacher_id == teacher_id)
        .filter(
            or_(
                InsurancePolicy.id.in_(
                    db.session.query(InsurancePolicyBlock.policy_id).filter(
                        InsurancePolicyBlock.block == current_block
                    )
                ),
                ~select(InsurancePolicyBlock.policy_id)
                .where(InsurancePolicyBlock.policy_id == InsurancePolicy.id)
                .exists(),
            )
        )
    )

    my_policies = StudentInsurance.query.join(
        InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
    ).filter(
        StudentInsurance.student_id == student.id,
        StudentInsurance.status == 'active',
        StudentInsurance.join_code == join_code,
        InsurancePolicy.teacher_id == teacher_id,
    ).all()

    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.teacher_id == teacher_id,
        InsurancePolicy.id.in_(visible_policy_ids),
    ).all()

    # Check which policies can be purchased
    can_purchase = {}
    repurchase_blocks = {}

    for policy in available_policies:
        # Check if already enrolled
        existing = StudentInsurance.query.filter_by(
            student_id=student.id,
            policy_id=policy.id,
            status='active',
            join_code=join_code,
        ).first()

        if existing:
            can_purchase[policy.id] = False
            continue

        # Check repurchase restrictions
        cancelled = StudentInsurance.query.filter_by(
            student_id=student.id,
            policy_id=policy.id,
            status='cancelled',
            join_code=join_code,
        ).order_by(StudentInsurance.cancel_date.desc()).first()

        if cancelled and policy.no_repurchase_after_cancel:
            can_purchase[policy.id] = False
            continue

        if cancelled and policy.enable_repurchase_cooldown and cancelled.cancel_date:
            cancel_dt = ensure_utc(cancelled.cancel_date)
            days_since_cancel = (now_utc - cancel_dt).days
            if days_since_cancel < policy.repurchase_wait_days:
                can_purchase[policy.id] = False
                repurchase_blocks[policy.id] = policy.repurchase_wait_days - days_since_cancel
                continue

        can_purchase[policy.id] = True

    # FIX: Get claims for my policies (scoped to current teacher)
    my_claims = InsuranceClaim.query.join(
        InsurancePolicy, InsuranceClaim.policy_id == InsurancePolicy.id
    ).filter(
        InsuranceClaim.student_id == student.id,
        InsuranceClaim.join_code == join_code,
        InsurancePolicy.teacher_id == teacher_id,
    ).all()

    # Group policies by tier for display
    tier_groups = {}
    ungrouped_policies = []
    for policy in available_policies:
        group_id = policy.effective_product_group_id
        if group_id:
            if group_id not in tier_groups:
                tier_groups[group_id] = {
                    'name': policy.tier_name or f"Tier {group_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups[group_id]['policies'].append(policy)
        else:
            ungrouped_policies.append(policy)

    # Check which tier the student has already selected from
    enrolled_tiers = set()
    for enrollment in my_policies:
        # Normalize dates for safe comparisons in templates
        enrollment.coverage_start_date = ensure_utc(enrollment.coverage_start_date)
        enrollment.cancel_date = ensure_utc(enrollment.cancel_date)
        if enrollment.policy.effective_product_group_id:
            enrolled_tiers.add(enrollment.policy.effective_product_group_id)

    return render_template('student_insurance_marketplace.html',
                          student=student,
                          my_policies=my_policies,
                          available_policies=ungrouped_policies,
                          tier_groups=tier_groups,
                          enrolled_tiers=enrolled_tiers,
                          can_purchase=can_purchase,
                          repurchase_blocks=repurchase_blocks,
                          my_claims=my_claims,
                          now=now_utc)


@student_bp.route('/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def purchase_insurance(policy_id):
    """Purchase insurance policy."""
    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context
    context = get_current_class_context()
    if not context:
        flash("No class selected.", "danger")
        return redirect(url_for('student.dashboard'))

    join_code = context['join_code']
    teacher_id = context['teacher_id']
    _activate_rebalances_for_context(context)

    policy = db.get_or_404(InsurancePolicy, policy_id)

    # FIX: Verify policy belongs to CURRENT teacher only
    if policy.teacher_id != teacher_id:
        flash("This insurance policy is not available in your current class.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Check if already enrolled
    existing = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='active',
        join_code=join_code,
    ).first()

    if existing:
        flash("You are already enrolled in this policy.", "warning")
        return redirect(url_for('student.student_insurance'))

    # Check repurchase restrictions
    cancelled = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='cancelled',
        join_code=join_code,
    ).order_by(StudentInsurance.cancel_date.desc()).first()

    if cancelled:
        if policy.no_repurchase_after_cancel:
            flash("This policy cannot be repurchased after cancellation.", "danger")
            return redirect(url_for('student.student_insurance'))

        # Check for cooldown period (temporary restriction)
        if policy.enable_repurchase_cooldown and cancelled.cancel_date:
            days_since_cancel = (utc_now() - cancelled.cancel_date).days
            if days_since_cancel < policy.repurchase_wait_days:
                flash(f"You must wait {policy.repurchase_wait_days - days_since_cancel} more days before repurchasing this policy.", "warning")
                return redirect(url_for('student.student_insurance'))

    # Check tier restrictions - can only have one policy per tier (scoped to current class)
    if policy.effective_product_group_id:
        existing_tier_enrollment = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id == student.id,
            StudentInsurance.status == 'active',
            StudentInsurance.join_code == join_code,
            or_(
                InsurancePolicy.product_group_id == policy.effective_product_group_id,
                and_(
                    InsurancePolicy.product_group_id.is_(None),
                    InsurancePolicy.tier_category_id == policy.effective_product_group_id,
                ),
            ),
            InsurancePolicy.teacher_id == teacher_id  # Scope to current class only
        ).first()

        if existing_tier_enrollment:
            flash(f"You already have a policy from the '{policy.tier_name or 'this'}' tier. You can only have one policy per tier.", "warning")
            return redirect(url_for('student.student_insurance'))

    # CRITICAL FIX v2: Check sufficient funds using join_code scoped balance
    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)
    banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None
    overdraft_shortfall = Decimal('0.00')

    allowed, shortfall, _, _ = evaluate_overdraft_allowance(
        student,
        policy.premium,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code
    )
    if not allowed:
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(
            student,
            banking_settings,
            teacher_id=teacher_id,
            join_code=join_code,
            force=True
        )
        if fee_charged:
            db.session.commit()

        if banking_settings and banking_settings.overdraft_protection_enabled:
            message = (f"Insufficient funds in both checking and savings. You need "
                       f"${policy.premium:.2f} but have ${checking_balance + savings_balance:.2f}.")
        else:
            message = (f"Insufficient funds. You need ${policy.premium:.2f} but only "
                       f"have ${checking_balance:.2f}.")

        if fee_charged:
            message += f" Overdraft fee of ${fee_amount:.2f} charged."

        flash(message, "danger")
        return redirect(url_for('student.student_insurance'))

    if shortfall > 0:
        overdraft_shortfall = shortfall

    # Create enrollment
    enrollment = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        join_code=join_code,
        status='active',
        purchase_date=utc_now(),
        last_payment_date=utc_now(),
        next_payment_due=_insurance_next_payment_due(utc_now(), policy.charge_frequency),
        coverage_start_date=utc_now(),
        payment_current=True
    )
    enrollment.freeze_policy_snapshot(policy)
    enrollment.coverage_start_date = utc_now() + timedelta(days=enrollment.contract_waiting_period_days or 0)
    db.session.add(enrollment)

    # CRITICAL FIX v2: Create transaction with join_code
    transaction = Transaction(
        student_id=student.id,
        teacher_id=teacher_id,
        join_code=join_code,  # CRITICAL: Add join_code for period isolation
        amount=-policy.premium,
        account_type='checking',
        status=TransactionStatus.PENDING,
        type='insurance_premium',
        description=f"Insurance premium: {policy.title}"
    )
    db.session.add(transaction)

    # Handle overdraft protection transfer if savings covers a shortfall
    if banking_settings and banking_settings.overdraft_protection_enabled and overdraft_shortfall > 0:
        _transfer_cid = str(uuid.uuid4())
        transfer_tx_withdraw = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=-overdraft_shortfall,
            account_type='savings',
            status=TransactionStatus.PENDING,
            type='Withdrawal',
            description='Overdraft protection transfer to checking',
            transfer_correlation_id=_transfer_cid,
        )
        transfer_tx_deposit = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,
            amount=overdraft_shortfall,
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='Deposit',
            description='Overdraft protection transfer from savings',
            transfer_correlation_id=_transfer_cid,
        )
        db.session.add(transfer_tx_withdraw)
        db.session.add(transfer_tx_deposit)

    db.session.commit()
    flash(f"Successfully purchased {policy.title}! Coverage starts after {policy.waiting_period_days} day waiting period.", "success")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
def cancel_insurance(enrollment_id):
    """Cancel insurance policy."""
    student = get_logged_in_student()
    enrollment = db.get_or_404(StudentInsurance, enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    enrollment.status = 'cancelled'
    enrollment.cancel_date = utc_now()

    db.session.commit()
    flash(f"Insurance policy '{enrollment.contract_title}' has been cancelled.", "info")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def file_claim(policy_id):
    """File insurance claim."""
    student = get_logged_in_student()
    context = get_current_class_context()
    current_join_code = context['join_code'] if context else None

    enrollment = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy_id,
        status='active',
        join_code=current_join_code,
    ).first()

    if not enrollment:
        flash("You are not enrolled in this policy.", "danger")
        return redirect(url_for('student.student_insurance'))

    policy = enrollment.policy
    claim_type = policy.claim_type
    max_claim_amount = None if claim_type == 'transaction_monetary' else enrollment.contract_max_claim_amount
    max_payout_per_period = enrollment.contract_max_payout_per_period
    max_claims_count = enrollment.contract_max_claims_count
    max_claims_period = (enrollment.contract_max_claims_period or 'month').lower()
    claim_time_limit_days = enrollment.contract_claim_time_limit_days
    contract_coverage_percent = enrollment.contract_coverage_percent
    form = InsuranceClaimForm()
    if claim_type == 'transaction_monetary' and not form.incident_date.data:
        form.incident_date.data = utc_now().date()

    # Validation errors
    errors = []

    # Normalize coverage dates for safe comparisons
    enrollment.coverage_start_date = ensure_utc(enrollment.coverage_start_date)
    enrollment.cancel_date = ensure_utc(enrollment.cancel_date)
    now_utc = utc_now()

    # Check if coverage has started
    if not enrollment.coverage_start_date or enrollment.coverage_start_date > now_utc:
        wait_until = enrollment.coverage_start_date.strftime('%B %d, %Y') if enrollment.coverage_start_date else 'coverage starts'
        errors.append(f"Coverage has not started yet. Please wait until {wait_until}.")

    # Check if payment is current
    if not enrollment.payment_current:
        errors.append("Your premium payments are not current. Please contact the teacher.")

    period_start, period_end = get_claim_period_bounds(max_claims_period)

    # Check max claims per period
    if max_claims_count:
        claims_count = InsuranceClaim.query.filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['pending', 'approved', 'paid']),
            InsuranceClaim.filed_date >= period_start,
            InsuranceClaim.filed_date <= period_end,
        ).count()

        if claims_count >= max_claims_count:
            errors.append(f"You have reached the maximum number of claims ({max_claims_count}) for this {max_claims_period}.")

    period_payouts = None
    remaining_period_cap = None
    if max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start,
            InsuranceClaim.processed_date <= period_end,
            InsuranceClaim.approved_amount.isnot(None),
        ).scalar()
        if period_payouts is None:
            period_payouts = Decimal('0.00')
        remaining_period_cap = max(max_payout_per_period - period_payouts, Decimal('0.00'))

    eligible_transactions = []
    eligible_transaction_rows = []
    if claim_type == 'transaction_monetary':
        effective_time_limit_days = int(claim_time_limit_days) if claim_time_limit_days is not None else None
        tx_query = (
            Transaction.query
            .filter(Transaction.student_id == student.id)
            .filter(Transaction.is_void == False)
            .filter(Transaction.status == TransactionStatus.POSTED)
            .filter(Transaction.amount < Decimal('0'))
            .filter(
                ~func.lower(func.coalesce(Transaction.type, '')).in_(
                    ['insurance_premium', 'insurance_reimbursement', 'interest', 'withdrawal', 'deposit']
                )
            )
        )
        if effective_time_limit_days is not None and effective_time_limit_days > 0:
            cutoff_date = now_utc - timedelta(days=effective_time_limit_days)
            tx_query = tx_query.filter(Transaction.timestamp >= cutoff_date)
        if enrollment.join_code:
            tx_query = tx_query.filter(Transaction.join_code == enrollment.join_code)
        candidate_transactions = tx_query.order_by(Transaction.timestamp.desc()).all()
        claimed_tx_ids = {
            row[0]
            for row in db.session.query(InsuranceClaim.transaction_id)
            .filter(InsuranceClaim.transaction_id.isnot(None))
            .all()
            if row[0] is not None
        }
        reimbursed_tx_ids = collect_reimbursed_source_tx_ids(enrollment.policy_id)
        eligible_transactions = []
        for tx in candidate_transactions:
            tx_is_eligible, _reason = evaluate_claim_transaction_eligibility(
                tx,
                enrollment=enrollment,
                now_utc=now_utc,
                claim_type=claim_type,
                claim_time_limit_days=claim_time_limit_days,
                policy_id=enrollment.policy_id,
                enrollment_join_code=enrollment.join_code,
                claimed_tx_ids=claimed_tx_ids,
                reimbursed_tx_ids=reimbursed_tx_ids,
            )
            if tx_is_eligible:
                eligible_transactions.append(tx)
        form.transaction_id.choices = [
            (
                tx.id,
                f"{tx.timestamp.strftime('%Y-%m-%d')} — {tx.description or 'No description'} (${abs(tx.amount):.2f})",
            )
            for tx in eligible_transactions
        ]
        for tx in eligible_transactions:
            transaction_amount = abs(tx.amount or Decimal('0.00'))
            estimated_payout = transaction_amount
            if contract_coverage_percent:
                estimated_payout = transaction_amount * contract_coverage_percent
            if remaining_period_cap is not None:
                estimated_payout = min(estimated_payout, remaining_period_cap)
            eligible_transaction_rows.append({
                'id': tx.id,
                'timestamp': ensure_utc(tx.timestamp) if tx.timestamp else None,
                'description': tx.description or 'No description',
                'transaction_amount': transaction_amount,
                'estimated_payout': estimated_payout,
            })
    else:
        form.transaction_id.choices = []

    if request.method == 'POST' and form.validate_on_submit():
        selected_transaction = None
        claim_amount_value = None
        claim_item_value = None
        incident_date_value = None
        transaction_id_value = None

        if claim_type == 'transaction_monetary':
            if not form.transaction_id.data:
                flash("You must select a transaction for this claim type.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            selected_transaction = (
                Transaction.query
                .filter(Transaction.id == form.transaction_id.data)
                .filter(Transaction.student_id == student.id)
                .filter(Transaction.is_void == False)
                .filter(Transaction.status == TransactionStatus.POSTED)
                .filter(Transaction.amount < Decimal('0'))
                .first()
            )
            if not selected_transaction:
                flash("Selected transaction is not eligible for claims.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            transaction_is_eligible, _reason = evaluate_claim_transaction_eligibility(
                selected_transaction,
                enrollment=enrollment,
                now_utc=now_utc,
                claim_type=claim_type,
                claim_time_limit_days=claim_time_limit_days,
                policy_id=enrollment.policy_id,
                enrollment_join_code=enrollment.join_code,
            )
            if not transaction_is_eligible:
                flash("Selected transaction is not eligible for claims.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            bind = db.session.get_bind()
            use_row_locking = bind and bind.dialect.name != 'sqlite'
            if use_row_locking:
                transaction_already_claimed = db.session.execute(
                    select(InsuranceClaim)
                    .where(InsuranceClaim.transaction_id == selected_transaction.id)
                    .with_for_update()
                ).scalar_one_or_none()
            else:
                transaction_already_claimed = InsuranceClaim.query.filter(
                    InsuranceClaim.transaction_id == selected_transaction.id
                ).first()

            if transaction_already_claimed:
                flash("This transaction already has a claim. Each transaction can only be claimed once.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            incident_date_value = ensure_utc(selected_transaction.timestamp)
            claim_amount_value = abs(selected_transaction.amount)
            transaction_id_value = selected_transaction.id

            days_since_incident = (now_utc - incident_date_value).days
        else:
            incident_date_value = ensure_utc(datetime.combine(form.incident_date.data, datetime.min.time()))
            days_since_incident = (now_utc - incident_date_value).days

        if claim_type == 'non_monetary':
            if not form.claim_item.data:
                flash("Claim item is required for non-monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))
            claim_item_value = form.claim_item.data
        elif claim_type == 'legacy_monetary':
            if not form.claim_amount.data:
                flash("Claim amount is required for monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))
            claim_amount_value = form.claim_amount.data

            if max_claim_amount and claim_amount_value > max_claim_amount:
                flash(f"Claim amount cannot exceed ${max_claim_amount:.2f}.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

        if claim_time_limit_days is not None and days_since_incident > claim_time_limit_days:
            flash(f"Claims must be filed within {claim_time_limit_days} days of the incident.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        if remaining_period_cap is not None and claim_type != 'non_monetary' and remaining_period_cap <= 0:
            flash("You have reached the maximum payout limit for this period.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        claim = InsuranceClaim(
            student_insurance_id=enrollment.id,
            policy_id=policy.id,
            student_id=student.id,
            join_code=enrollment.join_code,
            incident_date=incident_date_value,
            description=form.description.data,
            claim_amount=claim_amount_value if claim_type != 'non_monetary' else None,
            claim_item=claim_item_value if claim_type == 'non_monetary' else None,
            comments=form.comments.data,
            status='pending',
            transaction_id=transaction_id_value,
        )
        db.session.add(claim)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("This transaction already has a claim. Each transaction can only be claimed once.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Something went wrong while submitting your claim. Please try again.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        flash("Claim submitted successfully! It will be reviewed by your teacher.", "success")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this period
    claims_this_period = InsuranceClaim.query.filter_by(
        student_insurance_id=enrollment.id
    ).all()

    return render_template('student_file_claim.html',
                          student=student,
                          policy=policy,
                          enrollment=enrollment,
                          claim_type=claim_type,
                          contract_title=enrollment.contract_title,
                          contract_description=enrollment.contract_description,
                          contract_max_claim_amount=max_claim_amount,
                          contract_max_claims_count=max_claims_count,
                          contract_max_claims_period=max_claims_period,
                          contract_claim_time_limit_days=claim_time_limit_days,
                          contract_max_payout_per_period=max_payout_per_period,
                          contract_coverage_percent=contract_coverage_percent,
                          form=form,
                          errors=errors,
                          claims_this_period=claims_this_period,
                          eligible_transactions=eligible_transactions,
                          eligible_transaction_rows=eligible_transaction_rows,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


@student_bp.route('/insurance/policy/<int:enrollment_id>')
@login_required
def view_policy(enrollment_id):
    """View policy details and claims history."""
    student = get_logged_in_student()
    enrollment = db.get_or_404(StudentInsurance, enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this policy
    claims = InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    # Normalize dates for safe comparisons in template
    enrollment.coverage_start_date = ensure_utc(enrollment.coverage_start_date)
    enrollment.cancel_date = ensure_utc(enrollment.cancel_date)
    now_utc = utc_now()

    return render_template('student_view_policy.html',
                          student=student,
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          claims=claims,
                          now=now_utc)


# -------------------- SHOPPING --------------------

@student_bp.route('/shop')
@login_required
def shop():
    """Student shop - browse and purchase items."""
    # Check if store feature is enabled
    if not is_feature_enabled('store'):
        flash("The store feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']

    # Lazily expire collective goals whose deadline has passed, refunding pending purchases.
    process_expired_collective_goals(teacher_id)

    expired_rent_perks_cleared = _clear_expired_rent_perk_items(
        student.id,
        join_code=context.get('join_code'),
        teacher_id=teacher_id,
    )
    if expired_rent_perks_cleared:
        db.session.commit()

    current_block = (context.get('block') or '').strip().upper()

    now = utc_now()
    now_db = normalize_for_db(now)
    items_query = StoreItem.query.filter(
        StoreItem.teacher_id == teacher_id,
        StoreItem.is_active == True,
        or_(StoreItem.auto_delist_date == None, StoreItem.auto_delist_date > now_db),
    )
    if current_block:
        items_query = items_query.filter(
            or_(
                StoreItem.visible_blocks.any(func.upper(StoreItemBlock.block) == current_block),
                ~StoreItem.visible_blocks.any(),
            )
        )
    items = items_query.order_by(StoreItem.name).all()

    # FIX: Fetch student's purchased items scoped to current teacher's store
    student_items = student.items.join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        StoreItem.teacher_id == teacher_id  # FIX: Only current class items
    ).order_by(StudentItem.purchase_date.desc()).all()

    # Check if student has paid rent this month and get per-period rent item IDs
    from app.models import RentSettings, RentPayment, RentItem
    join_code = context.get('join_code')
    current_block = context.get('block')
    has_paid_rent = False
    per_period_rent_item_ids = set()
    rent_item_types_by_store_id = {}
    per_use_limit_by_store_id = {}
    rent_settings = None

    if teacher_id and join_code and current_block:
        rent_settings = RentSettings.query.filter_by(teacher_id=teacher_id, block=current_block).first()
        if rent_settings and rent_settings.is_enabled:
            now = utc_now()

            # Calculate current coverage period (pre-paid system)
            coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)

            
            if coverage_due_date:
                has_paid_rent = _is_student_coverage_period_paid(
                    rent_settings,
                    student.id,
                    current_block,
                    join_code,
                    coverage_due_date,
                    include_waivers=False,
                )

            rent_store_items = RentItem.query.filter(
                RentItem.rent_setting_id == rent_settings.id,
                RentItem.is_available_in_store == True,
                RentItem.store_item_id.isnot(None),
                RentItem.rent_item_type != 'hall_pass',
            ).all()
            rent_item_types_by_store_id = {}
            for rent_item in rent_store_items:
                if not rent_item.store_item_id:
                    continue
                effective_type = rent_item.rent_item_type
                # Backward compatibility: legacy rows can still carry privilege as the
                # default type while semantically behaving per-use via duration.
                if effective_type == 'privilege' and rent_item.purchase_duration == 'per_use':
                    effective_type = 'per_use'
                rent_item_types_by_store_id.setdefault(rent_item.store_item_id, set()).add(effective_type)
            per_use_limit_by_store_id = {
                rent_item.store_item_id: (rent_item.use_limit if rent_item.use_limit else -1)
                for rent_item in rent_store_items
                if rent_item.store_item_id and (
                    rent_item.rent_item_type == 'per_use' or
                    (rent_item.rent_item_type == 'privilege' and rent_item.purchase_duration == 'per_use')
                )
            }

            # Get privilege-type per-period rent items (only these are included/disabled).
            per_period_items = RentItem.query.filter_by(
                rent_setting_id=rent_settings.id,
                rent_item_type='privilege',
                is_available_in_store=True
            ).all()
            per_period_items = [item for item in per_period_items if item.purchase_duration != 'per_use']

            # Collect store item IDs (only privilege items get the "Included in your rent!" badge)
            per_period_rent_item_ids = {item.store_item_id for item in per_period_items if item.store_item_id}

    rent_perks_active = not (teacher_id and join_code and current_block and rent_settings and rent_settings.is_enabled) or has_paid_rent

    # Build free uses remaining map for rent-linked per-use items
    rent_free_uses = {}  # {store_item_id: uses_remaining or -1 for unlimited}
    if student and rent_perks_active:
        now_utc = utc_now()
        rent_linked_items_query = StudentItem.query.filter(
            StudentItem.student_id == student.id,
            StudentItem.uses_remaining != None,
            db.or_(
                StudentItem.uses_remaining > 0,
                StudentItem.uses_remaining == -1
            ),
            db.or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > now_utc
            )
        )
        rent_linked_items_query = rent_linked_items_query.filter(StudentItem.join_code == join_code)

        rent_linked_items = rent_linked_items_query.all()
        for si in rent_linked_items:
            if si.store_item_id:
                rent_free_uses[si.store_item_id] = si.uses_remaining

        # Backfill UI for paid-rent students who are entitled to per-use perks
        # but are missing grant rows (legacy/edge-state). Do not override items
        # that already have an explicit grant record (including exhausted = 0).
        if has_paid_rent and per_use_limit_by_store_id:
            existing_per_use_rows = StudentItem.query.filter(
                StudentItem.student_id == student.id,
                StudentItem.join_code == join_code,
                StudentItem.store_item_id.in_(list(per_use_limit_by_store_id.keys())),
                StudentItem.uses_remaining.isnot(None),
                db.or_(
                    StudentItem.expiry_date.is_(None),
                    StudentItem.expiry_date > now_utc
                )
            ).all()
            existing_per_use_ids = {row.store_item_id for row in existing_per_use_rows if row.store_item_id}

            for store_item_id, granted_uses in per_use_limit_by_store_id.items():
                if store_item_id not in existing_per_use_ids and store_item_id not in rent_free_uses:
                    rent_free_uses[store_item_id] = granted_uses

    # Calculate class size for collective goals (count unique students in this class)
    from app.models import TeacherBlock
    class_size = 0
    if join_code:
        class_size = db.session.query(db.func.count(db.func.distinct(Student.id))).join(
            TeacherBlock, TeacherBlock.student_id == Student.id
        ).filter(
            TeacherBlock.join_code == join_code,
            TeacherBlock.is_claimed == True,
            Student.is_teacher == False,  # Exclude teacher account from class size
        ).scalar() or 0

    collective_progress = {}
    collective_items = [item for item in items if item.item_type == 'collective']
    collective_item_ids = [item.id for item in collective_items]
    if collective_item_ids and join_code:
        progress_rows = (
            db.session.query(
                StudentItem.store_item_id,
                StudentItem.collective_goal_instance_code,
                db.func.count(db.distinct(StudentItem.student_id)).label('student_count'),
            )
            .join(Student, StudentItem.student_id == Student.id)
            .filter(
                StudentItem.store_item_id.in_(collective_item_ids),
                StudentItem.join_code == join_code,
                StudentItem.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
                Student.is_teacher == False,  # Exclude teacher purchases from progress
            )
            .group_by(StudentItem.store_item_id, StudentItem.collective_goal_instance_code)
            .all()
        )
        progress_counts = {
            (row.store_item_id, row.collective_goal_instance_code): int(row.student_count or 0)
            for row in progress_rows
        }

        for item in collective_items:
            if item.collective_goal_type == 'whole_class':
                target = class_size
            elif item.collective_goal_type == 'fixed':
                target = int(item.collective_goal_target or 0)
            else:
                target = 0
            count = progress_counts.get((item.id, item.collective_goal_instance_code), 0)
            collective_progress[item.id] = {
                'count': count,
                'target': target,
                'remaining': max(0, target - count),
                'percent': min(100, int((count / target) * 100)) if target > 0 else 0,
                'is_complete': bool(target > 0 and count >= target),
            }

    return render_template('student_shop.html', student=student, items=items, student_items=student_items,
                         has_paid_rent=has_paid_rent, per_period_rent_item_ids=per_period_rent_item_ids,
                         rent_item_types_by_store_id=rent_item_types_by_store_id,
                         rent_free_uses=rent_free_uses,
                         class_size=class_size, current_block=current_block,
                         collective_progress=collective_progress)


# -------------------- RENT --------------------

def _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=None, join_code=None, force=False):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.

    Args:
        force: Charge fee even if balance is non-negative (declined transaction).
    """
    return charge_overdraft_fee_if_needed(
        student,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code,
        force=force
    )


def _get_rent_timezone(settings):
    """
    Return the server-side timezone used for rent schedule semantics.

    This intentionally avoids session/client timezone so browser locale changes
    do not change due-date boundaries.
    """
    tz_name = getattr(settings, "timezone", None)
    if not tz_name and has_app_context():
        tz_name = current_app.config.get("DEFAULT_TIMEZONE")
    return get_timezone(tz_name)


def _calculate_rent_deadlines(settings, reference_date=None):
    """Return the due date and grace end date for the active month."""
    reference_date = ensure_utc(reference_date) if reference_date else utc_now()
    teacher_tz = _get_rent_timezone(settings)
    reference_local = reference_date.astimezone(teacher_tz)

    def _local_due_to_utc(
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
    ) -> datetime:
        local_due = teacher_tz.localize(datetime(year, month, day, hour, minute, second))
        return local_due.astimezone(timezone.utc)

    # If first_rent_due_date is set and we haven't reached it yet, return it
    if settings.first_rent_due_date:
        first_due = ensure_utc(settings.first_rent_due_date)
        first_due_local = first_due.astimezone(teacher_tz) if first_due else None
        if (
            first_due
            and first_due.hour == 0
            and first_due.minute == 0
            and first_due.second == 0
            and first_due.microsecond == 0
        ):
            # Preserve legacy day-only anchors that were stored as UTC midnight.
            first_due_local = teacher_tz.localize(datetime(first_due.year, first_due.month, first_due.day, 0, 0, 0))
            first_due = first_due_local.astimezone(timezone.utc)
        # If we're before the first due date, return the first due date
        if first_due_local and reference_local < first_due_local:
            grace_end_date = first_due + timedelta(days=settings.grace_period_days)
            return first_due, grace_end_date

        # Calculate due date based on frequency from first_rent_due_date
        if settings.frequency_type == 'monthly':
            # Calculate how many months have passed since first due date
            months_diff = (reference_local.year - first_due_local.year) * 12 + (reference_local.month - first_due_local.month)
            # Calculate the due date for the current period
            target_year = first_due_local.year + (first_due_local.month + months_diff - 1) // 12
            target_month = (first_due_local.month + months_diff - 1) % 12 + 1
            last_day_of_month = monthrange(target_year, target_month)[1]
            due_day = min(first_due_local.day, last_day_of_month)
            due_date = _local_due_to_utc(
                target_year,
                target_month,
                due_day,
                first_due_local.hour,
                first_due_local.minute,
                first_due_local.second,
            )
        else:
            # Calculate due date based on frequency
            freq_delta = None
            if settings.frequency_type == 'daily':
                freq_delta = timedelta(days=1)
            elif settings.frequency_type == 'weekly':
                freq_delta = timedelta(weeks=1)
            elif settings.frequency_type == 'custom':
                if settings.custom_frequency_unit == 'days':
                    freq_delta = timedelta(days=settings.custom_frequency_value)
                elif settings.custom_frequency_unit == 'weeks':
                    freq_delta = timedelta(weeks=settings.custom_frequency_value)
                elif settings.custom_frequency_unit == 'months':
                    # Custom monthly logic (Every X months)
                    # Calculate how many months have passed since first due date
                    months_diff = (reference_local.year - first_due_local.year) * 12 + (reference_local.month - first_due_local.month)

                    # Calculate the number of full periods passed
                    # We use integer division to find the start of the current cycle
                    periods = months_diff // settings.custom_frequency_value
                    total_months_add = periods * settings.custom_frequency_value

                    target_year = first_due_local.year + (first_due_local.month + total_months_add - 1) // 12
                    target_month = (first_due_local.month + total_months_add - 1) % 12 + 1

                    last_day_of_month = monthrange(target_year, target_month)[1]
                    due_day = min(first_due_local.day, last_day_of_month)
                    due_date = _local_due_to_utc(
                        target_year,
                        target_month,
                        due_day,
                        first_due_local.hour,
                        first_due_local.minute,
                        first_due_local.second,
                    )

            if freq_delta:
                # Calculate periods passed for fixed time deltas
                time_diff = reference_date - first_due
                periods = time_diff // freq_delta
                due_date = first_due + (periods * freq_delta)

            use_fallback = False
            if not freq_delta and settings.frequency_type != 'custom':
                # Fallback for unknown frequency types
                use_fallback = True
            elif settings.frequency_type == 'custom' and settings.custom_frequency_unit not in ['days', 'weeks', 'months']:
                 # Fallback for unknown custom units
                use_fallback = True

            if use_fallback:
                current_year = reference_local.year
                current_month = reference_local.month
                last_day_of_month = monthrange(current_year, current_month)[1]
                due_day = min(settings.due_day_of_month, last_day_of_month)
                due_date = _local_due_to_utc(current_year, current_month, due_day)

    else:
        # No first_rent_due_date set, use traditional monthly logic
        current_year = reference_local.year
        current_month = reference_local.month
        last_day_of_month = monthrange(current_year, current_month)[1]
        due_day = min(settings.due_day_of_month, last_day_of_month)
        due_date = _local_due_to_utc(current_year, current_month, due_day)

    grace_end_date = due_date + timedelta(days=settings.grace_period_days)
    return due_date, grace_end_date


def _get_rent_period_delta(settings):
    """Return a timedelta/relativedelta representing one rent period."""
    if settings.frequency_type == 'daily':
        return timedelta(days=1)
    if settings.frequency_type == 'weekly':
        return timedelta(weeks=1)
    if settings.frequency_type == 'monthly':
        return relativedelta(months=1)
    if settings.frequency_type == 'custom':
        unit = getattr(settings, 'custom_frequency_unit', None)
        value = getattr(settings, 'custom_frequency_value', None) or 1
        if unit == 'days':
            return timedelta(days=value)
        if unit == 'weeks':
            return timedelta(weeks=value)
        if unit == 'months':
            return relativedelta(months=value)
    # Fallback to monthly behavior
    return relativedelta(months=1)


def _add_rent_period(dt, delta):
    """Add a timedelta or relativedelta to dt."""
    return dt + delta


def _calculate_upcoming_rent_due_date(settings, due_date, coverage_due_date):
    """
    Return the next due date students can preview/pay toward.

    For monthly schedules without first_rent_due_date, derive next due date using
    _calculate_rent_deadlines to preserve due_day_of_month clamping (e.g., 31st).
    """
    if not coverage_due_date:
        return due_date

    if settings.frequency_type == 'monthly' and not settings.first_rent_due_date:
        reference_date = coverage_due_date + relativedelta(months=1)
        next_due, _ = _calculate_rent_deadlines(settings, reference_date)
        return next_due

    period_delta = _get_rent_period_delta(settings)
    return _add_rent_period(coverage_due_date, period_delta)


def _calculate_rent_timeline(settings, now):
    """Compute due-date timeline and activation flags used by rent views/payments."""
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    upcoming_due_date = _calculate_upcoming_rent_due_date(settings, due_date, coverage_due_date)

    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = upcoming_due_date - timedelta(days=settings.bill_preview_days)

    rent_is_active = False
    is_preview_period_candidate = False
    if coverage_due_date and now >= coverage_due_date:
        rent_is_active = True
    if preview_start_date and now >= preview_start_date and now < upcoming_due_date:
        rent_is_active = True
        is_preview_period_candidate = True

    return {
        'due_date': due_date,
        'grace_end_date': grace_end_date,
        'coverage_due_date': coverage_due_date,
        'upcoming_due_date': upcoming_due_date,
        'preview_start_date': preview_start_date,
        'rent_is_active': rent_is_active,
        'is_preview_period_candidate': is_preview_period_candidate,
    }


def _total_paid_by_grace(payments, grace_end_date):
    """Sum payments made on or before the grace end date."""
    if not payments or not grace_end_date:
        return Decimal('0.00')
    grace_end_date = ensure_utc(grace_end_date)
    return sum(
        (p.amount_paid for p in payments
         if p.payment_date and ensure_utc(p.payment_date) <= grace_end_date),
        Decimal('0.00')
    )


def _get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due_date):
    """Return the locked base-rent amount for a join_code coverage cycle.

    The rate is locked at the FIRST valid payer's base amount, preventing
    mid-cycle rate changes from affecting students already in the cycle.
    Uses timestamp-based transaction matching (same approach as the rest of
    the rent payment validation code) since RentPayment has no transaction_id
    column.
    """
    if not join_code or not coverage_due_date:
        return None

    # Order by payment_date ascending so the first valid payment is found first.
    cycle_payments = RentPayment.query.filter(
        RentPayment.join_code == join_code,
        RentPayment.coverage_month == coverage_due_date.month,
        RentPayment.coverage_year == coverage_due_date.year,
    ).order_by(RentPayment.payment_date.asc()).all()
    if not cycle_payments:
        return None

    # Walk payments in chronological order; return the base amount of the
    # first one backed by a non-void Rent Payment transaction.
    for payment in cycle_payments:
        txn = Transaction.query.filter(
            Transaction.student_id == payment.student_id,
            Transaction.type == 'Rent Payment',
            Transaction.join_code == join_code,
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.amount == -payment.amount_paid,
        ).first()

        if txn is None or txn.is_void:
            continue

        late_fee = _quantize_currency(payment.late_fee_charged or Decimal('0.00'))
        base_amount = _quantize_currency((payment.amount_paid or Decimal('0.00')) - late_fee)
        if base_amount > Decimal('0.00'):
            return base_amount

    return None


def _get_effective_rent_amount_for_coverage_period(settings, payments, coverage_due_date, join_code=None):
    """
    Return the rent amount that should apply for a specific coverage period.

    Rebalance updates should apply on the next cycle. If rent amount was updated
    after the current coverage period started and the student already paid toward
    that period before the update, keep the pre-update paid amount as the base due
    threshold for this period so students are not retroactively marked late.
    """
    current_amount = settings.rent_amount or Decimal('0.00')

    locked_amount = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due_date)
    if locked_amount is not None:
        return locked_amount

    # Fallback: if settings were updated AFTER the student's earliest payment
    # for this period, the rate was raised mid-cycle. Use the total base amount
    # the student paid (their rate at payment time) as the effective threshold.
    if payments:
        updated_at = getattr(settings, 'updated_at', None)
        if updated_at:
            payment_dates = [
                ensure_utc(p.payment_date) for p in payments if p.payment_date
            ]
            if payment_dates:
                earliest = min(payment_dates)
                if ensure_utc(updated_at) > earliest:
                    base_paid = sum(
                        (p.amount_paid or Decimal('0.00')) - (p.late_fee_charged or Decimal('0.00'))
                        for p in payments
                    )
                    if base_paid > Decimal('0.00'):
                        return base_paid

    return current_amount
def _filter_valid_rent_payments(payments, student_id, join_code):
    """Return payments that have a matching, non-void rent transaction."""
    if not payments:
        return []

    payment_dates = [p.payment_date for p in payments if p.payment_date]
    if not payment_dates:
        return []

    min_payment_date = min(payment_dates)
    max_payment_date = max(payment_dates)
    window_start = min_payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)
    window_end = max_payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)

    payment_amounts = {-(p.amount_paid) for p in payments}

    txn_query = Transaction.query.filter(
        Transaction.student_id == student_id,
        Transaction.type == 'Rent Payment',
        Transaction.timestamp >= window_start,
        Transaction.timestamp <= window_end,
        Transaction.amount.in_(payment_amounts)
    )
    if not join_code:
        return []
    txn_query = txn_query.filter(Transaction.join_code == join_code)

    candidate_txns = txn_query.all()
    txns_by_amount = {}
    for txn in candidate_txns:
        txns_by_amount.setdefault(txn.amount, []).append(txn)

    used_txn_ids = set()
    valid_payments = []
    for payment in payments:
        candidates = txns_by_amount.get(-payment.amount_paid, [])
        for txn in candidates:
            if txn.id in used_txn_ids or txn.is_void:
                continue
            if not txn.timestamp or not payment.payment_date:
                continue
            if abs((ensure_utc(txn.timestamp) - ensure_utc(payment.payment_date)).total_seconds()) > RENT_PAYMENT_MATCH_TOLERANCE_SECONDS:
                continue
            used_txn_ids.add(txn.id)
            valid_payments.append(payment)
            break
        else:
            # No matching non-void Transaction found for this payment — log anomaly.
            try:
                current_app.logger.warning(
                    "RentPayment id=%s (student=%s join_code=%s amount=%s) has no matching "
                    "non-void Transaction within %ss — treating as invalid.",
                    getattr(payment, 'id', '?'), student_id, join_code,
                    payment.amount_paid, RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
                )
            except RuntimeError:
                pass  # No app context — suppress logging outside request context.

    return valid_payments


def _is_coverage_period_paid(settings, valid_payments, coverage_due_date, include_late_fee=True, join_code=None):
    """
    Return True when a coverage period is fully paid.

    When include_late_fee is True (default), late fee is required when rent
    was not fully paid by grace. When False, this checks base-rent coverage
    only (used by hall-pass perk restoration).
    """
    if not settings or not coverage_due_date:
        return False
    effective_rent_amount = _get_effective_rent_amount_for_coverage_period(
        settings,
        valid_payments,
        coverage_due_date,
        join_code=join_code,
    )
    if effective_rent_amount <= Decimal('0.00'):
        return True
    if not valid_payments:
        return False

    total_paid = sum((p.amount_paid for p in valid_payments), Decimal('0.00'))
    grace_for_coverage = coverage_due_date + timedelta(days=settings.grace_period_days)
    paid_by_grace = _total_paid_by_grace(valid_payments, grace_for_coverage)

    required_total = effective_rent_amount
    if include_late_fee and paid_by_grace < effective_rent_amount:
        required_total += settings.late_fee

    return total_paid >= required_total


def _get_active_rent_waiver(student_id, join_code, coverage_due_date):
    """Return the waiver row covering the given coverage period, if any."""
    from app.models import RentWaiver
    if not student_id or not coverage_due_date:
        return None
    query = RentWaiver.query.filter(
        RentWaiver.student_id == student_id,
        RentWaiver.waiver_start_date <= coverage_due_date,
        RentWaiver.waiver_end_date >= coverage_due_date,
    )
    if join_code:
        query = query.filter(
            db.or_(
                RentWaiver.join_code == join_code,
                RentWaiver.join_code.is_(None),
            )
        )
    return query.order_by(RentWaiver.created_at.desc(), RentWaiver.id.desc()).first()


def _has_active_rent_waiver(student_id, join_code, coverage_due_date):
    """Return True when the student has an active waiver covering the given coverage period."""
    return _get_active_rent_waiver(student_id, join_code, coverage_due_date) is not None


def _iter_rent_waiver_coverage_dates(settings, waiver):
    """Expand a waiver row into the individual coverage due dates it covers."""
    if not settings or not waiver:
        return []

    delta = _get_rent_period_delta(settings)
    dates = []
    current = ensure_utc(waiver.waiver_start_date)
    end = ensure_utc(waiver.waiver_end_date)

    while current and end and current <= end:
        dates.append(current)
        next_date = _add_rent_period(current, delta)
        if next_date <= current:
            break
        current = next_date

    return dates


def _get_rent_coverage_label(coverage_due_date):
    if not coverage_due_date:
        return "Unknown"
    return (ensure_utc(coverage_due_date) + timedelta(days=1)).strftime('%b %Y')


def _expand_rent_waiver_history(settings, waivers, *, now=None):
    """Return one waiver-history row per covered rent period."""
    now = ensure_utc(now or utc_now())
    current_coverage_due_date = _calculate_rent_coverage_due_date(settings, now) if settings else None
    entries = []

    for waiver in waivers or []:
        for coverage_due_date in _iter_rent_waiver_coverage_dates(settings, waiver):
            coverage_day = ensure_utc(coverage_due_date).date()
            current_day = ensure_utc(current_coverage_due_date).date() if current_coverage_due_date else None

            if current_day is None or coverage_day > current_day:
                status = 'upcoming'
                status_label = 'Upcoming'
                cancellable = True
            elif current_day and coverage_day == current_day:
                status = 'current'
                status_label = 'Current'
                cancellable = False
            else:
                status = 'used'
                status_label = 'Used'
                cancellable = False

            entries.append({
                'waiver': waiver,
                'student': waiver.student,
                'join_code': waiver.join_code,
                'coverage_due_date': coverage_due_date,
                'coverage_label': _get_rent_coverage_label(coverage_due_date),
                'status': status,
                'status_label': status_label,
                'is_cancellable': cancellable,
                'created_at': ensure_utc(waiver.created_at) if waiver.created_at else None,
                'reason': waiver.reason,
            })

    status_rank = {'current': 0, 'upcoming': 1, 'used': 2}
    entries.sort(
        key=lambda item: (
            status_rank.get(item['status'], 3),
            -(item['coverage_due_date'].timestamp() if item['coverage_due_date'] else 0),
            -(item['created_at'].timestamp() if item['created_at'] else 0),
        )
    )
    return entries


def _is_student_coverage_period_paid(
    settings,
    student_id,
    period,
    join_code,
    coverage_due_date,
    include_late_fee=True,
    include_waivers=True,
):
    """Return True when a student's specific coverage period is fully paid or waived."""
    if not settings or not coverage_due_date or not join_code:
        return False
    normalized_period = (period or '').strip().upper()
    if not normalized_period:
        return False

    # A waiver exempts the student from paying rent for this coverage period.
    if include_waivers and _has_active_rent_waiver(student_id, join_code, coverage_due_date):
        return True

    coverage_payments = RentPayment.query.filter(
        RentPayment.student_id == student_id,
        db.func.upper(db.func.trim(RentPayment.period)) == normalized_period,
        RentPayment.coverage_month == coverage_due_date.month,
        RentPayment.coverage_year == coverage_due_date.year,
        RentPayment.join_code == join_code,
    ).all()

    valid_payments = _filter_valid_rent_payments(
        coverage_payments,
        student_id,
        join_code
    )
    return _is_coverage_period_paid(
        settings,
        valid_payments,
        coverage_due_date,
        include_late_fee=include_late_fee,
        join_code=join_code,
    )


def _calculate_rent_coverage_due_date(settings, reference_date=None):
    """
    Return the most recently passed due date for coverage tracking.

    If we're before the current due date, this returns the previous due date.
    """
    reference_date = ensure_utc(reference_date) if reference_date else utc_now()
    if settings.first_rent_due_date:
        first_due = ensure_utc(settings.first_rent_due_date)
        if first_due and reference_date < first_due:
            return None
    current_due_date, _ = _calculate_rent_deadlines(settings, reference_date)
    if not current_due_date:
        return None

    if reference_date >= current_due_date:
        return current_due_date

    # If we're before the current due date, compute the previous due date.
    # For monthly settings without a first_rent_due_date, compute the prior
    # month explicitly to preserve the configured day-of-month.
    if settings.frequency_type == 'monthly' and not settings.first_rent_due_date:
        teacher_tz = _get_rent_timezone(settings)
        current_due_local = ensure_utc(current_due_date).astimezone(teacher_tz)
        prev_year = current_due_local.year
        prev_month = current_due_local.month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1

        _, last_day = monthrange(prev_year, prev_month)
        due_day = settings.due_day_of_month or last_day
        due_day = min(due_day, last_day)
        previous_due_local = teacher_tz.localize(datetime(prev_year, prev_month, due_day, current_due_local.hour, current_due_local.minute, current_due_local.second))
        return previous_due_local.astimezone(timezone.utc)

    delta = _get_rent_period_delta(settings)
    return current_due_date - delta


def _ensure_rent_hall_pass_top_off(student, context, settings=None, now=None):
    """
    Reconcile rent-granted hall passes for the current coverage period.

    Returns:
        tuple[int, int, bool]: (passes_awarded, passes_revoked, state_changed)
    """
    if not student or not context:
        return 0, 0, False

    join_code = context.get('join_code')
    current_block = (context.get('block') or '').strip().upper()
    if not join_code or not current_block:
        return 0, 0, False

    settings = settings or get_rent_settings_for_context(context)
    if not settings or not settings.is_enabled:
        return 0, 0, False

    now = now or utc_now()
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    if not coverage_due_date:
        return 0, 0, False

    is_paid = _is_student_coverage_period_paid(
        settings,
        student.id,
        current_block,
        join_code,
        coverage_due_date,
        include_late_fee=False,
    )

    from app.models import RentItem, StudentBlock

    total_grant = db.session.query(
        db.func.coalesce(db.func.sum(RentItem.hall_pass_count), 0)
    ).filter(
        RentItem.rent_setting_id == settings.id,
        RentItem.rent_item_type == 'hall_pass',
    ).scalar() or 0
    total_grant = int(total_grant)

    student_block = StudentBlock.query.filter(
        StudentBlock.student_id == student.id,
        StudentBlock.period == current_block,
        db.or_(
            StudentBlock.join_code == join_code,
            StudentBlock.join_code.is_(None),
        ),
    ).order_by(
        db.case((StudentBlock.join_code == join_code, 0), else_=1)
    ).first()

    state_changed = False

    if student_block and not student_block.join_code and join_code:
        student_block.join_code = join_code
        state_changed = True
    elif not student_block and (is_paid and total_grant > 0):
        student_block = StudentBlock(
            student_id=student.id,
            period=current_block,
            join_code=join_code,
            rent_hall_passes=0,
        )
        db.session.add(student_block)
        state_changed = True

    current_total_passes = max(0, int(student.hall_passes or 0))
    current_rent_passes = max(0, int(student_block.rent_hall_passes or 0)) if student_block else 0
    effective_rent_passes = min(current_rent_passes, current_total_passes)
    target_rent_passes = total_grant if is_paid else 0
    delta = target_rent_passes - effective_rent_passes
    passes_awarded = max(0, delta)
    passes_revoked = max(0, -delta)

    if delta != 0:
        student.hall_passes = current_total_passes + delta
        db.session.add(student)
        state_changed = True

    if student_block:
        if student_block.rent_hall_passes != target_rent_passes:
            student_block.rent_hall_passes = target_rent_passes
            state_changed = True

    return passes_awarded, passes_revoked, state_changed


@student_bp.route('/rent')
@login_required
def rent():
    """View rent status and payment history (per period)."""
    context = get_current_class_context()
    _activate_rebalances_for_context(context)

    # Check if rent feature is enabled
    if not is_feature_enabled('rent'):
        flash("The rent feature is currently disabled for your class.", "warning")
        return redirect(url_for('student.dashboard'))

    student = get_logged_in_student()
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context.get('teacher_id')
    join_code = context.get('join_code')
    current_block = (context.get('block') or '').strip().upper()
    settings = get_rent_settings_for_context(context)

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "info")
        return redirect(url_for('student.dashboard'))

    if not current_block:
        flash("No class period found for this class.", "error")
        return redirect(url_for('student.dashboard'))

    # Get student's periods (scoped to the current class only)
    student_blocks = [current_block]

    # Calculate rent status for each period
    now = utc_now()

    timeline = _calculate_rent_timeline(settings, now)
    due_date = timeline['due_date']
    grace_end_date = timeline['grace_end_date']
    coverage_due_date = timeline['coverage_due_date']
    upcoming_due_date = timeline['upcoming_due_date']
    preview_start_date = timeline['preview_start_date']
    rent_is_active = timeline['rent_is_active']
    is_preview_period_candidate = timeline['is_preview_period_candidate']

    # CRITICAL FIX: Before allowing preview period, check if current coverage is paid
    # Students must pay overdue periods before pre-paying for upcoming periods
    current_coverage_paid = False
    if is_preview_period_candidate and not coverage_due_date:
        # No prior coverage period to settle; allow preview payments
        current_coverage_paid = True
    elif is_preview_period_candidate and coverage_due_date:
        current_coverage_paid = _is_student_coverage_period_paid(
            settings,
            student.id,
            current_block,
            join_code,
            coverage_due_date,
        )

    # Only allow preview period if current coverage is already paid
    is_preview_period = is_preview_period_candidate and current_coverage_paid

    # Calculate which coverage period we're checking for (pre-paid system)
    # CRITICAL FIX: Determine which due date to show for payment (matches payment route logic)
    if is_preview_period:
        coverage_month = upcoming_due_date.month
        coverage_year = upcoming_due_date.year
        grace_end_date_for_status = upcoming_due_date + timedelta(days=settings.grace_period_days)
        payment_due_date = upcoming_due_date  # Paying for upcoming period
    else:
        coverage_month = coverage_due_date.month if coverage_due_date else upcoming_due_date.month
        coverage_year = coverage_due_date.year if coverage_due_date else upcoming_due_date.year
        grace_end_date_for_status = (coverage_due_date + timedelta(days=settings.grace_period_days)) if coverage_due_date else grace_end_date
        payment_due_date = coverage_due_date or upcoming_due_date  # Paying for overdue/current period

    period_status = {}

    # Get all payments that COVER the current period (pre-paid system)
    all_payments_for_period = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.period == current_block,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
        RentPayment.join_code == join_code,
    ).all()

    # Filter out payments where the corresponding transaction was voided
    payments = _filter_valid_rent_payments(all_payments_for_period, student.id, join_code)

    total_paid = sum(p.amount_paid for p in payments) if payments else Decimal('0.00')

    waiver_query = RentWaiver.query.filter(RentWaiver.student_id == student.id)
    if join_code:
        waiver_query = waiver_query.filter(
            db.or_(
                RentWaiver.join_code == join_code,
                RentWaiver.join_code.is_(None),
            )
        )
    student_waivers = waiver_query.all()
    waiver_history = _expand_rent_waiver_history(
        settings,
        student_waivers,
        now=now,
    )
    active_waiver_entry = next(
        (
            row for row in waiver_history
            if ensure_utc(row['coverage_due_date']).date() == ensure_utc(payment_due_date).date()
        ),
        None,
    ) if payment_due_date else None
    active_waiver = active_waiver_entry['waiver'] if active_waiver_entry else None
    is_waived = active_waiver is not None

    paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
    effective_rent_amount = _get_effective_rent_amount_for_coverage_period(
        settings,
        payments,
        coverage_due_date,
        join_code=join_code,
    )
    late_fee = Decimal('0.00')
    if rent_is_active and not is_waived and now > grace_end_date_for_status and paid_by_grace < effective_rent_amount:
        late_fee = settings.late_fee

    total_due = Decimal('0.00') if is_waived else (effective_rent_amount + late_fee if rent_is_active else Decimal('0.00'))
    is_paid = True if is_waived else (total_paid >= total_due if rent_is_active else False)
    is_late = now > grace_end_date_for_status and not is_paid if rent_is_active else False
    remaining_amount = max(Decimal('0.00'), total_due - total_paid) if rent_is_active else Decimal('0.00')

    period_status[current_block] = {
        'is_paid': is_paid,
        'is_waived': is_waived,
        'waiver': active_waiver,
        'is_late': is_late,
        'payments': payments,
        'total_paid': total_paid,
        'total_due': total_due,
        'remaining_amount': remaining_amount,
        'late_fee': late_fee,
        'rent_is_active': rent_is_active,
        'is_preview_period': is_preview_period
    }

    # Get scoped balances for this class only
    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)

    # Get payment and waiver history for the current class only
    payment_history = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.join_code == join_code,
    ).order_by(
        RentPayment.payment_date.desc()
    ).limit(24).all()

    payment_history_rows = []
    for payment in payment_history:
        payment_history_rows.append({
            'entry_type': 'payment',
            'period': payment.period,
            'period_month': payment.coverage_month,
            'period_year': payment.coverage_year,
            'amount_paid': payment.amount_paid,
            'payment_date': payment.payment_date,
            'recorded_at': payment.payment_date,
            'status_text': f"Paid late with fee of ${payment.late_fee_charged:.2f}" if payment.was_late else 'On time',
        })

    from app.models import RentItem
    for row in waiver_history:
        payment_history_rows.append({
            'entry_type': 'waiver',
            'period': current_block,
            'period_month': row['coverage_due_date'].month,
            'period_year': row['coverage_due_date'].year,
            'amount_paid': None,
            'payment_date': None,
            'recorded_at': row['created_at'] or row['coverage_due_date'],
            'status_text': f"{row['status_label']} waiver",
        })

    payment_history_rows.sort(
        key=lambda row: ensure_utc(row['recorded_at']) if row.get('recorded_at') else UTC_MIN,
        reverse=True,
    )
    payment_history_rows = payment_history_rows[:24]

    # Get rent items for this setting to show what rent includes
    rent_items = []
    if settings:
        rent_items = RentItem.query.filter_by(rent_setting_id=settings.id).order_by(RentItem.order_index).all()

    # Calculate days until the currently payable due date for dynamic display
    days_until_due = None
    reference_due_date = payment_due_date or upcoming_due_date
    if reference_due_date:
        days_until_due = (reference_due_date - now).days

    return render_template('student_rent.html',
                          student=student,
                          settings=settings,
                          student_blocks=student_blocks,
                          period_status=period_status,
                          current_block=current_block,
                          join_code=join_code,
                          checking_balance=checking_balance,
                          savings_balance=savings_balance,
                          due_date=due_date,
                          payment_due_date=payment_due_date,  # CRITICAL FIX: Show correct period being paid for
                          grace_end_date=grace_end_date,
                          grace_end_date_for_status=grace_end_date_for_status,  # Add grace date for the payment period
                          preview_start_date=preview_start_date,
                          payment_history=payment_history_rows,
                          rent_items=rent_items,
                          days_until_due=days_until_due)


@student_bp.route('/rent/pay/<period>', methods=['POST'])
@login_required
def rent_pay(period):
    """Process rent payment for a specific period."""
    student = get_logged_in_student()
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context.get('teacher_id')
    join_code = context.get('join_code')
    current_block = (context.get('block') or '').strip().upper()
    _activate_rebalances_for_context(context)
    settings = get_rent_settings_for_context(context)

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student.dashboard'))

    if not student.is_rent_enabled:
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student.dashboard'))

    # Validate period for the current class context only
    period = (period or '').strip().upper()
    student_blocks = [current_block]
    if period != current_block:
        flash("Invalid period.", "error")
        return redirect(url_for('student.rent'))

    now = utc_now()

    timeline = _calculate_rent_timeline(settings, now)
    due_date = timeline['due_date']
    grace_end_date = timeline['grace_end_date']
    coverage_due_date = timeline['coverage_due_date']
    upcoming_due_date = timeline['upcoming_due_date']
    preview_start_date = timeline['preview_start_date']
    rent_is_active = timeline['rent_is_active']

    if not rent_is_active:
        if preview_start_date:
            available_date = preview_start_date
            message = f"Rent is not due yet. You can start paying on {available_date.strftime('%B %d, %Y')}."
        else:
            message = f"Rent is not due yet. Payment opens on {upcoming_due_date.strftime('%B %d, %Y')}."
        flash(message, "info")
        return redirect(url_for('student.rent'))

    current_month = now.month
    current_year = now.year

    # CRITICAL FIX: Check if student has paid current coverage period BEFORE allowing preview
    # If student is overdue, they must pay the overdue period first, not pre-pay for next month
    current_coverage_paid = False
    if not coverage_due_date:
        # No prior coverage period to settle; allow preview payments
        current_coverage_paid = True
    else:
        current_coverage_paid = _is_student_coverage_period_paid(
            settings,
            student.id,
            period,
            join_code,
            coverage_due_date,
        )

    # Determine which due date this payment should cover
    # Only allow preview period if current coverage is already paid
    is_preview_period = (
        current_coverage_paid and
        preview_start_date and
        now >= preview_start_date and
        now < upcoming_due_date
    )
    payment_due_date = upcoming_due_date if is_preview_period else (coverage_due_date or upcoming_due_date)

    # Calculate coverage period (pre-paid system)
    coverage_month = payment_due_date.month
    coverage_year = payment_due_date.year

    checking_balance = student.get_checking_balance(teacher_id=teacher_id, join_code=join_code)
    savings_balance = student.get_savings_balance(teacher_id=teacher_id, join_code=join_code)

    # Get all existing payments that cover this period
    all_payments = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.period == period,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
        RentPayment.join_code == join_code,
    ).all()

    # Filter out payments where the corresponding transaction was voided
    existing_payments = _filter_valid_rent_payments(all_payments, student.id, join_code)

    total_paid_so_far = sum(p.amount_paid for p in existing_payments) if existing_payments else Decimal('0.00')

    # Calculate if late and total amount due
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    grace_end_date_for_payment = grace_end_date
    if payment_due_date and payment_due_date != due_date:
        grace_end_date_for_payment = payment_due_date + timedelta(days=settings.grace_period_days)
    paid_by_grace = _total_paid_by_grace(existing_payments, grace_end_date_for_payment)
    effective_rent_amount = _get_effective_rent_amount_for_coverage_period(
        settings,
        existing_payments,
        payment_due_date,
        join_code=join_code,
    )
    is_late = now > grace_end_date_for_payment and paid_by_grace < effective_rent_amount

    # Calculate late fee if applicable
    late_fee = Decimal('0.00')
    if is_late:
        late_fee = _quantize_currency(settings.late_fee)

    # Total amount due (rent + late fee if applicable)
    total_due = _quantize_currency(effective_rent_amount + late_fee)

    # Calculate remaining amount to pay
    remaining_amount = _quantize_currency(total_due - total_paid_so_far)

    # Log anomaly: negative remaining balance indicates accounting inconsistency.
    if remaining_amount < Decimal('0'):
        current_app.logger.warning(
            "Negative remaining_amount (%.2f) for student=%s period=%s coverage=%s/%s join_code=%s — "
            "total_due=%.2f total_paid=%.2f. Continuing.",
            remaining_amount, student.id, period, coverage_month, coverage_year, join_code,
            total_due, total_paid_so_far,
        )

    # Check if already fully paid
    if remaining_amount <= 0:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    payment_mode = (request.form.get('payment_mode') or 'full').strip().lower()
    payment_amount_input = request.form.get('amount', '').strip()

    # Full payment is the safe default. Only treat a request as partial when the
    # client explicitly opts into partial mode. This prevents browser autofill or
    # stale form state from silently converting a "Pay Rent" click into a
    # one-cent-short partial payment.
    if settings.allow_incremental_payment and payment_mode == 'partial':
        if not payment_amount_input:
            flash("Enter an amount to make a partial payment.", "error")
            return redirect(url_for('student.rent'))
        try:
            payment_amount = _quantize_currency(payment_amount_input)
            if payment_amount <= Decimal('0'):
                flash("Payment amount must be greater than 0.", "error")
                return redirect(url_for('student.rent'))
            if payment_amount > remaining_amount:
                flash(f"Payment amount (${payment_amount:.2f}) exceeds remaining balance (${remaining_amount:.2f}). Paying exact remaining amount.", "info")
                payment_amount = remaining_amount
        except (ValueError, InvalidOperation):
            flash("Invalid payment amount.", "error")
            return redirect(url_for('student.rent'))
    else:
        payment_amount = remaining_amount

    # Get banking settings for overdraft handling (reuse teacher_id from above)
    banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id).first() if teacher_id else None

    # Check if student has enough funds for this payment using shared utility
    overdraft_shortfall = Decimal('0.00')
    allowed, shortfall, _, _ = evaluate_overdraft_allowance(
        student,
        payment_amount,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code
    )
    if not allowed:
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(
            student,
            banking_settings,
            teacher_id=teacher_id,
            join_code=join_code,
            force=True
        )
        if fee_charged:
            db.session.commit()

        if banking_settings and banking_settings.overdraft_protection_enabled:
            message = (f"Insufficient funds in both checking and savings. You need "
                       f"${payment_amount:.2f} but have ${checking_balance + savings_balance:.2f}.")
        else:
            message = (f"Insufficient funds. You need ${payment_amount:.2f} but only "
                       f"have ${checking_balance:.2f}.")

        if fee_charged:
            message += f" Overdraft fee of ${fee_amount:.2f} charged."

        flash(message, "error")
        return redirect(url_for('student.rent'))

    if shortfall > 0:
        overdraft_shortfall = shortfall

    # Duplicate submission guard: reject if the same student submitted a payment
    # for the same coverage period within the last 5 seconds (soft guard only).
    _dup_cutoff = utc_now() - timedelta(seconds=5)
    _dup_check = RentPayment.query.filter(
        RentPayment.student_id == student.id,
        RentPayment.period == period,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
        RentPayment.join_code == join_code,
        RentPayment.payment_date >= _dup_cutoff,
    ).first()
    if _dup_check:
        current_app.logger.warning(
            "Rapid-succession rent submission rejected: student=%s period=%s "
            "coverage=%s/%s join_code=%s — prior payment id=%s submitted within 5s.",
            student.id, period, coverage_month, coverage_year, join_code,
            getattr(_dup_check, 'id', '?'),
        )
        flash("Payment already submitted. Please wait a moment before trying again.", "info")
        return redirect(url_for('student.rent'))

    # FIX: Process payment with teacher_id
    # Deduct from checking account
    is_partial = settings.allow_incremental_payment and payment_mode == 'partial' and payment_amount < remaining_amount
    billed_period_date = payment_due_date or now
    payment_description = f'Rent for Period {period} - {billed_period_date.strftime("%B %Y")}'
    if is_partial and settings.allow_incremental_payment:
        payment_description += f' (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})'
    elif late_fee > Decimal('0'):
        payment_description += f' (includes ${late_fee:.2f} late fee)'

    projected_balance = Decimal(str(checking_balance)) - payment_amount

    # Pre-insert guard: abort if amount resolved to zero or less before touching the DB.
    if payment_amount <= Decimal('0'):
        current_app.logger.warning(
            "Pre-insert guard triggered: payment_amount=%.2f <= 0 for student=%s period=%s "
            "coverage=%s/%s — aborting without DB write.",
            payment_amount, student.id, period, coverage_month, coverage_year,
        )
        flash("Payment amount resolved to zero; no payment was created.", "error")
        return redirect(url_for('student.rent'))

    try:
        transaction = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,  # CRITICAL: Add join_code for period isolation
            amount=-payment_amount,
            account_type='checking',
            status=TransactionStatus.PENDING,
            type='Rent Payment',
            description=payment_description
        )
        student.transactions.append(transaction)
        db.session.add(transaction)

        # Calculate late fee portion for this payment (proportional if partial payment)
        late_fee_for_this_payment = Decimal('0.00')
        if is_late and late_fee > Decimal('0.00'):
            # If this is a partial payment, allocate late fee proportionally
            if is_partial:
                late_fee_for_this_payment = _quantize_currency((payment_amount / total_due) * late_fee)
            else:
                late_fee_for_this_payment = _quantize_currency(late_fee)

        # Record rent payment with coverage period (pre-paid system)
        payment = RentPayment(
            student_id=student.id,
            period=period,
            join_code=join_code,
            amount_paid=payment_amount,
            period_month=current_month,
            period_year=current_year,
            coverage_month=coverage_month,
            coverage_year=coverage_year,
            was_late=is_late,
            late_fee_charged=late_fee_for_this_payment
        )
        db.session.add(payment)

        db.session.flush()  # Flush to update balances without committing yet

        # Handle overdraft protection transfer if savings covers a shortfall
        if banking_settings and banking_settings.overdraft_protection_enabled and overdraft_shortfall > 0:
            _transfer_cid = str(uuid.uuid4())
            transfer_tx_withdraw = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=-overdraft_shortfall,
                account_type='savings',
                status=TransactionStatus.PENDING,
                type='Withdrawal',
                description='Overdraft protection transfer to checking',
                transfer_correlation_id=_transfer_cid,
            )
            transfer_tx_deposit = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,  # CRITICAL: Add join_code for period isolation
                amount=overdraft_shortfall,
                account_type='checking',
                status=TransactionStatus.PENDING,
                type='Deposit',
                description='Overdraft protection transfer from savings',
                transfer_correlation_id=_transfer_cid,
            )
            db.session.add(transfer_tx_withdraw)
            db.session.add(transfer_tx_deposit)
            db.session.flush()  # Flush to update balances

        # Check if overdraft fee should be charged (after overdraft protection)
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=teacher_id, join_code=join_code)

        # Award Hall Passes if rent is fully paid (top-off model)
        passes_awarded = 0
        # Only award if this payment completes full rent (not already fully paid)
        if total_paid_so_far < total_due and (total_paid_so_far + payment_amount >= total_due):
            passes_awarded, _, _ = _ensure_rent_hall_pass_top_off(
                student,
                context,
                settings=settings,
                now=now,
            )

        # Grant per-use free uses if rent is fully paid
        per_use_items_granted = 0
        if total_paid_so_far < total_due and (total_paid_so_far + payment_amount >= total_due):
            from app.models import RentItem
            per_use_items = RentItem.query.filter_by(
                rent_setting_id=settings.id,
                rent_item_type='per_use'
            ).all()

            for pu_item in per_use_items:
                if not pu_item.store_item_id:
                    continue

                # Check if student already has an active (non-expired) StudentItem with uses_remaining for this store item
                existing = StudentItem.query.filter(
                    StudentItem.student_id == student.id,
                    StudentItem.store_item_id == pu_item.store_item_id,
                    db.or_(
                        StudentItem.uses_remaining > 0,
                        StudentItem.uses_remaining == -1
                    ),
                    StudentItem.join_code == join_code,
                    db.or_(
                        StudentItem.expiry_date.is_(None),
                        StudentItem.expiry_date > utc_now()
                    )
                ).first()

                if existing:
                    # Top-off: reset uses_remaining to the granted amount (or unlimited)
                    if pu_item.use_limit:
                        existing.uses_remaining = pu_item.use_limit
                    else:
                        existing.uses_remaining = -1
                    continue

                # Calculate expiry (next rent due date)
                expiry_date = None
                if settings.first_rent_due_date:
                    from app.routes.api import _calculate_due_dates
                    now_ts = utc_now()
                    current_due, next_due = _calculate_due_dates(settings, now_ts)
                    if next_due:
                        expiry_date = next_due

                # Grant a free StudentItem with uses_remaining
                granted_item = StudentItem(
                    student_id=student.id,
                    store_item_id=pu_item.store_item_id,
                    join_code=join_code,
                    purchase_date=utc_now(),
                    expiry_date=expiry_date,
                    status='purchased',
                    is_from_bundle=False,
                    quantity_purchased=1,
                    uses_remaining=pu_item.use_limit if pu_item.use_limit else -1
                )
                db.session.add(granted_item)
                per_use_items_granted += 1

        # Commit all transactions together
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "rent_pay: unhandled error during payment commit for student=%s period=%s "
            "coverage=%s/%s join_code=%s — rolled back.",
            student.id, period, coverage_month, coverage_year, join_code,
        )
        flash("An unexpected error occurred while processing your payment. No charges were made. Please try again.", "error")
        return redirect(url_for('student.rent'))

    # Calculate new totals after this payment
    new_total_paid = total_paid_so_far + payment_amount
    new_remaining = total_due - new_total_paid

    # Success message
    if is_partial and settings.allow_incremental_payment:
        if new_remaining > 0:
            flash(f"Partial payment of ${payment_amount:.2f} successful! Remaining balance: ${new_remaining:.2f}", "success")
        else:
            msg = f"Final payment of ${payment_amount:.2f} successful! Rent for Period {period} is now fully paid."
            if passes_awarded > 0:
                msg += f" You received {passes_awarded} hall passes!"
            flash(msg, "success")
    else:
        msg = f"Rent payment for Period {period} (${payment_amount:.2f}) successful!"
        if passes_awarded > 0:
            msg += f" You received {passes_awarded} hall passes!"
        flash(msg, "success")

    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def login():
    """Student login with username and PIN."""
    form = StudentLoginForm()
    if form.validate_on_submit():
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Verify Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response')
        if not verify_turnstile_token(turnstile_token, get_real_ip()):
            current_app.logger.warning(f"Turnstile verification failed for student login attempt")
            if is_json:
                return jsonify(status="error", message="CAPTCHA verification failed. Please try again."), 403
            flash("CAPTCHA verification failed. Please try again.", "error")
            return redirect(url_for('student.login', next=request.args.get('next')))

        username = form.username.data.strip()
        pin = form.pin.data.strip()
        
        # Lookup student by username
        lookup_hash = hash_username_lookup(username)
        student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()

        try:
            # Fallback for legacy accounts without deterministic lookup hashes
            if not student:
                legacy_students_missing_lookup_hash = Student.query.filter(
                    Student.username_lookup_hash.is_(None),
                    Student.username_hash.isnot(None),
                )

                # Short-circuit if there are no legacy rows to scan
                if legacy_students_missing_lookup_hash.limit(1).first():
                    for s in legacy_students_missing_lookup_hash.yield_per(50):
                        candidate_hash = hash_username(username, s.salt)
                        if candidate_hash == s.username_hash:
                            student = s
                            break

            # Validate PIN
            pin_valid = False
            if student:
                pin_valid = check_password_hash(student.pin_hash or '', pin)

            if not student or not pin_valid:
                if is_json:
                    return jsonify(status="error", message="Invalid credentials"), 401
                flash("Invalid credentials", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))

            if not is_student_account_active(student):
                if is_json:
                    return jsonify(status="error", message="Account is inactive. Contact your teacher."), 403
                flash("Your account is inactive. Contact your teacher.", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))

            if not student.username_lookup_hash:
                student.username_lookup_hash = lookup_hash
                db.session.commit()

        except Exception as e:
            db.session.rollback()
            current_app.logger.error("Error during student login authentication")
            if is_json:
                return jsonify(status="error", message="An error occurred during login. Please try again."), 500
            flash("An error occurred during login. Please try again.", "error")
            return redirect(url_for('student.login'))

        # --- Set session timeout ---
        # Clear old student-specific session keys without wiping the CSRF token
        session.pop('student_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        # Explicitly clear other potential student-related session keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)
        clear_teacher_display_name_cache()


        session['student_id'] = student.id
        session['login_time'] = utc_now().isoformat()
        session['last_activity'] = session['login_time']
        _prime_student_teacher_display_name_cache(student.id)


        # Removed redirect to student_setup for has_completed_setup; new onboarding flow uses claim → username → pin/passphrase.

        # One-time username migration: redirect students whose usernames were
        # generated with the old dob_sum format to pick a new theme word.
        if not student.username_migrated:
            if is_json:
                return jsonify(
                    status="success",
                    message="Login successful",
                    redirect=url_for('student.migrate_username'),
                )
            return redirect(url_for('student.migrate_username'))

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            return redirect(url_for('student.dashboard'))
        return redirect(next_url or url_for('student.dashboard'))  # nosec # Safe: validated by is_safe_url()

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)

@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    # Check if this is a demo session
    is_demo = session.get('is_demo', False)
    demo_session_id = session.get('demo_session_id')

    if is_demo and demo_session_id:
        # Clean up demo session
        from app.models import DemoStudent
        try:
            demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
            if demo_session:
                demo_session.is_active = False
                demo_session.ended_at = utc_now()

                cleanup_demo_student_data(demo_session)

                db.session.commit()
                current_app.logger.info(f"Demo session {demo_session_id} ended and cleaned up")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cleaning up demo session: {e}", exc_info=True)

    session.clear()
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


@student_bp.route('/switch-class/<join_code>', methods=['POST'])
@login_required
def switch_class(join_code):
    """Switch to a different class using join_code for proper multi-tenancy isolation."""
    from app.models import TeacherBlock, Admin

    student = get_logged_in_student()

    # Verify student has a claimed seat for this join_code
    seat = TeacherBlock.query.filter_by(
        student_id=student.id,
        join_code=join_code,
        is_claimed=True
    ).first()

    if not seat:
        return jsonify(status="error", message="You don't have access to that class."), 403

    # Update session with new join code
    session['current_join_code'] = join_code

    # Get teacher name for response
    teacher = db.session.get(Admin, seat.teacher_id)
    teacher_cache = get_teacher_display_name_cache()
    teacher_name = teacher_cache.get(str(seat.teacher_id))
    if not teacher_name and teacher:
        teacher_name = teacher.get_display_name()
        upsert_teacher_display_name_cache({str(seat.teacher_id): teacher_name})
    if not teacher_name:
        teacher_name = "Unknown"

    # Get block/period info
    block_display = f"Block {seat.block.upper()}" if seat.block else "Unknown Block"

    return jsonify(
        status="success",
        message=f"Switched to {teacher_name}'s class ({block_display})",
        teacher_name=teacher_name,
        block=seat.block
    )


@student_bp.route('/switch-period/<int:teacher_id>', methods=['POST'])
@login_required
def switch_period(teacher_id):
    """DEPRECATED: Use switch_class instead. Kept for backwards compatibility."""
    student = get_logged_in_student()

    # Verify student has access to this teacher
    teacher_ids = [t.id for t in student.get_all_teachers()]
    if teacher_id not in teacher_ids:
        flash("You don't have access to that class.", "error")
        return redirect(url_for('student.dashboard'))

    # Update session with new teacher (old method)
    session['current_teacher_id'] = teacher_id

    # Get teacher name for flash message
    from app.models import Admin
    teacher = db.session.get(Admin, teacher_id)
    if teacher:
        flash(f"Switched to {teacher.get_display_name()}'s class")

    return redirect(url_for('student.dashboard'))


# -------------------- SETUP COMPLETE --------------------
# Note: This route is not prefixed with /student for backward compatibility

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html', student_name=student.first_name)


# -------------------- HELP AND SUPPORT - ISSUE RESOLUTION SYSTEM --------------------

@student_bp.route('/help-support', methods=['GET'])
@login_required
def help_support():
    """Show the student help and support page with issue tracking."""
    from app.utils.issue_categories import init_default_categories
    from app.models import Issue, IssueResolutionAction

    student = get_logged_in_student()
    class_context = get_current_class_context()

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Initialize default categories if they don't exist
    init_default_categories()

    base_issue_query = Issue.query.options(selectinload(Issue.category)).filter_by(
        student_id=student.id,
        teacher_id=class_context['teacher_id'],
        join_code=class_context['join_code']
    )

    # Get student's issues for current class (last 20)
    my_issues = base_issue_query.order_by(Issue.submitted_at.desc()).limit(20).all()
    teacher_decisions = IssueResolutionAction.query.join(
        Issue, IssueResolutionAction.issue_id == Issue.id
    ).filter(
        Issue.student_id == student.id,
        Issue.teacher_id == class_context['teacher_id'],
        Issue.join_code == class_context['join_code'],
        IssueResolutionAction.join_code == class_context['join_code'],
        IssueResolutionAction.performed_by_type == IssueResolutionAction.PERFORMED_BY_TEACHER,
    ).order_by(IssueResolutionAction.created_at.desc()).limit(100).all()

    return render_template('student_help_support_new.html',
                         current_page='help',
                         page_title='Help & Support',
                         my_issues=my_issues,
                         teacher_decisions=teacher_decisions,
                         help_content=HELP_ARTICLES['student'],
                         format_utc_iso=format_utc_iso)


@student_bp.route('/help-support/submit-issue', methods=['GET', 'POST'])
@login_required
def submit_general_issue():
    """Submit a general issue or help request."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm

    student = get_logged_in_student()
    class_context = get_current_class_context()

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    form = StudentIssueSubmissionForm()
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")
    show_recent_error_option = has_recent_error_for_actor('student', actor_opaque_id)

    # Populate category choices
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('general')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            issue = create_issue(
                student=student,
                teacher_id=class_context['teacher_id'],
                join_code=class_context['join_code'],
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                include_recent_error=include_recent_error,
            )

            flash("Your issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report an Issue',
                         form=form,
                         issue_type='general',
                         show_recent_error_option=show_recent_error_option)


@student_bp.route('/help-support/transaction/<int:transaction_id>/report', methods=['GET', 'POST'])
@login_required
def report_transaction_issue(transaction_id):
    """Report an issue with a specific transaction."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm, TransactionIssueSubmissionForm

    student = get_logged_in_student()
    class_context = get_current_class_context()

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Get the transaction and verify it belongs to this student and class
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        student_id=student.id,
        join_code=class_context['join_code']
    ).first_or_404()

    form = TransactionIssueSubmissionForm()
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")
    show_recent_error_option = has_recent_error_for_actor('student', actor_opaque_id)

    # Populate category choices with general categories
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('transaction')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            create_issue(
                student=student,
                teacher_id=class_context['teacher_id'],
                join_code=class_context['join_code'],
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                related_transaction_id=transaction_id,
                related_record_type='transaction',
                include_recent_error=include_recent_error,
            )

            flash("Your transaction issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting transaction issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report Transaction Issue',
                         form=form,
                         issue_type='transaction',
                         transaction=transaction,
                         show_recent_error_option=show_recent_error_option)


@student_bp.route('/help-support/tap-event/<int:tap_event_id>/report', methods=['GET', 'POST'])
@login_required
def report_tap_event_issue(tap_event_id):
    """Report an issue with a specific tap event (clock in/out record)."""
    from app.utils.issue_categories import get_active_categories
    from app.utils.issue_helpers import create_issue
    from app.forms import StudentIssueSubmissionForm

    student = get_logged_in_student()
    class_context = get_current_class_context()

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Get the tap event and verify it belongs to this student and class
    tap_event = TapEvent.query.filter_by(
        id=tap_event_id,
        student_id=student.id,
        join_code=class_context['join_code']
    ).first_or_404()

    form = StudentIssueSubmissionForm()
    actor_opaque_id = generate_anonymous_code(f"student_issue:{student.id}")
    show_recent_error_option = has_recent_error_for_actor('student', actor_opaque_id)

    # Populate category choices with general categories (includes "Clock In/Out Not Working")
    form.category_id.choices = [(0, 'Select an issue type...')] + get_active_categories('general')

    if form.validate_on_submit():
        include_recent_error = request.form.get('include_recent_error') == 'on' if show_recent_error_option else True
        try:
            create_issue(
                student=student,
                teacher_id=class_context['teacher_id'],
                join_code=class_context['join_code'],
                category_id=form.category_id.data,
                explanation=form.explanation.data,
                expected_outcome=form.expected_outcome.data,
                related_transaction_id=None,  # No transaction for tap events
                related_record_type='tap_event',
                related_record_id=tap_event_id,
                include_recent_error=include_recent_error,
            )

            flash("Your attendance issue has been submitted. Your teacher will review it soon.", "success")
            return redirect(url_for('student.help_support'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting tap event issue: {str(e)}")
            flash("An error occurred while submitting your issue. Please try again.", "error")

    return render_template('student_submit_issue.html',
                         current_page='help',
                         page_title='Report Attendance Issue',
                         form=form,
                         issue_type='attendance',
                         tap_event=tap_event,
                         show_recent_error_option=show_recent_error_option)


# ================== TEACHER ACCOUNT RECOVERY ==================

@student_bp.route('/verify-recovery/<int:code_id>', methods=['GET', 'POST'])
@login_required
def verify_recovery(code_id):
    """
    Student verification page for teacher account recovery.
    Student authenticates with passphrase, then gets a 6-digit code to give to teacher.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    from app.models import StudentRecoveryCode, RecoveryRequest
    recovery_code = db.get_or_404(StudentRecoveryCode, code_id)

    # Verify this is for the logged-in student
    if recovery_code.student_id != student.id:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Check if already verified
    if recovery_code.code_hash:
        flash("You have already verified this recovery request.", "info")
        return redirect(url_for('student.dashboard'))

    # Check if expired
    # Handle timezone naive/aware comparison for SQLite/Test
    expires_at = ensure_utc(recovery_code.recovery_request.expires_at)

    if expires_at < utc_now():
        flash("This recovery request has expired.", "error")
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        passphrase = request.form.get('passphrase', '').strip()

        if not passphrase:
            flash("Please enter your passphrase.", "error")
            return render_template('student_verify_recovery.html',
                                 recovery_code=recovery_code,
                                 student=student)

        # Verify passphrase
        if not student.passphrase_hash or not check_password_hash(student.passphrase_hash, passphrase):
            current_app.logger.warning(f"Recovery verification failed: incorrect passphrase for student {student.id}")
            flash("Incorrect passphrase. Please try again.", "error")
            return render_template('student_verify_recovery.html',
                                 recovery_code=recovery_code,
                                 student=student)

        # Generate 6-digit recovery code using cryptographically secure randomness
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])

        # Hash and store the code
        recovery_code.code_hash = hash_hmac(code.encode(), b'')
        recovery_code.verified_at = utc_now()
        db.session.commit()

        current_app.logger.info(f"Student {student.id} verified recovery request {recovery_code.recovery_request_id}")

        return render_template('student_verify_recovery.html',
                             recovery_code=recovery_code,
                             student=student,
                             generated_code=code,
                             verified=True)

    return render_template('student_verify_recovery.html',
                         recovery_code=recovery_code,
                         student=student)


@student_bp.route('/dismiss-recovery/<int:code_id>', methods=['POST'])
@login_required
def dismiss_recovery(code_id):
    """
    Dismiss the recovery notification banner.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    from app.models import StudentRecoveryCode
    recovery_code = db.get_or_404(StudentRecoveryCode, code_id)

    # Verify this is for the logged-in student
    if recovery_code.student_id != student.id:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Mark as dismissed
    recovery_code.dismissed = True
    db.session.commit()

    flash("Recovery notification dismissed. You can still verify later from your notifications.", "info")
    return redirect(url_for('student.dashboard'))

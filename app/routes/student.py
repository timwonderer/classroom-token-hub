"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import secrets
import re
from collections import defaultdict
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Blueprint, redirect, url_for, flash, request, session, jsonify, current_app, has_app_context, abort
from sqlalchemy import or_, func, select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from dateutil.relativedelta import relativedelta

from app.extensions import db, limiter
from app.models import (
    Student, Transaction, TransactionStatus, TapEvent, StoreItem, StoreItemBlock, StudentItem,
    RentSettings, RentPayment, RentWaiver, InsurancePolicy, StudentInsurance, InsuranceClaim,
    BankingSettings, UserReport, FeatureSettings, Issue, Seat, User, StudentTeacher,
    ClassMembership, ClassEconomy, TeacherBlock, _quantize_currency
)
from app.auth import (
    admin_required,
    get_current_class_id,
    get_current_seat,
    get_current_user,
    get_current_student_seat,
    login_required,
    get_logged_in_student,
    is_student_account_active,
    SESSION_TIMEOUT_MINUTES,
    sync_student_session_context,
)
from app.forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, InsuranceClaimForm, StudentCompleteProfileForm
)

# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso, render_template_with_fallback as render_template
from app.utils.constants import THEME_PROMPTS
from app.utils.turnstile import verify_turnstile_token
from app.utils.ip_handler import get_real_ip
from app.utils.claim_credentials import compute_primary_claim_hash, match_claim_hash
from app.utils.name_utils import hash_last_name_parts
from app.utils.overdraft import charge_overdraft_fee_if_needed, evaluate_overdraft_allowance
from app.utils.help_content import HELP_ARTICLES
from app.utils.economy_policy import get_class_feature_settings, resolve_feature_class
from app.hash_utils import hash_hmac, hash_username, hash_username_lookup
from app.access import (
    AccessScopeDenied,
    resolve_scope,
    resolve_student_class_switch_scope,
)
from app.services.attendance_service import get_all_block_statuses
from app.services.ledger_service import (
    apply_overdraft_fee_if_needed as apply_ledger_overdraft_fee,
    apply_monthly_savings_interest as post_monthly_savings_interest,
    get_available_balances,
)
from app.services import access_policy_service, identity_service, store_service
from app.services.recovery_bridge_service import (
    dismiss_recovery_code as dismiss_recovery_code_row,
    get_pending_recovery_code_for_student,
    get_recovery_code_for_student,
    set_recovery_code_verified,
)
from app.feats.base import feat_shell
from app.feats.rent_payment_feat import execute_rent_payment
from app.feats.transfer_feat import execute_account_transfer
from app.feats.insurance_purchase_feat import execute_insurance_purchase
from app.feats.insurance_claim_feat import execute_file_claim
from app.payroll import get_pay_rate_for_block
from app.utils.time import (
    utc_now,
    ensure_utc,
    normalize_for_db,
    get_timezone,
    class_date,
    claim_period_bounds_utc,
    get_class_month_start_utc,
    get_class_week_range_utc,
    get_class_now,
)
from app.utils.seat_scope import get_seat_id_for_class, transaction_scope_filter, seat_scoped_filter
from app.utils.insurance_eligibility import (
    compute_waiting_end_class_for_enrollment,
    evaluate_claim_transaction_eligibility,
    collect_reimbursed_source_tx_ids,
    resolve_claim_type,
)


def _get_identity_bound_seat_options(student: Student):
    """Return class options for a student's identity-bound seats."""
    seat_rows = (
        db.session.query(Seat, ClassEconomy)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.student_id == student.id,
            Seat.user_id.isnot(None),
            Seat.claimed_at.isnot(None),
            Seat.class_id.isnot(None),
        )
        .order_by(ClassEconomy.display_name.asc(), ClassEconomy.join_code.asc(), Seat.id.asc())
        .all()
    )
    return [
        {
            "seat_id": seat.id,
            "class_id": seat.class_id,
            "join_code": seat.join_code,
            "class_identifier": seat.block_identifier or seat.block or seat.join_code,
            "class_name": class_row.display_name,
        }
        for seat, class_row in seat_rows
    ]
from app.utils.display_name_session import (
    get_teacher_display_name_cache,
    upsert_teacher_display_name_cache,
    clear_teacher_display_name_cache,
)
from app.services.tlcp import has_recent_error_for_actor

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')

STUDENT_FEATURE_ENDPOINTS = {
    'student.payroll': 'payroll',
    'student.transfer': 'banking',
    'student.student_insurance': 'insurance',
    'student.purchase_insurance': 'insurance',
    'student.cancel_insurance': 'insurance',
    'student.file_claim': 'insurance',
    'student.view_policy': 'insurance',
    'student.shop': 'store',
    'student.rent': 'rent',
    'student.rent_pay': 'rent',
}


@student_bp.before_request
def enforce_student_feature_gates():
    """Hide disabled student features by returning hard 404 for mapped routes."""
    endpoint = request.endpoint or ""
    feature_name = STUDENT_FEATURE_ENDPOINTS.get(endpoint)
    if not feature_name:
        return None

    # Let auth/session guards run first when no student is logged in.
    if not get_logged_in_student():
        return None

    # Some legacy tests/flows hydrate seat context lazily during route execution.
    # Only enforce here when class context is already resolvable.
    if not get_current_class_context():
        return None

    if not is_feature_enabled(feature_name):
        abort(404)
    return None

# Tolerance used to match RentPayment rows with their Transaction rows.
# This guards against small timestamp drift without weakening ownership checks.
RENT_PAYMENT_MATCH_TOLERANCE_SECONDS = 300


# -------------------- DATETIME HELPERS --------------------




# -------------------- PERIOD SELECTION HELPERS --------------------

def _find_linked_user_for_student(student_id: int | None) -> User | None:
    if not student_id:
        return None
    return (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .filter(
            Seat.student_id == student_id,
            Seat.user_id.isnot(None),
        )
        .order_by(Seat.id.asc())
        .first()
    )


def _get_or_create_setup_user_for_student(student_id: int | None) -> User | None:
    if not student_id:
        return None

    user = _find_linked_user_for_student(student_id)
    if user:
        return user

    user = User(
        username_hash=hash_username_lookup(f"pending_{student_id}_{secrets.token_urlsafe(8)}"),
        password_hash=generate_password_hash(secrets.token_urlsafe(24)),
    )
    db.session.add(user)
    db.session.flush()
    return user


def _get_or_create_bridge_seat_for_teacher_block(
    teacher_block,
    student_id: int | None = None,
    user_id: int | None = None,
) -> Seat | None:
    if not teacher_block or not teacher_block.join_code:
        return None

    seat = (
        Seat.query.filter_by(
            join_code=teacher_block.join_code,
            student_id=student_id or teacher_block.student_id,
        )
        .order_by(Seat.id.asc())
        .first()
    )
    if seat:
        if user_id and seat.user_id != user_id:
            seat.user_id = user_id
        if seat.block_identifier is None and teacher_block.block:
            seat.block_identifier = teacher_block.block
        if seat.block is None and teacher_block.block:
            seat.block = teacher_block.block
        if not seat.claimed_at and teacher_block.claimed_at:
            seat.claimed_at = teacher_block.claimed_at
        return seat

    seat = Seat(
        user_id=user_id,
        class_id=getattr(teacher_block, "class_id", None),
        role='student',
        block_identifier=teacher_block.block,
        join_code=teacher_block.join_code,
        student_id=student_id or teacher_block.student_id,
        block=teacher_block.block,
        claimed_at=teacher_block.claimed_at,
    )
    db.session.add(seat)
    db.session.flush()
    return seat


def _find_existing_teacher_shadow_student(teacher_id: int | None) -> Student | None:
    if not teacher_id:
        return None

    return (
        Student.query
        .join(StudentTeacher, StudentTeacher.student_id == Student.id)
        .filter(
            StudentTeacher.teacher_id == teacher_id,
            Student.is_teacher.is_(True),
        )
        .order_by(Student.id.asc())
        .first()
    )


def _ensure_student_class_membership(student_id: int | None, join_code: str | None) -> None:
    if not student_id or not join_code:
        return

    existing_membership = ClassMembership.query.filter_by(
        join_code=join_code,
        student_id=student_id,
    ).first()
    if existing_membership:
        return

    db.session.add(ClassMembership(
        join_code=join_code,
        student_id=student_id,
        role='student',
    ))


def _ensure_class_anchor_for_teacher_block(teacher_block) -> str | None:
    """Backfill the canonical class row for legacy seats before v2 membership writes."""
    if not teacher_block or not teacher_block.join_code or not teacher_block.teacher_id:
        return getattr(teacher_block, "class_id", None) if teacher_block else None

    class_row = ClassEconomy.query.filter_by(join_code=teacher_block.join_code).first()
    if class_row is None:
        class_row = ClassEconomy(
            join_code=teacher_block.join_code,
            teacher_id=teacher_block.teacher_id,
            created_by_admin_id=teacher_block.teacher_id,
            display_name=teacher_block.block,
            class_id=getattr(teacher_block, "class_id", None),
        )
        db.session.add(class_row)
        db.session.flush()

    teacher_block.class_id = teacher_block.class_id or class_row.class_id

    admin_membership = ClassMembership.query.filter_by(
        join_code=teacher_block.join_code,
        admin_id=teacher_block.teacher_id,
    ).first()
    if not admin_membership:
        db.session.add(ClassMembership(
            join_code=teacher_block.join_code,
            admin_id=teacher_block.teacher_id,
            role='admin',
        ))

    teacher_seat = Seat.query.filter_by(
        class_id=class_row.class_id,
        role='teacher',
    ).first()
    if teacher_seat is None:
        db.session.add(Seat(
            class_id=class_row.class_id,
            join_code=teacher_block.join_code,
            role='teacher',
        ))

    return class_row.class_id


def _get_claimed_setup_state():
    seat_id = session.get('claimed_seat_id')
    student_id = session.get('claimed_student_id')
    user_id = session.get('claimed_user_id')

    seat = db.session.get(Seat, seat_id) if seat_id else None
    student = db.session.get(Student, student_id) if student_id else None
    user = db.session.get(User, user_id) if user_id else None

    if seat and not student and seat.student_id:
        student = db.session.get(Student, seat.student_id)
    if seat and not user and seat.user_id:
        user = db.session.get(User, seat.user_id)

    return seat, student, user

def get_current_class_context():
    """Get the currently selected class context.

    CRITICAL: This function enforces proper multi-tenancy isolation by using
    class_id as the source of truth.

    Returns:
        dict with keys: class_id, join_code, teacher_id, block, seat_id
        None if no context available
    """
    student = get_logged_in_student()
    if not student:
        return None

    current_seat = get_current_student_seat()
    if not current_seat:
        # Fallback to the first seat if no seat selected
        current_seat = Seat.query.filter_by(student_id=student.id).order_by(Seat.id.asc()).first()
        if current_seat:
            sync_student_session_context(student, seat_id=current_seat.id)
    
    if current_seat:
        class_row = ClassEconomy.query.filter_by(class_id=current_seat.class_id).first()
        if class_row:
            return {
                'class_id': class_row.class_id,
                'join_code': class_row.join_code,
                'teacher_id': class_row.teacher_id,
                'block': current_seat.block_identifier or current_seat.block,
                'seat_id': current_seat.id,
            }

    return None


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
    """Return rent settings scoped strictly to the current class_id."""
    if not context:
        return None

    class_id = context.get('class_id')
    current_block = (context.get('block') or '').strip().upper()
    if not class_id:
        return None

    base_query = RentSettings.query.filter(
        RentSettings.class_id == class_id,
    )
    if current_block:
        scoped = base_query.filter(func.upper(RentSettings.block) == current_block).first()
        if scoped:
            return scoped

    if not current_block:
        scoped = base_query.filter(RentSettings.block.is_not(None)).first()
        if scoped:
            return scoped

    return base_query.filter(RentSettings.block.is_(None)).first()


def _support_actor_public_id(class_context):
    seat_id = class_context.get('seat_id') if class_context else None
    seat = db.session.get(Seat, seat_id) if seat_id else None
    return seat.public_id if seat else None


def _get_rent_coverage_window(settings, coverage_due_date):
    """Return canonical [start, end) coverage window for a rent cycle."""
    if not settings or not coverage_due_date:
        return (None, None)
    start = ensure_utc(coverage_due_date)
    period_delta = _get_rent_period_delta(settings)
    end = _add_rent_period(start, period_delta)
    return (start, end)


def get_banking_settings_for_context(context):
    """Return banking settings scoped strictly to the current class_id."""
    if not context:
        return None

    class_id = context.get('class_id')
    current_block = (context.get('block') or '').strip().upper()
    if not class_id:
        return None

    base_query = BankingSettings.query.filter(
        BankingSettings.class_id == class_id,
    )
    if current_block:
        scoped = base_query.filter(func.upper(BankingSettings.block) == current_block).first()
        if scoped:
            return scoped

    return base_query.filter(BankingSettings.block.is_(None)).first()


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


def get_feature_settings_for_student():
    """
    Get feature settings for the currently logged-in student.

    Returns the class-scoped feature settings for the student's current teacher/period context.

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

    join_code = context.get('join_code')
    if not join_code:
        return FeatureSettings.get_defaults()

    current_block = (context.get('block') or '').strip().upper()
    scoped_features = get_class_feature_settings(
        teacher_id,
        block=current_block,
        join_code=join_code,
    )
    if scoped_features:
        return scoped_features["features"]

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

    context = get_current_class_context()
    if not context:
        return False

    scoped_feature = resolve_feature_class(
        context.get('teacher_id'),
        feature_name,
        block=context.get('block'),
        join_code=context.get('join_code'),
    )
    return bool(scoped_feature["enabled"]) if scoped_feature else False


def calculate_scoped_balances(student: 'Student', join_code: str, teacher_id: int) -> tuple[Decimal, Decimal]:
    """Compatibility wrapper around the ledger-owned balance query."""
    del teacher_id
    if not student or not join_code:
        return Decimal('0.00'), Decimal('0.00')
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        return Decimal('0.00'), Decimal('0.00')
    seat_id = get_seat_id_for_class(student.id, class_row.class_id)
    if not seat_id:
        return Decimal('0.00'), Decimal('0.00')
    return get_available_balances(seat_id, class_row.class_id)



# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-001")
def claim_account():
    """
    PAGE 1: Claim Account - Verify identity using join code to begin setup.

    New join code-based flow:
    1. Student enters join code (resolves to class_id)
    2. Student enters full first + last name
    3. If multiple seats match, student enters optional dedupe code
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
        first_name = (form.first_name.data or "").strip()
        last_name = form.last_name.data.strip()
        dedupe_code = (form.dedupe_code.data or "").strip().upper()

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

        # Try to find matching seats by v2 claim identity:
        # join_code + full first_name + full last_name (+ optional dedupe on collisions).
        from app.utils.name_utils import verify_last_name_parts

        matched_seats = []
        match_attempts = []  # Track why each seat didn't match

        for seat in unclaimed_seats:
            seat_first_name = (seat.first_name or "").strip()
            first_name_matches = seat_first_name.casefold() == first_name.casefold()

            # Check last name with fuzzy matching
            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )
            match_attempts.append({
                'seat_id': seat.id,
                'first_name_matches': first_name_matches,
                'last_name_matches': last_name_matches,
            })

            if first_name_matches and last_name_matches:
                matched_seats.append(seat)

        if not matched_seats:
            # Log detailed match failure information
            current_app.logger.warning(
                f"Claim attempt failed for join_code={join_code}, "
                f"first_name={first_name}, with last_name from input. "
                f"Attempted {len(match_attempts)} seat(s). Match details: {match_attempts}"
            )
            flash("No matching account found. Please check your join code and credentials.", "claim")
            return redirect(url_for('student.claim_account'))

        matched_seat = None
        if len(matched_seats) == 1:
            matched_seat = matched_seats[0]
        else:
            if not dedupe_code:
                flash(
                    "Multiple students in this class share that name. Enter your deduplication code from your teacher.",
                    "claim",
                )
                return redirect(url_for('student.claim_account'))
            dedupe_matches = [
                seat
                for seat in matched_seats
                if ((seat.dedupe_key or "")[:8].upper() == dedupe_code)
            ]
            if len(dedupe_matches) != 1:
                flash("Invalid deduplication code. Check with your teacher.", "claim")
                return redirect(url_for('student.claim_account'))
            matched_seat = dedupe_matches[0]

        # Check if this student already has an account (claiming from another teacher).
        # Use first_half_hash for matching — it stays set even after dob_sum is cleaned up
        # post-claim, so this lookup works regardless of cleanup state.
        existing_student = None
        if matched_seat.is_teacher:
            existing_student = _find_existing_teacher_shadow_student(matched_seat.teacher_id)
        if not existing_student:
            existing_student = Student.query.filter_by(
                first_half_hash=matched_seat.first_half_hash
            ).first()

        if existing_student:
            # Student already exists - link this seat to existing student
            _ensure_class_anchor_for_teacher_block(matched_seat)
            matched_seat.student_id = existing_student.id
            matched_seat.is_claimed = True
            matched_seat.claimed_at = utc_now()
            # Null out PII on the now-claimed seat — no longer needed for matching
            matched_seat.dob_sum_hash = None
            matched_seat.last_name_hash_by_part = None

            # Create StudentTeacher link
            existing_link = StudentTeacher.query.filter_by(
                student_id=existing_student.id,
                teacher_id=matched_seat.teacher_id
            ).first()

            if not existing_link:
                link = StudentTeacher(
                    student_id=existing_student.id,
                    teacher_id=matched_seat.teacher_id,
                    join_code=matched_seat.join_code,
                )
                db.session.add(link)

            _ensure_student_class_membership(existing_student.id, matched_seat.join_code)
            linked_user = _get_or_create_setup_user_for_student(existing_student.id)
            bridge_seat = _get_or_create_bridge_seat_for_teacher_block(
                matched_seat,
                existing_student.id,
                linked_user.id if linked_user else None,
            )

            db.session.flush()

            # Student already completed setup in another class, redirect to login
            if existing_student.has_completed_setup:
                flash("This seat has been linked to your existing account. Please log in.", "claim")
                return redirect(url_for('student.login'))
            else:
                # Continue setup process
                session['claimed_student_id'] = existing_student.id
                session['claimed_seat_id'] = bridge_seat.id if bridge_seat else None
                session['claimed_user_id'] = linked_user.id if linked_user else None
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)
                return redirect(url_for('student.create_username'))

        # New student - create Student record
        # Generate an opaque credential hash value; DOB is no longer part of claim identity.
        _ensure_class_anchor_for_teacher_block(matched_seat)
        second_half_hash = hash_hmac(secrets.token_bytes(16), matched_seat.salt)

        new_student = Student(
            first_name=matched_seat.first_name,
            last_initial=matched_seat.last_initial,
            block=matched_seat.block,
            salt=matched_seat.salt,
            first_half_hash=matched_seat.first_half_hash,
            second_half_hash=second_half_hash,
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
            existing_by_hash = None
            if matched_seat.is_teacher:
                existing_by_hash = _find_existing_teacher_shadow_student(matched_seat.teacher_id)
            if not existing_by_hash:
                existing_by_hash = Student.query.filter_by(
                    first_half_hash=matched_seat.first_half_hash
                ).first()

            if existing_by_hash:
                # Link this seat to the existing student
                _ensure_class_anchor_for_teacher_block(matched_seat)
                matched_seat.student_id = existing_by_hash.id
                matched_seat.is_claimed = True
                matched_seat.claimed_at = utc_now()
                # Null out PII on the now-claimed seat
                matched_seat.dob_sum_hash = None
                matched_seat.last_name_hash_by_part = None

                # Create StudentTeacher link if not exists
                existing_link = StudentTeacher.query.filter_by(
                    student_id=existing_by_hash.id,
                    teacher_id=matched_seat.teacher_id
                ).first()

                if not existing_link:
                    link = StudentTeacher(
                        student_id=existing_by_hash.id,
                        teacher_id=matched_seat.teacher_id,
                        join_code=matched_seat.join_code,
                    )
                    db.session.add(link)

                _ensure_student_class_membership(existing_by_hash.id, matched_seat.join_code)
                linked_user = _get_or_create_setup_user_for_student(existing_by_hash.id)
                bridge_seat = _get_or_create_bridge_seat_for_teacher_block(
                    matched_seat,
                    existing_by_hash.id,
                    linked_user.id if linked_user else None,
                )

                db.session.flush()

                if existing_by_hash.has_completed_setup:
                    flash("This seat has been linked to your existing account. Please log in.", "claim")
                    return redirect(url_for('student.login'))
                else:
                    session['claimed_student_id'] = existing_by_hash.id
                    session['claimed_seat_id'] = bridge_seat.id if bridge_seat else None
                    session['claimed_user_id'] = linked_user.id if linked_user else None
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
        # Null out seat verification hashes once claim succeeds.
        matched_seat.dob_sum_hash = None
        matched_seat.last_name_hash_by_part = None

        # Create StudentTeacher link
        link = StudentTeacher(
            student_id=new_student.id,
            teacher_id=matched_seat.teacher_id,
            join_code=matched_seat.join_code,
        )
        db.session.add(link)
        _ensure_student_class_membership(new_student.id, matched_seat.join_code)
        linked_user = _get_or_create_setup_user_for_student(new_student.id)
        bridge_seat = _get_or_create_bridge_seat_for_teacher_block(
            matched_seat,
            new_student.id,
            linked_user.id if linked_user else None,
        )
        db.session.flush()

        # Start setup flow
        session['claimed_student_id'] = new_student.id
        session['claimed_seat_id'] = bridge_seat.id if bridge_seat else None
        session['claimed_user_id'] = linked_user.id if linked_user else None
        session.pop('generated_username', None)
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)

        return redirect(url_for('student.create_username'))

    return render_template('student_account_claim.html', form=form)


@student_bp.route('/create-username', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-002")
def create_username():
    """PAGE 2: Create Username - Generate themed username."""
    # Only allow if claimed
    seat, student, user = _get_claimed_setup_state()
    if not student:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student.claim_account'))
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
        adjectives = [
            "brave", "clever", "curious", "daring", "eager", "fancy", "gentle", "honest", "jolly", "kind",
            "lucky", "mighty", "noble", "quick", "proud", "silly", "witty", "zesty", "sunny", "chill"
        ]
        adjective = random.choice(adjectives)
        # Username generation uses a transient backend-generated 4-digit
        # segment so setup never derives usernames from DOB or stable IDs.
        numeric_segment = random.randint(1000, 9999)
        initials = f"{student.first_name[0].upper()}{student.last_initial.upper()}"
        username = f"{adjective}{write_in_word}{numeric_segment}{initials}"
        # Save username plaintext in session for display
        session['generated_username'] = username
        user = user or _find_linked_user_for_student(student.id)
        if not user:
            user = User(
                username_hash=hash_username_lookup(username),
                password_hash=generate_password_hash(secrets.token_urlsafe(24)),
            )
            db.session.add(user)
            db.session.flush()
        else:
            user.username_hash = hash_username_lookup(username)

        if seat and seat.user_id != user.id:
            seat.user_id = user.id
            seat.claimed_at = seat.claimed_at or utc_now()

        # Hash and store in legacy student auth fields during the bridge period.
        student.username_hash = hash_username(username, student.salt)
        student.username_lookup_hash = hash_username_lookup(username)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash("That username is unavailable. Please try another word.", "setup")
            return redirect(url_for('student.create_username'))
        session['claimed_user_id'] = user.id
        # Clear theme prompt from session
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)


@student_bp.route('/setup-pin-passphrase', methods=['GET', 'POST'])
@feat_shell("FEAT-IDEN-001")
def setup_pin_passphrase():
    """PAGE 3: Setup PIN & Passphrase - Secure the account."""
    # Only allow if claimed and username generated
    seat, student, user = _get_claimed_setup_state()
    username = session.get('generated_username')
    if not student or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student.claim_account'))
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
        if user:
            user.password_hash = generate_password_hash(passphrase)
        if seat and user and seat.user_id != user.id:
            seat.user_id = user.id
        if seat and not seat.claimed_at:
            seat.claimed_at = utc_now()
        if student.recovery_status == 'to_be_claimed':
            # Complete recovery only after credentials are successfully re-established.
            student.reset_code = None
            student.reset_code_expires_at = None
            student.recovery_status = 'active'

        # Mark profile migration complete; claim verification data is stored only on seats.
        student.has_completed_profile_migration = True

        db.session.flush()
        # Clear session onboarding keys
        session.pop('claimed_student_id', None)
        session.pop('claimed_seat_id', None)
        session.pop('claimed_user_id', None)
        session.pop('generated_username', None)
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('student.setup_complete'))
    return render_template('student_pin_setup.html', username=username, form=form)


# -------------------- ADD NEW CLASS --------------------

@student_bp.route('/add-class', methods=['GET', 'POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def add_class():
    """
    Allow logged-in students to add a new class by entering a join code.

    Each join_code is an independent scoped universe. Credentials entered here
    are matched against the *new* class's own unclaimed roster seat, which still
    carries its own verification hashes (dob_sum, last_name_hash_by_part).
    Those hashes are deleted from the seat after it is claimed.

    Note: The student's own account has no stored dob_sum or last_name_hash_by_part.
    This is intentional —
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
                dob_sum,
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

            dob_sum_matches = (
                seat.dob_sum_hash is not None
                and hash_hmac(str(dob_sum).encode(), seat.salt) == seat.dob_sum_hash
            )
            if credential_matches and last_name_matches and name_matches and dob_sum_matches:
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
            teacher_id=matched_seat.teacher_id
        ).first()

        if existing_link:
            current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            new_block_check = matched_seat.block.strip().upper()
            if new_block_check in current_blocks:
                flash(f"You are already enrolled in Block {new_block_check}.", "warning")
                return redirect(_get_return_target())

        # Link the seat to the student and null out its PII (no longer needed post-claim)
        _ensure_class_anchor_for_teacher_block(matched_seat)
        matched_seat.student_id = student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = utc_now()
        matched_seat.dob_sum_hash = None
        matched_seat.last_name_hash_by_part = None

        # Create StudentTeacher link if it doesn't exist
        if not existing_link:
            link = StudentTeacher(
                student_id=student.id,
                teacher_id=matched_seat.teacher_id,
                join_code=matched_seat.join_code,
            )
            db.session.add(link)

        _ensure_student_class_membership(student.id, matched_seat.join_code)
        linked_user = _get_or_create_setup_user_for_student(student.id)
        _get_or_create_bridge_seat_for_teacher_block(
            matched_seat,
            student.id,
            linked_user.id if linked_user else None,
        )

        # Update student's block to include the new block if not already there
        current_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        new_block = matched_seat.block.strip().upper()

        if new_block not in current_blocks:
            current_blocks.append(new_block)
            student.block = ','.join(sorted(current_blocks))

        try:
            db.session.flush()
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

    try:
        scope = resolve_scope(
            actor=student,
            selected_join_code=session.get("current_join_code"),
        )
        access_policy_service.assert_can_view_dashboard(scope)
    except AccessScopeDenied as exc:
        flash(exc.message, "error")
        return redirect(url_for("student.select_class_context"))
    except access_policy_service.AccessPolicyDenied as exc:
        flash(exc.message, "error")
        return redirect(url_for('student.login'))

    join_code = scope.join_code
    teacher_id = scope.teacher_id
    current_block = scope.block  # Get current class block
    if not scope.class_id:
        flash("Class context unavailable. Please select a class and retry.", "error")
        return redirect(url_for("student.select_class"))
    if not scope.seat_id:
        flash("Seat context unavailable. Please select a class and retry.", "error")
        return redirect(url_for("student.select_class"))

    # Canonical ledger scope: seat_id + class_id.
    transactions = Transaction.query.filter_by(
        seat_id=scope.seat_id,
        class_id=scope.class_id,
    ).order_by(Transaction.timestamp.desc()).all()

    # FIX: Filter student items by current teacher's store
    student_items = student.items.join(
        StoreItem, StudentItem.store_item_id == StoreItem.id
    ).filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired']),
        StudentItem.class_id == scope.class_id,
        StudentItem.seat_id == scope.seat_id,
    ).order_by(StudentItem.purchase_date.desc()).all()

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    checking_balance, savings_balance = get_available_balances(scope.seat_id, scope.class_id)
    # Calculate forecast interest using Decimal
    forecast_interest = _quantize_currency(savings_balance * Decimal('0.045') / Decimal('12'))

    # FIX: Only show tap in/out status for CURRENT class, not all classes
    # Get status for only the current block (not all blocks)
    period_states = get_all_block_statuses(student, class_id=scope.class_id)
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
        blk: (state.get("projected_pay") or 0)
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
    context = {
        'join_code': scope.join_code,
        'teacher_id': scope.teacher_id,
        'class_id': scope.class_id,
        'block': scope.block,
        'seat_id': scope.seat_id,
    }
    teacher_id = scope.teacher_id
    class_id = scope.class_id
    active_insurance = student.get_active_insurance(class_id=join_code, teacher_id=teacher_id)

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
            rent_scope = seat_scoped_filter(RentPayment, student.id, seat_ids)
            all_payments_for_period = RentPayment.query.filter(
                rent_scope,
                RentPayment.class_id == class_id,
                RentPayment.coverage_month == coverage_month,
                RentPayment.coverage_year == coverage_year,
            ).all()

            payments = []
            for payment in all_payments_for_period:
                txn_scope = transaction_scope_filter(Transaction, student.id, seat_ids)
                txn = Transaction.query.filter(
                    txn_scope,
                    Transaction.type == 'Rent Payment',
                    Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
                    Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
                    Transaction.amount == -payment.amount_paid,
                    Transaction.join_code == join_code
                ).first()

                if txn and not txn.is_void:
                    payments.append(payment)

            total_paid = sum(p.amount_paid for p in payments) if payments else Decimal('0.00')
            paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
            late_fee = Decimal('0.00')
            if rent_is_active and now > grace_end_date_for_status and paid_by_grace < rent_settings.rent_amount:
                late_fee = rent_settings.late_fee
            total_due = rent_settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
            is_paid = total_paid >= total_due if rent_is_active else False

            if rent_is_active and not is_paid:
                all_paid = False
                break

        rent_status = {
            'is_active': rent_is_active,
            'is_paid': all_paid if rent_is_active else False,
            'is_preview': is_preview_period
        }

    tz = get_timezone()
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
    pending_recovery_code = get_pending_recovery_code_for_student(student.id, utc_now())

    # --- Calculate weekly/monthly analytics ---
    from app.models import TapEvent
    now_utc = utc_now()
    if class_id:
        class_now_utc = get_class_now(class_id, reference_time_utc=now_utc).astimezone(timezone.utc)
        week_start, week_end = get_class_week_range_utc(class_id, reference_time_utc=class_now_utc)
        month_start = get_class_month_start_utc(class_id, reference_time=class_now_utc)
    else:
        week_start, week_end = get_class_week_range_utc(
            context.get('class_id'),
            reference_time_utc=now_utc,
        ) if context.get('class_id') else (now_utc, now_utc + timedelta(days=7))
        month_start = get_class_month_start_utc(
            context.get('class_id'),
            reference_time=now_utc,
        ) if context.get('class_id') else now_utc



    # Days tapped in this week
    tap_events_this_week = TapEvent.query.filter(
        TapEvent.student_id == student.id,
        TapEvent.join_code == join_code,
        TapEvent.timestamp >= week_start,
        TapEvent.timestamp < week_end,
        TapEvent.is_deleted == False
    ).all()

    # Calculate unique days and total minutes
    unique_days_tapped = len(
        {
            ensure_utc(event.timestamp).astimezone(tz).date()
            for event in tap_events_this_week
            if event.status == 'active'
        }
    )

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
        current_join_code=join_code,
        scoped_total_earnings=student.get_total_earnings(join_code=join_code, teacher_id=teacher_id),
    )


@student_bp.route('/payroll')
@login_required
def payroll():
    """Student payroll page with attendance record, productivity stats, and projected pay."""
    # Check if payroll feature is enabled
    if not is_feature_enabled('payroll'):
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()

    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))
    if not class_id:
        flash("Class context unavailable. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    current_block = (context.get('block') or '').upper()
    join_code = context.get('join_code')
    teacher_id = context.get('teacher_id')
    period_states = get_all_block_statuses(student, class_id=class_id)

    # Scope dashboard data to the selected class context only
    period_states = {current_block: period_states.get(current_block, {})}
    student_blocks = [current_block]

    # Determine the pay rate for the current block (per minute)
    pay_rate_per_second = get_pay_rate_for_block(
        current_block,
        class_id=class_id,
    )
    pay_rate_per_minute = round(pay_rate_per_second * 60, 2)

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: round((state.get("projected_pay") or 0), 2)
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
        now=utc_now(),
        current_join_code=join_code,
        scoped_total_earnings=student.get_total_earnings(join_code=join_code, teacher_id=teacher_id),
    )


# -------------------- FINANCIAL TRANSACTIONS --------------------

@student_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer funds between checking and savings accounts."""
    # Check if banking feature is enabled
    if not is_feature_enabled('banking'):
        abort(404)

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
        
        # Enforce single-use transfer token to prevent form replay
        submitted_token = request.form.get("transfer_token")
        expected_token = session.pop('transfer_token', None)
        if not expected_token or submitted_token != expected_token:
            message = "This transfer has already been processed or the session is invalid. Please refresh the page and try again."
            if is_json:
                return jsonify(status="error", message=message), 400
            flash(message, "transfer_error")
            return redirect(url_for("student.transfer"))

        passphrase = request.form.get("passphrase")
        if not check_password_hash(student.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student.transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        # Convert form input to Decimal for precise financial calculation
        from app.models import _quantize_currency
        amount = _quantize_currency(request.form.get('amount'))

        # CRITICAL FIX: Calculate balances using join_code scoping
        checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)
        banking_settings = get_banking_settings_for_context(context)

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
        # Resolve seat_id and class_id for V2 identity
        from app.models import ClassEconomy
        economy = ClassEconomy.query.filter_by(join_code=join_code, teacher_id=teacher_id).first()
        class_id = economy.class_id if economy else None
        
        if not class_id:
            if is_json:
                return jsonify(status="error", message="Invalid class context."), 400
            flash("Invalid class context.", "transfer_error")
            return redirect(url_for("student.transfer"))

        seat_id = get_seat_id_for_class(student.id, class_id)
        if not seat_id:
            if is_json:
                return jsonify(status="error", message="No seat assigned in this class."), 400
            flash("No seat assigned in this class.", "transfer_error")
            return redirect(url_for("student.transfer"))

        if from_account == 'checking' and amount > checking_balance:
            fee_charged, fee_amount = _charge_overdraft_fee_if_needed(
                student,
                banking_settings,
                class_id=class_id,
                force=True
            )

            message = "Insufficient checking funds."
            if fee_charged:
                message += f" Overdraft fee of ${fee_amount:.2f} charged."
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
            try:
                execute_account_transfer(
                    seat_id=seat_id,
                    class_id=class_id,
                    teacher_id=teacher_id,
                    amount=amount,
                    from_account=from_account,
                    to_account=to_account,
                )
                current_app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for seat {seat_id}"
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

    # CRITICAL FIX v2: Get transactions for display - strict class_id/seat_id scoping.
    transactions = Transaction.query.filter(
        Transaction.seat_id == context.get('seat_id'),
        Transaction.class_id == context.get('class_id'),
        Transaction.is_void == False,
    ).order_by(Transaction.timestamp.desc()).all()
    checking_transactions = [t for t in transactions if t.account_type == 'checking']
    savings_transactions = [t for t in transactions if t.account_type == 'savings']

    # Get banking settings for interest rate display
    settings = get_banking_settings_for_context(context)
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

    import secrets
    transfer_token = secrets.token_hex(16)
    session['transfer_token'] = transfer_token

    return render_template('student_transfer.html',
                         student=student,
                         transactions=transactions,
                         checking_transactions=checking_transactions,
                         savings_transactions=savings_transactions,
                         checking_balance=checking_balance,
                         savings_balance=savings_balance,
                         forecast_interest=forecast_interest,
                         scoped_total_earnings=student.get_total_earnings(join_code=join_code, teacher_id=teacher_id),
                         settings=settings,
                         calculation_type=calculation_type,
                         compound_frequency=compound_frequency,
                         projection_months=projection_months,
                         projection_balances=projection_balances,
                         transfer_token=transfer_token)


def apply_savings_interest(student, annual_rate=Decimal('0.045')):
    """Compatibility command wrapper that forwards savings-interest writes into the ledger service."""
    context = get_current_class_context()
    if not context:
        return None
    interest_tx = post_monthly_savings_interest(
        student,
        teacher_id=context.get('teacher_id'),
        join_code=context.get('join_code'),
        annual_rate=annual_rate,
    )
    return interest_tx


# -------------------- INSURANCE --------------------

@student_bp.route('/insurance', endpoint='student_insurance')
@login_required
def insurance_marketplace():
    """Insurance marketplace - browse and manage policies."""


    # Check if insurance feature is enabled
    if not is_feature_enabled('insurance'):
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context (join_code is source of truth)
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']
    join_code = context['join_code']
    if not class_id:
        class_id = context.get('class_id')
    now_utc = utc_now()

    # FIX: Get student's active policies scoped to current class only
    my_policies = StudentInsurance.query.join(
        InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
    ).filter(
        StudentInsurance.student_id == student.id,
        StudentInsurance.status == 'active',
        StudentInsurance.join_code == join_code,
    ).all()

    # FIX: Get available policies (only from current teacher)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.join_code == join_code,
    ).all()

    # Check which policies can be purchased
    can_purchase = {}
    repurchase_blocks = {}

    for policy in available_policies:
        # Check if already enrolled
        existing = StudentInsurance.query.filter_by(
            student_id=student.id,
            policy_id=policy.id,
            status='active'
        ).first()

        if existing:
            can_purchase[policy.id] = False
            continue

        # Check repurchase restrictions
        if policy.no_repurchase_after_cancel:
            cancelled = StudentInsurance.query.filter_by(
                student_id=student.id,
                policy_id=policy.id,
                status='cancelled'
            ).order_by(StudentInsurance.cancel_date.desc()).first()

            if cancelled and cancelled.cancel_date:
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
    ).all()

    # Group policies by tier for display
    tier_groups = {}
    ungrouped_policies = []
    for policy in available_policies:
        if policy.tier_category_id:
            if policy.tier_category_id not in tier_groups:
                tier_groups[policy.tier_category_id] = {
                    'name': policy.tier_name or f"Tier {policy.tier_category_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups[policy.tier_category_id]['policies'].append(policy)
        else:
            ungrouped_policies.append(policy)

    # Check which tier the student has already selected from
    enrolled_tiers = set()
    for enrollment in my_policies:
        # Normalize dates for safe comparisons in templates
        enrollment.coverage_start_date = ensure_utc(enrollment.coverage_start_date)
        enrollment.cancel_date = ensure_utc(enrollment.cancel_date)
        if enrollment.policy.tier_category_id:
            enrolled_tiers.add(enrollment.policy.tier_category_id)

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

    policy = db.get_or_404(InsurancePolicy, policy_id)

    # FIX: Verify policy belongs to CURRENT teacher only
    if policy.join_code != join_code:
        flash("This insurance policy is not available in your current class.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Check if already enrolled
    existing = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='active'
    ).first()

    if existing:
        flash("You are already enrolled in this policy.", "warning")
        return redirect(url_for('student.student_insurance'))

    # Check repurchase restrictions
    cancelled = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='cancelled'
    ).order_by(StudentInsurance.cancel_date.desc()).first()

    if cancelled:
        # Check for permanent block (no repurchase allowed EVER)
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
    if policy.tier_category_id:
        existing_tier_enrollment = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id == student.id,
            StudentInsurance.status == 'active',
            InsurancePolicy.tier_category_id == policy.tier_category_id,
            StudentInsurance.join_code == join_code,
        ).first()

        if existing_tier_enrollment:
            flash(f"You already have a policy from the '{policy.tier_name or 'this'}' tier. You can only have one policy per tier.", "warning")
            return redirect(url_for('student.student_insurance'))

    # CRITICAL FIX v2: Check sufficient funds using seat/class scoped balance
    checking_balance, savings_balance = calculate_scoped_balances(student, join_code, teacher_id)
    banking_settings = get_banking_settings_for_context(context)
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

    execute_insurance_purchase(
        student=student,
        teacher_id=teacher_id,
        join_code=join_code,
        class_id=context.get('class_id'),
        policy=policy,
        banking_settings=banking_settings,
        overdraft_shortfall=overdraft_shortfall,
    )
    flash(f"Successfully purchased {policy.title}! Coverage starts after {policy.waiting_period_days} day waiting period.", "success")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-OBL-001")
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

    db.session.flush()
    flash(f"Insurance policy '{enrollment.contract_title}' has been cancelled.", "info")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def file_claim(policy_id):
    """File insurance claim."""
    student = get_logged_in_student()

    # Get student's enrollment for this policy
    enrollment = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy_id,
        status='active'
    ).first()

    if not enrollment:
        flash("You are not enrolled in this policy.", "danger")
        return redirect(url_for('student.student_insurance'))
    try:
        scope = resolve_scope(
            actor=student,
            selected_join_code=enrollment.join_code or session.get("current_join_code"),
        )
    except AccessScopeDenied as exc:
        flash(exc.message, "danger")
        return redirect(url_for('student.student_insurance'))

    policy = enrollment.policy
    claim_type = resolve_claim_type(policy_claim_type=policy.claim_type)
    max_claim_amount = enrollment.contract_max_claim_amount
    max_payout_per_period = enrollment.contract_max_payout_per_period
    max_claims_count = enrollment.contract_max_claims_count
    max_claims_period = (enrollment.contract_max_claims_period or 'month').lower()
    claim_time_limit_days = enrollment.contract_claim_time_limit_days
    form = InsuranceClaimForm()
    if claim_type == 'transaction_monetary' and not form.incident_date.data:
        form.incident_date.data = class_date()

    # Validation errors
    errors = []

    # Normalize coverage dates for safe comparisons
    enrollment.coverage_start_date = ensure_utc(enrollment.coverage_start_date)
    enrollment.cancel_date = ensure_utc(enrollment.cancel_date)
    now_utc = utc_now()

    waiting_end_class = compute_waiting_end_class_for_enrollment(
        enrollment,
        fallback_purchase_utc=now_utc,
    )
    coverage_not_started = False
    if waiting_end_class is not None and enrollment.class_id:
        now_class = get_class_now(enrollment.class_id, reference_time_utc=now_utc)
        coverage_not_started = now_class < waiting_end_class
    elif not enrollment.coverage_start_date or enrollment.coverage_start_date > now_utc:
        coverage_not_started = True

    # Check if coverage has started
    if coverage_not_started:
        wait_until = (
            waiting_end_class.strftime('%B %d, %Y')
            if waiting_end_class is not None
            else enrollment.coverage_start_date.strftime('%B %d, %Y') if enrollment.coverage_start_date else 'coverage starts'
        )
        errors.append(f"Coverage has not started yet. Please wait until {wait_until}.")

    # Check if payment is current
    if not enrollment.payment_current:
        errors.append("Your premium payments are not current. Please contact the teacher.")

    period_start, period_end = claim_period_bounds_utc(max_claims_period, reference_time=now_utc)
    period_start_db = normalize_for_db(period_start)
    period_end_db = normalize_for_db(period_end)

    # Check max claims per period
    if max_claims_count:
        claims_count = InsuranceClaim.query.filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['pending', 'approved', 'paid']),
            InsuranceClaim.filed_date >= period_start_db,
            InsuranceClaim.filed_date < period_end_db,
        ).count()

        if claims_count >= max_claims_count:
            errors.append(f"You have reached the maximum number of claims ({max_claims_count}) for this {max_claims_period}.")

    period_payouts = None
    remaining_period_cap = None
    if max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start_db,
            InsuranceClaim.processed_date < period_end_db,
            InsuranceClaim.approved_amount.isnot(None),
        ).scalar()
        if period_payouts is None:
            period_payouts = Decimal('0.00')
        remaining_period_cap = max(max_payout_per_period - period_payouts, Decimal('0.00'))

    eligible_transactions = []
    if claim_type == 'transaction_monetary':
        effective_time_limit_days = int(claim_time_limit_days) if claim_time_limit_days is not None else None
        tx_query = (
            Transaction.query
            .filter(Transaction.seat_id == scope['seat_id'])
            .filter(Transaction.class_id == scope['class_id'])
            .filter(Transaction.is_void == False)
            .filter(Transaction.status == TransactionStatus.POSTED)
            .filter(Transaction.amount < Decimal('0'))
            .filter(
                ~func.lower(func.coalesce(Transaction.type, '')).in_(
                    ['rent payment', 'insurance_premium', 'insurance_reimbursement', 'withdrawal', 'deposit']
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
                .filter(Transaction.seat_id == scope['seat_id'])
                .filter(Transaction.class_id == scope['class_id'])
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

        try:
            class_id = scope.class_id
            seat_id = get_seat_id_for_class(student.id, class_id)

            execute_file_claim(
                scope=scope,
                enrollment=enrollment,
                seat_id=seat_id,
                class_id=class_id,
                incident_date=incident_date_value,
                description=form.description.data,
                claim_amount=claim_amount_value if claim_type != 'non_monetary' else None,
                claim_item=claim_item_value if claim_type == 'non_monetary' else None,
                comments=form.comments.data,
                transaction_id=transaction_id_value,
            )
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
                          form=form,
                          errors=errors,
                          claims_this_period=claims_this_period,
                          eligible_transactions=eligible_transactions,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


@student_bp.route('/insurance/policy/<int:enrollment_id>')
@login_required
def view_policy(enrollment_id):
    """View policy details and claims history."""
    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
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
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
        student = get_logged_in_student()

    # CRITICAL FIX v2: Get full class context
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please select a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    teacher_id = context['teacher_id']
    join_code = context['join_code']
    if not class_id:
        class_id = context.get('class_id')

    current_block = (context.get('block') or '').strip().upper()

    now = utc_now()
    now_db = normalize_for_db(now)
    items_query = StoreItem.query.filter(
        StoreItem.join_code == join_code,
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
        StudentItem.join_code == join_code,
    ).order_by(StudentItem.purchase_date.desc()).all()

    # Check if student has paid rent this month and get per-period rent item IDs
    from app.models import RentSettings, RentPayment, RentItem
    current_block = context.get('block')
    has_paid_rent = False
    per_period_rent_item_ids = set()
    rent_item_types_by_store_id = {}
    per_use_limit_by_store_id = {}

    if teacher_id and class_id and current_block:
        seat_id = get_seat_id_for_class(student.id, class_id)
        rent_settings = get_rent_settings_for_context(context)
        if rent_settings and rent_settings.is_enabled:
            now = utc_now()

            # Calculate current coverage period (pre-paid system)
            coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)

            
            if coverage_due_date and seat_id:
                has_paid_rent = _is_student_coverage_period_paid(
                    rent_settings,
                    seat_id,
                    class_id,
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

    # Build free uses remaining map for rent-linked per-use items
    rent_free_uses = {}  # {store_item_id: uses_remaining or -1 for unlimited}
    if student:
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
                db.func.count(db.distinct(StudentItem.student_id)).label('student_count'),
            )
            .join(Student, StudentItem.student_id == Student.id)
            .join(StoreItem, StudentItem.store_item_id == StoreItem.id)
            .filter(
                StudentItem.store_item_id.in_(collective_item_ids),
                StudentItem.join_code == join_code,
                StudentItem.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
                Student.is_teacher == False,  # Exclude teacher purchases from progress
                StudentItem.collective_goal_instance_code == StoreItem.collective_goal_instance_code,
            )
            .group_by(StudentItem.store_item_id)
            .all()
        )
        progress_counts = {row.store_item_id: int(row.student_count or 0) for row in progress_rows}

        for item in collective_items:
            if item.collective_goal_type == 'whole_class':
                target = class_size
            elif item.collective_goal_type == 'fixed':
                target = int(item.collective_goal_target or 0)
            else:
                target = 0
            count = progress_counts.get(item.id, 0)
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

def _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id=None, class_id=None, join_code=None, force=False):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.

    Args:
        force: Charge fee even if balance is non-negative (declined transaction).
    """
    if not class_id and join_code:
        from app.models import ClassEconomy
        ce = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = ce.class_id if ce else None

    if not class_id:
        return False, Decimal('0.00')

    seat_id = get_seat_id_for_class(student.id, class_id)
    if not seat_id:
        return False, Decimal('0.00')

    from app.models import Seat
    seat = db.session.get(Seat, seat_id)

    return apply_ledger_overdraft_fee(
        seat,
        banking_settings,
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


def _calculate_due_dates(settings, now):
    """Return the current and next due dates for rent-linked expiry calculations."""
    first_due = ensure_utc(settings.first_rent_due_date)
    if not first_due:
        return (None, None)

    delta = _get_rent_period_delta(settings)
    if now < first_due:
        return (first_due, _add_rent_period(first_due, delta))

    current_due = first_due
    next_due = _add_rent_period(first_due, delta)
    while next_due and next_due <= now:
        current_due = next_due
        next_due = _add_rent_period(next_due, delta)

    return (current_due, next_due)


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
    """Return the first valid payer's base rent for a join_code coverage cycle."""
    if not join_code or not coverage_due_date:
        return None
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        return None

    cycle_payments = RentPayment.query.filter(
        RentPayment.class_id == class_row.class_id,
        RentPayment.coverage_month == coverage_due_date.month,
        RentPayment.coverage_year == coverage_due_date.year,
    ).order_by(RentPayment.payment_date.asc()).all()
    if not cycle_payments:
        return None

    for payment in cycle_payments:
        txn = Transaction.query.filter(
            Transaction.seat_id == payment.seat_id,
            Transaction.class_id == payment.class_id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.amount == -payment.amount_paid,
        ).first()
        if txn is None or txn.is_void:
            continue

        late_fee = (payment.late_fee_charged or Decimal('0.00'))
        base_amount = (payment.amount_paid or Decimal('0.00')) - late_fee
        if base_amount > Decimal('0.00'):
            return base_amount

    return None


def _get_effective_rent_amount_for_coverage_period(
    settings,
    payments,
    coverage_due_date,
    join_code=None,
    locked_amount=None,
):
    """
    Return the effective base rent for the coverage period.

    If the class rate changed mid-cycle, lock to the first valid payer's base
    amount for that join code. As a fallback, keep a student's earlier paid
    base amount when the setting update happened after their first payment.
    """
    current_amount = settings.rent_amount or Decimal('0.00')

    if locked_amount is None:
        locked_amount = _get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due_date)
    if locked_amount is not None:
        return locked_amount

    if payments:
        updated_at = getattr(settings, 'updated_at', None)
        if updated_at:
            payment_dates = [ensure_utc(p.payment_date) for p in payments if p.payment_date]
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


def _match_valid_rent_payments(payments, candidate_txns):
    """Match payments to non-void rent transactions using existing tolerance rules."""
    if not payments:
        return []
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

    return valid_payments


def _filter_valid_rent_payments(payments, student_id, join_code, seat_ids=None):
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

    txn_scope = transaction_scope_filter(Transaction, student_id, seat_ids or [])
    txn_query = Transaction.query.filter(
        txn_scope,
        Transaction.type == 'Rent Payment',
        Transaction.timestamp >= window_start,
        Transaction.timestamp <= window_end,
        Transaction.amount.in_(payment_amounts)
    )
    if not join_code:
        return []
    txn_query = txn_query.filter(Transaction.join_code == join_code)

    candidate_txns = txn_query.all()
    return _match_valid_rent_payments(payments, candidate_txns)


def _build_rent_coverage_context(
    settings,
    *,
    class_id,
    seat_ids,
    coverage_due_date,
    include_waivers=True,
):
    """
    Preload rent facts for a single class + coverage period.

    Callers can pass this to _is_student_coverage_period_paid(...) to avoid
    repeating equivalent queries for every student in the same request.
    """
    if not settings or not class_id or not coverage_due_date or not seat_ids:
        return None

    class_row = db.session.get(ClassEconomy, class_id)
    join_code = class_row.join_code if class_row else None
    if not join_code:
        return None

    seat_rows = (
        db.session.query(Seat.id, Seat.student_id)
        .filter(Seat.class_id == class_id, Seat.id.in_(seat_ids))
        .all()
    )
    student_id_by_seat = {seat_id: student_id for seat_id, student_id in seat_rows}
    valid_seat_ids = list(student_id_by_seat.keys())
    if not valid_seat_ids:
        return None

    waived_seat_ids = set()
    if include_waivers:
        waiver_rows = (
            RentWaiver.query
            .filter(
                RentWaiver.class_id == class_id,
                RentWaiver.seat_id.in_(valid_seat_ids),
                RentWaiver.waiver_start_date <= coverage_due_date,
                RentWaiver.waiver_end_date >= coverage_due_date,
            )
            .all()
        )
        waived_seat_ids = {row.seat_id for row in waiver_rows if row.seat_id}

    coverage_start, coverage_end = _get_rent_coverage_window(settings, coverage_due_date)
    payments_query = RentPayment.query.filter(
        RentPayment.class_id == class_id,
        RentPayment.seat_id.in_(valid_seat_ids),
        RentPayment.coverage_month == coverage_due_date.month,
        RentPayment.coverage_year == coverage_due_date.year,
    )
    if coverage_start and coverage_end:
        payments_query = payments_query.filter(
            RentPayment.payment_date >= coverage_start,
            RentPayment.payment_date < coverage_end,
        )
    coverage_payments = payments_query.all()

    payments_by_seat = defaultdict(list)
    for payment in coverage_payments:
        if payment.seat_id:
            payments_by_seat[payment.seat_id].append(payment)

    # Preload candidate rent transactions once and reuse the same matching rules.
    payment_dates = [p.payment_date for p in coverage_payments if p.payment_date]
    payment_amounts = {-(p.amount_paid) for p in coverage_payments if p.amount_paid is not None}
    txns_by_seat = defaultdict(list)
    if payment_dates and payment_amounts:
        window_start = min(payment_dates) - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)
        window_end = max(payment_dates) + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS)
        candidate_txns = Transaction.query.filter(
            Transaction.seat_id.in_(list(student_id_by_seat.keys())),
            Transaction.class_id == class_id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= window_start,
            Transaction.timestamp <= window_end,
            Transaction.amount.in_(payment_amounts),
        ).all()
        for txn in candidate_txns:
            if txn.seat_id:
                txns_by_seat[txn.seat_id].append(txn)

    valid_payments_by_seat = {}
    for seat_id, payments in payments_by_seat.items():
        valid_payments_by_seat[seat_id] = _match_valid_rent_payments(
            payments,
            txns_by_seat.get(seat_id, []),
        )

    return {
        "class_id": class_id,
        "coverage_due_date": ensure_utc(coverage_due_date),
        "join_code": join_code,
        "student_id_by_seat": student_id_by_seat,
        "waived_seat_ids": waived_seat_ids,
        "valid_payments_by_seat": valid_payments_by_seat,
        "locked_rent_amount": _get_locked_rent_amount_for_join_code_cycle(join_code, coverage_due_date),
    }


def _is_coverage_period_paid(
    settings,
    valid_payments,
    coverage_due_date,
    include_late_fee=True,
    join_code=None,
    locked_amount=None,
):
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
        locked_amount=locked_amount,
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


def _get_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
    """Return the waiver row covering the given coverage period, if any."""
    from app.models import RentWaiver

    if not seat_id or not class_id or not coverage_due_date:
        return None
    query = RentWaiver.query.filter(
        RentWaiver.seat_id == seat_id,
        RentWaiver.class_id == class_id,
        RentWaiver.waiver_start_date <= coverage_due_date,
        RentWaiver.waiver_end_date >= coverage_due_date,
    )
    return query.order_by(RentWaiver.created_at.desc(), RentWaiver.id.desc()).first()


def _has_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
    """Return True when a waiver covers the given coverage period."""
    return _get_active_rent_waiver_v2(seat_id, class_id, coverage_due_date) is not None


def _has_active_rent_waiver(student_id, join_code, coverage_due_date):
    """Legacy compatibility wrapper for waiver checks keyed by student + join_code."""
    if not student_id or not join_code or not coverage_due_date:
        return False

    legacy_waiver = RentWaiver.query.filter(
        RentWaiver.student_id == student_id,
        RentWaiver.join_code == join_code,
        RentWaiver.waiver_start_date <= coverage_due_date,
        RentWaiver.waiver_end_date >= coverage_due_date,
    ).order_by(RentWaiver.created_at.desc(), RentWaiver.id.desc()).first()
    if legacy_waiver:
        return True

    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row or not class_row.class_id:
        return False

    seat_id = get_seat_id_for_class(student_id, class_row.class_id)
    if not seat_id:
        return False

    return _has_active_rent_waiver_v2(seat_id, class_row.class_id, coverage_due_date)


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
    seat_id,
    class_id,
    coverage_due_date,
    include_late_fee=True,
    include_waivers=True,
    coverage_context=None,
):
    """
    Return True when a student's specific coverage period is fully paid or waived.
    """
    if not settings:
        return False
    if not coverage_due_date or not class_id:
        return False

    context_applies = False
    if coverage_context:
        context_class_id = coverage_context.get("class_id")
        context_coverage_due = ensure_utc(coverage_context.get("coverage_due_date"))
        context_applies = (
            context_class_id == class_id
            and context_coverage_due == ensure_utc(coverage_due_date)
        )

    join_code = None
    student_id = None
    locked_amount = None
    if context_applies:
        join_code = coverage_context.get("join_code")
        student_id = (coverage_context.get("student_id_by_seat") or {}).get(seat_id)
        locked_amount = coverage_context.get("locked_rent_amount")
        if include_waivers and seat_id in (coverage_context.get("waived_seat_ids") or set()):
            return True
    else:
        if class_id:
            class_row = db.session.get(ClassEconomy, class_id)
            join_code = class_row.join_code if class_row else None
        if seat_id:
            seat = db.session.get(Seat, seat_id)
            student_id = seat.student_id if seat else None
        if include_waivers:
            if _has_active_rent_waiver_v2(seat_id, class_id, coverage_due_date):
                return True

    if context_applies:
        valid_payments = (coverage_context.get("valid_payments_by_seat") or {}).get(seat_id, [])
    else:
        coverage_start, coverage_end = _get_rent_coverage_window(settings, coverage_due_date)
        coverage_payments_query = RentPayment.query.filter(
            RentPayment.coverage_month == coverage_due_date.month,
            RentPayment.coverage_year == coverage_due_date.year,
        )
        if coverage_start and coverage_end:
            coverage_payments_query = coverage_payments_query.filter(
                RentPayment.payment_date >= coverage_start,
                RentPayment.payment_date < coverage_end,
            )
        coverage_payments_query = coverage_payments_query.filter(
            RentPayment.seat_id == seat_id,
            RentPayment.class_id == class_id,
        )
        coverage_payments = coverage_payments_query.all()

        seat_ids = [seat_id] if seat_id else []
        valid_payments = _filter_valid_rent_payments(
            coverage_payments,
            student_id,
            join_code,
            seat_ids=seat_ids,
        )
    return _is_coverage_period_paid(
        settings,
        valid_payments,
        coverage_due_date,
        include_late_fee=include_late_fee,
        join_code=join_code,
        locked_amount=locked_amount,
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
    class_id = context.get('class_id')
    if not class_id:
        from app.models import ClassEconomy
        ce = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = ce.class_id if ce else None

    if not class_id:
        return 0, 0, False

    seat_id = get_seat_id_for_class(student.id, class_id)
    if not seat_id:
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
        seat_id,
        class_id,
        coverage_due_date,
        include_late_fee=False,
    )

    from app.models import Seat
    seat = Seat.query.get(seat_id)

    total_grant = store_service.get_rent_hall_pass_grant_total(settings.id)
    target_rent_passes = total_grant if is_paid else 0
    return identity_service.reconcile_rent_hall_pass_top_off(
        seat=seat,
        target_rent_passes=target_rent_passes,
    )


@student_bp.route('/rent')
@login_required
def rent():
    """View rent status and payment history (per period)."""
    # Check if rent feature is enabled
    if not is_feature_enabled('rent'):
        abort(404)

    seat = get_current_seat()
    class_id = get_current_class_id()
    _ = get_current_user()
    student = db.session.get(Student, seat.student_id) if seat and seat.student_id else None
    if not student:
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

    class_id = class_id or context.get('class_id')
    if not class_id:
        from app.models import ClassEconomy
        ce = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = ce.class_id if ce else None

    if not class_id:
        flash("No class context available.", "error")
        return redirect(url_for('student.dashboard'))

    seat_id = get_seat_id_for_class(student.id, class_id)
    if not seat_id:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))

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
            seat_id,
            class_id,
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
        RentPayment.seat_id == seat_id,
        RentPayment.class_id == class_id,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
    ).all()

    # Filter out payments where the corresponding transaction was voided
    payments = []
    for payment in all_payments_for_period:
        txn = Transaction.query.filter(
            Transaction.seat_id == seat_id,
            Transaction.class_id == class_id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.amount == -payment.amount_paid
        ).first()

        if txn and not txn.is_void:
            payments.append(payment)

    total_paid = sum(p.amount_paid for p in payments) if payments else Decimal('0.00')

    paid_by_grace = _total_paid_by_grace(payments, grace_end_date_for_status)
    late_fee = Decimal('0.00')
    if rent_is_active and now > grace_end_date_for_status and paid_by_grace < settings.rent_amount:
        late_fee = settings.late_fee

    total_due = settings.rent_amount + late_fee if rent_is_active else Decimal('0.00')
    active_waiver = _get_active_rent_waiver_v2(seat_id, class_id, payment_due_date) if payment_due_date else None
    is_paid = total_paid >= total_due if rent_is_active else False
    is_late = now > grace_end_date_for_status and not is_paid if rent_is_active else False
    remaining_amount = max(Decimal('0.00'), total_due - total_paid) if rent_is_active else Decimal('0.00')

    period_status[current_block] = {
        'is_paid': is_paid,
        'is_waived': bool(active_waiver and total_paid <= Decimal('0.00')),
        'is_late': is_late,
        'payments': payments,
        'total_paid': total_paid,
        'total_due': total_due,
        'remaining_amount': remaining_amount,
        'late_fee': late_fee,
        'rent_is_active': rent_is_active,
        'is_preview_period': is_preview_period,
        'waiver': active_waiver,
    }

    # Get scoped balances for this class only
    checking_balance, savings_balance = get_available_balances(seat_id, class_id)

    # Get payment history for the current class only
    payment_history = RentPayment.query.filter(
        RentPayment.seat_id == seat_id,
        RentPayment.class_id == class_id,
    ).order_by(
        RentPayment.payment_date.desc()
    ).limit(24).all()  # Increased to show more history with multiple periods

    waiver_history = []
    if settings:
        waiver_rows = RentWaiver.query.filter(
            RentWaiver.seat_id == seat_id,
            RentWaiver.class_id == class_id,
        ).all()
        waiver_history = _expand_rent_waiver_history(settings, waiver_rows, now=now)

    payment_history_rows = []
    for payment in payment_history:
        payment_history_rows.append({
            'period_month': payment.period_month,
            'period_year': payment.period_year,
            'amount_paid': payment.amount_paid,
            'recorded_at': payment.payment_date,
            'status_text': (
                f"Paid late with fee of ${payment.late_fee_charged:.2f}"
                if payment.was_late else "On Time"
            ),
            'entry_type': 'payment',
        })

    for waiver_entry in waiver_history:
        payment_history_rows.append({
            'period_month': waiver_entry['coverage_due_date'].month,
            'period_year': waiver_entry['coverage_due_date'].year,
            'amount_paid': None,
            'recorded_at': waiver_entry['created_at'] or waiver_entry['coverage_due_date'],
            'status_text': waiver_entry['status_label'],
            'entry_type': 'waiver',
        })

    payment_history_rows.sort(
        key=lambda row: ensure_utc(row['recorded_at']) if row.get('recorded_at') else now,
        reverse=True,
    )

    # Get rent items for this setting to show what rent includes
    from app.models import RentItem
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
@feat_shell("FEAT-OBL-001")
def rent_pay(period):
    """Process rent payment for a specific period."""
    student = get_logged_in_student()
    try:
        scope = resolve_scope(
            actor=student,
            selected_join_code=session.get('current_join_code'),
        )
    except AccessScopeDenied as exc:
        flash(exc.message, "error")
        return redirect(url_for('student.dashboard'))
    context = get_current_class_context()
    if not context:
        flash("No class selected. Please choose a class to continue.", "error")
        return redirect(url_for('student.dashboard'))

    class_id = context.get('class_id')
    if not class_id:
        from app.models import ClassEconomy
        ce = ClassEconomy.query.filter_by(join_code=join_code).first()
        class_id = ce.class_id if ce else None

    if not class_id:
        flash("No class context available.", "error")
        return redirect(url_for('student.dashboard'))

    seat_id = get_seat_id_for_class(student.id, class_id)
    if not seat_id:
        flash("No seat assigned in this class.", "error")
        return redirect(url_for('student.dashboard'))

    settings = get_rent_settings_for_context(context)

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student.dashboard'))

    if not student.is_rent_enabled:
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student.dashboard'))

    # Validate period for the current class context only
    period = (period or '').strip().upper()
    current_block = context.get('block', '').strip().upper()
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
            seat_id,
            class_id,
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

    checking_balance, savings_balance = get_available_balances(seat_id, class_id)

    # Get all existing payments that cover this period
    all_payments = RentPayment.query.filter(
        RentPayment.seat_id == seat_id,
        RentPayment.class_id == class_id,
        RentPayment.coverage_month == coverage_month,
        RentPayment.coverage_year == coverage_year,
    ).all()

    # Filter out payments where the corresponding transaction was voided
    existing_payments = []
    for payment in all_payments:
        # Find the transaction for this payment
        txn = Transaction.query.filter(
            Transaction.seat_id == seat_id,
            Transaction.class_id == class_id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=RENT_PAYMENT_MATCH_TOLERANCE_SECONDS),
            Transaction.amount == -payment.amount_paid
        ).first()

        # Only include if transaction exists and is not voided
        if txn and not txn.is_void:
            existing_payments.append(payment)

    total_paid_so_far = sum(p.amount_paid for p in existing_payments) if existing_payments else Decimal('0.00')

    # Calculate if late and total amount due
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    grace_end_date_for_payment = grace_end_date
    if payment_due_date and payment_due_date != due_date:
        grace_end_date_for_payment = payment_due_date + timedelta(days=settings.grace_period_days)
    paid_by_grace = _total_paid_by_grace(existing_payments, grace_end_date_for_payment)
    is_late = now > grace_end_date_for_payment and paid_by_grace < settings.rent_amount

    # Calculate late fee if applicable
    late_fee = Decimal('0.00')
    if is_late:
        late_fee = settings.late_fee

    # Total amount due (rent + late fee if applicable)
    total_due = _quantize_currency(settings.rent_amount + late_fee)

    # Calculate remaining amount to pay
    remaining_amount = _quantize_currency(total_due - total_paid_so_far)

    # Check if already fully paid
    if remaining_amount <= 0:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    # Get payment amount from form (supports incremental payments)
    payment_amount_input = request.form.get('amount', '').strip()

    # Determine payment amount based on incremental setting
    if settings.allow_incremental_payment and payment_amount_input:
        try:
            payment_amount = _quantize_currency(payment_amount_input)
            # Validate payment amount
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
        # Full payment required (or no amount specified with incremental disabled)
        payment_amount = remaining_amount

    # Get banking settings for overdraft handling (reuse teacher_id from above)
    banking_settings = get_banking_settings_for_context(context)

    from app.models import Seat
    seat = db.session.get(Seat, seat_id)

    # Check if student has enough funds for this payment using shared utility
    overdraft_shortfall = Decimal('0.00')
    allowed, shortfall, _, _ = evaluate_overdraft_allowance(
        seat,
        payment_amount,
        banking_settings,
    )
    if not allowed:
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(
            student,
            banking_settings,
            class_id=class_id,
            force=True,
        )

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

    result = execute_rent_payment(
        seat=seat,
        context=context,
        payment_amount=payment_amount,
        period=period,
        settings=settings,
        is_late=is_late,
        late_fee=late_fee,
        total_paid_so_far=total_paid_so_far,
        total_due=total_due,
        remaining_amount=remaining_amount,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        current_month=current_month,
        current_year=current_year,
        payment_due_date=payment_due_date,
        banking_settings=banking_settings,
        overdraft_shortfall=overdraft_shortfall,
        now=now,
        calculate_due_dates_fn=_calculate_due_dates,
    )

    # Success message
    if result.is_partial and settings.allow_incremental_payment:
        if result.new_remaining > 0:
            flash(f"Partial payment of ${result.amount_paid:.2f} successful! Remaining balance: ${result.new_remaining:.2f}", "success")
        else:
            msg = f"Final payment of ${result.amount_paid:.2f} successful! Rent for Period {period} is now fully paid."
            if result.passes_awarded > 0:
                msg += f" You received {result.passes_awarded} hall passes!"
            flash(msg, "success")
    else:
        msg = f"Rent payment for Period {period} (${result.amount_paid:.2f}) successful!"
        if result.passes_awarded > 0:
            msg += f" You received {result.passes_awarded} hall passes!"
        flash(msg, "success")

    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
@feat_shell("FEAT-IDEN-001")
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
                db.session.flush()

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
        session.pop('student_user_id', None)
        session.pop('current_seat_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        # Explicitly clear other potential student-related session keys
        session.pop('claimed_student_id', None)
        session.pop('claimed_seat_id', None)
        session.pop('claimed_user_id', None)
        session.pop('generated_username', None)
        clear_teacher_display_name_cache()


        session['student_id'] = student.id
        session['login_time'] = utc_now().isoformat()
        session['last_activity'] = session['login_time']

        linked_user = (
            User.query
            .join(Seat, Seat.user_id == User.id)
            .filter(
                Seat.student_id == student.id,
                Seat.user_id.isnot(None),
            )
            .order_by(Seat.id.asc())
            .first()
        )

        if linked_user and linked_user.last_active_class_id:
            has_active_class_seat = Seat.query.filter_by(
                student_id=student.id,
                user_id=linked_user.id,
                class_id=linked_user.last_active_class_id,
            ).first()
            if not has_active_class_seat:
                linked_user.last_active_class_id = None
                db.session.flush()

        seat_options = _get_identity_bound_seat_options(student)
        if linked_user and linked_user.last_active_class_id is None:
            if seat_options:
                return redirect(url_for('student.select_class_context'))
            current_app.logger.critical(
                "P0 INCIDENT: Student %s login has NULL last_active_class_id and no surviving seats.",
                student.id,
            )
            session.pop('student_id', None)
            session.pop('student_user_id', None)
            session.pop('current_seat_id', None)
            session.pop('current_class_id', None)
            session.pop('current_join_code', None)
            session.pop('seat_id', None)
            session.pop('class_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            if is_json:
                return jsonify(status="error", message="Account scope incident detected. Contact support immediately."), 500
            flash("Account scope incident detected. Contact support immediately.", "error")
            return redirect(url_for('student.login', next=request.args.get('next')))

        seat = sync_student_session_context(student, allow_writes=True)
        if seat is None:
            session.pop('student_id', None)
            session.pop('student_user_id', None)
            session.pop('current_seat_id', None)
            session.pop('current_class_id', None)
            session.pop('current_join_code', None)
            session.pop('seat_id', None)
            session.pop('class_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            if is_json:
                return jsonify(status="error", message="Account has no valid seat context."), 403
            flash("Your account is missing class seat context. Contact your teacher.", "error")
            return redirect(url_for('student.login', next=request.args.get('next')))
        _prime_student_teacher_display_name_cache(student.id)


        # Removed redirect to student_setup for has_completed_setup; new onboarding flow uses claim → username → pin/passphrase.

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            return redirect(url_for('student.dashboard'))
        return redirect(next_url or url_for('student.dashboard'))  # nosec # Safe: validated by is_safe_url()

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)


@student_bp.route('/select-class-context', methods=['GET', 'POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def select_class_context():
    """Explicit class-selection gate when no durable class context exists."""
    student = get_logged_in_student()
    if not student:
        return redirect(url_for('student.login'))

    linked_user = (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .filter(
            Seat.student_id == student.id,
            Seat.user_id.isnot(None),
        )
        .order_by(Seat.id.asc())
        .first()
    )
    if not linked_user:
        current_app.logger.critical(
            "P0 INCIDENT: Student %s has no identity-linked user during class-context gate.",
            student.id,
        )
        session.clear()
        flash("Account scope incident detected. Contact support immediately.", "error")
        return redirect(url_for('student.login'))

    seat_options = _get_identity_bound_seat_options(student)
    if not seat_options:
        current_app.logger.critical(
            "P0 INCIDENT: Student %s has no surviving seats during class-context gate.",
            student.id,
        )
        session.clear()
        flash("Account scope incident detected. Contact support immediately.", "error")
        return redirect(url_for('student.login'))

    if request.method == 'POST':
        selected_class_id = (request.form.get('class_id') or '').strip()
        allowed_class_ids = {item["class_id"] for item in seat_options}
        if selected_class_id not in allowed_class_ids:
            flash("Invalid class selection.", "error")
            return render_template('student_select_class_context.html', class_options=seat_options), 400

        selected_seat = sync_student_session_context(student, class_id=selected_class_id)
        if selected_seat is None:
            current_app.logger.critical(
                "P0 INCIDENT: Student %s selected class %s but seat context failed to resolve.",
                student.id,
                selected_class_id,
            )
            session.clear()
            flash("Account scope incident detected. Contact support immediately.", "error")
            return redirect(url_for('student.login'))

        linked_user.last_active_class_id = selected_class_id
        db.session.flush()

        scope = resolve_scope(actor=student, actor_role="student")
        if not scope or scope.class_id != selected_class_id:
            current_app.logger.critical(
                "P0 INCIDENT: Scope construction mismatch for student %s class %s.",
                student.id,
                selected_class_id,
            )
            session.clear()
            flash("Account scope incident detected. Contact support immediately.", "error")
            return redirect(url_for('student.login'))

        return redirect(url_for('student.dashboard'))

    return render_template('student_select_class_context.html', class_options=seat_options)


@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


@student_bp.route('/switch-class/<class_id>', methods=['POST'])
@login_required
@feat_shell("FEAT-IDEN-001")
def switch_class(class_id):
    """Switch to a different class using class_id as the stable backend reference."""
    from app.models import Seat, Admin

    student = get_logged_in_student()
    try:
        resolved_switch = resolve_student_class_switch_scope(actor=student, class_id=class_id)
        access_policy_service.assert_can_switch_class(resolved_switch.scope)
    except (AccessScopeDenied, access_policy_service.AccessPolicyDenied) as exc:
        return jsonify(status="error", message="You don't have access to that class."), 403
    seat = db.session.get(Seat, resolved_switch.seat_id)
    if seat is None:
        return jsonify(status="error", message="You don't have access to that class."), 403

    # Use canonical session context switch (Logs: SESSION-CONTEXT-SWITCH)
    from app.auth import switch_student_session_context
    switch_student_session_context(
        student, 
        class_id=resolved_switch.scope.class_id, 
        seat_id=seat.id,
    )

    # Get teacher name for response
    teacher_id = resolved_switch.scope.teacher_id
    teacher = db.session.get(Admin, teacher_id)
    teacher_cache = get_teacher_display_name_cache()
    teacher_name = teacher_cache.get(str(teacher_id))
    if not teacher_name and teacher:
        teacher_name = teacher.get_display_name()
        upsert_teacher_display_name_cache({str(teacher_id): teacher_name})
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
    """Legacy numeric-ID switch route is disabled in strict join-code mode."""
    current_app.logger.warning(
        "Deprecated student switch-period route called with teacher_id=%s; route is disabled.",
        teacher_id,
    )
    flash("This class switch path is no longer supported. Please switch using class context.", "warning")
    return redirect(url_for('student.dashboard'))


@student_bp.route('/switch-teacher/<string:teacher_public_id>', methods=['POST'])
@login_required
def switch_teacher(teacher_public_id):
    """Reject obsolete role-specific public-ID switching."""
    abort(404)


# -------------------- SETUP COMPLETE --------------------
# Note: This route is not prefixed with /student for backward compatibility

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = get_logged_in_student()
    return render_template('student_setup_complete.html', student_name=student.first_name)


# -------------------- HELP AND SUPPORT - ISSUE RESOLUTION SYSTEM --------------------

@student_bp.route('/help-support', methods=['GET'])
@login_required
def help_support():
    """Show the student help and support page with issue tracking."""
    from app.utils.issue_categories import init_default_categories

    student = get_logged_in_student()
    class_context = get_current_class_context()

    if not class_context:
        flash("Please select a class first.", "warning")
        return redirect(url_for('student.dashboard'))

    # Initialize default categories if they don't exist
    init_default_categories()

    # Get student's issues for current class (last 20)
    my_issues = Issue.query.filter_by(
        student_id=student.id,
        join_code=class_context['join_code']
    ).order_by(Issue.submitted_at.desc()).limit(20).all()

    return render_template('student_help_support_new.html',
                         current_page='help',
                         page_title='Help & Support',
                         my_issues=my_issues,
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
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

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
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

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
    actor_public_id = _support_actor_public_id(class_context)
    show_recent_error_option = bool(
        actor_public_id and has_recent_error_for_actor('student', actor_public_id)
    )

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
@feat_shell("FEAT-IDEN-002")
def verify_recovery(code_id):
    """
    Student verification page for teacher account recovery.
    Student authenticates with passphrase, then gets a 6-digit code to give to teacher.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    recovery_code = get_recovery_code_for_student(code_id, student.id)
    if recovery_code is None:
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
        verified_at = utc_now()
        set_recovery_code_verified(code_id, hash_hmac(code.encode(), b''), verified_at)
        recovery_code.code_hash = "verified"
        recovery_code.verified_at = verified_at
        db.session.flush()

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
@feat_shell("FEAT-IDEN-002")
def dismiss_recovery(code_id):
    """
    Dismiss the recovery notification banner.
    """
    student = get_logged_in_student()

    # Get the recovery code request
    recovery_code = get_recovery_code_for_student(code_id, student.id)
    if recovery_code is None:
        flash("Invalid recovery request.", "error")
        return redirect(url_for('student.dashboard'))

    # Mark as dismissed
    dismiss_recovery_code_row(code_id)
    db.session.flush()

    flash("Recovery notification dismissed. You can still verify later from your notifications.", "info")
    return redirect(url_for('student.dashboard'))

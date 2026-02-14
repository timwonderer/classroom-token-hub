"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import random
import string
import re
import pytz
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import func, or_
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from werkzeug.security import check_password_hash

from app.extensions import db, limiter
from app.models import (
    Student, Admin, StoreItem, StudentItem, Transaction, TapEvent,
    HallPassLog, HallPassSettings, InsuranceClaim, BankingSettings,
    StudentTeacher, TeacherBlock, StudentBlock, DemoStudent,
    RedemptionAuditLog, RedemptionAuditAction, RedemptionAuditSource
)
from app.auth import (
    login_required, admin_required, membership_required, check_membership_access,
    get_logged_in_student, get_current_admin, SESSION_TIMEOUT_MINUTES
)
from app.routes.student import get_current_class_context, get_current_teacher_id, get_rent_settings_for_context
from app.utils.join_code import generate_join_code
from app.utils.name_utils import hash_last_name_parts
from app.utils.overdraft import charge_overdraft_fee_if_needed
from app.utils.time import utc_now, ensure_utc, normalize_for_db

# Import external modules
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    get_all_block_statuses,
    get_join_code_for_student_period
)
from app.payroll import get_pay_rate_for_block

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


# -------------------- Rent Helpers --------------------




def _get_period_delta(rent_setting):
    """Return the timedelta/relativedelta for a rent setting."""
    if rent_setting.frequency_type == 'daily':
        return timedelta(days=1)
    if rent_setting.frequency_type == 'weekly':
        return timedelta(weeks=1)
    if rent_setting.frequency_type == 'monthly':
        return relativedelta(months=1)
    if rent_setting.frequency_type == 'custom':
        unit = rent_setting.custom_frequency_unit or 'days'
        value = rent_setting.custom_frequency_value or 1
        if unit == 'days':
            return timedelta(days=value)
        if unit == 'weeks':
            return timedelta(weeks=value)
        if unit == 'months':
            return relativedelta(months=value)
    return timedelta(days=30)


def _add_period(dt, delta):
    """Add a timedelta or relativedelta to dt."""
    return dt + delta


def _calculate_due_dates(rent_setting, now):
    """
    Calculate the current and next due dates for a rent setting based on the provided time.
    Returns (current_due, next_due). If first due date is not set, returns (None, None).
    """
    first_due = ensure_utc(rent_setting.first_rent_due_date)
    if not first_due:
        return (None, None)

    delta = _get_period_delta(rent_setting)

    # If before the first due date, the first due date is both current and next marker
    if now < first_due:
        return (first_due, _add_period(first_due, delta))

    current_due = first_due
    next_due = _add_period(first_due, delta)

    # Advance until next_due is after now
    while next_due and next_due <= now:
        current_due = next_due
        next_due = _add_period(next_due, delta)

    return (current_due, next_due)


def _resolve_class_display_label(teacher_id, join_code, fallback_block=None):
    """
    Resolve a stable class display label snapshot for audit logging.
    """
    if join_code:
        seat = TeacherBlock.query.filter_by(teacher_id=teacher_id, join_code=join_code).first()
        if seat:
            label = seat.get_class_label()
            if label:
                return label
            if seat.block:
                return seat.block
    return fallback_block or "Unknown Class"


def _append_redemption_audit_log(*, student_item, student, teacher_id, action, notes, guard_state, fallback_block=None):
    """
    Append exactly one live redemption audit log row for this request path.

    Must be called before redemption state mutations.
    """
    if guard_state.get('inserted'):
        raise RuntimeError("Duplicate redemption audit insertion attempt in single request path")

    action_map = {
        'request': RedemptionAuditAction.REQUEST,
        'approved': RedemptionAuditAction.APPROVED,
        'rejected': RedemptionAuditAction.REJECTED,
    }
    if action not in action_map:
        raise ValueError(f"Unsupported redemption audit action: {action}")

    student_name = student.full_name if student else "Unknown Student"
    join_code = getattr(student_item, 'join_code', None)
    class_label = _resolve_class_display_label(teacher_id, join_code, fallback_block=fallback_block)

    db.session.add(RedemptionAuditLog(
        student_item_id=student_item.id if student_item else None,
        student_display_name=student_name,
        class_display_label=class_label,
        action=action_map[action],
        notes=notes if notes else None,
        teacher_id=teacher_id,
        timestamp=utc_now(),
        source=RedemptionAuditSource.LIVE,
    ))
    guard_state['inserted'] = True


# -------------------- TIPS API --------------------

@api_bp.route('/tips/<user_type>')
@limiter.exempt
def get_tips(user_type):
    """
    Return tips for login loading screens as JSON.

    Endpoint: GET /api/tips/<user_type>
    User types: 'student' or 'teacher'

    Exempt from rate limiting because it's called on every login page load.
    """
    if user_type == 'student':
        tips = [
            "You don't have to stay logged in after starting work. You'll continue to earn minutes even when you're away from the page.",
            "Check your balance regularly to track your earnings and plan your spending wisely.",
            "Your teacher can award bonus tokens for exceptional work or good behavior.",
            "Remember to log your attendance every day to earn your payroll minutes.",
            "The shop refreshes with new items regularly - check back often for deals!",
            "Save up for big purchases by setting financial goals for yourself.",
            "Hall passes deduct from your balance - plan your breaks wisely.",
            "Insurance can protect your balance from unexpected classroom events.",
            "Ask your teacher about bonus opportunities to earn extra tokens.",
            "Keep track of your transaction history to understand your spending habits."
        ]
    elif user_type == 'teacher':
        tips = [
            "Students don't have to stay logged in after starting work. They'll continue to earn minutes even when away from the page.",
            "Use the bulk transaction feature to quickly award or deduct tokens from multiple students.",
            "Set up automated payroll to save time on manual attendance tracking.",
            "The analytics dashboard shows spending trends to help you understand student behavior.",
            "Create custom store items to incentivize specific behaviors or achievements.",
            "Use insurance policies to teach students about risk management and financial protection.",
            "Rent settings can simulate monthly expenses to teach budgeting skills.",
            "Check the transaction log regularly to monitor unusual spending patterns.",
            "Bonus tokens are a great way to reward exceptional effort or good citizenship.",
            "Export your class data regularly for backup and analysis purposes."
        ]
    else:
        return jsonify({"error": "Invalid user type. Use 'student' or 'teacher'."}), 400

    return jsonify({"tips": tips})


# -------------------- STORE API --------------------

def _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id, join_code, force=False):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.

    Args:
        student: Student object
        banking_settings: BankingSettings object
        teacher_id: Teacher ID for multi-tenancy isolation
        join_code: Join code for multi-tenancy isolation
        force: Charge fee even if balance is non-negative (declined transaction).
    """
    return charge_overdraft_fee_if_needed(
        student,
        banking_settings,
        teacher_id=teacher_id,
        join_code=join_code,
        force=force
    )


@api_bp.route('/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    from app.routes.student import get_current_class_context

    student = get_logged_in_student()
    data = request.get_json()
    item_id = data.get('item_id')
    passphrase = data.get('passphrase')
    quantity = int(data.get('quantity', 1))  # Default to 1 if not specified

    if not all([item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # CRITICAL FIX v3: Get context using ClassMembership-aware helper
    context = get_current_class_context()
    if not context:
        return jsonify({"status": "error", "message": "No class context available."}), 400

    join_code = context['join_code']
    teacher_id = context['teacher_id']
    membership_id = context.get('membership_id')

    # CRITICAL: Use join_code as primary filter for class isolation
    # Fall back to teacher_id for items without join_code (legacy)
    item = StoreItem.query.filter_by(id=item_id, join_code=join_code).first()
    if not item:
        # Fallback: Check for legacy items scoped by teacher_id only
        item = StoreItem.query.filter_by(id=item_id, teacher_id=teacher_id, join_code=None).first()

    if not item or not item.is_active:
        return jsonify({"status": "error", "message": "This item is not available."}), 404

    # Check visible blocks if applicable (prevent cross-class leakage within same teacher)
    current_block = context.get('block', '').upper()
    if item.visible_blocks.count() > 0:
        is_visible = any(b.block == current_block for b in item.visible_blocks)
        if not is_visible:
             return jsonify({"status": "error", "message": "This item is not available for your class period."}), 404

    # Check rent late restrictions
    from app.models import RentSettings, RentPayment, RentItem
    from datetime import datetime, timedelta

    rent_settings = get_rent_settings_for_context(context)
    if rent_settings and rent_settings.is_enabled and rent_settings.prevent_purchase_when_late:
        # Check if student is late on rent
        now = utc_now()

        from app.routes.student import _calculate_rent_coverage_due_date
        coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)

        if coverage_due_date:
            grace_end_date = coverage_due_date + timedelta(days=rent_settings.grace_period_days)

            # Pre-paid system: use the most recently passed due date
            # as the coverage period so we match payments that COVER this cycle.
            coverage_month = coverage_due_date.month
            coverage_year = coverage_due_date.year

            # Check if past grace period
            if now > grace_end_date:
                # Check if rent is paid for current coverage period
                current_block = context.get('block', '').strip().upper()
                total_paid = db.session.query(db.func.sum(RentPayment.amount_paid)).filter(
                    RentPayment.student_id == student.id,
                    RentPayment.period == current_block,
                    RentPayment.coverage_month == coverage_month,
                    RentPayment.coverage_year == coverage_year,
                    db.or_(RentPayment.join_code == join_code, RentPayment.join_code.is_(None))
                ).scalar() or 0

                # Student is late if they haven't paid full rent
                if total_paid < rent_settings.rent_amount:
                    # Check if itemization is enabled
                    rent_items = RentItem.query.filter_by(rent_setting_id=rent_settings.id).all()

                    if rent_items:
                        # Itemization is enabled: check if this item is a rent item
                        rent_item_store_ids = [ri.store_item_id for ri in rent_items if ri.store_item_id]

                        if item.id not in rent_item_store_ids:
                            # This item is NOT part of rent - block purchase
                            return jsonify({
                                "status": "error",
                                "message": "You are late on rent. You can only purchase items covered by rent until you pay your rent."
                            }), 403
                        # If item IS part of rent, allow purchase (they can buy à la carte)
                    else:
                        # No itemization: block ALL purchases
                        return jsonify({
                            "status": "error",
                            "message": "You cannot make purchases while late on rent. Please pay your rent first."
                        }), 403

    # Check if student has free uses remaining from rent (per-use rent items)
    if item.is_rent_linked and quantity == 1:
        # Look for an active StudentItem with uses_remaining for this store item
        rent_item_query = StudentItem.query.filter(
            StudentItem.student_id == student.id,
            StudentItem.store_item_id == item.id,
            db.or_(
                StudentItem.uses_remaining > 0,
                StudentItem.uses_remaining == -1
            ),
            db.or_(
                StudentItem.expiry_date.is_(None),
                StudentItem.expiry_date > utc_now()
            )
        )
        if join_code:
            rent_item_query = rent_item_query.filter(StudentItem.join_code == join_code)
        else:
            rent_item_query = rent_item_query.filter(StudentItem.join_code.is_(None))

        active_rent_item = rent_item_query.first()

        if active_rent_item:
            # Free purchase from rent perk - decrement available free uses unless unlimited (-1)
            if active_rent_item.uses_remaining != -1:
                active_rent_item.uses_remaining -= 1

            # For rent perks, purchasing is $0 and usage is logged later on /use-item.
            purchase_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher_id,
                join_code=join_code,
                amount=0.0,
                account_type='checking',
                type='purchase',
                description=f"Purchase: {item.name} [Rent Perk $0]"
            )
            db.session.add(purchase_tx)

            expiry_date = None
            if item.item_type == 'delayed' and item.auto_expiry_days:
                expiry_date = utc_now() + timedelta(days=item.auto_expiry_days)

            db.session.add(StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                join_code=join_code,
                purchase_date=utc_now(),
                expiry_date=expiry_date,
                status='purchased',
                is_from_bundle=False,
                quantity_purchased=1,
                uses_remaining=None,
            ))
            db.session.commit()

            remaining = active_rent_item.uses_remaining
            if remaining == -1:
                return jsonify({"status": "success", "message": f"You purchased {item.name} for $0 (rent perk). Unlimited free purchases remaining this period."})
            if remaining > 0:
                return jsonify({"status": "success", "message": f"You purchased {item.name} for $0 (rent perk). {remaining} free purchase(s) remaining this period."})
            return jsonify({"status": "success", "message": f"You purchased {item.name} for $0 (rent perk). No free purchases remaining this period."})

    # Calculate price (with bulk discount if applicable)
    unit_price = item.price
    if (item.bulk_discount_enabled and
        item.bulk_discount_quantity is not None and
        item.bulk_discount_percentage is not None and
        quantity >= item.bulk_discount_quantity):
        discount_multiplier = 1 - (item.bulk_discount_percentage / 100)
        unit_price = item.price * discount_multiplier

    total_price = unit_price * quantity

    # Get banking settings for overdraft handling
    # CRITICAL: Use join_code as primary filter for class isolation
    banking_settings = BankingSettings.query.filter_by(join_code=join_code).first()
    if not banking_settings:
        # Fallback: Legacy settings by teacher_id
        banking_settings = BankingSettings.query.filter_by(teacher_id=teacher_id, join_code=None).first()

    # Check if student has sufficient funds
    if student.checking_balance < total_price:
        shortfall = total_price - student.checking_balance
        # Check if overdraft protection is enabled (savings can cover the difference)
        if (banking_settings and banking_settings.overdraft_protection_enabled and
                student.savings_balance >= shortfall):
            # Allow transaction - overdraft protection will transfer from savings
            pass
        else:
            fee_charged, fee_amount = _charge_overdraft_fee_if_needed(
                student,
                banking_settings,
                teacher_id,
                join_code,
                force=True
            )
            if fee_charged:
                db.session.commit()

            if banking_settings and banking_settings.overdraft_protection_enabled:
                message = (f"Insufficient funds in both checking and savings. You need "
                           f"${total_price:.2f} total but have "
                           f"${student.checking_balance + student.savings_balance:.2f}.")
            else:
                message = (f"Insufficient funds. You need ${total_price:.2f} but have "
                           f"${student.checking_balance:.2f}.")

            if fee_charged:
                message += f" Overdraft fee of ${fee_amount:.2f} charged."

            return jsonify({"status": "error", "message": message}), 400

    if item.inventory is not None and item.inventory < quantity:
        return jsonify({"status": "error", "message": f"Insufficient stock. Only {item.inventory} available."}), 400

    if item.limit_per_student is not None:
        if item.item_type == 'hall_pass':
            # For hall passes, check transaction history and sum quantities
            # Description format: "Purchase: {name}" or "Purchase: {name} (xN)" or "Purchase: {name} (xN) [discount]"
            transactions = Transaction.query.filter(
                Transaction.student_id == student.id,
                Transaction.type == 'purchase',
                Transaction.description.like(f"Purchase: {item.name}%")
            ).all()

            # Parse quantities from transaction descriptions
            total_purchased = 0
            for txn in transactions:
                # Extract quantity from description (e.g., "(x3)" -> 3)
                match = re.search(r'\(x(\d+)\)', txn.description)
                if match:
                    total_purchased += int(match.group(1))
                else:
                    # No quantity suffix means quantity was 1
                    total_purchased += 1

            purchase_count = total_purchased
        else:
            purchase_count = StudentItem.query.filter(
                StudentItem.student_id == student.id,
                StudentItem.store_item_id == item.id,
                StudentItem.status.notin_(['voided', 'rejected'])
            ).count()
        if purchase_count + quantity > item.limit_per_student:
            return jsonify({"status": "error", "message": f"You can only purchase {item.limit_per_student - purchase_count} more of this item."}), 400

    # 3. Process the transaction
    try:
        # Deduct from checking account
        purchase_description = f"Purchase: {item.name}"
        if quantity > 1:
            purchase_description += f" (x{quantity})"
        if item.bulk_discount_enabled and quantity >= item.bulk_discount_quantity:
            purchase_description += f" [{item.bulk_discount_percentage}% bulk discount]"

        # CRITICAL FIX v2: Add join_code to purchase transaction
        purchase_tx = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,  # CRITICAL: Add join_code for period isolation
            actor_membership_id=membership_id, # Audit Anchor
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description
        )
        db.session.add(purchase_tx)

        # Handle inventory
        if item.inventory is not None:
            item.inventory -= quantity

        # --- Handle special item type: Hall Pass ---
        if item.item_type == 'hall_pass':
            student.hall_passes += quantity  # Add all purchased hall passes
            db.session.flush()  # Flush to update balances without committing yet

            # Check if overdraft protection should transfer funds from savings
            if banking_settings and banking_settings.overdraft_protection_enabled and student.checking_balance < 0:
                shortfall = abs(student.checking_balance)
                if student.savings_balance >= shortfall:
                    # CRITICAL FIX v2: Transfer from savings to checking with join_code
                    transfer_tx_withdraw = Transaction(
                        student_id=student.id,
                        teacher_id=teacher_id,
                        join_code=join_code,  # CRITICAL: Add join_code for period isolation
                        actor_membership_id=membership_id, # Audit Anchor
                        amount=-shortfall,
                        account_type='savings',
                        type='Withdrawal',
                        description='Overdraft protection transfer to checking'
                    )
                    transfer_tx_deposit = Transaction(
                        student_id=student.id,
                        teacher_id=teacher_id,
                        join_code=join_code,  # CRITICAL: Add join_code for period isolation
                        actor_membership_id=membership_id, # Audit Anchor
                        amount=shortfall,
                        account_type='checking',
                        type='Deposit',
                        description='Overdraft protection transfer from savings'
                    )
                    db.session.add(transfer_tx_withdraw)
                    db.session.add(transfer_tx_deposit)
                    db.session.flush()  # Flush to update balances

            # Check if overdraft fee should be charged (after overdraft protection)
            fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id, join_code)

            # Commit all transactions together
            db.session.commit()

            return jsonify({"status": "success", "message": f"You purchased {quantity} Hall Pass(es)! Your new balance is {student.hall_passes}."})

        # --- Standard Item Logic ---
        # Create the student's item(s)
        expiry_date = None

        # Check if this is a rent item
        from app.models import RentItem, RentSettings
        rent_item = RentItem.query.filter_by(store_item_id=item.id).first()
        uses_remaining = None

        if rent_item:
            if rent_item.rent_item_type == 'privilege':
                # Calculate NEXT rent due date and set as expiry
                rent_setting = db.session.get(RentSettings, rent_item.rent_setting_id)
                if rent_setting and rent_setting.is_enabled:
                    now = utc_now()

                    if rent_setting.first_rent_due_date:
                        current_due, next_due = _calculate_due_dates(rent_setting, now)

                        if current_due and next_due:
                            # Align expiry to the next scheduled due date
                            expiry_date = next_due
                    else:
                        # No first_rent_due_date set, use simple calculation from now
                        # This is a fallback for backwards compatibility
                        delta = _get_period_delta(rent_setting)
                        expiry_date = _add_period(now, delta)
            # For per-use rent items, do not set uses_remaining on paid purchases.

        # Fall back to standard auto_expiry for delayed items
        if expiry_date is None and item.item_type == 'delayed' and item.auto_expiry_days:
            expiry_date = utc_now() + timedelta(days=item.auto_expiry_days)

        student_item_status = 'purchased'
        if item.item_type == 'immediate':
            student_item_status = 'redeemed' # Immediate use items are redeemed instantly
        elif item.item_type == 'collective':
            student_item_status = 'pending'
        else: # delayed
            student_item_status = 'purchased'

        # Handle bundle items - create one StudentItem with bundle tracking
        if item.is_bundle and item.bundle_quantity is not None:
            new_student_item = StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                join_code=join_code,
                purchase_date=utc_now(),
                expiry_date=expiry_date,
                status=student_item_status,
                is_from_bundle=True,
                bundle_remaining=item.bundle_quantity * quantity,  # Total uses = bundle_quantity * number of bundles purchased
                quantity_purchased=quantity,
                uses_remaining=uses_remaining
            )
            db.session.add(new_student_item)
        elif item.is_bundle and item.bundle_quantity is None:
            # Safety: if bundle is enabled but quantity is missing, treat as regular item
            current_app.logger.error(f"Bundle item {item.id} has is_bundle=True but bundle_quantity=None. Treating as regular item.")
            new_student_item = StudentItem(
                student_id=student.id,
                store_item_id=item.id,
                join_code=join_code,
                purchase_date=utc_now(),
                expiry_date=expiry_date,
                status=student_item_status,
                is_from_bundle=False,
                quantity_purchased=quantity,
                uses_remaining=uses_remaining
            )
            db.session.add(new_student_item)
        else:
            # For non-bundle items, create separate StudentItem records for each quantity
            for _ in range(quantity):
                new_student_item = StudentItem(
                    student_id=student.id,
                    store_item_id=item.id,
                    join_code=join_code,
                    purchase_date=utc_now(),
                    expiry_date=expiry_date,
                    status=student_item_status,
                    is_from_bundle=False,
                    quantity_purchased=1,
                    uses_remaining=uses_remaining
                )
                db.session.add(new_student_item)

        db.session.flush()  # Flush to update balances without committing yet

        # Handle overdraft protection and fees for regular items
        # Check if overdraft protection should transfer funds from savings
        if banking_settings and banking_settings.overdraft_protection_enabled and student.checking_balance < 0:
            shortfall = abs(student.checking_balance)
            if student.savings_balance >= shortfall:
                # CRITICAL FIX v2: Transfer from savings to checking with join_code
                transfer_tx_withdraw = Transaction(
                    student_id=student.id,
                    teacher_id=teacher_id,
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    actor_membership_id=membership_id, # Audit Anchor
                    amount=-shortfall,
                    account_type='savings',
                    type='Withdrawal',
                    description='Overdraft protection transfer to checking'
                )
                transfer_tx_deposit = Transaction(
                    student_id=student.id,
                    teacher_id=teacher_id,
                    join_code=join_code,  # CRITICAL: Add join_code for period isolation
                    actor_membership_id=membership_id, # Audit Anchor
                    amount=shortfall,
                    account_type='checking',
                    type='Deposit',
                    description='Overdraft protection transfer from savings'
                )
                db.session.add(transfer_tx_withdraw)
                db.session.add(transfer_tx_deposit)
                db.session.flush()  # Flush to update balances

        # Check if overdraft fee should be charged (after overdraft protection)
        fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings, teacher_id, join_code)

        # --- Collective Item Logic ---
        if item.item_type == 'collective':
            class_size = TeacherBlock.query.filter_by(
                teacher_id=teacher_id,
                join_code=join_code,
                is_claimed=True,
            ).count()
            purchased_students_count = db.session.query(func.count(func.distinct(StudentItem.student_id))).filter(
                StudentItem.store_item_id == item.id,
                StudentItem.join_code == join_code,
                StudentItem.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
            ).scalar() or 0

            if item.collective_goal_type == 'fixed':
                target = int(item.collective_goal_target or 0)
            else:
                target = class_size

            if target > 0 and purchased_students_count >= target:
                # Threshold met for this class: unlock only this class period's pending items
                StudentItem.query.filter(
                    StudentItem.store_item_id == item.id,
                    StudentItem.join_code == join_code,
                    StudentItem.status == 'pending'
                ).update({"status": "processing"})
                current_app.logger.info(
                    "Collective goal '%s' reached for join_code=%s (%s/%s)",
                    item.name,
                    join_code,
                    purchased_students_count,
                    target,
                )

        # Commit purchases for both collective and non-collective items
        db.session.commit()

        # Build success message
        success_message = f"You purchased {item.name}!"
        if item.is_bundle and item.bundle_quantity is not None:
            total_uses = item.bundle_quantity * quantity
            success_message = f"You purchased {quantity} bundle(s) of {item.name}! You have {total_uses} uses."
        elif quantity > 1:
            success_message = f"You purchased {quantity}x {item.name}!"

        if (item.bulk_discount_enabled and
            item.bulk_discount_quantity is not None and
            item.bulk_discount_percentage is not None and
            quantity >= item.bulk_discount_quantity):
            success_message += f" (Saved {item.bulk_discount_percentage}% with bulk discount!)"

        return jsonify({"status": "success", "message": success_message})

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Purchase failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred during purchase. Please try again."}), 500


@api_bp.route('/use-item', methods=['POST'])
@login_required
def use_item():
    student = get_logged_in_student()
    data = request.get_json()
    student_item_id = data.get('student_item_id')
    passphrase = data.get('passphrase')
    details = data.get('redemption_details', data.get('details', ''))  # optional notes from student

    if not all([student_item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 2. Get the student's item
    student_item = db.session.get(StudentItem, student_item_id)

    if not student_item or student_item.student_id != student.id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Validate the item can be used
    if student_item.is_from_bundle:
        # For bundle items, check bundle_remaining
        if student_item.bundle_remaining is None or student_item.bundle_remaining <= 0:
            return jsonify({"status": "error", "message": "All uses from this bundle have been consumed."}), 400
    else:
        # For regular items, check status
        if student_item.status not in ['purchased', 'pending']:
            return jsonify({"status": "error", "message": "This item has already been used or is not available."}), 400

    # Check expiry
    if student_item.expiry_date and utc_now() > student_item.expiry_date:
        student_item.status = 'expired'
        db.session.commit()
        return jsonify({"status": "error", "message": "This item has expired."}), 400

    # Get context up front for audit snapshots and transaction scoping.
    context = get_current_class_context()
    teacher_id_for_audit = (
        context['teacher_id'] if context else
        (student_item.store_item.teacher_id if student_item.store_item else None)
    )
    fallback_block = context.get('block') if context else student.block

    # Request action happens when item transitions into admin approval workflow.
    will_create_request = (
        not student_item.is_from_bundle and (
            student_item.uses_remaining is None or
            (student_item.uses_remaining != -1 and student_item.uses_remaining <= 1)
        )
    )

    # 3. Mark as processing and create redemption transaction
    try:
        audit_guard = {'inserted': False}
        if will_create_request:
            _append_redemption_audit_log(
                student_item=student_item,
                student=student,
                teacher_id=teacher_id_for_audit,
                action='request',
                notes=details,
                guard_state=audit_guard,
                fallback_block=fallback_block,
            )

        # Handle bundle items differently
        if student_item.is_from_bundle:
            # Decrement bundle_remaining
            student_item.bundle_remaining -= 1
            if student_item.bundle_remaining == 0:
                student_item.status = 'redeemed'  # All uses consumed
            student_item.redemption_date = utc_now()
            if student_item.redemption_details:
                student_item.redemption_details += f"\n---\n{details}"
            else:
                student_item.redemption_details = details
        elif student_item.uses_remaining is not None:
            # Multi-use item (Rent Per-Use with limit > 1) or unlimited (-1)
            # Don't decrement if unlimited
            if student_item.uses_remaining != -1:
                student_item.uses_remaining -= 1
                if student_item.uses_remaining <= 0:
                    # Last use - mark as processing (if requires approval) or completed/redeemed
                    # Assuming rent per-use items are 'delayed' type (request redemption)
                    student_item.status = 'processing'
                else:
                    # Still has uses remaining - keep status as 'purchased' so it remains in "My Items"
                    pass

            student_item.redemption_date = utc_now()
            if student_item.uses_remaining == -1:
                uses_msg = "unlimited uses remaining"
            else:
                uses_msg = f"{student_item.uses_remaining} uses remaining"
            
            if student_item.redemption_details:
                student_item.redemption_details += f"\n---\n{details} ({uses_msg})"
            else:
                student_item.redemption_details = f"{details} ({uses_msg})"
        else:
            # Regular item - mark as processing
            student_item.status = 'processing'
            student_item.redemption_date = utc_now()
            student_item.redemption_details = details

        # CRITICAL FIX v2: Create a redemption transaction with join_code
        # This is a $0 transaction to log the redemption event
        if context:
            membership_id = context.get('membership_id')

            redemption_tx = Transaction(
                student_id=student.id,
                teacher_id=context['teacher_id'],
                join_code=context['join_code'],  # CRITICAL: Add join_code for period isolation
                actor_membership_id=membership_id, # Audit Anchor
                amount=0.0,
                account_type='checking',
                type='redemption',
                description=f"Used: {student_item.store_item.name}" + (f" (bundle: {student_item.bundle_remaining} remaining)" if student_item.is_from_bundle else "")
            )
            db.session.add(redemption_tx)
        db.session.commit()

        if student_item.is_from_bundle:
            return jsonify({"status": "success", "message": f"You have used 1 from your bundle of {student_item.store_item.name}. {student_item.bundle_remaining} uses remaining."})
        elif student_item.uses_remaining is not None:
            if student_item.uses_remaining == -1:
                return jsonify({"status": "success", "message": f"You have used {student_item.store_item.name}. Unlimited uses remaining."})
            elif student_item.uses_remaining > 0:
                return jsonify({"status": "success", "message": f"You have used {student_item.store_item.name}. {student_item.uses_remaining} uses remaining."})
            else:
                return jsonify({"status": "success", "message": f"You have requested to use {student_item.store_item.name}. Awaiting admin approval."})
        else:
            return jsonify({"status": "success", "message": f"You have requested to use {student_item.store_item.name}. Awaiting admin approval."})

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.session.rollback()
        current_app.logger.error(f"Item use failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred. Please try again."}), 500


@api_bp.route('/approve-redemption', methods=['POST'])
@admin_required
def approve_redemption():
    data = request.get_json(silent=True) or {}
    student_item_id = data.get('student_item_id')

    if not student_item_id:
        return jsonify({"status": "error", "message": "Missing student item ID."}), 400

    student_item = db.session.get(StudentItem, student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    # SECURITY: Verify the current admin owns the store item
    current_admin = get_current_admin()
    if not current_admin or student_item.store_item.teacher_id != current_admin.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        audit_guard = {'inserted': False}
        _append_redemption_audit_log(
            student_item=student_item,
            student=student_item.student,
            teacher_id=current_admin.id,
            action='approved',
            notes=student_item.redemption_details,
            guard_state=audit_guard,
            fallback_block=student_item.student.block if student_item.student else None,
        )

        student_item.status = 'completed'

        # Find the corresponding 'redemption' transaction and update its description
        redemption_tx = Transaction.query.filter_by(
            student_id=student_item.student_id,
            type='redemption',
            join_code=student_item.join_code,
        ).filter(
            Transaction.description.like(f"Used: {student_item.store_item.name}%")
        ).order_by(Transaction.timestamp.desc()).first()

        if redemption_tx:
            redemption_tx.description = f"Redeemed: {student_item.store_item.name}"

        db.session.commit()
        return jsonify({"status": "success", "message": "Redemption approved."})
    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.session.rollback()
        current_app.logger.error(f"Redemption approval failed for student_item {student_item_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred."}), 500


@api_bp.route('/reject-redemption', methods=['POST'])
@admin_required
def reject_redemption():
    data = request.get_json(silent=True) or {}
    student_item_id = data.get('student_item_id')

    if not student_item_id:
        return jsonify({"status": "error", "message": "Missing student item ID."}), 400

    student_item = db.session.get(StudentItem, student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    # SECURITY: Verify the current admin owns the store item
    current_admin = get_current_admin()
    if not current_admin or student_item.store_item.teacher_id != current_admin.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    try:
        audit_guard = {'inserted': False}
        _append_redemption_audit_log(
            student_item=student_item,
            student=student_item.student,
            teacher_id=current_admin.id,
            action='rejected',
            notes=student_item.redemption_details,
            guard_state=audit_guard,
            fallback_block=student_item.student.block if student_item.student else None,
        )

        # 1. Determine Refund Amount from original purchase transaction
        # Look up the actual amount paid (handles price changes and bulk discounts)
        purchase_tx_query = Transaction.query.filter_by(
            student_id=student_item.student_id,
            teacher_id=student_item.store_item.teacher_id,
            type='purchase',
        ).filter(
            Transaction.description.like(f"Purchase: {student_item.store_item.name}%")
        )
        if student_item.join_code:
            purchase_tx_query = purchase_tx_query.filter(
                Transaction.join_code == student_item.join_code
            )
        purchase_txs = purchase_tx_query.all()

        purchase_tx = None
        if purchase_txs:
            if student_item.purchase_date:
                target_ts = ensure_utc(student_item.purchase_date)

                def _distance(tx):
                    if not tx.timestamp:
                        return float('inf')
                    return abs((ensure_utc(tx.timestamp) - target_ts).total_seconds())

                purchase_tx = min(purchase_txs, key=_distance)
            else:
                purchase_tx = max(
                    purchase_txs,
                    key=lambda tx: ensure_utc(tx.timestamp) if tx.timestamp else datetime.min.replace(tzinfo=timezone.utc)
                )

        if purchase_tx and purchase_tx.amount is not None:
            total_amount = abs(purchase_tx.amount)
            quantity = 1
            if purchase_tx.description:
                match = re.search(r'\(x(\d+)\)', purchase_tx.description)
                if match:
                    try:
                        parsed_qty = int(match.group(1))
                        if parsed_qty > 0:
                            quantity = parsed_qty
                    except ValueError:
                        pass
            refund_amount = total_amount / quantity
        else:
            # Fallback to current store price if purchase transaction not found
            refund_amount = student_item.store_item.price

        # 2. Refund the student
        # Create refund transaction
        # CRITICAL: Use join_code from student_item for proper scoping
        # CRITICAL FIX: Handle legacy StudentItems without join_code
        refund_join_code = student_item.join_code
        if not refund_join_code and purchase_tx and purchase_tx.join_code:
            refund_join_code = purchase_tx.join_code

        if not refund_join_code:
            # Legacy StudentItem without join_code - resolve from student blocks
            student = db.session.get(Student, student_item.student_id)
            teacher_id = student_item.store_item.teacher_id

            if student and student.block:
                student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
                if student_blocks:
                    refund_join_code = get_join_code_for_student_period(
                        student.id, student_blocks[0], teacher_id
                    )

        if not refund_join_code:
            current_app.logger.error(
                f"Unable to resolve join_code for legacy StudentItem {student_item.id} "
                "during refund. Aborting to avoid unscoped transaction."
            )
            return jsonify({"status": "error", "message": "Unable to resolve class for refund."}), 400

        if refund_join_code != student_item.join_code:
            current_app.logger.warning(
                f"Legacy StudentItem {student_item.id} missing join_code. "
                f"Resolved to: {refund_join_code} for refund transaction."
            )

        refund_tx = Transaction(
            student_id=student_item.student_id,
            teacher_id=student_item.store_item.teacher_id,
            join_code=refund_join_code,  # Now guaranteed to have a value
            amount=refund_amount,
            account_type='checking',
            type='refund',
            original_transaction_id=purchase_tx.id if purchase_tx else None,
            description=f"Refund: {student_item.store_item.name} (Redemption Rejected)"
        )
        db.session.add(refund_tx)
        if purchase_tx:
            purchase_tx.reversal_transaction_id = refund_tx.id

        # 3. Mark item as rejected (terminal state) instead of deleting history.
        student_item.status = 'rejected'
        student_item.redemption_date = utc_now()
        if student_item.redemption_details:
            student_item.redemption_details = f"{student_item.redemption_details}\n---\nStatus: rejected"
        else:
            student_item.redemption_details = "Status: rejected"

        db.session.commit()
        return jsonify({"status": "success", "message": "Redemption rejected and refunded."})

    except (SQLAlchemyError, RuntimeError, ValueError) as e:
        db.session.rollback()
        current_app.logger.error(f"Redemption rejection failed for student_item {student_item_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred."}), 500


# -------------------- HALL PASS API --------------------

@api_bp.route('/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
def handle_hall_pass_action(pass_id, action):
    log_entry = db.get_or_404(HallPassLog, pass_id)
    student = log_entry.student
    now = utc_now()

    # Audit Anchor: Determine who is acting
    from app.auth import get_membership
    admin_id = session.get('admin_id')
    # Logic: Admin is acting on a specific hall pass associated with log_entry.join_code
    # We must find the admin's membership in that specific class economy
    actor_membership = get_membership(join_code=log_entry.join_code, admin_id=admin_id)

    if actor_membership:
        log_entry.actor_membership_id = actor_membership.id
    else:
        # Fallback or error? For now, log warning if admin has no membership in this class
        # This occurs if a system admin acts, or if data is inconsistent
        if not session.get('is_system_admin'):
            current_app.logger.warning(f"Admin {admin_id} acting on HallPass {pass_id} without membership in {log_entry.join_code}")

    if action == 'approve':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        # Check if hall pass deduction is needed (not for Office/Summons/Done for the day)
        should_deduct = log_entry.reason.lower() not in ['office', 'summons', 'done for the day']

        if should_deduct and student.hall_passes <= 0:
            return jsonify({"status": "error", "message": "Student has no hall passes left."}), 400

        # Generate unique pass number (letter + 2 digits)
        while True:
            letter = random.choice(string.ascii_uppercase)
            digits = random.randint(10, 99)
            pass_number = f"{letter}{digits}"
            # Check if this pass number already exists
            existing = HallPassLog.query.filter_by(pass_number=pass_number).first()
            if not existing:
                break

        log_entry.status = 'approved'
        log_entry.decision_time = now
        log_entry.pass_number = pass_number

        # Only deduct hall pass for regular reasons (not Office/Summons/Done for the day)
        if should_deduct:
            student.hall_passes -= 1
            # Decrement rent_hall_passes first (rent-granted passes consumed before purchased)
            block_period = log_entry.period or student.block
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=block_period
            ).first()
            if student_block and not student_block.join_code and log_entry.join_code:
                student_block.join_code = log_entry.join_code
            elif not student_block:
                student_block = StudentBlock(
                    student_id=student.id,
                    period=block_period,
                    join_code=log_entry.join_code
                )
                db.session.add(student_block)
            if student_block and student_block.rent_hall_passes > 0:
                student_block.rent_hall_passes -= 1

        db.session.commit()
        return jsonify({"status": "success", "message": "Pass approved.", "pass_number": pass_number})

    elif action == 'reject':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        log_entry.status = 'rejected'
        log_entry.decision_time = now
        db.session.commit()
        return jsonify({"status": "success", "message": "Pass rejected."})

    elif action == 'leave':
        if log_entry.status != 'approved':
            return jsonify({"status": "error", "message": "Pass is not approved."}), 400

        # Create a tap-out event for attendance tracking
        tap_out_event = TapEvent(
            student_id=student.id,
            period=log_entry.period,
            status='inactive',
            timestamp=now,
            reason=log_entry.reason,
            join_code=log_entry.join_code
        )
        log_entry.status = 'left'
        log_entry.left_time = now
        db.session.add(tap_out_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has left the class."})

    elif action == 'return':
        if log_entry.status != 'left':
            return jsonify({"status": "error", "message": "Student is not out of class."}), 400

        # Create a tap-in event to close the loop
        tap_in_event = TapEvent(
            student_id=student.id,
            period=log_entry.period,
            status='active',
            timestamp=now,
            reason="Return from hall pass",
            join_code=log_entry.join_code
        )
        log_entry.status = 'returned'
        log_entry.return_time = now
        db.session.add(tap_in_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has returned."})

    return jsonify({"status": "error", "message": "Invalid action."}), 400


@api_bp.route('/hall-pass/verification/active', methods=['GET'])
def get_active_hall_passes():
    """Get last 10 students who used hall passes for verification display

    CRITICAL: This endpoint requires join_code for proper class isolation.
    Usage: /api/hall-pass/verification/active?join_code=ABC123
    Legacy: /api/hall-pass/verification/active?teacher_id=123 (deprecated)
    """

    from app.models import Admin, Student, StudentTeacher
    from sqlalchemy import or_

    # CRITICAL: Use join_code as primary scoping mechanism
    join_code = request.args.get('join_code')
    teacher_id = request.args.get('teacher_id', type=int)

    # Start with base query
    query = HallPassLog.query.filter(
        HallPassLog.status.in_(['left', 'returned']),
        HallPassLog.left_time.isnot(None)
    )

    # Primary: Scope by join_code (new architecture)
    if join_code:
        query = query.filter(HallPassLog.join_code == join_code)

    # Fallback: Scope by teacher_id (legacy)
    elif teacher_id:
        # Validate teacher exists
        teacher = db.session.get(Admin, teacher_id)
        if not teacher:
            return jsonify({
                "status": "error",
                "message": "Invalid teacher_id"
            }), 404

        # If querying as admin, verify authorization (only their own data unless system admin)
        if session.get('is_admin') and not session.get('is_system_admin'):
            if session.get('admin_id') != teacher_id:
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized"
                }), 403

        # Build subquery for students belonging to this teacher
        # Include both primary ownership (teacher_id) and shared access (student_teachers)
        shared_student_ids = (
            StudentTeacher.query.with_entities(StudentTeacher.student_id)
            .filter(StudentTeacher.admin_id == teacher_id)
            .subquery()
        )

        student_ids_subquery = (
            Student.query.with_entities(Student.id)
            .filter(
                Student.id.in_(sa.select(shared_student_ids))
            )
            .subquery()
        )

        # Add teacher scoping filter
        query = query.filter(HallPassLog.student_id.in_(sa.select(student_ids_subquery)))

    else:
        # SECURITY: Require either join_code or teacher_id to prevent global data leak
        # System admins can still see all data by providing teacher_id
        if not session.get('is_system_admin'):
            return jsonify({
                "status": "error",
                "message": "join_code or teacher_id is required"
            }), 400

    # Get the last 10 students who have left class
    recent_passes = query.order_by(HallPassLog.left_time.desc()).limit(10).all()

    # Helper function to ensure times are marked as UTC
    def format_utc_time(dt):
        if not dt:
            return None
        # Ensure datetime is treated as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    passes_data = []
    for log_entry in recent_passes:
        student = log_entry.student
        passes_data.append({
            "student_name": student.full_name,
            "period": log_entry.period,
            "destination": log_entry.reason,
            "left_time": format_utc_time(log_entry.left_time),
            "return_time": format_utc_time(log_entry.return_time),
            "pass_number": log_entry.pass_number,
            "status": log_entry.status
        })

    return jsonify({
        "status": "success",
        "passes": passes_data
    })


@api_bp.route('/hall-pass/lookup/<string:pass_number>', methods=['GET'])
def lookup_hall_pass(pass_number):
    """Look up a hall pass by its pass number (for terminal use)"""
    # Find the hall pass log entry by pass number
    log_entry = HallPassLog.query.filter_by(pass_number=pass_number.upper()).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Pass number not found."}), 404

    student = log_entry.student

    # Return the pass information (ensure times are marked as UTC)
    def format_utc_time(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return jsonify({
        "status": "success",
        "pass": {
            "id": log_entry.id,
            "student_name": student.full_name,
            "period": log_entry.period,
            "destination": log_entry.reason,
            "pass_number": log_entry.pass_number,
            "pass_status": log_entry.status,
            "request_time": format_utc_time(log_entry.request_time),
            "decision_time": format_utc_time(log_entry.decision_time),
            "left_time": format_utc_time(log_entry.left_time),
            "return_time": format_utc_time(log_entry.return_time)
        }
    })


def _get_default_timezone():
    """Return the configured default timezone or fall back to Pacific Time."""
    tz_name = current_app.config.get('DEFAULT_TIMEZONE', 'America/Los_Angeles')
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        current_app.logger.warning(
            "Invalid DEFAULT_TIMEZONE '%s' configured; falling back to America/Los_Angeles.",
            tz_name
        )
        return pytz.timezone('America/Los_Angeles')


def _check_simultaneous_pass_limit(log_entry):
    """Validate destination settings and simultaneous pass limits."""
    teacher_block = TeacherBlock.query.filter_by(join_code=log_entry.join_code).first()
    teacher_id = teacher_block.teacher_id if teacher_block else None
    if not teacher_id:
        # Fallback for legacy data: derive teacher from StudentTeacher link
        teacher_id = (
            StudentTeacher.query.with_entities(StudentTeacher.admin_id)
            .filter(StudentTeacher.student_id == log_entry.student_id)
            .scalar()
        )
    if not teacher_id:
        return None

    settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
    if not settings:
        return None

    pass_types = settings.get_pass_types()

    # Find configuration for this destination
    pass_type_config = next((pt for pt in pass_types if pt['name'].lower() == log_entry.reason.lower()), None)

    # Check if pass type is enabled
    if pass_type_config and not pass_type_config.get('enabled', True):
        return jsonify({
            "status": "error",
            "message": f"{log_entry.reason} pass type is currently disabled."
        }), 403

    # Check simultaneous limit
    if pass_type_config and pass_type_config.get('simultaneous_limit') is not None:
        user_tz = _get_default_timezone()
        now_user_tz = utc_now().astimezone(user_tz)
        today_start_user_tz = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_user_tz.astimezone(pytz.utc)
        today_start_db = normalize_for_db(today_start_utc)

        # Count currently out students for THIS destination from today (excluding this student)
        currently_out = HallPassLog.query.filter(
            HallPassLog.status == 'left',
            HallPassLog.reason == log_entry.reason,
            HallPassLog.join_code == log_entry.join_code,
            HallPassLog.left_time >= today_start_db,
            HallPassLog.id != log_entry.id  # Exclude current pass
        ).count()

        simultaneous_limit = pass_type_config['simultaneous_limit']

        # Check if limit is reached
        if currently_out >= simultaneous_limit:
            return jsonify({
                "status": "error",
                "message": (
                    f"{log_entry.reason} limit reached. {currently_out}/{simultaneous_limit} students are "
                    "currently out. Please wait for someone to return."
                )
            }), 403

    return None


@api_bp.route('/hall-pass/terminal/use', methods=['POST'])
def hall_pass_terminal_use():
    """Mark a hall pass as 'left' when student scans at terminal"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').strip().upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Invalid pass number."}), 404

    if log_entry.status != 'approved':
        return jsonify({"status": "error", "message": f"Pass is not approved. Current status: {log_entry.status}"}), 400

    limit_response = _check_simultaneous_pass_limit(log_entry)
    if limit_response:
        return limit_response

    # Mark as left and create tap-out event
    now = utc_now()
    log_entry.status = 'left'
    log_entry.left_time = now

    # Create tap-out event for attendance tracking
    tap_out_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='inactive',
        timestamp=now,
        reason=log_entry.reason,
        join_code=log_entry.join_code
    )
    db.session.add(tap_out_event)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"{log_entry.student.full_name} has left for {log_entry.reason}.",
            "student_name": log_entry.student.full_name,
            "destination": log_entry.reason
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass terminal use failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/terminal/return', methods=['POST'])
def hall_pass_terminal_return():
    """Mark a hall pass as 'returned' when student scans back in at terminal"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').strip().upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Invalid pass number."}), 404

    if log_entry.status != 'left':
        return jsonify({"status": "error", "message": f"Student is not currently out. Status: {log_entry.status}"}), 400

    # Mark as returned and create tap-in event
    now = utc_now()
    log_entry.status = 'returned'
    log_entry.return_time = now

    # Create tap-in event for attendance tracking
    tap_in_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='active',
        timestamp=now,
        reason="Returned from hall pass",
        join_code=log_entry.join_code
    )
    db.session.add(tap_in_event)

    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"{log_entry.student.full_name} has returned.",
            "student_name": log_entry.student.full_name
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass terminal return failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/cancel/<int:pass_id>', methods=['POST'])
@login_required
def cancel_hall_pass(pass_id):
    """Allow students to cancel their pending hall pass request"""
    student = get_logged_in_student()
    log_entry = db.get_or_404(HallPassLog, pass_id)

    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403

    # Only pending passes can be cancelled
    if log_entry.status != 'pending':
        return jsonify({"status": "error", "message": "Only pending passes can be cancelled."}), 400

    # Mark as rejected (or create a new 'cancelled' status if preferred)
    log_entry.status = 'rejected'
    log_entry.decision_time = utc_now()

    db.session.commit()
    return jsonify({"status": "success", "message": "Hall pass request cancelled."})


@api_bp.route('/hall-pass/checkout', methods=['POST'])
@login_required
def checkout_hall_pass():
    """Allow student to check out with their approved hall pass (replaces terminal use)"""
    student = get_logged_in_student()
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    
    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    
    # Verify pass is approved
    if log_entry.status != 'approved':
        return jsonify({"status": "error", "message": f"Pass is not approved. Current status: {log_entry.status}"}), 400
    
    limit_response = _check_simultaneous_pass_limit(log_entry)
    if limit_response:
        return limit_response
    
    # Mark as left and create tap-out event
    now = utc_now()
    log_entry.status = 'left'
    log_entry.left_time = now
    
    # Create tap-out event for attendance tracking
    tap_out_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='inactive',
        timestamp=now,
        reason=log_entry.reason,
        join_code=log_entry.join_code
    )
    db.session.add(tap_out_event)
    
    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Checked out for {log_entry.reason}.",
            "destination": log_entry.reason,
            "left_time": now.isoformat()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkout failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/checkin', methods=['POST'])
@login_required
def checkin_hall_pass():
    """Allow student to check in from their hall pass (replaces terminal return)"""
    student = get_logged_in_student()
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    
    # Verify this pass belongs to the logged-in student
    if log_entry.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    
    # Verify pass is in 'left' status
    if log_entry.status != 'left':
        return jsonify({"status": "error", "message": f"You are not currently checked out. Status: {log_entry.status}"}), 400
    
    # Mark as returned and create tap-in event
    now = utc_now()
    log_entry.status = 'returned'
    log_entry.return_time = now
    
    # Create tap-in event for attendance tracking
    tap_in_event = TapEvent(
        student_id=log_entry.student_id,
        period=log_entry.period,
        status='active',
        timestamp=now,
        reason="Returned from hall pass",
        join_code=log_entry.join_code
    )
    db.session.add(tap_in_event)
    
    try:
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Checked in successfully. Welcome back!",
            "return_time": now.isoformat()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkin failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/queue', methods=['GET'])
def get_hall_pass_queue():
    """Get current hall pass queue (approved but not yet checked out) and currently out count.

    Supports both:
    - join_code mode (membership-gated, join_code-scoped)
    - legacy teacher_id mode (teacher-scoped fallback for migration compatibility)
    """
    join_code = request.args.get('join_code')
    teacher_id = request.args.get('teacher_id', type=int)

    # Join-code mode (new architecture): explicit membership and role check
    if join_code:
        is_allowed, membership, economy, error = check_membership_access(
            join_code, allowed_roles=['admin']
        )
        if not is_allowed:
            return jsonify({"status": "error", "message": error}), 403
        join_code = economy.join_code
        teacher_id = membership.admin_id if membership else None

        settings = HallPassSettings.query.filter_by(join_code=join_code).first()
        if not settings and teacher_id:
            settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
        if not settings:
            settings = HallPassSettings(queue_enabled=True, queue_limit=10)

        # Today's boundary in user timezone
        tz_name = session.get('timezone', 'America/Los_Angeles')
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            current_app.logger.warning(f"Invalid timezone '{tz_name}' in session, defaulting to Pacific Time.")
            user_tz = pytz.timezone('America/Los_Angeles')
        now_user_tz = utc_now().astimezone(user_tz)
        today_start_utc = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

        base_query = HallPassLog.query.filter_by(join_code=join_code)
        queue_logs = base_query.filter(
            HallPassLog.status.in_(['approved', 'pending']),
            HallPassLog.created_at >= today_start_utc
        ).order_by(HallPassLog.created_at).all()
        currently_out_count = base_query.filter(
            HallPassLog.status == 'left',
            HallPassLog.created_at >= today_start_utc
        ).count()
    else:
        # Legacy teacher_id mode retained for compatibility during migration
        if not teacher_id and session.get('is_admin'):
            teacher_id = session.get('admin_id')
        if not teacher_id:
            return jsonify({
                "status": "error",
                "message": "teacher_id parameter required for queue display"
            }), 400

        teacher = db.session.get(Admin, teacher_id)
        if not teacher:
            return jsonify({"status": "error", "message": "Invalid teacher_id"}), 404

        if session.get('is_admin') and not session.get('is_system_admin'):
            if session.get('admin_id') != teacher_id:
                return jsonify({"status": "error", "message": "Unauthorized"}), 403

        settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
        if not settings:
            settings = HallPassSettings(queue_enabled=True, queue_limit=10)

        tz_name = session.get('timezone', 'America/Los_Angeles')
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            current_app.logger.warning(f"Invalid timezone '{tz_name}' in session, defaulting to Pacific Time.")
            user_tz = pytz.timezone('America/Los_Angeles')
        now_user_tz = utc_now().astimezone(user_tz)
        today_start_db = normalize_for_db(
            now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
        )

        shared_student_ids = (
            StudentTeacher.query.with_entities(StudentTeacher.student_id)
            .filter(StudentTeacher.admin_id == teacher_id)
            .subquery()
        )
        demo_student_ids = DemoStudent.query.with_entities(DemoStudent.student_id).subquery()
        student_ids_subquery = (
            Student.query.with_entities(Student.id)
            .filter(
                Student.id.in_(sa.select(shared_student_ids)),
                ~Student.id.in_(sa.select(demo_student_ids))
            )
            .subquery()
        )

        queue_logs = HallPassLog.query.filter(
            HallPassLog.status == 'approved',
            HallPassLog.decision_time >= today_start_db,
            HallPassLog.student_id.in_(sa.select(student_ids_subquery))
        ).order_by(HallPassLog.decision_time.asc()).all()
        currently_out_count = HallPassLog.query.filter(
            HallPassLog.status == 'left',
            HallPassLog.left_time >= today_start_db,
            HallPassLog.student_id.in_(sa.select(student_ids_subquery))
        ).count()

    # Response payload includes both legacy and new key names
    queue_data = []
    for log in queue_logs:
        student_name = f"{log.student.first_name} {log.student.last_initial}."
        queue_data.append({
            "id": log.id,
            "student_name": student_name,
            "destination": log.reason,
            "student_first": log.student.first_name,
            "student_last": log.student.last_initial,
            "reason": log.reason,
            "status": log.status,
            "created_at": (log.request_time or log.decision_time or log.left_time).isoformat()
            if (log.request_time or log.decision_time or log.left_time) else None,
            "pass_number": log.pass_number
        })

    return jsonify({
        "status": "success",
        "queue": queue_data,
        "currently_out": currently_out_count,
        "total": len(queue_data) + currently_out_count,
        "queue_enabled": settings.queue_enabled if settings else True,
        "queue_limit": settings.queue_limit if settings else 10
    })


@api_bp.route('/hall-pass/settings', methods=['GET', 'POST'])
@admin_required
def hall_pass_settings():
    """Get or update hall pass settings (admin only)"""
    # CRITICAL: Scope by join_code if available for multi-tenancy
    teacher_id = session.get('admin_id')
    current_join_code = session.get('current_join_code')
    
    if not teacher_id:
        return jsonify({"status": "error", "message": "Admin ID not found in session"}), 401

    if current_join_code:
        # Phase A/B: Settings scoped to join_code
        settings = HallPassSettings.query.filter_by(join_code=current_join_code).first()
        if not settings:
             # Create new settings for this join_code
             # Note: We don't copy old teacher settings automatically to avoid confusion?
             # Or should we? For now, clean slate or default.
             settings = HallPassSettings(
                teacher_id=teacher_id,
                join_code=current_join_code,
                block=None,
                queue_enabled=True,
                queue_limit=10
             )
             db.session.add(settings)
             db.session.commit()
    else:
        # Legacy fallback: Scope by teacher_id
        # This path should fade out as admin UI enforces join_code selection
        settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
        if not settings:
            settings = HallPassSettings(
                teacher_id=teacher_id,
                block=None,
                queue_enabled=True,
                queue_limit=10
            )
            db.session.add(settings)
            db.session.commit()

    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "settings": {
                "queue_enabled": settings.queue_enabled,
                "queue_limit": settings.queue_limit
            }
        })

    # POST - update settings
    data = request.get_json()

    if 'queue_enabled' in data:
        settings.queue_enabled = bool(data['queue_enabled'])

    if 'queue_limit' in data:
        queue_limit = int(data['queue_limit'])
        if queue_limit < 1 or queue_limit > 50:
            return jsonify({"status": "error", "message": "Queue limit must be between 1 and 50"}), 400
        settings.queue_limit = queue_limit

    settings.updated_at = utc_now()
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Settings updated successfully",
        "settings": {
            "queue_enabled": settings.queue_enabled,
            "queue_limit": settings.queue_limit
        }
    })


@api_bp.route('/hall-pass/history', methods=['GET'])
@admin_required
def hall_pass_history():
    """Get paginated hall pass history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 25)), 100)  # Max 100 per page

        # Get filter parameters
        period = request.args.get('period', '').strip()
        pass_type = request.args.get('type', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        # Get student IDs that the current admin can access (tenant-scoped)
        # Includes both primary ownership and shared students
        student_ids_subquery = (
            get_admin_student_query(include_unassigned=False)
            .with_entities(Student.id)
            .subquery()
        )

        # Build query with tenant scoping
        query = (
            HallPassLog.query
            .filter(HallPassLog.student_id.in_(sa.select(student_ids_subquery)))
        )

        # Apply filters
        if period:
            query = query.filter(HallPassLog.period == period)

        if pass_type:
            query = query.filter(HallPassLog.reason == pass_type)

        if start_date:
            try:
                # Parse date and treat as UTC midnight (start of day)
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)
                query = query.filter(HallPassLog.request_time >= start_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                # Parse date and treat as UTC end of day (23:59:59)
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query = query.filter(HallPassLog.request_time <= end_datetime)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Order by most recent first
        query = query.order_by(HallPassLog.request_time.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Helper function to format timestamp as UTC with 'Z' suffix
        def format_timestamp(dt):
            if not dt:
                return None
            # Ensure timestamp is treated as UTC and format properly
            if dt.tzinfo is None:
                # Naive datetime - assume UTC
                return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            else:
                # Convert to UTC if not already
                return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Format records for response
        records_data = []
        for record in records:
            records_data.append({
                "id": record.id,
                "student_name": record.student.full_name if record.student else "Unknown",
                "period": record.period,
                "reason": record.reason,
                "pass_number": record.pass_number,
                "status": record.status,
                "request_time": format_timestamp(record.request_time),
                "decision_time": format_timestamp(record.decision_time),
                "left_time": format_timestamp(record.left_time),
                "return_time": format_timestamp(record.return_time)
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching hall pass history: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch history"}), 500


@api_bp.route('/hall-pass/setup', methods=['GET'])
@admin_required
def get_hall_pass_setup():
    """Get teacher's hall pass configuration"""
    teacher_id = session.get('admin_id')

    # Get or create settings for this teacher
    settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()

    if not settings:
        # Return default configuration
        return jsonify({
            "status": "success",
            "hall_pass_enabled": True,
            "pass_types": HallPassSettings.get_default_pass_types()
        })

    # Return configured pass types with fallback to defaults
    return jsonify({
        "status": "success",
        "hall_pass_enabled": settings.queue_enabled,
        "pass_types": settings.get_pass_types()
    })


@api_bp.route('/hall-pass/setup', methods=['POST'])
@admin_required
def save_hall_pass_setup():
    """Save teacher's hall pass configuration"""
    teacher_id = session.get('admin_id')
    data = request.get_json()

    pass_types = data.get('pass_types', [])
    hall_pass_enabled = data.get('hall_pass_enabled', True)

    # Validate hall_pass_enabled
    if not isinstance(hall_pass_enabled, bool):
        return jsonify({"status": "error", "message": "hall_pass_enabled must be a boolean"}), 400

    # Validate pass_types format
    if not isinstance(pass_types, list):
        return jsonify({"status": "error", "message": "pass_types must be a list"}), 400

    for pt in pass_types:
        if not isinstance(pt, dict):
            return jsonify({"status": "error", "message": "Each pass type must be an object"}), 400
        if 'name' not in pt:
            return jsonify({"status": "error", "message": "Each pass type must have a name"}), 400
        if not pt['name'].strip():
            return jsonify({"status": "error", "message": "Pass type name cannot be empty"}), 400

        # Validate enabled (defaults to True if not provided)
        if 'enabled' not in pt:
            pt['enabled'] = True
        if not isinstance(pt['enabled'], bool):
            return jsonify({"status": "error", "message": "enabled must be a boolean"}), 400

        # Validate queue_limit and simultaneous_limit (can be None or positive integer)
        for field in ['queue_limit', 'simultaneous_limit']:
            if field in pt and pt[field] is not None:
                try:
                    val = int(pt[field])
                    if val < 0:
                        return jsonify({"status": "error", "message": f"{field} must be non-negative"}), 400
                    pt[field] = val
                except (ValueError, TypeError):
                    return jsonify({"status": "error", "message": f"{field} must be a number or blank"}), 400

    try:
        # Get or create settings for this teacher
        settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()

        if not settings:
            settings = HallPassSettings(
                teacher_id=teacher_id,
                block=None,
                queue_enabled=hall_pass_enabled,
                queue_limit=10,
                pass_types=pass_types
            )
            db.session.add(settings)
        else:
            settings.queue_enabled = hall_pass_enabled
            settings.pass_types = pass_types
            settings.updated_at = utc_now()

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Hall pass configuration saved successfully",
            "hall_pass_enabled": settings.queue_enabled,
            "pass_types": settings.get_pass_types()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving hall pass setup: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to save configuration"}), 500


@api_bp.route('/hall-pass/available-types', methods=['GET'])
@login_required
def get_available_hall_pass_types():
    """Get available pass types for a teacher (endpoint for authenticated student use)"""
    teacher_id = request.args.get('teacher_id', type=int)

    if not teacher_id:
        return jsonify({"status": "error", "message": "teacher_id is required"}), 400

    # Get settings for this teacher
    settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()

    if not settings:
        # Return defaults if not configured
        return jsonify({
            "status": "success",
            "pass_types": HallPassSettings.get_default_pass_types()
        })

    # Return just the names for enabled pass types
    pass_types = settings.get_pass_types()
    enabled_pass_types = [{"name": pt["name"]} for pt in pass_types if pt.get("enabled", True)]

    return jsonify({
        "status": "success",
        "pass_types": enabled_pass_types
    })


@api_bp.route('/attendance/history', methods=['GET'])
@admin_required
def attendance_history():
    """Get paginated attendance history with filters (admin only)"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)  # Max 100 per page

        # Get filter parameters
        period = request.args.get('period', '').strip()
        block = request.args.get('block', '').strip()
        status = request.args.get('status', '').strip()  # 'active' or 'inactive'
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Import auth helper for tenant scoping
        from app.auth import get_admin_student_query
        
        # Get student IDs that the current admin can access (tenant-scoped)
        accessible_student_ids_query = get_admin_student_query(include_unassigned=False).with_entities(Student.id)
        
        # Build query scoped to admin's students and exclude deleted records
        query = TapEvent.query.filter(
            TapEvent.student_id.in_(accessible_student_ids_query),
            TapEvent.is_deleted.is_(False)
        )

        # Apply filters
        if period:
            query = query.filter(TapEvent.period == period)

        if status:
            query = query.filter(TapEvent.status == status)

        if start_date:
            try:
                # Parse date and treat as UTC midnight (start of day)
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)
                query = query.filter(TapEvent.timestamp >= normalize_for_db(start_datetime))
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                # Parse date and treat as UTC end of day (23:59:59)
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                query = query.filter(TapEvent.timestamp <= normalize_for_db(end_datetime))
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Filter by block (need to join with Student)
        if block:
            query = query.join(Student, TapEvent.student_id == Student.id)
            # Use LIKE to match comma-separated blocks
            query = query.filter(Student.block.like(f'%{block}%'))

        # Order by most recent first
        query = query.order_by(TapEvent.timestamp.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        # Build student lookup for names and blocks
        student_ids = [r.student_id for r in records]
        students = {s.id: {'name': s.full_name, 'block': s.block} for s in Student.query.filter(Student.id.in_(student_ids)).all()}

        # Get class labels for blocks
        admin_id = session.get("admin_id")
        blocks_in_records = set(students[sid]['block'] for sid in students if students[sid]['block'])
        class_labels = {}
        if blocks_in_records:
            teacher_blocks = TeacherBlock.query.filter(
                TeacherBlock.teacher_id == admin_id,
                TeacherBlock.block.in_(blocks_in_records)
            ).all()
            for teacher_block in teacher_blocks:
                class_labels[teacher_block.block] = teacher_block.get_class_label()

        # Format records for response
        records_data = []
        for record in records:
            student_info = students.get(record.student_id, {'name': 'Unknown', 'block': 'Unknown'})
            student_block = student_info['block']
            student_class_label = class_labels.get(student_block, student_block) if student_block != 'Unknown' else 'Unknown'

            # Format timestamp as UTC with 'Z' suffix
            timestamp_str = None
            if record.timestamp:
                # Ensure timestamp is treated as UTC and format properly
                if record.timestamp.tzinfo is None:
                    # Naive datetime - assume UTC
                    timestamp_str = record.timestamp.replace(tzinfo=timezone.utc).isoformat()
                else:
                    # Convert to UTC if not already
                    timestamp_str = record.timestamp.astimezone(timezone.utc).isoformat()
                # Replace +00:00 with Z for cleaner UTC representation
                timestamp_str = timestamp_str.replace('+00:00', 'Z')

            records_data.append({
                "id": record.id,
                "student_id": record.student_id,
                "student_name": student_info['name'],
                "student_block": student_block,
                "student_class_label": student_class_label,
                "period": record.period,
                "status": record.status,
                "reason": record.reason if record.reason else None,
                "timestamp": timestamp_str
            })

        return jsonify({
            "status": "success",
            "records": records_data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching attendance history: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to fetch attendance history"}), 500


# -------------------- ATTENDANCE API --------------------

@api_bp.route('/tap', methods=['POST'])
@limiter.limit("100 per minute")
def handle_tap():
    data = request.get_json()
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    current_app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    student = get_logged_in_student()

    if not student:
        current_app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not check_password_hash(student.pin_hash or '', pin):
        current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student.id}")
        return jsonify({"error": "Invalid PIN"}), 403


    student_blocks_raw = [b.strip() for b in student.block.split(',') if b.strip()] if student and isinstance(student.block, str) else []
    block_lookup = {b.upper(): b for b in student_blocks_raw}
    valid_periods = list(block_lookup.keys())
    period = data.get("period", "").upper()
    action = data.get("action")

    current_app.logger.info(f"TAP DEBUG: student_id={getattr(student, 'id', None)}, valid_periods={valid_periods}, period={period}, action={action}")

    # Support both old and new action names
    action_map = {
        "tap_in": "start_work",
        "tap_out": "stop_work",
        "start_work": "start_work",
        "stop_work": "stop_work"
    }

    if period not in valid_periods or action not in action_map:
        current_app.logger.warning(f"TAP ERROR: Invalid period or action: period={period}, valid_periods={valid_periods}, action={action}")
        return jsonify({"error": "Invalid period or action"}), 400

    # Normalize action to new terminology
    normalized_action = action_map[action]

    join_code = get_join_code_for_student_period(student.id, period)
    if not join_code:
        current_app.logger.warning(
            f"TAP ERROR: Unable to resolve join_code for student_id={student.id}, period={period}"
        )
        return jsonify({"error": "Unable to resolve class context for this period."}), 400

    now = utc_now()

    # --- Check if tap is enabled for this student in this period ---
    from app.models import StudentBlock
    student_block = StudentBlock.query.filter_by(
        student_id=student.id,
        period=period
    ).first()

    # If no StudentBlock record exists, create one with default settings (tap_enabled=True)
    if not student_block:
        try:
            student_block = StudentBlock(
                student_id=student.id,
                period=period,
                tap_enabled=True
            )
            db.session.add(student_block)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=period
            ).first()

    # Check if tap is disabled for this period
    if not student_block.tap_enabled:
        return jsonify({"error": "Start Work / Break is currently disabled for this period."}), 403

    # --- Check "done for the day" lock ---
    if normalized_action == "start_work":
        # Use Pacific timezone for "done for the day" check
        pacific = pytz.timezone('America/Los_Angeles')
        now_pacific = now.astimezone(pacific)
        today_pacific = now_pacific.date()

        # Automatically clear "done for the day" lock if it's from a previous day
        if student_block.done_for_day_date is not None and student_block.done_for_day_date < today_pacific:
            student_block.done_for_day_date = None
            db.session.commit()
        if student_block.done_for_day_date == today_pacific:
            return jsonify({"error": "You are done for the day. You cannot Start Work again until tomorrow."}), 403


    # --- Hall Pass Logic for Stop Work ---
    if normalized_action == 'stop_work':
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "A reason is required for a hall pass."}), 400

        # Special case for "Done for the day" - this is the old "tap out" behavior
        if reason.lower() in ['done', 'done for the day']:
            # Fall through to the standard TapEvent creation logic below
            pass
        else:
            # All other reasons go through the hall pass approval flow
            # Check hall pass settings and queue limits

            # CRITICAL: Get teacher_id from join_code for multi-tenancy scoping
            from app.models import TeacherBlock
            teacher_block = TeacherBlock.query.filter_by(join_code=join_code).first()
            if not teacher_block:
                return jsonify({"error": "Unable to resolve teacher for this class period."}), 400

            teacher_id = teacher_block.teacher_id

            # Query settings scoped to this teacher (block=None means global default)
            settings = HallPassSettings.query.filter_by(teacher_id=teacher_id, block=None).first()
            if not settings:
                settings = HallPassSettings(
                    teacher_id=teacher_id,
                    block=None,
                    queue_enabled=True,
                    queue_limit=10
                )
                db.session.add(settings)
                db.session.commit()

            # Get pass types configuration
            pass_types = settings.get_pass_types()

            # Find configuration for this specific destination/reason
            pass_type_config = next((pt for pt in pass_types if pt['name'].lower() == reason.lower()), None)

            # If queue is disabled globally, check if we should block this request
            # (we can still allow passes if they have unlimited limits for BOTH queue and simultaneous)
            if not settings.queue_enabled:
                # Allow only if this pass type has BOTH limits set to unlimited
                if pass_type_config and (pass_type_config.get('queue_limit') is None and pass_type_config.get('simultaneous_limit') is None):
                    pass  # Allow through
                else:
                    return jsonify({
                        "error": "Queue system is currently disabled."
                    }), 403

            # Check per-destination queue limits
            if pass_type_config and pass_type_config.get('queue_limit') is not None:
                # Get user's timezone from session for today's count
                tz_name = session.get('timezone', 'America/Los_Angeles')
                try:
                    user_tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    user_tz = pytz.timezone('America/Los_Angeles')

                now_user_tz = utc_now().astimezone(user_tz)
                today_start_user_tz = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
                today_start_utc = today_start_user_tz.astimezone(pytz.utc)
                today_start_db = normalize_for_db(today_start_utc)

                # Count approved (waiting) passes for THIS destination from today
                queue_count = HallPassLog.query.filter(
                    HallPassLog.status == 'approved',
                    HallPassLog.reason == reason,
                    HallPassLog.join_code == join_code,
                    HallPassLog.decision_time >= today_start_db
                ).count()

                # Count currently out students for THIS destination from today
                out_count = HallPassLog.query.filter(
                    HallPassLog.status == 'left',
                    HallPassLog.reason == reason,
                    HallPassLog.join_code == join_code,
                    HallPassLog.left_time >= today_start_db
                ).count()

                total_in_queue = queue_count + out_count
                queue_limit = pass_type_config['queue_limit']

                # Check if queue is at capacity for this destination
                if total_in_queue >= queue_limit:
                    return jsonify({
                        "error": f"{reason} queue is full ({total_in_queue}/{queue_limit}). Please wait for someone to return."
                    }), 403

            # Check if hall pass is required (not for Office/Summons/Done for the day)
            should_require_pass = reason.lower() not in ['office', 'summons', 'done for the day']

            if should_require_pass and student.hall_passes <= 0:
                return jsonify({"error": "Insufficient hall passes."}), 400

            # Create a hall pass log entry
            hall_pass_log = HallPassLog(
                student_id=student.id,
                reason=reason,
                period=period,
                join_code=join_code,
                status='pending',
                request_time=now
            )
            db.session.add(hall_pass_log)
            db.session.commit()

            # Since the student is just requesting, they are still 'active'.
            # We need to return the current state to the UI.
            is_active = True
            last_payroll_time = get_last_payroll_time(student_id=student.id)
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)
            rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period))
            projected_pay = duration * rate_per_second

            return jsonify({
                "status": "ok",
                "message": "Hall pass requested.",
                "active": is_active,
                "duration": duration,
                "projected_pay": float(projected_pay),
                "hall_pass": {
                    "id": hall_pass_log.id,
                    "status": hall_pass_log.status,
                    "reason": hall_pass_log.reason,
                    "pass_number": hall_pass_log.pass_number
                }
            })

    # --- Standard Start/Stop Work Logic ---
    try:
        status = "active" if normalized_action == "start_work" else "inactive"
        reason = data.get("reason") if normalized_action == "stop_work" else None

        # Auto-tap-out from other periods when tapping into a new period
        if normalized_action == "start_work":
            # Find all other periods where student is currently active
            for other_period in valid_periods:
                if other_period == period:
                    continue  # Skip the period we're tapping into

                latest_other = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=other_period, is_deleted=False)
                    .filter_by(join_code=join_code)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                if latest_other and latest_other.status == "active":
                    # Auto tap-out from this period
                    auto_tapout = TapEvent(
                        student_id=student.id,
                        period=other_period,
                        status="inactive",
                        timestamp=now,
                        reason="auto_switch",  # Mark as automatic switch
                        join_code=join_code
                    )
                    db.session.add(auto_tapout)
                    current_app.logger.info(f"Auto-tapped out student {student.id} from period {other_period} when tapping into {period}")

        # Prevent duplicate tap-in or tap-out
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period, is_deleted=False)
            .filter_by(join_code=join_code)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        if latest_event and latest_event.status == status:
            current_app.logger.info(f"Duplicate {action} ignored for student {student.id} in period {period}")
            last_payroll_time = get_last_payroll_time(student_id=student.id)
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)
            return jsonify({
                "status": "ok",
                "active": latest_event.status == "active",
                "duration": duration
            })

        # Check daily limit when Starting Work
        if normalized_action == "start_work":
            from app.payroll import get_daily_limit_seconds
            from app.attendance import calculate_period_attendance_utc_range

            daily_limit = get_daily_limit_seconds(period)
            if daily_limit:
                # Use Pacific timezone for daily reset
                pacific = pytz.timezone('America/Los_Angeles')
                now_pacific = now.astimezone(pacific)
                today_pacific = now_pacific.date()

                # Calculate UTC boundaries for today in Pacific timezone
                start_of_day_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
                start_of_day_utc = start_of_day_pacific.astimezone(timezone.utc)
                end_of_day_pacific = start_of_day_pacific + timedelta(days=1)
                end_of_day_utc = end_of_day_pacific.astimezone(timezone.utc)

                # Query using proper UTC boundaries
                today_attendance = calculate_period_attendance_utc_range(
                    student.id, period, start_of_day_utc, end_of_day_utc
                )

                if today_attendance >= daily_limit:
                    hours_limit = daily_limit / 3600.0
                    current_app.logger.warning(
                        f"Student {student.id} attempted to tap in for {period} but has reached daily limit of {hours_limit} hours"
                    )
                    return jsonify({
                        "error": f"Daily limit of {hours_limit:.1f} hours reached for this period. Please try again tomorrow."
                    }), 400

        # When Starting Work, automatically return any active hall pass
        if normalized_action == "start_work":
            active_hall_pass = HallPassLog.query.filter_by(
                student_id=student.id,
                period=period,
                join_code=join_code,
                status='left'
            ).order_by(HallPassLog.request_time.desc()).first()

            if active_hall_pass:
                active_hall_pass.status = 'returned'
                active_hall_pass.return_time = now
                current_app.logger.info(f"Auto-returned hall pass {active_hall_pass.id} for student {student.id}")

        event = TapEvent(
            student_id=student.id,
            period=period,
            status=status,
            timestamp=now,  # UTC-aware
            reason=reason,
            join_code=join_code
        )
        db.session.add(event)

        # Update "done for the day" status when Stopping Work with reason "done"
        pacific = pytz.timezone('America/Los_Angeles')
        now_pacific = now.astimezone(pacific)
        today_pacific = now_pacific.date()
        # Clear done_for_day_date if it's a new day
        if student_block.done_for_day_date and student_block.done_for_day_date != today_pacific:
            student_block.done_for_day_date = None
            current_app.logger.info(f"Cleared done_for_day_date for student {student.id} in period {period} (new day)")
        # Set or clear done_for_day_date based on stop work reason
        if normalized_action == "stop_work":
            if reason and reason.lower() in ['done', 'done for the day']:
                student_block.done_for_day_date = today_pacific
                current_app.logger.info(f"Student {student.id} marked as done for the day in period {period}")
            else:
                if student_block.done_for_day_date is not None:
                    student_block.done_for_day_date = None
                    current_app.logger.info(f"Cleared done_for_day_date for student {student.id} in period {period} (reason: {reason})")

        db.session.commit()
        current_app.logger.info(f"TAP success - student {student.id} {period} {action}")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    # Fetch latest status and unpaid duration for the tapped period
    latest_event = (
        TapEvent.query
        .filter_by(student_id=student.id, period=period, is_deleted=False)
        .filter_by(join_code=join_code)
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = latest_event.status == "active" if latest_event else False
    last_payroll_time = get_last_payroll_time(student_id=student.id)
    duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time, join_code=join_code)

    rate_per_second = get_pay_rate_for_block(block_lookup.get(period, period))
    projected_pay = duration * rate_per_second

    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": float(projected_pay)
    })


@api_bp.route('/admin/tap-entries/<int:student_id>', methods=['GET'])
def get_tap_entries(student_id):
    """
    Get all tap entries for a student with pairing validation.
    Returns entries grouped by period with pairing status.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import TapEvent
    from app.auth import get_student_for_admin

    # SECURITY FIX: Use scoped helper to verify admin owns this student
    student = get_student_for_admin(student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    # Get all tap events for this student
    events = TapEvent.query.filter_by(
        student_id=student_id
    ).order_by(TapEvent.period, TapEvent.timestamp.asc()).all()

    # Group by period and validate pairing
    periods = {}
    for event in events:
        if event.period not in periods:
            periods[event.period] = []
        periods[event.period].append({
            'id': event.id,
            'status': event.status,
            'timestamp': event.timestamp.isoformat() if event.timestamp else None,
            'reason': event.reason,
            'is_deleted': event.is_deleted,
            'deleted_at': event.deleted_at.isoformat() if event.deleted_at else None
        })

    # Validate pairing for each period
    period_data = {}
    for period, events_list in periods.items():
        # Filter out deleted events for pairing validation
        active_events = [e for e in events_list if not e['is_deleted']]

        # Check for unpaired entries
        unpaired = []
        expected_status = 'active'
        for event in active_events:
            if event['status'] == expected_status:
                expected_status = 'inactive' if expected_status == 'active' else 'active'
            else:
                unpaired.append(event['id'])

        # If we end on 'active', the last event is unpaired (student still tapped in)
        if active_events and active_events[-1]['status'] == 'active':
            # This is actually valid (student is currently working), remove from unpaired
            if active_events[-1]['id'] in unpaired:
                unpaired.remove(active_events[-1]['id'])

        period_data[period] = {
            'events': events_list,
            'unpaired_event_ids': unpaired,
            'is_valid': len(unpaired) == 0
        }

    return jsonify({
        'student_id': student_id,
        'student_name': student.full_name,
        'periods': period_data
    })


@api_bp.route('/admin/tap-entries/<int:event_id>', methods=['DELETE'])
def delete_tap_entry(event_id):
    """
    Soft-delete a tap entry by marking it as deleted.
    Only allows deletion of unpaired or invalid entries.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models import TapEvent
    from app.auth import get_student_for_admin

    event = db.session.get(TapEvent, event_id)
    if not event:
        return jsonify({"error": "Tap entry not found"}), 404

    # SECURITY FIX: Use scoped helper to verify admin owns this student
    student = get_student_for_admin(event.student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    # Mark as deleted
    event.is_deleted = True
    event.deleted_at = utc_now()
    event.deleted_by = admin.id

    db.session.commit()

    current_app.logger.info(f"Admin {admin.id} deleted tap entry {event_id} for student {event.student_id}")

    return jsonify({
        "status": "ok",
        "message": "Tap entry deleted successfully"
    })


@api_bp.route('/admin/student-block-settings', methods=['POST'])
def update_student_block_settings():
    """
    Update StudentBlock settings (tap_enabled toggle) for a student-period combination.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    student_id = data.get('student_id')
    period = data.get('period', '').upper()
    tap_enabled = data.get('tap_enabled')

    if not student_id or not period or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400

    from app.models import StudentBlock
    from app.auth import get_student_for_admin

    # SECURITY FIX: Use scoped helper AND removed deprecated teacher_id check
    student = get_student_for_admin(student_id)
    if not student:
        return jsonify({"error": "Student not found or access denied"}), 404

    # Get or create StudentBlock record
    student_block = StudentBlock.query.filter_by(
        student_id=student_id,
        period=period
    ).first()

    if not student_block:
        student_block = StudentBlock(
            student_id=student_id,
            period=period,
            tap_enabled=tap_enabled
        )
        db.session.add(student_block)
    else:
        student_block.tap_enabled = tap_enabled

    db.session.commit()

    current_app.logger.info(f"Admin {admin.id} set tap_enabled={tap_enabled} for student {student_id} period {period}")

    return jsonify({
        "status": "ok",
        "tap_enabled": tap_enabled
    })


def check_and_auto_tapout_if_limit_reached(student, commit=True):
    """
    Checks if an active student has reached their daily limit and auto-taps them out.
    This function should be called periodically (e.g., during status checks).
    Daily limits reset at midnight Pacific time.
    
    Args:
        student: Student model instance
        commit: Whether to commit the transaction immediately (default: True).
                Set to False if calling in a loop to batch commits.
    """
    import pytz
    from app.payroll import get_daily_limit_seconds
    from app.attendance import calculate_period_attendance_utc_range

    # Helper function to ensure UTC timezone-aware datetime


    # Keep original case for settings lookup, but uppercase for TapEvent queries
    student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
    now_utc = utc_now()

    # Use Pacific timezone for daily reset
    pacific = pytz.timezone('America/Los_Angeles')
    now_pacific = now_utc.astimezone(pacific)
    today_pacific = now_pacific.date()

    # Calculate UTC boundaries for today in Pacific timezone
    # Start: midnight Pacific today -> UTC
    start_of_day_pacific = pacific.localize(datetime.combine(today_pacific, datetime.min.time()))
    start_of_day_utc = start_of_day_pacific.astimezone(timezone.utc)

    # End: midnight Pacific tomorrow -> UTC
    end_of_day_pacific = start_of_day_pacific + timedelta(days=1)
    end_of_day_utc = end_of_day_pacific.astimezone(timezone.utc)

    for block_original in student_blocks:
        period_upper = block_original.upper()

        # Check if student is currently active in this period (TapEvent uses uppercase)
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period_upper, is_deleted=False)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )

        if latest_event and latest_event.status == "active":
            # Get teacher_id for this block (needed for settings lookup)
            teacher_id = None
            # Try to find seat for this block
            seat = TeacherBlock.query.filter_by(student_id=student.id, block=block_original, is_claimed=True).first()
            if seat:
                teacher_id = seat.teacher_id
            else:
                # Fallback: get first teacher from StudentTeacher table
                first_link = StudentTeacher.query.filter_by(student_id=student.id).first()
                teacher_id = first_link.admin_id if first_link else None

            # Get daily limit for this period (use original case for settings lookup)
            daily_limit = get_daily_limit_seconds(block_original, teacher_id=teacher_id)

            if daily_limit:
                # Calculate today's completed attendance using proper Pacific day boundaries
                today_attendance = calculate_period_attendance_utc_range(
                    student.id, period_upper, start_of_day_utc, end_of_day_utc
                )

                # Add current active session time
                # Convert to UTC-aware datetime to prevent TypeError
                last_tap_in_utc = ensure_utc(latest_event.timestamp)

                # Only add active session time if tapped in today (within Pacific day boundaries)
                if start_of_day_utc <= last_tap_in_utc < end_of_day_utc:
                    current_session_seconds = (now_utc - last_tap_in_utc).total_seconds()
                    today_attendance += current_session_seconds

                # If limit reached or exceeded, auto-tap-out
                if today_attendance >= daily_limit:
                    hours_limit = daily_limit / 3600.0

                    # Prioritize join_code from the active event we are closing
                    join_code = latest_event.join_code
                    if not join_code:
                        # Fallback for legacy events without a join_code
                        join_code = get_join_code_for_student_period(student.id, period_upper)

                    if not join_code:
                        current_app.logger.warning(
                            f"Unable to resolve join_code for student {student.id} in period {period_upper} for auto-tap-out. TapEvent ID is {latest_event.id}."
                        )
                        continue

                    # IDEMPOTENCY CHECK: Check if we already created a daily limit tap-out today
                    # This prevents duplicate tap-outs from race conditions (multiple browser tabs, scheduled job, etc.)
                    existing_limit_tapout = TapEvent.query.filter(
                        TapEvent.student_id == student.id,
                        TapEvent.period == period_upper,
                        TapEvent.status == "inactive",
                        TapEvent.timestamp >= start_of_day_utc,
                        TapEvent.timestamp < end_of_day_utc,
                        TapEvent.reason.like(f"Daily limit%"),  # Matches "Daily limit (X.Xh) reached"
                        TapEvent.is_deleted == False
                    ).first()

                    if existing_limit_tapout:
                        current_app.logger.debug(
                            f"Skipping duplicate auto-tap-out for student {student.id} in {period_upper} - "
                            f"daily limit tap-out already exists at {existing_limit_tapout.timestamp}"
                        )
                        continue  # Skip creating duplicate

                    current_app.logger.info(
                        f"Auto-tapping out student {student.id} from {period_upper} - daily limit of {hours_limit} hours reached (total: {today_attendance/3600:.2f}h)"
                    )

                    # Calculate when they SHOULD have been tapped out (at exactly the limit)
                    # If they've been active for 90 minutes and limit is 75, tap them out 15 minutes ago
                    overage_seconds = today_attendance - daily_limit
                    tapout_timestamp = now_utc - timedelta(seconds=overage_seconds)

                    # Create tap-out event backdated to when they hit the limit
                    tap_out_event = TapEvent(
                        student_id=student.id,
                        period=period_upper,
                        status="inactive",
                        timestamp=tapout_timestamp,
                        reason=f"Daily limit ({hours_limit:.1f}h) reached",
                        join_code=join_code
                    )
                    db.session.add(tap_out_event)

                    # Lock the student for the rest of the day in this period
                    student_block = StudentBlock.query.filter_by(
                        student_id=student.id,
                        period=period_upper
                    ).first()
                    if not student_block:
                        student_block = StudentBlock(
                            student_id=student.id,
                            period=period_upper,
                            tap_enabled=True,
                            join_code=join_code
                        )
                        db.session.add(student_block)
                    student_block.done_for_day_date = today_pacific

    # Commit all auto-tap-outs at once if requested
    if commit:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to auto-tap-out student {student.id}: {e}")


@api_bp.route('/student-status', methods=['GET'])
@login_required
def student_status():
    from app.routes.student import get_current_class_context

    student = get_logged_in_student()

    context = get_current_class_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    # Check and auto-tap-out if daily limit reached
    check_and_auto_tapout_if_limit_reached(student)

    period_states = get_all_block_statuses(student, join_code=context['join_code'])

    # Convert Decimal values to float for JSON serialization
    for state in period_states.values():
        if 'projected_pay' in state and state['projected_pay'] is not None:
            state['projected_pay'] = float(state['projected_pay'])

    return jsonify({
        "status": "ok",
        "periods": period_states
    })


# -------------------- UTILITY API --------------------

@api_bp.route('/set-timezone', methods=['POST'])
def set_timezone():
    """Store user's timezone in session for datetime formatting"""
    # Allow access if user is logged in as student OR admin
    is_authenticated = False
    now = utc_now()

    # Check Admin Session
    if session.get('is_admin') and session.get('admin_id'):
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if (now - last_activity_dt) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass # Invalid date format, treat as unauthenticated
        else:
             # If no last_activity but is_admin is set, treat as active for now
             # (matches admin_required logic which would set it if missing)
             is_authenticated = True
             session['last_activity'] = now.isoformat()

    # Check System Admin Session (if not already authenticated)
    if not is_authenticated and session.get('is_system_admin') and session.get('sysadmin_id'):
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if (now - last_activity_dt) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass
        else:
            # If no last_activity but sysadmin_id is set, treat as active
            is_authenticated = True
            session['last_activity'] = now.isoformat()

    # Check Student Session (if not already authenticated as admin or sysadmin)
    if not is_authenticated and 'student_id' in session:
        login_time_str = session.get('login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                if (now - login_time) < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                    is_authenticated = True
                    session['last_activity'] = now.isoformat()
            except ValueError:
                pass

    if not is_authenticated:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json()
    timezone_name = data.get('timezone')

    if not timezone_name:
        return jsonify({"status": "error", "message": "Timezone is required."}), 400

    # Validate Timezone
    if timezone_name not in pytz.all_timezones:
         return jsonify({"status": "error", "message": "Invalid timezone."}), 400

    # Store in session
    session['timezone'] = timezone_name
    current_app.logger.info(f"Timezone set to {timezone_name} for session")

    return jsonify({"status": "success", "message": f"Timezone set to {timezone_name}."})


# -------------------- VIEW AS STUDENT API --------------------

@api_bp.route('/admin/create-demo-student', methods=['POST'])
@admin_required
def create_demo_student():
    """Create a demo student session with custom configuration"""
    from app.models import DemoStudent
    from werkzeug.security import generate_password_hash
    import secrets

    try:
        from app.models import _quantize_currency
        admin_id = session.get('admin_id')
        data = request.get_json()

        # Extract configuration
        checking_balance = _quantize_currency(data.get('checking_balance', '0'))
        savings_balance = _quantize_currency(data.get('savings_balance', '0'))
        hall_passes = int(data.get('hall_passes', 3))
        insurance_plan = data.get('insurance_plan', 'none')
        period = data.get('period', 'A')
        rent_enabled = bool(data.get('rent_enabled', True))
        join_code = generate_join_code()

        # Generate a unique session ID for this demo
        demo_session_id = secrets.token_urlsafe(32)

        # Create a temporary demo student record
        # Use encrypted first name for demo student
        demo_student = Student(
            first_name='Demo',
            last_initial='S',
            block=period,
            salt=secrets.token_bytes(16),
            pin_hash=generate_password_hash('1234'),  # Default PIN for demo
            passphrase_hash=generate_password_hash('demo'),  # Default passphrase for demo
            hall_passes=hall_passes,
            is_rent_enabled=rent_enabled,
            insurance_plan=insurance_plan,
            has_completed_setup=True,
            teacher_id=admin_id
        )
        demo_student.first_half_hash = secrets.token_hex(32)
        demo_student.second_half_hash = secrets.token_hex(32)

        db.session.add(demo_student)
        db.session.flush()  # Get the student ID

        # Link demo student to admin for scoped queries
        demo_link = StudentTeacher(student_id=demo_student.id, admin_id=admin_id)
        db.session.add(demo_link)

        # Ensure ClassEconomy exists (for ClassMembership join)
        # Note: In a real flow, this would exist. For demo, we might need to assume it's created or implied.
        # However, ClassMembership requires a join_code foreign key.
        # TeacherBlock migration logic typically handles ClassEconomy creation.
        # Here we just ensure the join_code is valid for membership.
        # (Assuming ClassEconomy creation is handled elsewhere or implicitly safe for demo logic,
        # but optimally we should create it if we enforce FKs)
        from app.models import ClassEconomy, ClassMembership

        # Check if ClassEconomy exists for this join_code, if not create (for demo safety)
        if not ClassEconomy.query.get(join_code):
            db.session.add(ClassEconomy(join_code=join_code, display_name=f"Demo {period}"))
            db.session.flush() # Ensure it exists for FKs

        # Create a claimed seat for this demo student so student routes have class context
        demo_seat = TeacherBlock(
            teacher_id=admin_id,
            block=period,
            class_label=f"Demo {period}",
            first_name='Demo',
            last_initial='S',
            last_name_hash_by_part=hash_last_name_parts('S', demo_student.salt),
            dob_sum=0,
            salt=demo_student.salt,
            first_half_hash=secrets.token_hex(32),
            join_code=join_code,
            student_id=demo_student.id,
            is_claimed=True,
            claimed_at=utc_now()
        )
        db.session.add(demo_seat)

        # Create Admin ClassMembership (The "Actor" for setup)
        admin_membership = ClassMembership.query.filter_by(join_code=join_code, admin_id=admin_id).first()
        if not admin_membership:
            admin_membership = ClassMembership(
                join_code=join_code,
                admin_id=admin_id,
                role='admin',
                status='active'
            )
            db.session.add(admin_membership)
            db.session.flush() # Get ID

        # Create Student ClassMembership (Required for context resolution)
        student_membership = ClassMembership(
            join_code=join_code,
            student_id=demo_student.id,
            role='student',
            status='active'
        )
        db.session.add(student_membership)

        # Ensure tap settings exist for the demo block
        db.session.add(StudentBlock(student_id=demo_student.id, period=period, tap_enabled=True))

        # Create initial balance transactions
        if checking_balance > 0:
            checking_tx = Transaction(
                student_id=demo_student.id,
                teacher_id=admin_id,
                join_code=join_code,
                actor_membership_id=admin_membership.id, # Audit Anchor: Admin created this
                amount=checking_balance,
                account_type='checking',
                type='admin_adjustment',
                description='Demo student initial balance'
            )
            db.session.add(checking_tx)

        if savings_balance > 0:
            savings_tx = Transaction(
                student_id=demo_student.id,
                teacher_id=admin_id,
                join_code=join_code,
                actor_membership_id=admin_membership.id, # Audit Anchor: Admin created this
                amount=savings_balance,
                account_type='savings',
                type='admin_adjustment',
                description='Demo student initial balance'
            )
            db.session.add(savings_tx)

        # Create demo session record
        demo_session = DemoStudent(
            admin_id=admin_id,
            student_id=demo_student.id,
            session_id=demo_session_id,
            expires_at=utc_now() + timedelta(minutes=10),
            config_checking_balance=checking_balance,
            config_savings_balance=savings_balance,
            config_hall_passes=hall_passes,
            config_insurance_plan=insurance_plan,
            config_is_rent_enabled=rent_enabled,
            config_period=period
        )
        db.session.add(demo_session)
        db.session.commit()

        current_app.logger.info(f"Admin {admin_id} created demo student session {demo_session_id} with student_id={demo_student.id}")

        # Return success with the session ID
        return jsonify({
            "status": "success",
            "message": "Demo student session created successfully",
            "session_id": demo_session_id,
            "redirect_url": f"/student/demo-login/{demo_session_id}"
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create demo student: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Failed to create demo student session. Please try again."
        }), 500


@api_bp.route('/admin/block-tap-settings', methods=['GET'])
@admin_required
def get_block_tap_settings():
    """
    Get tap_enabled settings for all students in a specific block.
    Returns true if any student has tap enabled, false if all are disabled.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    block = request.args.get('block', '').strip().upper()
    if not block:
        return jsonify({"error": "Block parameter is required"}), 400
    
    from app.models import Student, StudentBlock
    from app.auth import get_admin_student_query
    
    # Get all students for this admin in this block
    students = get_admin_student_query().all()
    students_in_block = [
        s for s in students
        if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
    ]
    
    if not students_in_block:
        # No students in this block, default to enabled
        return jsonify({"tap_enabled": True})
    
    # Check if tap is enabled for any student in this block
    # Returns the overall block state: true if at least one student has tap enabled,
    # false if all students have it disabled
    any_enabled = False
    for student in students_in_block:
        student_block = StudentBlock.query.filter_by(
            student_id=student.id,
            period=block
        ).first()
        
        if student_block:
            if student_block.tap_enabled:
                any_enabled = True
                break
        else:
            # No StudentBlock record means tap is enabled by default
            any_enabled = True
            break
    
    return jsonify({"tap_enabled": any_enabled})


@api_bp.route('/admin/block-tap-settings', methods=['POST'])
@admin_required
def update_block_tap_settings():
    """
    Update tap_enabled settings for all students in a specific block/period.
    This sets the tap_enabled flag for all students in the specified block.
    """
    admin = get_current_admin()
    if not admin:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    block = data.get('block', '').strip().upper()
    tap_enabled = data.get('tap_enabled')
    
    if not block or tap_enabled is None:
        return jsonify({"error": "Missing required fields"}), 400
    
    from app.models import Student, StudentBlock
    from app.auth import get_admin_student_query
    
    try:
        # Get all students for this admin in this block
        students = get_admin_student_query().all()
        students_in_block = [
            s for s in students
            if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
        ]
        
        updated_count = 0
        for student in students_in_block:
            # Get or create StudentBlock record
            student_block = StudentBlock.query.filter_by(
                student_id=student.id,
                period=block
            ).first()
            
            if not student_block:
                student_block = StudentBlock(
                    student_id=student.id,
                    period=block,
                    tap_enabled=tap_enabled
                )
                db.session.add(student_block)
            else:
                student_block.tap_enabled = tap_enabled
            
            updated_count += 1
        
        db.session.commit()
        
        current_app.logger.info(
            f"Admin {admin.id} set tap_enabled={tap_enabled} for {updated_count} students in block {block}"
        )
        
        return jsonify({
            "status": "ok",
            "tap_enabled": tap_enabled,
            "updated_count": updated_count
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating block tap settings: {e}", exc_info=True)
        return jsonify({"error": "Failed to update tap settings"}), 500


@api_bp.route('/admin/view-as-student-status', methods=['GET'])
@admin_required
def view_as_student_status():
    """Get the current view-as-student mode status"""
    return jsonify({
        "status": "success",
        "view_as_student": session.get('view_as_student', False)
    })

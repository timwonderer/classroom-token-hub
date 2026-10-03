"""
API routes for Classroom Token Hub.

RESTful JSON API endpoints for student transactions, hall passes, attendance,
and other interactive features. Most routes require authentication.
"""

import re
import secrets
import uuid
import pytz
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from flask import Blueprint, request, jsonify, session, current_app, g
from sqlalchemy import func, or_
import sqlalchemy as sa
from sqlalchemy.orm import aliased
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.hash_utils import verify_password

from app.extensions import db, limiter, student_status_seat_limit_key
from app.models import (
    Transaction, TransactionStatus, AttendanceSession,
    AttendanceReasonCode, HallPassLog, HallPassSettings,
    # Legacy tap models are unauthorized; use attendance_sessions (DOM-PROD-001).
    # StoreItemBlock removed — store_item_blocks unauthorized; use store_item_visibility (DOM-STORE-001)
    StoreItemVisibility, User,
    _quantize_currency,
    ClassEconomy, Seat, IdentityProfile,
    PendingAction,
)
from app.auth import (
    login_required,
    admin_required,
    get_current_seat,

    get_current_user,
    get_current_class_id,
    SESSION_TIMEOUT_MINUTES,
)
from app.access import AccessScopeDenied, resolve_scope
from app.services.context_resolver import ContextResolutionError, resolve_canonical_context

from app.feats.attendance import (
    rotate_teacher_hall_pass_verify_token as feat_rotate_teacher_hall_pass_verify_token,
    save_hall_pass_setup_config as feat_save_hall_pass_setup_config,
    update_hall_pass_queue_settings as feat_update_hall_pass_queue_settings,
)
from app.feats.prod import record_attendance_session
from app.routes.student import (
    get_feature_settings_for_student,
)
from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
from app.feats.base import FEATContext, FEATContextError
from app.feats.store_purchase_feat import execute_store_purchase
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.services import store_service
from app.services.entitlement_read_service import (
    derive_display_status,
    entitlement_terminal_event,
    get_purchase_count,
    latest_entitlement_grant,
    pending_action_for_entitlement,
)
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_hall_pass_settings,
)
from app.services.entitlement_service import consume_entitlement, get_hall_pass_balance, grant_hall_passes
from app.services.hall_pass_status_service import (
    HALL_PASS_STATUS_RETURNED,
    resolve_hall_pass_lifecycle_status,
)
from app.feats.hall_pass_request_feat import (
    approve_hall_pass_request,
    cancel_hall_pass_request,
    reject_hall_pass_request,
    submit_hall_pass_request,
)
from app.services.hall_pass_request_queue import HallPassRequestNotFound
from app.utils.economy_policy import resolve_class_scope, resolve_feature_class, resolve_feature_class_for_class
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
    utc_now,
)
from app.utils.join_code import get_display_join_code
from app.utils.transaction_idempotency import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    get_idempotent_transaction,
    purchase_transaction_key,
)
from app.utils.canonical_temporal_resolver import utc_now, ensure_utc

# Import external modules
from app.services.attendance_service import (
    calculate_unpaid_attendance_seconds,
    calculate_worked_attendance_seconds_today,
    get_class_attendance_status,
    is_done_for_day,
)
from app.services.ledger_posting_service import create_pending_transaction, create_pending_transaction_idempotent
from app.services.ledger_balance_query_service import get_available_balances
from app.services.payroll.pricing import estimate_unpaid_amount

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


def _log_api_client_error(route_name, exc, *, extra=None):
    current_app.logger.info(
        "API client error on %s: %s%s",
        route_name,
        exc.__class__.__name__,
        f" ({extra})" if extra else "",
    )


def _safe_exception_prefix_message(exc, default_message, *, allowed_prefixes=None):
    message = str(exc)
    if allowed_prefixes:
        for allowed_prefix in allowed_prefixes:
            if message.startswith(allowed_prefix):
                return allowed_prefix
    return default_message


@api_bp.errorhandler(ContextResolutionError)
def handle_api_context_resolution_error(e):
    from app.services.context_resolver import ContextForbidden, ContextMismatch
    if isinstance(e, (ContextForbidden, ContextMismatch)):
        return jsonify({"status": "error", "message": "Not Found", "error": "Not Found"}), 404
    return jsonify({"status": "error", "message": "Class context required", "error": "Class context required"}), 401



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


def _resolve_class_display_label(class_id, fallback_block=None):
    """
    Resolve a stable class display label snapshot for audit logging.
    """
    if class_id:
        class_economy = get_class_economy(class_id)
        if class_economy:
            return class_economy.display_name or get_display_join_code(class_id)

    return fallback_block or "Unknown Class"


def _get_hall_pass_settings_scope(user_id, class_id):
    """Resolve canonical class scope for hall pass settings."""
    return resolve_class_scope(user_id, class_id=class_id)


def _admin_has_class_scope(canonical_context, class_id):
    """Return True when admin owns the class_id via active admin membership."""
    if canonical_context is None or not getattr(canonical_context, "user_id", None) or not class_id:
        return False

    user_id = canonical_context.user_id
    return db.session.query(
        sa.exists().where(
            sa.and_(
                Seat.user_id == user_id,
                Seat.class_id == class_id,
                Seat.role == 'teacher',
            )
        )
    ).scalar()


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

# Student-facing copy for each way a purchase can be refused, keyed by the
# FEAT's `error_code`. The FEAT's own `error_message` is a developer diagnostic
# and must not reach a student: it names internal domain boundaries and can
# carry a raw reason code. Answering the two questions a student actually has —
# what went wrong, and what they can do — is a presentation concern, so it is
# decided here rather than in the domain that raised it.
_PURCHASE_ERROR_COPY = {
    "INSUFFICIENT_FUNDS": "You do not have enough in checking to buy this right now.",
    "HOLDING_LIMIT_EXCEEDED": "You already have as many of these as you are allowed to hold.",
    "RENT_PAST_DUE_PURCHASE_BLOCKED": "Rent is overdue, so this item cannot be bought until it is paid.",
    "COLLECTIVE_GOAL_EXPIRED": "This class goal has closed, so it can no longer be bought into.",
    "QUANTITY_NOT_ALLOWED": "That quantity is not available for this item.",
    "PRODUCT_NOT_PURCHASABLE": "This item is not on sale right now.",
    "DIRECT_PURCHASE_NOT_ALLOWED": "This item cannot be bought directly — your teacher grants it.",
    "PRICE_NOT_CONFIGURED": "This item has no price set yet, so it cannot be bought.",
    "INSURANCE_NOT_PURCHASABLE_VIA_STORE": "Insurance is bought from the Insurance page, not the Store.",
    "POLICY_NOT_FOUND": "This item is no longer available.",
    "POLICY_INVALID": "This item is not available right now.",
    "POLICY_SCOPE_MISMATCH": "This item belongs to a different class.",
    "INVALID_CONTEXT": "Your class session could not be confirmed. Sign in again and retry.",
}

_PURCHASE_ERROR_FALLBACK = "The purchase could not be completed. Nothing was charged."


def _student_purchase_error(error_code):
    """Student-readable sentence for a purchase refusal.

    An unmapped code falls back rather than leaking the code itself: a student
    can do nothing with `POLICY_SCOPE_MISMATCH`, and a new code added to the
    FEAT should degrade to something harmless rather than to jargon.
    """
    return _PURCHASE_ERROR_COPY.get(error_code, _PURCHASE_ERROR_FALLBACK)


@api_bp.route('/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    """
    Purchase an item from the store.

    Wired to FEAT-STOR-001 (Store Purchase and Entitlement Grant).
    Creates EntitlementEvent(s) for purchased quantity.
    """
    # 1. Resolve context and verify actor
    try:
        context = resolve_canonical_context()
    except ContextResolutionError:
        return jsonify({"status": "error", "message": "No class context available."}), 400

    if not context or not context.seat_id:
        return jsonify({"status": "error", "message": "No seat assigned in this class."}), 403

    user = db.session.get(User, context.user_id)
    if not user:
        return jsonify({"status": "error", "message": "Actor not found."}), 403

    # 2. Parse and validate input
    data = request.get_json(silent=True) or {}
    policy_uuid = data.get('policy_uuid')
    passphrase = data.get('passphrase')

    try:
        quantity = int(data.get('quantity', 1))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Quantity must be a whole number."}), 400

    if not policy_uuid or not passphrase:
        return jsonify({"status": "error", "message": "Missing policy UUID or passphrase."}), 400

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1."}), 400

    # 3. Verify passphrase
    if not verify_password(passphrase, user.passphrase_hash or ''):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 4. Call FEAT-STOR-001: Create entitlement grants via purchase
    result = execute_store_purchase(
        canonical_context=context,
        policy_uuid=policy_uuid,
        quantity=quantity,
    )

    if not result.success:
        # `result.error_message` is a diagnostic written for developers and
        # logs — it names internal domains ("Purchase denied by Ledger") and the
        # ledger branch interpolates a raw reason code, or the literal string
        # "unknown", straight into it. Rendering it put that in front of a
        # child. `error_code` is the classification and is already correct on
        # every branch, so the student-facing sentence is derived from it here,
        # at the presentation boundary, and the diagnostic stays in the log.
        current_app.logger.info(
            "Store purchase refused: code=%s detail=%s",
            result.error_code,
            result.error_message,
        )
        return jsonify({
            "status": "error",
            "message": _student_purchase_error(result.error_code),
        }), 400

    return jsonify({
        "status": "success",
        "message": f"Purchase successful! Quantity: {quantity}",
        "correlation_id": result.correlation_id,
    })


@api_bp.route('/use-item', methods=['POST'])
@login_required
def use_item():
    context = getattr(g, "canonical_context", None)
    if not context:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    user = db.session.get(User, context.user_id)
    student = db.session.get(Seat, context.seat_id)
    student_id = student.id if student else None
    
    if not user or not student:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json()
    entitlement_id = data.get('entitlement_id')
    passphrase = data.get('passphrase')
    details = data.get('redemption_details', data.get('details', ''))  # optional notes from student

    if not all([entitlement_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing entitlement ID or passphrase."}), 400

    # 1. Verify the passphrase.
    #
    # FEAT-IDEN-002 "Credential boundary" is normative and assigns "using an
    # entitlement except hall passes" to the passphrase. Hall passes are the
    # named exception and use the PIN, but they are not redeemable here at all:
    # a hall pass is exercised from the attendance Break flow
    # (`/api/hall-pass/request`), which is the only surface that knows whether
    # the student is currently clocked in. See the hall-pass refusal below.
    if not verify_password(passphrase, user.passphrase_hash or ''):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    # 2. Get the entitlement lineage
    entitlement = latest_entitlement_grant(entitlement_id)
    if not entitlement or entitlement.target_seat_id != student.id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    # Check availability via canonical display status
    display_status = derive_display_status(entitlement.entitlement_id)
    if display_status not in ('purchased', 'processing'):
        return jsonify({"status": "error", "message": "This item is not available for redemption."}), 400

    store_item = store_service.resolve_entitlement_product(entitlement)
    if not store_item or store_item.class_id != entitlement.class_id:
        return jsonify({"status": "error", "message": "Invalid item."}), 404

    current_action = pending_action_for_entitlement(entitlement.entitlement_id)
    if current_action:
        return jsonify({"status": "error", "message": "This item is already pending approval."}), 400

    if store_item.item_type == 'immediate':
        terminal = entitlement_terminal_event(entitlement.entitlement_id)
        if terminal:
            return jsonify({"status": "error", "message": "This item is not available for redemption."}), 400
        from app.feats.entitlement_lifecycle_feat import execute_use_item_immediate
        execute_use_item_immediate(
            entitlement_id=entitlement.entitlement_id,
            class_id=entitlement.class_id,
            target_seat_id=entitlement.target_seat_id,
            product_id=entitlement.product_id,
            entitlement_type=entitlement.entitlement_type,
            acquisition_type=entitlement.acquisition_type,
            item_type=store_item.item_type,
            details=details,
            idempotency_key=f"feat:stor:use_imm:{entitlement.entitlement_id}",
        )
        return jsonify({"status": "success", "message": f"You used {store_item.name}."})

    if store_item.item_type == 'hall_pass':
        # A hall pass is not redeemed from the Store. Exercising one marks the
        # student *out of an active work session* — DOM-PROD-001 records it on
        # the attendance timeline as `reason_code = hall_pass` carrying the
        # consumed entitlement's `hall_pass_id` — so outside a session there is
        # nothing to be marked out of, and this route cannot know.
        #
        # `/api/hall-pass/request` is the lawful path: it refuses when the seat
        # holds no pass and when the latest attendance event is not `active`,
        # and it is reached from the dashboard Break flow, where the control is
        # disabled until the student starts work. This branch previously built a
        # second request with none of those preconditions, so a student who had
        # never clocked in — or who had already finished for the day — could
        # request a pass from the Store tab.
        #
        # Purchased passes still reach the student: FEAT-STOR-001 credits the
        # hall-pass balance at sale, which the dashboard renders as passes
        # remaining. Nothing is lost by refusing here.
        return jsonify({
            "status": "error",
            "message": "Hall passes are used from the Break button on your dashboard, once you have started work.",
        }), 400

    action_payload = {
        "action": "REQUEST",
        "item_type": store_item.item_type,
        "product_id": store_item.product_lineage_uuid,
        "policy_uuid": store_item.policy_uuid,
        "details": details or None,
    }

    # PendingAction.correlation_id is unique, and the key below becomes that
    # correlation. A rejected request stays on file for the audit history while
    # `pending_action_for_entitlement` above only blocks on *unresolved* rows —
    # so a student may legitimately re-request after a rejection, and a key
    # derived from the entitlement alone would collide at flush. Keying on the
    # attempt keeps each request distinct; a double submit within one attempt is
    # already refused by the pending-action check above.
    request_attempt = (
        PendingAction.query
        .filter(PendingAction.entitlement_id == entitlement.entitlement_id)
        .count()
    )
    from app.feats.entitlement_lifecycle_feat import execute_use_item_request
    execute_use_item_request(
        class_id=entitlement.class_id,
        seat_id=student.id,
        entitlement_id=entitlement.entitlement_id,
        action_payload=action_payload,
        idempotency_key=f"feat:stor:use_req:{entitlement.entitlement_id}:{request_attempt}",
    )
    return jsonify({"status": "success", "message": f"You have requested to use {store_item.name}. Awaiting admin approval."})


class _RedemptionDecisionRefused(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def _load_redemption_for_decision(data):
    """Resolve and lock the waiting request a teacher is deciding.

    Accepts the request id (``request_id``, the pending action) or the
    entitlement it acts on (``entitlement_id``). Either way the request must be
    unresolved and in the teacher's active class: a class the teacher owns is
    not enough, because ownership spans every period they teach. The pending
    row is locked, so a second decision arriving at the same moment waits and
    then finds nothing left to decide.
    """
    ctx = g.canonical_context
    try:
        active_class_id = ctx.class_id
    except AttributeError:
        active_class_id = None
    if not active_class_id or not _admin_has_class_scope(ctx, active_class_id):
        raise _RedemptionDecisionRefused("Select a class first.", 403)

    request_id = str(data.get('request_id') or '').strip()
    entitlement_id = str(data.get('entitlement_id') or '').strip()
    if not request_id and not entitlement_id:
        raise _RedemptionDecisionRefused("Missing redemption request.", 400)

    query = PendingAction.query.filter(
        PendingAction.class_id == active_class_id,
        PendingAction.authoritative_feat == "FEAT-STOR-002",
        PendingAction.payload["outcome"].as_string().is_(None),
        # A redemption request carries no kind; an immediate-use reminder
        # (DOM-STORE-001 §VIII.E.3) is resolved only by marking it complete.
        PendingAction.payload["kind"].as_string().is_(None),
    )
    if request_id:
        query = query.filter(PendingAction.pending_action_id == request_id)
    if entitlement_id:
        query = query.filter(PendingAction.entitlement_id == entitlement_id)
    pending_action = query.with_for_update().first()
    if pending_action is None:
        raise _RedemptionDecisionRefused(
            "This request has already been decided, or it is not in this class.", 409
        )

    entitlement = latest_entitlement_grant(pending_action.entitlement_id)
    if (
        entitlement is None
        or entitlement.class_id != active_class_id
        or entitlement.target_seat_id != pending_action.seat_id
    ):
        raise _RedemptionDecisionRefused("Invalid item.", 404)

    store_item = store_service.resolve_entitlement_product(entitlement)
    if not store_item or store_item.class_id != active_class_id:
        raise _RedemptionDecisionRefused("Invalid item.", 404)
    return ctx, pending_action, entitlement, store_item


@api_bp.route('/approve-redemption', methods=['POST'])
@admin_required
def approve_redemption():
    """Approve a waiting redemption request. The decision is final.

    Scope checks run here as reads; the mutation is FEAT-STOR-002, whose shell
    owns the transaction. A refusal from the FEAT leaves the request waiting.
    """
    data = request.get_json(silent=True) or {}
    try:
        ctx, pending_action, entitlement, store_item = _load_redemption_for_decision(data)
    except _RedemptionDecisionRefused as refused:
        return jsonify({"status": "error", "message": refused.message}), refused.status

    try:
        from app.feats.entitlement_lifecycle_feat import execute_approve_redemption
        execute_approve_redemption(
            entitlement=entitlement,
            store_item=store_item,
            pending_action=pending_action,
            ctx=ctx,
            idempotency_key=f"feat:stor:appr_req:{pending_action.pending_action_id}",
        )
    except (SQLAlchemyError, ValueError) as e:
        current_app.logger.info(
            "Redemption approval failed for request %s: %s",
            pending_action.pending_action_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": str(e) if isinstance(e, ValueError) else "Redemption request could not be approved.",
        }), 409

    return jsonify({"status": "success", "message": f"Approved {store_item.name}."})


@api_bp.route('/reject-redemption', methods=['POST'])
@admin_required
def reject_redemption():
    """Deny a waiting redemption request. The decision is final.

    A redemption request is a use: denying it ends the entitlement with no
    refund and no void, by the teacher's own classroom norms (FEAT-STOR-002).
    """
    data = request.get_json(silent=True) or {}
    try:
        ctx, pending_action, entitlement, store_item = _load_redemption_for_decision(data)
    except _RedemptionDecisionRefused as refused:
        return jsonify({"status": "error", "message": refused.message}), refused.status

    note = str(data.get('note') or '').strip()
    try:
        from app.feats.entitlement_lifecycle_feat import execute_deny_redemption
        execute_deny_redemption(
            entitlement=entitlement,
            store_item=store_item,
            pending_action=pending_action,
            ctx=ctx,
            decision_note=note or None,
            idempotency_key=f"feat:stor:deny_req:{pending_action.pending_action_id}",
        )
    except (SQLAlchemyError, ValueError) as e:
        current_app.logger.info(
            "Redemption denial failed for request %s: %s",
            pending_action.pending_action_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": str(e) if isinstance(e, ValueError) else "Redemption request could not be denied.",
        }), 409

    return jsonify({"status": "success", "message": f"Denied {store_item.name}."})


@api_bp.route('/return-redemption', methods=['POST'])
@admin_required
def return_redemption():
    """Return a waiting redemption request: the student keeps the item unused.

    The request is closed for good; the item is not, so the student may ask
    again later (FEAT-STOR-002).
    """
    data = request.get_json(silent=True) or {}
    try:
        ctx, pending_action, entitlement, store_item = _load_redemption_for_decision(data)
    except _RedemptionDecisionRefused as refused:
        return jsonify({"status": "error", "message": refused.message}), refused.status

    try:
        from app.feats.entitlement_lifecycle_feat import execute_return_redemption
        execute_return_redemption(
            entitlement=entitlement,
            pending_action=pending_action,
            ctx=ctx,
            idempotency_key=f"feat:stor:return_req:{pending_action.pending_action_id}",
        )
    except (SQLAlchemyError, ValueError) as e:
        current_app.logger.info(
            "Redemption return failed for request %s: %s",
            pending_action.pending_action_id,
            e,
        )
        return jsonify({
            "status": "error",
            "message": str(e) if isinstance(e, ValueError) else "Redemption request could not be returned.",
        }), 409

    return jsonify({
        "status": "success",
        "message": f"Returned {store_item.name}. The student still has it and can ask again.",
    })


@api_bp.route('/complete-immediate-use', methods=['POST'])
@admin_required
def complete_immediate_use():
    """Mark an immediate-use purchase complete (DOM-STORE-001 §VIII.E.3)."""
    data = request.get_json(silent=True) or {}
    ctx = g.canonical_context
    try:
        active_class_id = ctx.class_id
    except AttributeError:
        active_class_id = None
    if not active_class_id or not _admin_has_class_scope(ctx, active_class_id):
        return jsonify({"status": "error", "message": "Select a class first."}), 403

    request_id = str(data.get('request_id') or '').strip()
    if not request_id:
        return jsonify({"status": "error", "message": "Missing purchase."}), 400
    pending_action = (
        PendingAction.query.filter(
            PendingAction.class_id == active_class_id,
            PendingAction.pending_action_id == request_id,
            PendingAction.authoritative_feat == "FEAT-STOR-002",
            PendingAction.payload["kind"].as_string() == "immediate_use_acknowledgement",
        )
        .with_for_update()
        .first()
    )
    if pending_action is None:
        return jsonify({
            "status": "error",
            "message": "This purchase was already marked complete, or it is not in this class.",
        }), 409

    try:
        from app.feats.entitlement_lifecycle_feat import execute_complete_immediate_use
        execute_complete_immediate_use(
            pending_action=pending_action,
            ctx=ctx,
            idempotency_key=f"feat:stor:complete_imm:{request_id}",
        )
    except (SQLAlchemyError, ValueError) as e:
        current_app.logger.info("Immediate-use completion failed for %s: %s", request_id, e)
        return jsonify({"status": "error", "message": "This purchase could not be marked complete."}), 409

    return jsonify({"status": "success", "message": "Marked complete."})


# -------------------- HALL PASS API --------------------

@api_bp.route('/hall-pass/request', methods=['POST'])
@login_required
def request_hall_pass():
    """Submit a hall-pass request for teacher approval (a ``pending_actions`` row)."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    if not context or not student or student.class_id != context.class_id:
        return jsonify({"status": "error", "message": "Student class context is required."}), 403

    data = request.get_json(silent=True) or {}
    destination = (data.get("destination") or data.get("reason") or "Bathroom").strip()
    if not destination:
        return jsonify({"status": "error", "message": "Destination is required."}), 400

    # FEAT-IDEN-002 "Credential boundary" is normative: hall-pass use is the
    # explicit exception to the entitlement rule and takes the PIN. This route
    # is the only lawful way to exercise a pass, and it previously took none —
    # anyone with the session could spend a pass off the seat's balance and put
    # the student on the attendance timeline as out of the room.
    student_user = db.session.get(User, context.user_id)
    pin = (data.get("pin") or "").strip()
    if not student_user or not verify_password(pin, student_user.pin_hash or ''):
        return jsonify({"status": "error", "message": "Incorrect PIN."}), 403

    if get_hall_pass_balance(student.id, context.class_id) <= 0:
        return jsonify({"status": "error", "message": "No hall passes available."}), 403

    latest_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=student.id,
            class_id=context.class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    if not latest_event or latest_event.status != "active":
        return jsonify({"status": "error", "message": "Start work before requesting a hall pass."}), 400

    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="current_time",
    )
    # A pending_actions row (DOM-STORE-001 §VII.B, §IX), written by the
    # submitting FEAT. It replaces any earlier pending request from this seat.
    try:
        pending_request = submit_hall_pass_request(
            ctx=context,
            destination=destination,
            requested_at_utc=evaluation.canonical_now_utc,
            idempotency_key=f"hall_pass_request:{context.class_id}:{student.id}:{secrets.token_urlsafe(12)}",
        )
    except ValueError:
        return jsonify({"status": "error", "message": "No hall passes available."}), 403
    return jsonify({
        "status": "success",
        "message": "Hall pass request sent.",
        "hall_pass": {
            "id": pending_request.request_id,
            "status": "pending",
            "reason": pending_request.destination,
        },
    })


@api_bp.route('/hall-pass/request/<request_id>/cancel', methods=['POST'])
@login_required
def cancel_pending_hall_pass_request(request_id):
    """Cancel the current student's own pending hall-pass request."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    if not context or not student or student.class_id != context.class_id:
        return jsonify({"status": "error", "message": "Pending request not found."}), 404
    try:
        # Only the requesting seat's own row, in its own class, can be taken.
        cancel_hall_pass_request(
            ctx=context,
            request_id=request_id,
            idempotency_key=f"hall_pass_cancel:{context.class_id}:{request_id}",
        )
    except HallPassRequestNotFound:
        return jsonify({"status": "error", "message": "Pending request not found."}), 404
    return jsonify({"status": "success", "message": "Hall pass request cancelled."})


@api_bp.route('/hall-pass/request/<request_id>/<string:action>', methods=['POST'])
@admin_required
def handle_pending_hall_pass_request(request_id, action):
    """Approve or reject a pending hall-pass request (a ``pending_actions`` row)."""
    ctx = g.canonical_context
    if action == "reject":
        try:
            reject_hall_pass_request(
                ctx=ctx,
                request_id=request_id,
                idempotency_key=f"hall_pass_reject:{ctx.class_id}:{request_id}",
            )
        except HallPassRequestNotFound:
            return jsonify({"status": "error", "message": "Pending request not found."}), 404
        return jsonify({"status": "success", "message": "Hall pass request rejected."})

    if action != "approve":
        return jsonify({"status": "error", "message": "Unsupported hall pass action."}), 400

    idempotency_key = f"hall_pass_approve:{ctx.class_id}:{request_id}"
    try:
        # One FEAT-PROD-002 transaction locks and deletes the pending row and
        # records the pass. A concurrent approval of the same request waits on
        # the row lock and then finds nothing, so it cannot record a second
        # pass. The idempotency key is not what prevents that: nothing refuses a
        # second write carrying the same key. A failed approval rolls back,
        # leaving the request pending.
        #
        # No route-level FEATContext: the FEAT opens its own, and nesting is
        # forbidden (live-test finding 29).
        approve_hall_pass_request(
            ctx=ctx,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        return jsonify({"status": "success", "message": "Hall pass issued."})
    except HallPassRequestNotFound:
        return jsonify({"status": "error", "message": "Pending request not found."}), 404
    except ValueError as exc:
        _log_api_client_error("handle_pending_hall_pass_request", exc, extra=f"request_id={request_id}")
        return jsonify({"status": "error", "message": "Hall pass request cannot be approved."}), 400
    except FEATContextError as exc:
        # A constitutional violation is a server fault, not a client one, and it
        # must be named as such rather than escaping as an unhandled 500.
        current_app.logger.error(
            "Hall pass approval violated FEAT context rules: %s", exc, exc_info=True
        )
        return jsonify({"status": "error", "message": "Hall pass could not be issued."}), 500
    except SQLAlchemyError as exc:
        current_app.logger.error("Hall pass approval failed: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
def handle_hall_pass_action(pass_id, action):
    log_entry = db.get_or_404(HallPassLog, pass_id)
    ctx = g.canonical_context
    if not log_entry.class_id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404
    if ctx.class_id != log_entry.class_id:
        return jsonify({"status": "error", "message": "Pass not found."}), 404

    try:
        if action == 'leave':
            latest_event = (
                AttendanceSession.query.filter_by(
                    target_seat_id=log_entry.requested_by_seat_id,
                    class_id=log_entry.class_id,
                )
                .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
                .first()
            )
            if latest_event and latest_event.status == "inactive" and latest_event.reason_code == AttendanceReasonCode.HALL_PASS.value:
                return jsonify({"status": "success", "message": "Student is already marked out."})
            record_attendance_session(
                ctx=ctx,
                target_seat_id=log_entry.requested_by_seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="inactive",
                reason=log_entry.destination,
                reason_code=AttendanceReasonCode.HALL_PASS,
                hall_pass_id=log_entry.hall_pass_id,
                idempotency_key=f"hall_pass_leave:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
            )
            return jsonify({"status": "success", "message": "Student has left the class."})
        if action == 'return':
            latest_event = (
                AttendanceSession.query.filter_by(
                    target_seat_id=log_entry.requested_by_seat_id,
                    class_id=log_entry.class_id,
                )
                .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
                .first()
            )
            if latest_event and latest_event.status == "active":
                return jsonify({"status": "success", "message": "Student is already marked returned."})
            record_attendance_session(
                ctx=ctx,
                target_seat_id=log_entry.requested_by_seat_id,
                actor_seat_id=ctx.seat_id,
                mechanism="teacher",
                status="active",
                reason="Return from hall pass",
                hall_pass_id=log_entry.hall_pass_id,
                idempotency_key=f"hall_pass_return:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
            )
            return jsonify({"status": "success", "message": "Student has returned."})
    except ValueError as exc:
        _log_api_client_error("handle_hall_pass_action", exc, extra=f"action={action}")
        safe_messages = {
            "leave": "Hall pass cannot be checked out in its current state.",
            "return": "Hall pass cannot be checked in in its current state.",
        }
        return jsonify({"status": "error", "message": safe_messages.get(action, "Invalid action.")}), 400

    return jsonify({"status": "error", "message": "Invalid action."}), 400



def _enforce_hall_pass_student_context(student, log_entry):
    """
    Enforce active student class context for hall-pass state mutations.

    Class context is required and must match the pass class/join scope.
    """
    context = resolve_canonical_context()
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({
            "status": "error",
            "message": "This pass belongs to a different class context. Switch class and retry.",
        }), 403

    if current_class_id and log_entry.class_id and log_entry.class_id != current_class_id:
        return jsonify({
            "status": "error",
            "message": "This pass belongs to a different class context. Switch class and retry.",
        }), 403

    return None




@api_bp.route('/hall-pass/checkout', methods=['POST'])
@login_required
def checkout_hall_pass():
    """Append an inactive attendance row for an issued hall pass."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKOUT_DEBUG: seat_id=%s pass_id=%s pass_requested_by_seat_id=%s pass_class_id=%s session_class_id=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.requested_by_seat_id,
        log_entry.class_id,
        getattr(getattr(g, "canonical_context", None), "class_id", None),
    )
    
    if not student or log_entry.requested_by_seat_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error

    try:
        latest_event = (
            AttendanceSession.query.filter_by(
                target_seat_id=student.id,
                class_id=log_entry.class_id,
            )
            .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
            .first()
        )
        if latest_event and latest_event.status == "inactive" and latest_event.reason_code == AttendanceReasonCode.HALL_PASS.value:
            return jsonify({
                "status": "success",
                "message": "You are already checked out.",
                "destination": log_entry.destination,
            })

        record_attendance_session(
            ctx=context,
            target_seat_id=student.id,
            actor_seat_id=context.seat_id,
            mechanism="self",
            status="inactive",
            reason=log_entry.destination,
            reason_code=AttendanceReasonCode.HALL_PASS,
            hall_pass_id=log_entry.hall_pass_id,
            idempotency_key=f"student_hall_pass_checkout:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
        )
        return jsonify({
            "status": "success",
            "message": "Hall pass checked out.",
            "destination": log_entry.destination,
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKOUT_IDENTITY_MISSING: seat_id=%s pass_id=%s message=%s",
            getattr(student, "id", None),
            pass_id,
            str(exc),
        )
        return jsonify({"status": "error", "message": "Student session is missing required class context."}), 401
    except ValueError as exc:
        _log_api_client_error("checkout_hall_pass", exc, extra=f"pass_id={pass_id}")
        return jsonify({
            "status": "error",
            "message": _safe_exception_prefix_message(
                exc,
                "Hall pass cannot be checked out in its current state.",
                allowed_prefixes={"Pass is not approved."},
            ),
        }), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkout failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500


@api_bp.route('/hall-pass/checkin', methods=['POST'])
@login_required
def checkin_hall_pass():
    """Append an active attendance row when the student returns from hall pass."""
    context = getattr(g, "canonical_context", None)
    student = db.session.get(Seat, context.seat_id) if context else None
    data = request.get_json()
    pass_id = data.get('pass_id')
    
    if not pass_id:
        return jsonify({"status": "error", "message": "Pass ID is required."}), 400
    
    log_entry = db.get_or_404(HallPassLog, pass_id)
    current_app.logger.info(
        "HALL_PASS_CHECKIN_DEBUG: seat_id=%s pass_id=%s pass_requested_by_seat_id=%s pass_class_id=%s session_class_id=%s",
        getattr(student, "id", None),
        pass_id,
        log_entry.requested_by_seat_id,
        log_entry.class_id,
        getattr(getattr(g, "canonical_context", None), "class_id", None),
    )
    
    if not student or log_entry.requested_by_seat_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized."}), 403
    context_error = _enforce_hall_pass_student_context(student, log_entry)
    if context_error:
        return context_error
    
    try:
        # Scoped to THIS pass's own attendance sequence, not merely "is the
        # seat's latest event active" -- an unrelated active row (an ordinary
        # clock-in, say) sitting more recently than this pass's departure must
        # not be read as "already checked in from this pass" (that read made
        # checkin silently no-op and leave the pass stuck at "left" forever).
        lifecycle = resolve_hall_pass_lifecycle_status(
            class_id=log_entry.class_id,
            seat_id=student.id,
            hall_pass_id=log_entry.hall_pass_id,
        )
        if lifecycle.status == HALL_PASS_STATUS_RETURNED:
            return jsonify({"status": "success", "message": "You are already checked in."})

        record_attendance_session(
            ctx=context,
            target_seat_id=student.id,
            actor_seat_id=context.seat_id,
            mechanism="self",
            status="active",
            reason="Return from hall pass",
            hall_pass_id=log_entry.hall_pass_id,
            idempotency_key=f"student_hall_pass_checkin:{log_entry.class_id}:{log_entry.id}:{secrets.token_hex(12)}",
        )
        return jsonify({
            "status": "success",
            "message": "Hall pass checked in.",
        })
    except PermissionError as exc:
        current_app.logger.error(
            "HALL_PASS_CHECKIN_IDENTITY_MISSING: seat_id=%s pass_id=%s message=%s",
            getattr(student, "id", None),
            pass_id,
            str(exc),
        )
        return jsonify({"status": "error", "message": "Student session is missing required class context."}), 401
    except ValueError as exc:
        _log_api_client_error("checkin_hall_pass", exc, extra=f"pass_id={pass_id}")
        return jsonify({
            "status": "error",
            "message": _safe_exception_prefix_message(
                exc,
                "Hall pass cannot be checked in in its current state.",
                allowed_prefixes={"You are not currently checked out."},
            ),
        }), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Hall pass checkin failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Database error."}), 500




@api_bp.route('/hall-pass/settings', methods=['GET'])
@admin_required
def hall_pass_settings():
    """Get hall pass queue settings (admin only)"""
    context = getattr(g, "canonical_context", None)
    class_id = context.class_id if context else None
    if not class_id:
        return jsonify({"status": "error", "message": "Class context is required"}), 400

    settings = get_hall_pass_settings(class_id)

    return jsonify({
        "status": "success",
        "settings": {
            "max_queue_limit": settings.max_queue_limit if settings else 10,
            "pass_type_payload": settings.get_pass_types() if settings else HallPassSettings.get_default_pass_types()
        }
    })


@api_bp.route('/hall-pass/settings', methods=['POST'])
@admin_required
def update_hall_pass_settings():
    """Update hall pass queue settings (admin only)."""
    context = getattr(g, "canonical_context", None)
    class_id = context.class_id if context else None
    if not class_id:
        return jsonify({"status": "error", "message": "Class context is required"}), 400

    data = request.get_json() or {}
    if (not isinstance(data, dict) or set(data) != {"max_queue_limit"}
            or type(data["max_queue_limit"]) is not int
            or not 1 <= data["max_queue_limit"] <= 50):
        return jsonify({"status": "error", "message": "Out Limit must be a whole number between 1 and 50."}), 400
    try:
        settings = feat_update_hall_pass_queue_settings(
            user_id=context.user_id if context else None,
            class_id=class_id,
            max_queue_limit=data["max_queue_limit"],
            updated_at=utc_now(),
            correlation_id=f"corr_settings_queue_{uuid.uuid4().hex}",
            idempotency_key=f"feat:settings:hall-pass-queue:{context.user_id}:{class_id}:{uuid.uuid4().hex}",
        )
    except ValueError as exc:
        _log_api_client_error("update_hall_pass_settings", exc, extra=f"class_id={class_id}")
        return jsonify({"status": "error", "message": "Hall pass settings are invalid."}), 400

    return jsonify({
        "status": "success",
        "message": "Settings updated successfully",
        "settings": {
            "max_queue_limit": settings.max_queue_limit,
            "pass_type_payload": settings.get_pass_types(),
            "effective_queue_limit": settings.effective_queue_limit,
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

        # Get filter parameters (no client-supplied period per C2 canonical scoping)
        pass_type = request.args.get('type', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        context = getattr(g, "canonical_context", None)
        current_class_id = (getattr(context, "class_id", None) or "").strip()
        if not current_class_id:
            return jsonify({"status": "error", "message": "Class context required"}), 400

        # Enforce single-class context for admin history views (v2 canonical scoping).
        query = HallPassLog.query.filter(HallPassLog.class_id == current_class_id)

        # Apply filters

        if pass_type:
            query = query.filter(HallPassLog.destination == pass_type)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=start_day,
                )
                query = query.filter(HallPassLog.timestamp >= start_bounds.boundary_start_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                end_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=end_day,
                )
                query = query.filter(HallPassLog.timestamp < end_bounds.boundary_end_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        # Order by most recent first
        query = query.order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        from app.utils.temporal_display import format_timestamp as _fmt_display, resolve_display_timezone as _resolve_tz
        _display_tz = _resolve_tz(context)

        def format_timestamp(dt):
            if not dt:
                return None
            return _fmt_display(dt, _display_tz)

        # Format records for response
        records_data = []
        for record in records:
            seat = record.requested_by_seat
            profile = IdentityProfile.query.filter_by(
                seat_id=record.requested_by_seat_id,
                class_id=record.class_id,
            ).first()
            student_name = (
                " ".join(part for part in [
                    getattr(profile, "first_name", None),
                    getattr(profile, "last_name", None),
                ] if part).strip()
                or "Unknown"
            )
            class_row = get_class_economy(record.class_id)
            # Unbounded by day: a history record has no single "today" to scope
            # to, unlike the two other callers of this resolver.
            lifecycle = resolve_hall_pass_lifecycle_status(
                class_id=record.class_id,
                seat_id=record.requested_by_seat_id,
                hall_pass_id=record.hall_pass_id,
            )
            left_row = lifecycle.left_row
            return_row = lifecycle.return_row
            status = lifecycle.status
            records_data.append({
                "id": record.id,
                "student_name": student_name,
                "period": class_row.section if class_row else "",
                "reason": record.destination,
                "status": status,
                "request_time": format_timestamp(record.timestamp),
                "decision_time": None,
                "left_time": format_timestamp(left_row.timestamp if left_row else None),
                "return_time": format_timestamp(return_row.timestamp if return_row else None),
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
    _ = get_current_user()
    context = getattr(g, "canonical_context", None)
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400

    scope = _get_hall_pass_settings_scope(context.user_id, current_class_id)
    if not scope:
        return jsonify({"status": "error", "message": "Class scope not found"}), 404

    feature_scope = resolve_feature_class_for_class(scope["class_id"], 'hall_pass')
    if feature_scope and not feature_scope["enabled"]:
        return jsonify({"status": "error", "message": "Hall pass is disabled for this class"}), 403

    settings = get_hall_pass_settings(scope["class_id"])

    if not settings:
        # Return default configuration
        return jsonify({
            "status": "success",
            "hall_pass_enabled": True,
            "pass_type_payload": HallPassSettings.get_default_pass_types()
        })

    # Return configured pass types with fallback to defaults
    return jsonify({
        "status": "success",
        "hall_pass_enabled": True,
        "pass_type_payload": settings.get_pass_types()
    })


@api_bp.route('/hall-pass/setup', methods=['POST'])
@admin_required
def save_hall_pass_setup():
    """Save teacher's hall pass configuration"""
    user_id = g.canonical_context.user_id
    data = request.get_json() or {}
    context = getattr(g, "canonical_context", None)
    current_class_id = context.class_id if context else None
    if not current_class_id:
        return jsonify({"status": "error", "message": "Active class context is required"}), 400

    pass_types = data.get('pass_type_payload', [])
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
        if set(pt) != {'pass_name', 'max_queue', 'consume_pass'}:
            return jsonify({"status": "error", "message": "Each pass type must contain pass_name, max_queue, and consume_pass"}), 400
        if not isinstance(pt['pass_name'], str) or not pt['pass_name'].strip():
            return jsonify({"status": "error", "message": "Pass type name cannot be empty"}), 400

        # Validate enabled (defaults to True if not provided)
        if (
            not isinstance(pt['consume_pass'], bool)
            or not isinstance(pt['max_queue'], int)
            or isinstance(pt['max_queue'], bool)
            or pt['max_queue'] < 0
        ):
            return jsonify({"status": "error", "message": "Invalid pass type limits"}), 400

    try:
        scope = _get_hall_pass_settings_scope(context.user_id, current_class_id)
        if not scope:
            return jsonify({"status": "error", "message": "Class scope not found"}), 404
        feature_scope = resolve_feature_class_for_class(scope["class_id"], 'hall_pass')
        if feature_scope and not feature_scope["enabled"]:
            return jsonify({"status": "error", "message": "Hall pass is disabled for this class"}), 403

        settings = feat_save_hall_pass_setup_config(
            user_id=user_id,
            class_id=scope["class_id"],
            hall_pass_enabled=hall_pass_enabled,
            pass_type_payload=pass_types,
            max_queue_limit=int(data.get('max_queue_limit', 10)),
            updated_at=utc_now(),
            correlation_id=f"corr_settings_setup_{uuid.uuid4().hex}",
            idempotency_key=f"feat:settings:hall-pass-setup:{user_id}:{scope['class_id']}:{uuid.uuid4().hex}",
        )

        return jsonify({
            "status": "success",
            "message": "Hall pass configuration saved successfully",
            "hall_pass_enabled": hall_pass_enabled,
            "pass_type_payload": settings.get_pass_types(),
            "policy_uuid": settings.policy_uuid,
            "effective_queue_limit": settings.effective_queue_limit,
            "queue_limit_notice": (
                f"Per-pass limits reduce effective queue capacity to {settings.effective_queue_limit}."
                if settings.effective_queue_limit < settings.max_queue_limit else None
            ),
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving hall pass setup: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to save configuration"}), 500


@api_bp.route('/hall-pass/verify-token/rotate', methods=['POST'])
@admin_required
def rotate_hall_pass_verify_token():
    """
    Rotate the teacher's hall pass public verification token.

    Generates a new 256-bit random token and overwrites the old one.
    The old token is immediately invalid. Use after a lost pass, suspicious
    traffic, or student screenshot concern.
    """
    user_id = g.canonical_context.user_id

    try:
        token = feat_rotate_teacher_hall_pass_verify_token(
            user_id=user_id,
            correlation_id=f"corr_settings_token_{uuid.uuid4().hex}",
            idempotency_key=f"feat:settings:hall-pass-token:{user_id}:{uuid.uuid4().hex}",
        )
    except LookupError as exc:
        _log_api_client_error("rotate_hall_pass_verify_token", exc, extra=f"user_id={user_id}")
        return jsonify({"status": "error", "message": "Hall pass verification settings were not found."}), 404
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.error("Failed to rotate hall pass verify token", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to rotate token."}), 500

    return jsonify({
        "status": "success",
        "token": token
    })


@api_bp.route('/hall-pass/available-types', methods=['GET'])
@login_required
def get_available_hall_pass_types():
    """Get available pass types for the current class.

    Authority: class_id is canonical and required.
    """
    requested_class_id = (request.args.get('class_id') or '').strip() or None

    resolved_class_id = None
    context = resolve_canonical_context()

    if context:
        # Session class context is authoritative for logged-in student/admin flows.
        resolved_class_id = context.class_id
        if requested_class_id and requested_class_id != resolved_class_id:
            return jsonify({"status": "error", "message": "class_id is out of scope for this session"}), 403
    elif requested_class_id:
        class_row = get_class_economy(requested_class_id)
        if class_row:
            resolved_class_id = class_row.class_id

    if not resolved_class_id:
        return jsonify({
            "status": "error",
            "message": "class_id is required"
        }), 400

    settings = None
    if resolved_class_id:
        settings = get_hall_pass_settings(resolved_class_id)
    feature_scope = resolve_feature_class_for_class(resolved_class_id, 'hall_pass')
    if not feature_scope or not feature_scope.get("enabled"):
        return jsonify({
            "status": "error",
            "message": "Hall pass is disabled for this class",
        }), 403

    if not settings:
        # Return defaults if not configured
        return jsonify({
            "status": "success",
            "pass_type_payload": HallPassSettings.get_default_pass_types()
        })

    # Return just the names for enabled pass types
    pass_types = settings.get_pass_types()
    enabled_pass_types = [
        {"pass_name": pt["pass_name"], "max_queue": pt["max_queue"], "consume_pass": pt["consume_pass"]}
        for pt in pass_types
    ]

    return jsonify({
        "status": "success",
        "pass_type_payload": enabled_pass_types
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
        status = request.args.get('status', '').strip()  # 'active' or 'inactive'
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        context = getattr(g, "canonical_context", None)
        current_class_id = (getattr(context, "class_id", None) or "").strip()
        if not current_class_id:
            return jsonify({"status": "error", "message": "Class context required"}), 400

        # Claimed student seats only. Unclaim preserves a seat's attendance
        # facts, but an unclaimed seat is no economic participant and appears in
        # no teacher-facing log or history (DOM-IDEN-002 §VIII).
        query = (
            AttendanceSession.query
            .join(Seat, AttendanceSession.target_seat_id == Seat.id)
            .filter(
                AttendanceSession.class_id == current_class_id,
                Seat.role == "student",
                Seat.claimed_at.isnot(None),
            )
        )

        if status:
            if status not in {'active', 'inactive'}:
                return jsonify({"status": "error", "message": "Invalid status filter"}), 400
            query = query.filter(AttendanceSession.status == status)

        if start_date:
            try:
                start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=start_day,
                )
                query = query.filter(AttendanceSession.timestamp >= start_bounds.boundary_start_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid start date format"}), 400

        if end_date:
            try:
                end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
                end_bounds = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=context,
                    primitive="evaluation_day_boundaries",
                    evaluation_date=end_day,
                )
                query = query.filter(AttendanceSession.timestamp < end_bounds.boundary_end_utc)
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid end date format"}), 400

        query = query.order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        records = query.offset(offset).limit(page_size).all()

        seat_ids = [r.target_seat_id for r in records if r.target_seat_id]
        seats = {}
        if seat_ids:
            seat_rows = (
                db.session.query(
                    Seat.id,
                    Seat.class_id,
                    ClassEconomy.section,
                    ClassEconomy.display_name,
                    ClassEconomy.join_code,
                    IdentityProfile.first_name,
                    IdentityProfile.last_name,
                )
                .outerjoin(IdentityProfile, IdentityProfile.seat_id == Seat.id)
                .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                .filter(Seat.id.in_(seat_ids))
                .all()
            )
        else:
            seat_rows = []

        for row in seat_rows:
            student_name = " ".join(part for part in [row.first_name, row.last_name] if part).strip() or "Unknown"
            seats[row.id] = {
                "name": student_name,
                "class_id": row.class_id,
                "period": row.section or "",
                "class_label": row.display_name or row.join_code or row.class_id,
            }

        records_data = []
        for record in records:
            seat_info = seats.get(record.target_seat_id, {
                'name': 'Unknown',
                'class_id': record.class_id,
                'period': '',
                'class_label': record.class_id,
            })
            student_class_id = seat_info['class_id']
            student_class_label = seat_info['class_label'] or student_class_id or 'Unknown'

            timestamp_str = None
            formatted_ts = None
            if record.timestamp:
                timestamp_str = ensure_utc(record.timestamp).isoformat().replace('+00:00', 'Z')
                from app.utils.temporal_display import format_timestamp as _format_ts, resolve_display_timezone as _resolve_tz
                formatted_ts = _format_ts(record.timestamp, _resolve_tz(context))

            records_data.append({
                "id": record.id,
                "seat_id": record.target_seat_id,
                "student_name": seat_info['name'],
                "student_block": student_class_label,
                "student_class_label": student_class_label,
                "period": seat_info['period'],
                "status": record.status,
                "reason": record.reason_code,
                "timestamp": timestamp_str,
                "formatted_timestamp": formatted_ts,
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
    """Student-initiated attendance tap (FEAT-PROD-001).

    The FEAT envelope belongs to ``record_attendance_session``, which carries
    its own ``@requires_feat_context("FEAT-PROD-001")``. This route must open
    none: a route-level decorator here makes that call nest inside it and raise
    ``FEATContextError``. The route's own work is PIN verification and
    resolution — reads only.
    """
    data = request.get_json(silent=True) or {}
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    current_app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    context = getattr(g, "canonical_context", None)
    student_seat = db.session.get(Seat, context.seat_id) if context else None
    student_user = db.session.get(User, context.user_id) if context else None

    if not student_seat or not student_user:
        current_app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not verify_password(pin, student_user.pin_hash or ''):
        current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student_user.id}")
        return jsonify({"error": "Invalid PIN"}), 403

    context = resolve_canonical_context()
    class_id = context.class_id if context else None
    if not class_id:
        current_app.logger.warning("ATTENDANCE ERROR: Missing class_id context for user_id=%s", student_user.id)
        return jsonify({"error": "Unable to resolve class context for this period."}), 400

    action = data.get("action")

    current_app.logger.info("TAP DEBUG: class_id=%s action=%s", class_id, action)

    # Support both old and new action names
    action_map = {
        "tap_in": "start_work",
        "tap_out": "stop_work",
        "start_work": "start_work",
        "stop_work": "stop_work"
    }

    if action not in action_map:
        current_app.logger.warning("TAP ERROR: Invalid action: action=%s", action)
        return jsonify({"error": "Invalid action"}), 400

    normalized_action = action_map[action]

    seat_id = student_seat.id if student_seat and student_seat.class_id == class_id else None
    if not seat_id:
        return jsonify({"error": "No seat assigned in this class."}), 403

    latest_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    currently_active = bool(latest_event and latest_event.status == "active")

    if normalized_action == "start_work" and currently_active:
        return jsonify({
            "status": "ok", "active": True, "done": False, "duration": 0,
            "duration_today": calculate_worked_attendance_seconds_today(
                seat_id, class_id, ctx=context
            ),
        })

    if normalized_action == "stop_work" and not currently_active:
        return jsonify({
            "status": "ok", "active": False,
            "done": is_done_for_day(seat_id, class_id, ctx=context),
            "duration": 0,
            "duration_today": calculate_worked_attendance_seconds_today(
                seat_id, class_id, ctx=context
            ),
        })

    reason = data.get("reason") if normalized_action == "stop_work" else None
    reason_code = None
    if normalized_action == "stop_work":
        if not reason:
            return jsonify({"error": "A reason is required."}), 400
        if reason.lower() in ['done', 'done for the day']:
            reason_code = AttendanceReasonCode.DONE_FOR_DAY
        else:
            return jsonify({"error": "Hall-pass requests are handled by the hall-pass command surface."}), 400

    try:
        status = "active" if normalized_action == "start_work" else "inactive"
        record_attendance_session(
            ctx=context,
            status=status,
            reason=reason,
            reason_code=reason_code,
            idempotency_key=f"prod_attendance:{class_id}:{seat_id}:{normalized_action}:{secrets.token_hex(12)}",
        )
        current_app.logger.info("TAP success - seat %s class_id=%s action=%s", seat_id, class_id, action)
    except ValueError as e:
        db.session.rollback()
        current_app.logger.warning(
            "TAP rejected for seat %s class_id=%s action=%s: %s",
            seat_id,
            class_id,
            action,
            e,
        )
        return jsonify({"error": "Unable to record the attendance request."}), 409
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"TAP failed for seat {seat_id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    refreshed_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    is_active = bool(refreshed_event and refreshed_event.status == "active")
    duration = calculate_unpaid_attendance_seconds(seat_id, class_id, ctx=context)

    # Closed sessions at the setting in force when each closed, the open one as
    # if it closed now (DOM-PROD-001 §XV.3).
    projected_pay = estimate_unpaid_amount(seat_id, class_id, ctx=context)
    duration_today = calculate_worked_attendance_seconds_today(
        seat_id, class_id, ctx=context
    )

    return jsonify({
        "status": "ok",
        "active": is_active,
        "done": is_done_for_day(seat_id, class_id, ctx=context),
        "duration": duration,
        "duration_today": duration_today,
        "projected_pay": float(projected_pay)
    })


# The dashboard polls this every 10 seconds per visible tab: 6 a minute, 12 for
# two tabs side by side, plus one refresh after each hall-pass action. The
# limit is per seat, not per address (see student_status_seat_limit_key), and
# sits below @login_required so it keys on the context that decorator
# validated. It replaces the address-keyed defaults, which one student's
# poller alone exhausted in about 33 minutes. A caller without a session is
# refused by login_required before this limit is consulted.
@api_bp.route('/student-status', methods=['GET'])
@login_required
@limiter.limit("30 per minute", key_func=student_status_seat_limit_key)
def student_status():
    from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

    # Tracked debt: this re-resolves the context login_required already
    # validated and attached to g (DOM-IDEN-006 §IX, §X).
    context = resolve_canonical_context()
    if not context:
        return jsonify({"status": "error", "message": "No class selected."}), 400

    student = db.session.get(Seat, context.seat_id)

    class_id = context.class_id
    if not class_id:
        return jsonify({"status": "error", "message": "Class context unavailable."}), 400

    attendance_state = get_class_attendance_status(student, class_id=class_id, ctx=context)
    if 'projected_pay' in attendance_state and attendance_state['projected_pay'] is not None:
        attendance_state['projected_pay'] = float(attendance_state['projected_pay'])

    return jsonify({
        "status": "ok",
        "attendance_state": attendance_state
    })


# -------------------- UTILITY API --------------------

    # set-timezone endpoint — REMOVED (SPEC-TIME-001: display timezone is server-supplied from ClassEconomy.class_timezone)
    # view_as_student_status endpoint — REMOVED (prohibited feature)

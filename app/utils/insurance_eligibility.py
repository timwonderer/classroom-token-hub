"""Shared transaction-based insurance eligibility rules."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Set, Tuple

from sqlalchemy import and_

from app.models import InsuranceClaim, StoreItem, StudentItem, Transaction, TransactionStatus
from app.utils.time import ensure_utc


CLAIM_REASON_HARD_DENY_CATEGORY = "HARD_DENY_CATEGORY"
CLAIM_REASON_INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
CLAIM_REASON_DELAY_USE_NOT_USED = "DELAY_USE_NOT_USED"
CLAIM_REASON_DELAY_USE_EXPIRED = "DELAY_USE_EXPIRED"
CLAIM_REASON_NO_ACTIVE_POLICY = "NO_ACTIVE_POLICY"
CLAIM_REASON_PREMIUM_NOT_CURRENT = "PREMIUM_NOT_CURRENT"
CLAIM_REASON_WAITING_PERIOD = "WAITING_PERIOD"
CLAIM_REASON_TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
CLAIM_REASON_ALREADY_CLAIMED = "ALREADY_CLAIMED"
CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS = "REIMBURSEMENT_ALREADY_EXISTS"
CLAIM_REASON_UNCLASSIFIED_TRANSACTION = "UNCLASSIFIED_TRANSACTION"

_PURCHASE_NAME_RE = re.compile(r"^Purchase:\s*(.+?)(?:\s+\(x\d+\)|\s+\[|$)")
_TRANSFER_TYPES = {"withdrawal", "deposit"}
_HARD_DENY_TYPES = {"insurance_premium", "insurance_reimbursement", "interest"}


def _normalize_tx_type(tx_type: Optional[str]) -> str:
    return (tx_type or "").strip().lower()


def _is_internal_transfer(tx: Transaction) -> bool:
    tx_type = _normalize_tx_type(tx.type)
    if tx_type in _TRANSFER_TYPES:
        return True
    desc = (tx.description or "").lower()
    return "transfer to " in desc or "transfer from " in desc


def _is_hard_deny(tx: Transaction) -> bool:
    tx_type = _normalize_tx_type(tx.type)
    if tx_type in _HARD_DENY_TYPES:
        return True
    desc = (tx.description or "").lower()
    if "insurance premium" in desc:
        return True
    return False


def _extract_purchase_item_name(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = _PURCHASE_NAME_RE.match(description.strip())
    if not match:
        return None
    return match.group(1).strip() or None


def _check_delay_use_rule(tx: Transaction, now_utc: datetime) -> Optional[str]:
    if _normalize_tx_type(tx.type) != "purchase":
        return None

    item_name = _extract_purchase_item_name(tx.description)
    if not item_name:
        # Preserve claimability for legacy/manual purchase descriptions.
        return None

    item_query = StoreItem.query.filter(StoreItem.name == item_name)
    if tx.teacher_id:
        item_query = item_query.filter(StoreItem.teacher_id == tx.teacher_id)
    store_item = item_query.order_by(StoreItem.id.desc()).first()
    if not store_item:
        # Store item metadata may have changed; skip delay-use checks when unknown.
        return None
    if store_item.item_type != "delayed":
        return None

    tx_ts = ensure_utc(tx.timestamp)
    tolerance = timedelta(minutes=5)
    item_query = StudentItem.query.filter(
        StudentItem.student_id == tx.student_id,
        StudentItem.store_item_id == store_item.id,
        and_(
            StudentItem.purchase_date >= tx_ts - tolerance,
            StudentItem.purchase_date <= tx_ts + tolerance,
        ),
    )
    if tx.join_code:
        item_query = item_query.filter(StudentItem.join_code == tx.join_code)
    item_row = item_query.order_by(StudentItem.id.desc()).first()
    if not item_row:
        # Fallback for historical rows with slight timestamp drift.
        fallback_query = StudentItem.query.filter(
            StudentItem.student_id == tx.student_id,
            StudentItem.store_item_id == store_item.id,
        )
        if tx.join_code:
            fallback_query = fallback_query.filter(StudentItem.join_code == tx.join_code)
        item_row = fallback_query.order_by(StudentItem.purchase_date.desc()).first()
    if not item_row:
        # Legacy data may not have a matching StudentItem row.
        return None

    used_at = ensure_utc(item_row.redemption_date) if item_row.redemption_date else None
    if not used_at:
        return CLAIM_REASON_DELAY_USE_NOT_USED

    expiry_at = ensure_utc(item_row.expiry_date) if item_row.expiry_date else None
    if expiry_at and used_at > expiry_at:
        return CLAIM_REASON_DELAY_USE_EXPIRED
    if expiry_at and not used_at and now_utc > expiry_at:
        return CLAIM_REASON_DELAY_USE_EXPIRED
    return None


def evaluate_claim_transaction_eligibility(
    tx: Transaction,
    *,
    enrollment,
    now_utc: datetime,
    claim_type: Optional[str] = None,
    claim_time_limit_days: Optional[int] = None,
    policy_id: Optional[int] = None,
    enrollment_join_code: Optional[str] = None,
    claimed_tx_ids: Optional[Set[int]] = None,
    reimbursed_tx_ids: Optional[Set[int]] = None,
) -> Tuple[bool, Optional[str]]:
    """Return (eligible, reason_code) for transaction-based claims."""
    if not tx or tx.id is None:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if claim_type != "transaction_monetary":
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if not enrollment or enrollment.status != "active":
        return False, CLAIM_REASON_NO_ACTIVE_POLICY

    if tx.amount is None or tx.amount >= 0 or tx.is_void:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if tx.status != TransactionStatus.POSTED:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if _normalize_tx_type(tx.type) == "":
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if _is_hard_deny(tx):
        return False, CLAIM_REASON_HARD_DENY_CATEGORY

    if _is_internal_transfer(tx):
        return False, CLAIM_REASON_INTERNAL_TRANSFER

    if not enrollment.payment_current:
        return False, CLAIM_REASON_PREMIUM_NOT_CURRENT

    coverage_start = ensure_utc(enrollment.coverage_start_date) if enrollment.coverage_start_date else None
    if not coverage_start or coverage_start > now_utc:
        return False, CLAIM_REASON_WAITING_PERIOD
    if tx.timestamp and ensure_utc(tx.timestamp) < coverage_start:
        return False, CLAIM_REASON_WAITING_PERIOD

    tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else None
    if tx_ts is None:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION
    effective_time_limit = int(claim_time_limit_days) if claim_time_limit_days is not None else None
    if effective_time_limit is not None and effective_time_limit > 0:
        if (now_utc - tx_ts).days > effective_time_limit:
            return False, CLAIM_REASON_TIME_LIMIT_EXCEEDED

    if enrollment_join_code and tx.join_code != enrollment_join_code:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if claimed_tx_ids is None:
        existing_claim = InsuranceClaim.query.filter(InsuranceClaim.transaction_id == tx.id).first()
        if existing_claim:
            return False, CLAIM_REASON_ALREADY_CLAIMED
    elif tx.id in claimed_tx_ids:
        return False, CLAIM_REASON_ALREADY_CLAIMED

    if reimbursed_tx_ids is None:
        if policy_id is None:
            return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION
        existing_reimbursement = Transaction.query.filter(
            Transaction.type == "insurance_reimbursement",
            Transaction.original_transaction_id == tx.id,
            Transaction.policy_id == policy_id,
            Transaction.is_void.is_(False),
        ).first()
        if existing_reimbursement:
            return False, CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS
    elif tx.id in reimbursed_tx_ids:
        return False, CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS

    delay_reason = _check_delay_use_rule(tx, now_utc)
    if delay_reason:
        return False, delay_reason

    return True, None


def collect_reimbursed_source_tx_ids(policy_id: int) -> Set[int]:
    rows = (
        Transaction.query.with_entities(Transaction.original_transaction_id)
        .filter(
            Transaction.type == "insurance_reimbursement",
            Transaction.policy_id == policy_id,
            Transaction.original_transaction_id.isnot(None),
            Transaction.is_void.is_(False),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}

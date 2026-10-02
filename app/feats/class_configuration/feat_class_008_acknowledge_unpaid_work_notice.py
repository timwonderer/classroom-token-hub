"""FEAT-CLASS-008: Acknowledge the unpaid-work notice.

Records that a class's teacher dismissed the notice for work recorded before
the class's first payroll setting (DOM-PROD-001 §XV.6). Authority:
DOM-CLASS-001 §VII.1; contract: docs/FEATURE-EXECUTION/FEAT-CLASS-008.

The FEAT never evaluates the notice's condition. Acknowledgement and resolution
are independent (owner rulings 2026-10-01): a dismissal from a tab left open
after payroll setup is recorded like any other.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import Seat
from app.services.class_configuration_query_service import verify_teacher_owns_class
from app.services.class_notice_service import record_unpaid_work_notice_acknowledgement
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


@dataclass(frozen=True)
class UnpaidWorkNoticeAcknowledgementResult:
    success: bool
    acknowledged_at: datetime | None = None
    newly_recorded: bool = False
    error_code: str | None = None
    error_message: str | None = None


def _refused(code: str, message: str) -> UnpaidWorkNoticeAcknowledgementResult:
    return UnpaidWorkNoticeAcknowledgementResult(success=False, error_code=code, error_message=message)


def execute_acknowledge_unpaid_work_notice(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> UnpaidWorkNoticeAcknowledgementResult:
    """Record the class teacher's dismissal. Idempotent; the first timestamp wins."""
    return _execute_acknowledge_unpaid_work_notice_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key or f"feat:class-008:unpaid-work-notice:{class_id}",
    )


@requires_feat_context("FEAT-CLASS-008")
def _execute_acknowledge_unpaid_work_notice_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> UnpaidWorkNoticeAcknowledgementResult:
    ctx = canonical_context
    if (
        ctx is None
        or getattr(ctx, "actor_role", None) != "teacher"
        or not getattr(ctx, "class_id", None)
        or not getattr(ctx, "seat_id", None)
    ):
        return _refused("INVALID_CONTEXT", "A class-scoped teacher context is required.")
    if not class_id or class_id != ctx.class_id:
        return _refused("CLASS_SCOPE_MISMATCH", "The notice belongs to a different class than the active one.")
    if verify_teacher_owns_class(class_id, ctx.user_id) is None:
        return _refused("UNAUTHORIZED", "The teacher does not own this class.")

    # The acting seat must be this class's teacher seat (INV-ARC-019): the seat
    # is who acted in the class; owning the class is not enough on its own.
    acting_seat = db.session.get(Seat, ctx.seat_id)
    if (
        acting_seat is None
        or acting_seat.class_id != class_id
        or acting_seat.role != "teacher"
        or str(acting_seat.user_id) != str(ctx.user_id)
    ):
        return _refused("SEAT_NOT_CLASS_TEACHER", "The acting seat is not this class's teacher seat.")

    now = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    ).canonical_now_utc
    recorded = record_unpaid_work_notice_acknowledgement(class_id, now)
    return UnpaidWorkNoticeAcknowledgementResult(
        success=True,
        acknowledged_at=recorded.acknowledged_at,
        newly_recorded=recorded.newly_recorded,
    )

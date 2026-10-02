"""Class Configuration domain command: record a class-level notice acknowledgement.

DOM-CLASS-001 §VII.1. ``classes.unpaid_work_notice_acknowledged_at`` is written
once and never overwritten. The write is a single conditional UPDATE so that a
repeat, a replay or a concurrent dismissal cannot move the first timestamp.

Plain domain command: it opens no FEAT context. FEAT-CLASS-008 composes it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa

from app.extensions import db
from app.models import ClassEconomy


@dataclass(frozen=True)
class NoticeAcknowledgement:
    acknowledged_at: datetime
    newly_recorded: bool


def record_unpaid_work_notice_acknowledgement(class_id: str, acknowledged_at: datetime) -> NoticeAcknowledgement:
    """Set the class's acknowledgement timestamp if it is not set yet.

    Returns the stored timestamp, which is ``acknowledged_at`` only when this
    call recorded it. Raises ``LookupError`` if the class does not exist.
    """
    if not class_id:
        raise ValueError("class_id is required.")
    table = ClassEconomy.__table__
    column = table.c.unpaid_work_notice_acknowledged_at
    written = db.session.execute(
        sa.update(table)
        .where(table.c.class_id == class_id, column.is_(None))
        .values({column: acknowledged_at})
        .returning(column)
    ).scalar_one_or_none()
    if written is not None:
        return NoticeAcknowledgement(acknowledged_at=written, newly_recorded=True)

    existing = db.session.execute(
        sa.select(column).where(table.c.class_id == class_id)
    ).one_or_none()
    if existing is None:
        raise LookupError(f"Class {class_id} not found.")
    return NoticeAcknowledgement(acknowledged_at=existing[0], newly_recorded=False)

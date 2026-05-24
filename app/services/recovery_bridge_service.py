from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import sqlalchemy as sa

from app.extensions import db


@dataclass
class RecoveryCodeView:
    id: int
    student_id: int
    recovery_request_id: int
    code_hash: str | None
    verified_at: datetime | None
    dismissed: bool
    recovery_request: SimpleNamespace


def _tables() -> tuple[sa.Table, sa.Table]:
    requests = db.metadata.tables["recovery_requests"]
    codes = db.metadata.tables["student_recovery_codes"]
    return requests, codes


def _row_to_view(row: sa.Row) -> RecoveryCodeView:
    return RecoveryCodeView(
        id=row.code_id,
        student_id=row.student_id,
        recovery_request_id=row.recovery_request_id,
        code_hash=row.code_hash,
        verified_at=row.verified_at,
        dismissed=bool(row.dismissed),
        recovery_request=SimpleNamespace(expires_at=row.expires_at),
    )


def get_pending_recovery_code_for_student(student_id: int, now_utc: datetime) -> RecoveryCodeView | None:
    requests, codes = _tables()
    stmt = (
        sa.select(
            codes.c.id.label("code_id"),
            codes.c.student_id,
            codes.c.recovery_request_id,
            codes.c.code_hash,
            codes.c.verified_at,
            codes.c.dismissed,
            requests.c.expires_at,
        )
        .select_from(codes.join(requests, requests.c.id == codes.c.recovery_request_id))
        .where(
            codes.c.student_id == student_id,
            codes.c.dismissed.is_(False),
            codes.c.code_hash.is_(None),
            requests.c.status == "pending",
            requests.c.expires_at > now_utc,
        )
        .order_by(codes.c.id.asc())
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _row_to_view(row) if row else None


def get_recovery_code_for_student(code_id: int, student_id: int) -> RecoveryCodeView | None:
    requests, codes = _tables()
    stmt = (
        sa.select(
            codes.c.id.label("code_id"),
            codes.c.student_id,
            codes.c.recovery_request_id,
            codes.c.code_hash,
            codes.c.verified_at,
            codes.c.dismissed,
            requests.c.expires_at,
        )
        .select_from(codes.join(requests, requests.c.id == codes.c.recovery_request_id))
        .where(
            codes.c.id == code_id,
            codes.c.student_id == student_id,
        )
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _row_to_view(row) if row else None


def set_recovery_code_verified(code_id: int, code_hash: str, verified_at: datetime) -> None:
    _requests, codes = _tables()
    stmt = (
        sa.update(codes)
        .where(codes.c.id == code_id)
        .values(
            code_hash=code_hash,
            verified_at=verified_at,
        )
    )
    db.session.execute(stmt)


def dismiss_recovery_code(code_id: int) -> None:
    _requests, codes = _tables()
    stmt = sa.update(codes).where(codes.c.id == code_id).values(dismissed=True)
    db.session.execute(stmt)

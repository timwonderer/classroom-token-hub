from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa

from app.extensions import db


@dataclass
class AdminCredentialView:
    id: int
    user_id: int
    credential_id: str | None
    authenticator_name: str | None
    created_at: datetime | None
    last_used: datetime | None


def _credentials_table() -> sa.Table:
    return db.metadata.tables["passkey_credentials"]


def _credential_row_to_view(row: sa.Row) -> AdminCredentialView:
    return AdminCredentialView(
        id=row.id,
        user_id=row.user_id,
        credential_id=row.credential_id,
        authenticator_name=row.authenticator_name,
        created_at=row.created_at,
        last_used=row.last_used,
    )


def admin_has_passkeys(user_id: int) -> bool:
    credentials = _credentials_table()
    if user_id is None:
        return False
    stmt = (
        sa.select(credentials.c.id)
        .where(credentials.c.user_id == user_id)
        .limit(1)
    )
    return db.session.execute(stmt).first() is not None


def touch_admin_credentials_last_used(user_id: int, now: datetime) -> int:
    credentials = _credentials_table()
    if user_id is None:
        return 0
    stmt = (
        sa.update(credentials)
        .where(credentials.c.user_id == user_id)
        .values(last_used=now)
    )
    result = db.session.execute(stmt)
    return result.rowcount or 0


def list_admin_credentials(user_id: int) -> list[AdminCredentialView]:
    credentials = _credentials_table()
    if user_id is None:
        return []
    stmt = (
        sa.select(credentials)
        .where(credentials.c.user_id == user_id)
        .order_by(credentials.c.created_at.desc())
    )
    return [_credential_row_to_view(row) for row in db.session.execute(stmt).all()]


def delete_admin_credentials_for_user(user_id: int) -> None:
    credentials = _credentials_table()
    if user_id is None:
        return
    db.session.execute(sa.delete(credentials).where(credentials.c.user_id == user_id))


def delete_admin_account_rows(admin_user, legacy_admin=None) -> None:
    if legacy_admin is not None:
        db.session.delete(legacy_admin)
    db.session.delete(admin_user)

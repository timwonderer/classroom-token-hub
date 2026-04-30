"""encrypt admin display name at rest

Revision ID: d2e4f6a8b0c1
Revises: c1d2e3f4a5b7
Create Date: 2026-02-24 21:30:00.000000

"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet


# revision identifiers, used by Alembic.
revision = 'd2e4f6a8b0c1'
down_revision = 'c1d2e3f4a5b7'
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def _is_binary_column(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for col in inspector.get_columns(table_name):
            if col['name'] != column_name:
                continue
            type_name = str(col['type']).lower()
            return any(token in type_name for token in ('bytea', 'blob', 'binary'))
    except Exception:
        return False
    return False


def _encrypt_value(value, fernet: Fernet):
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        plaintext = value
    else:
        plaintext = str(value).encode('utf-8')
    return fernet.encrypt(plaintext)


def _decrypt_value(value, fernet: Fernet):
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, str):
        value = value.encode('utf-8')
    if not isinstance(value, bytes):
        value = bytes(value)
    return fernet.decrypt(value).decode('utf-8')


def upgrade():
    if not table_exists('admins'):
        return

    if not column_exists('admins', 'display_name'):
        if column_exists('admins', 'display_name_encrypted'):
            with op.batch_alter_table('admins', schema=None) as batch_op:
                batch_op.alter_column(
                    'display_name_encrypted',
                    new_column_name='display_name',
                    existing_type=sa.LargeBinary(),
                    existing_nullable=True,
                )
        return

    if _is_binary_column('admins', 'display_name'):
        return

    if not column_exists('admins', 'display_name_encrypted'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('display_name_encrypted', sa.LargeBinary(), nullable=True))

    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("Missing required environment variable: ENCRYPTION_KEY")

    fernet = Fernet(key)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, display_name FROM admins WHERE display_name IS NOT NULL")).fetchall()
    for row in rows:
        encrypted_value = _encrypt_value(row.display_name, fernet)
        conn.execute(
            sa.text("UPDATE admins SET display_name_encrypted = :encrypted_value WHERE id = :admin_id"),
            {"encrypted_value": encrypted_value, "admin_id": row.id},
        )

    with op.batch_alter_table('admins', schema=None) as batch_op:
        if column_exists('admins', 'display_name'):
            batch_op.drop_column('display_name')
        if column_exists('admins', 'display_name_encrypted'):
            batch_op.alter_column(
                'display_name_encrypted',
                new_column_name='display_name',
                existing_type=sa.LargeBinary(),
                existing_nullable=True,
            )


def downgrade():
    if not table_exists('admins') or not column_exists('admins', 'display_name'):
        return

    if not _is_binary_column('admins', 'display_name'):
        return

    if not column_exists('admins', 'display_name_plain'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('display_name_plain', sa.String(length=100), nullable=True))

    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("Missing required environment variable: ENCRYPTION_KEY")

    fernet = Fernet(key)
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, display_name FROM admins WHERE display_name IS NOT NULL")).fetchall()
    for row in rows:
        try:
            decrypted = _decrypt_value(row.display_name, fernet)
        except Exception:
            decrypted = None
        conn.execute(
            sa.text("UPDATE admins SET display_name_plain = :display_name_plain WHERE id = :admin_id"),
            {"display_name_plain": decrypted, "admin_id": row.id},
        )

    with op.batch_alter_table('admins', schema=None) as batch_op:
        if column_exists('admins', 'display_name'):
            batch_op.drop_column('display_name')
        if column_exists('admins', 'display_name_plain'):
            batch_op.alter_column(
                'display_name_plain',
                new_column_name='display_name',
                existing_type=sa.String(length=100),
                existing_nullable=True,
            )

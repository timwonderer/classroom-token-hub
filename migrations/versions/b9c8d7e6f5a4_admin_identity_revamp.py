"""admin identity revamp

Revision ID: b9c8d7e6f5a4
Revises: a1b2c3d4e5f0
Create Date: 2026-02-24 12:00:00.000000

"""
from __future__ import annotations

import re
import secrets
from pathlib import Path
from random import SystemRandom

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9c8d7e6f5a4'
down_revision = 'a1b2c3d4e5f0'
branch_labels = None
depends_on = None


_WORD_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_DEFAULT_WORDS = (
    "anchor", "beacon", "canyon", "cedar", "comet", "copper",
    "delta", "ember", "falcon", "forest", "harbor", "juniper",
    "lantern", "maple", "meadow", "mint", "nebula", "orbit",
    "otter", "prairie", "quartz", "ridge", "river", "spruce",
    "summit", "timber", "valley", "willow",
)


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


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def _load_words() -> list[str]:
    repo_root = Path(__file__).resolve().parents[2]
    words_path = repo_root / "app" / "data" / "random_words.txt"
    words: list[str] = []

    if words_path.exists():
        for raw in words_path.read_text(encoding="utf-8").splitlines():
            token = _WORD_TOKEN_RE.sub("", raw.strip().lower())
            if len(token) >= 3:
                words.append(token)

    deduped = list(dict.fromkeys(words))
    if len(deduped) >= 128:
        return deduped
    return list(_DEFAULT_WORDS)


def _generate_teacher_public_id(existing: set[str], words: list[str]) -> str:
    chooser = SystemRandom()
    for _ in range(100):
        candidate = "_".join(chooser.choice(words) for _ in range(3))
        if candidate not in existing:
            return candidate
    while True:
        candidate = f"{'_'.join(chooser.choice(words) for _ in range(3))}_{secrets.token_hex(2)}"
        if candidate not in existing:
            return candidate


def _generate_verify_token(existing: set[str]) -> str:
    while True:
        token = secrets.token_hex(32)
        if token not in existing:
            return token


def upgrade():
    if not table_exists('admins'):
        return

    # Safe to re-run if already nullable.
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(length=80), nullable=True)

    if not column_exists('admins', 'username_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('username_hash', sa.String(length=64), nullable=True))

    if not column_exists('admins', 'username_lookup_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('username_lookup_hash', sa.String(length=64), nullable=True))

    if not column_exists('admins', 'teacher_public_id'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.add_column(sa.Column('teacher_public_id', sa.String(length=120), nullable=True))

    if not index_exists('admins', 'ix_admins_username_lookup_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.create_index('ix_admins_username_lookup_hash', ['username_lookup_hash'], unique=True)

    if not index_exists('admins', 'ix_admins_teacher_public_id'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.create_index('ix_admins_teacher_public_id', ['teacher_public_id'], unique=True)

    conn = op.get_bind()
    admins = sa.table(
        'admins',
        sa.column('id', sa.Integer),
        sa.column('teacher_public_id', sa.String),
        sa.column('hall_pass_verify_token', sa.String),
    )
    rows = conn.execute(
        sa.select(
            admins.c.id,
            admins.c.teacher_public_id,
            admins.c.hall_pass_verify_token,
        )
    ).fetchall()

    existing_teacher_ids = {row.teacher_public_id for row in rows if row.teacher_public_id}
    existing_tokens = {row.hall_pass_verify_token for row in rows if row.hall_pass_verify_token}
    words = _load_words()

    for row in rows:
        updates = {}
        if not row.teacher_public_id:
            new_teacher_id = _generate_teacher_public_id(existing_teacher_ids, words)
            existing_teacher_ids.add(new_teacher_id)
            updates['teacher_public_id'] = new_teacher_id
        if not row.hall_pass_verify_token:
            new_token = _generate_verify_token(existing_tokens)
            existing_tokens.add(new_token)
            updates['hall_pass_verify_token'] = new_token
        if updates:
            conn.execute(
                sa.update(admins)
                .where(admins.c.id == row.id)
                .values(**updates)
            )


def downgrade():
    if not table_exists('admins'):
        return

    if index_exists('admins', 'ix_admins_teacher_public_id'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.drop_index('ix_admins_teacher_public_id')

    if index_exists('admins', 'ix_admins_username_lookup_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.drop_index('ix_admins_username_lookup_hash')

    if column_exists('admins', 'teacher_public_id'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.drop_column('teacher_public_id')

    if column_exists('admins', 'username_lookup_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.drop_column('username_lookup_hash')

    if column_exists('admins', 'username_hash'):
        with op.batch_alter_table('admins', schema=None) as batch_op:
            batch_op.drop_column('username_hash')

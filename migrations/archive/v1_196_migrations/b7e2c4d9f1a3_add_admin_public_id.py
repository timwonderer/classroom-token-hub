"""add admin public id

Revision ID: b7e2c4d9f1a3
Revises: aa8fb7f5a2c1
Create Date: 2026-02-17 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
import secrets


# revision identifiers, used by Alembic.
revision = "b7e2c4d9f1a3"
down_revision = "aa8fb7f5a2c1"
branch_labels = None
depends_on = None


def _column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return False
    return column_name in columns


def _index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False
    return index_name in indexes


def upgrade():
    if not _column_exists("admins", "public_id"):
        op.add_column("admins", sa.Column("public_id", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    admin_rows = bind.execute(sa.text("SELECT id FROM admins WHERE public_id IS NULL")).fetchall()
    for row in admin_rows:
        bind.execute(
            sa.text("UPDATE admins SET public_id = :public_id WHERE id = :admin_id"),
            {"public_id": secrets.token_urlsafe(18), "admin_id": row.id},
        )

    with op.batch_alter_table("admins", schema=None) as batch_op:
        batch_op.alter_column("public_id", existing_type=sa.String(length=64), nullable=False)

    if not _index_exists("admins", "ix_admins_public_id"):
        op.create_index("ix_admins_public_id", "admins", ["public_id"], unique=True)


def downgrade():
    if _index_exists("admins", "ix_admins_public_id"):
        op.drop_index("ix_admins_public_id", table_name="admins")

    if _column_exists("admins", "public_id"):
        with op.batch_alter_table("admins", schema=None) as batch_op:
            batch_op.drop_column("public_id")

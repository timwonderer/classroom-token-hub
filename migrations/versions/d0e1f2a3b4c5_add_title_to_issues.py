"""add durable support-ticket titles

Revision ID: d0e1f2a3b4c5
Revises: c9d8e7f6a5b4
"""

from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if not column_exists("issues", "title"):
        op.add_column(
            "issues",
            sa.Column("title", sa.String(length=200), nullable=False, server_default="Support Ticket"),
        )
        op.alter_column("issues", "title", server_default=None)


def downgrade():
    if column_exists("issues", "title"):
        op.drop_column("issues", "title")

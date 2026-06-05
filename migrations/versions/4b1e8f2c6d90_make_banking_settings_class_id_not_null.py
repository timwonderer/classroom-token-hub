"""Make BankingSettings class_id not null

Revision ID: 4b1e8f2c6d90
Revises: 3c7d9e1f2a43
Create Date: 2026-06-05 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


# revision identifiers, used by Alembic.
revision = "4b1e8f2c6d90"
down_revision = "3c7d9e1f2a43"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("banking_settings") or not column_exists("banking_settings", "class_id"):
        return
    op.alter_column("banking_settings", "class_id", existing_type=sa.String(length=36), nullable=False)


def downgrade():
    if not table_exists("banking_settings") or not column_exists("banking_settings", "class_id"):
        return
    op.alter_column("banking_settings", "class_id", existing_type=sa.String(length=36), nullable=True)

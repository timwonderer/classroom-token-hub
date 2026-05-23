"""drop legacy pending rebalance json

Revision ID: d2f9f1d9be2e
Revises: c4e36a4ab2f1
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2f9f1d9be2e"
down_revision = "c4e36a4ab2f1"
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
        return column_name in [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False


def upgrade():
    if table_exists("feature_settings") and column_exists("feature_settings", "economy_pending_rebalance_json"):
        with op.batch_alter_table("feature_settings", schema=None) as batch_op:
            batch_op.drop_column("economy_pending_rebalance_json")


def downgrade():
    if table_exists("feature_settings") and not column_exists("feature_settings", "economy_pending_rebalance_json"):
        with op.batch_alter_table("feature_settings", schema=None) as batch_op:
            batch_op.add_column(sa.Column("economy_pending_rebalance_json", sa.Text(), nullable=True))

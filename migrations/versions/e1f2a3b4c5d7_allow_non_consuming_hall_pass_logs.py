"""allow hall-pass logs without an entitlement for non-consuming destinations

Revision ID: e1f2a3b4c5d7
Revises: d0e1f2a3b4c5
"""

from alembic import op
import sqlalchemy as sa


revision = "e1f2a3b4c5d7"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("hall_pass_logs")}
    if columns.get("hall_pass_id", {}).get("nullable") is False:
        op.alter_column("hall_pass_logs", "hall_pass_id", existing_type=sa.String(length=100), nullable=True)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("hall_pass_logs")}
    if columns.get("hall_pass_id", {}).get("nullable") is True:
        # Rows written while the column was nullable are exactly the non-consuming
        # approvals this revision exists to allow: a hall-pass log with no
        # entitlement behind it. Restoring NOT NULL over them would fail, so the
        # downgrade deletes them. They carry no entitlement lifecycle, so nothing
        # downstream is orphaned by the delete — but the approvals themselves are
        # lost, which is the cost of returning to the pre-revision contract.
        op.execute(sa.text("DELETE FROM hall_pass_logs WHERE hall_pass_id IS NULL"))
        op.alter_column("hall_pass_logs", "hall_pass_id", existing_type=sa.String(length=100), nullable=False)

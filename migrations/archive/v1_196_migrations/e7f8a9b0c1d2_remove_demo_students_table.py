"""Remove deprecated DemoStudent feature and drop demo_students table.

Revision ID: e7f8a9b0c1d2
Revises: d1f2e3c4b5a6
Create Date: 2026-03-03

Removed deprecated DemoStudent feature.
No data retained.
Feature previously sunset.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d1f2e3c4b5a6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "demo_students" in tables:
        op.drop_table("demo_students")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "demo_students" not in tables:
        op.create_table(
            "demo_students",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("admin_id", sa.Integer(), nullable=False),
            sa.Column("join_code", sa.String(length=20), nullable=True),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("config_checking_balance", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("config_savings_balance", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("config_hall_passes", sa.Integer(), nullable=True),
            sa.Column("config_insurance_plan", sa.String(length=50), nullable=True),
            sa.Column("config_is_rent_enabled", sa.Boolean(), nullable=True),
            sa.Column("config_period", sa.String(length=10), nullable=True),
            sa.ForeignKeyConstraint(["admin_id"], ["admins.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )
        op.create_index("ix_demo_students_join_code", "demo_students", ["join_code"], unique=False)

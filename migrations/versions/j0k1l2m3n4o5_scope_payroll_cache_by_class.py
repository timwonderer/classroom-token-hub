"""Scope payroll cache uniqueness to class_id

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-09 14:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {uc["name"] for uc in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    if unique_constraint_exists("payroll_cache", "payroll_cache_teacher_id_key"):
        with op.batch_alter_table("payroll_cache") as batch_op:
            batch_op.drop_constraint("payroll_cache_teacher_id_key", type_="unique")
    elif index_exists("payroll_cache", "payroll_cache_teacher_id_key"):
        op.drop_index("payroll_cache_teacher_id_key", table_name="payroll_cache")

    if not index_exists("payroll_cache", "ix_payroll_cache_teacher_id"):
        op.create_index("ix_payroll_cache_teacher_id", "payroll_cache", ["teacher_id"], unique=False)

    if not unique_constraint_exists("payroll_cache", "uq_payroll_cache_class_id"):
        with op.batch_alter_table("payroll_cache") as batch_op:
            batch_op.create_unique_constraint("uq_payroll_cache_class_id", ["class_id"])


def downgrade() -> None:
    with op.batch_alter_table("payroll_cache") as batch_op:
        if unique_constraint_exists("payroll_cache", "uq_payroll_cache_class_id"):
            batch_op.drop_constraint("uq_payroll_cache_class_id", type_="unique")

    if index_exists("payroll_cache", "ix_payroll_cache_teacher_id"):
        op.drop_index("ix_payroll_cache_teacher_id", table_name="payroll_cache")

    if not unique_constraint_exists("payroll_cache", "payroll_cache_teacher_id_key"):
        with op.batch_alter_table("payroll_cache") as batch_op:
            batch_op.create_unique_constraint("payroll_cache_teacher_id_key", ["teacher_id"])

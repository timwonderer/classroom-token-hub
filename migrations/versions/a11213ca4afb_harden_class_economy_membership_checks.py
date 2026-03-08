"""Harden ClassEconomy and ClassMembership status/role constraints.

Revision ID: a11213ca4afb
Revises: c4e1a2b3d4f6
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a11213ca4afb"
down_revision = "c4e1a2b3d4f6"
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def check_constraint_exists(table_name, constraint_name):
    """Check if a check constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        checks = [chk.get("name") for chk in inspector.get_check_constraints(table_name)]
        return constraint_name in checks
    except Exception:
        return False


def drop_check_constraint_if_exists(table_name, constraint_name):
    """Drop a check constraint only when it exists."""
    if check_constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="check")


def upgrade():
    if table_exists("class_economies") and column_exists("class_economies", "status"):
        op.execute(
            sa.text(
                """
                UPDATE class_economies
                SET status = 'active'
                WHERE status IS NULL OR status NOT IN ('active', 'archived')
                """
            )
        )

        if not check_constraint_exists("class_economies", "ck_class_economies_status_allowed"):
            op.create_check_constraint(
                "ck_class_economies_status_allowed",
                "class_economies",
                "status IN ('active', 'archived')",
            )

    if table_exists("class_memberships"):
        if column_exists("class_memberships", "role"):
            op.execute(
                sa.text(
                    """
                    UPDATE class_memberships
                    SET role = CASE
                        WHEN admin_id IS NOT NULL THEN 'admin'
                        ELSE 'student'
                    END
                    WHERE role IS NULL OR role NOT IN ('admin', 'student')
                    """
                )
            )

        if column_exists("class_memberships", "status"):
            op.execute(
                sa.text(
                    """
                    UPDATE class_memberships
                    SET status = 'active'
                    WHERE status IS NULL OR status NOT IN ('active', 'archived')
                    """
                )
            )

        if not check_constraint_exists("class_memberships", "ck_class_memberships_role_allowed"):
            op.create_check_constraint(
                "ck_class_memberships_role_allowed",
                "class_memberships",
                "((admin_id IS NOT NULL AND role = 'admin') OR (student_id IS NOT NULL AND role = 'student'))",
            )

        if not check_constraint_exists("class_memberships", "ck_class_memberships_status_allowed"):
            op.create_check_constraint(
                "ck_class_memberships_status_allowed",
                "class_memberships",
                "status IN ('active', 'archived')",
            )


def downgrade():
    if table_exists("class_memberships"):
        drop_check_constraint_if_exists("class_memberships", "ck_class_memberships_status_allowed")
        drop_check_constraint_if_exists("class_memberships", "ck_class_memberships_role_allowed")

    if table_exists("class_economies"):
        drop_check_constraint_if_exists("class_economies", "ck_class_economies_status_allowed")

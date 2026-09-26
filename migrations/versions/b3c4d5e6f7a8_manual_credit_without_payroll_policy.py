"""Let manual payroll credits exist without a payroll policy version.

Attendance-derived payroll events still require policy_version_id and policy_uuid;
a teacher's manual credit does not (DOM-PROD-001 §VIII). A check constraint keeps
the requirement for payroll events now that the columns are nullable.

Revision ID: b3c4d5e6f7a8
Revises: a1e1f2a3b4c5
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a1e1f2a3b4c5'
branch_labels = None
depends_on = None

TABLE = 'payroll_event'
CHECK = 'ck_payroll_event_payroll_policy'


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
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def check_constraint_exists(table_name, constraint_name):
    """Check if a check constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return constraint_name in {c['name'] for c in inspector.get_check_constraints(table_name)}
    except Exception:
        return False


def upgrade():
    if not table_exists(TABLE):
        print(f"⚠️  {TABLE} does not exist, skipping...")
        return
    for column, type_ in (('policy_version_id', sa.Integer()), ('policy_uuid', sa.String(length=36))):
        if column_exists(TABLE, column):
            op.alter_column(TABLE, column, existing_type=type_, nullable=True)
    if not check_constraint_exists(TABLE, CHECK):
        op.create_check_constraint(
            CHECK, TABLE,
            "payroll_event_type <> 'payroll' OR (policy_version_id IS NOT NULL AND policy_uuid IS NOT NULL)",
        )
        print(f"✅ Added {CHECK}; manual credits no longer need a payroll policy")
    else:
        print(f"⚠️  {CHECK} already exists, skipping...")


def downgrade():
    if not table_exists(TABLE):
        return
    orphaned = op.get_bind().execute(sa.text(
        "SELECT 1 FROM payroll_event WHERE policy_version_id IS NULL OR policy_uuid IS NULL LIMIT 1"
    )).first()
    if orphaned:
        raise RuntimeError(
            'Cannot restore NOT NULL: payroll events without a payroll policy exist. '
            'No rows were changed.'
        )
    if check_constraint_exists(TABLE, CHECK):
        op.drop_constraint(CHECK, TABLE, type_='check')
    for column, type_ in (('policy_version_id', sa.Integer()), ('policy_uuid', sa.String(length=36))):
        if column_exists(TABLE, column):
            op.alter_column(TABLE, column, existing_type=type_, nullable=False)

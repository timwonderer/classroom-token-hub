"""Persist successful teacher sign-in time for account retention policy."""
from alembic import op
import sqlalchemy as sa

revision = 'b6f6a7b8c9d0'
down_revision = 'a5e5f6a7b8c9'
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
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    if not column_exists("users", "last_signed_in_at"):
        op.add_column("users", sa.Column("last_signed_in_at", sa.DateTime(timezone=True), nullable=True))
    if not index_exists("users", "ix_users_last_signed_in_at"):
        op.create_index("ix_users_last_signed_in_at", "users", ["last_signed_in_at"])
    # Preserve only recorded sign-in evidence, never infer it from class activity.
    bind.execute(sa.text("""UPDATE users SET last_signed_in_at = current_session_started_at
        WHERE user_role = 'teacher' AND last_signed_in_at IS NULL
          AND current_session_started_at IS NOT NULL"""))


def downgrade():
    if index_exists("users", "ix_users_last_signed_in_at"):
        op.drop_index("ix_users_last_signed_in_at", table_name="users")
    if column_exists("users", "last_signed_in_at"):
        op.drop_column("users", "last_signed_in_at")

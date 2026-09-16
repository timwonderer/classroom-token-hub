"""Persist successful teacher sign-in time for account retention policy."""
from alembic import op
import sqlalchemy as sa

revision = "b6f6a7b8c9d0"
down_revision = "a5e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if "last_signed_in_at" not in columns:
        op.add_column("users", sa.Column("last_signed_in_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("users")}
    if "ix_users_last_signed_in_at" not in indexes:
        op.create_index("ix_users_last_signed_in_at", "users", ["last_signed_in_at"])
    # Preserve only recorded sign-in evidence, never infer it from class activity.
    bind.execute(sa.text("""UPDATE users SET last_signed_in_at = current_session_started_at
        WHERE user_role = 'teacher' AND last_signed_in_at IS NULL
          AND current_session_started_at IS NOT NULL"""))


def downgrade():
    op.drop_index("ix_users_last_signed_in_at", table_name="users")
    op.drop_column("users", "last_signed_in_at")

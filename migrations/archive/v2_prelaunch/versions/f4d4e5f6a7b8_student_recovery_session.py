"""Store the verifier and deadline for session-bound student recovery."""
from alembic import op
import sqlalchemy as sa

revision = "f4d4e5f6a7b8"
down_revision = "e3c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # The bootstrap migration creates current ORM metadata on an empty database.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    with op.batch_alter_table("users") as batch:
        if "recovery_setup_nonce_hash" not in columns:
            batch.add_column(sa.Column("recovery_setup_nonce_hash", sa.String(64), nullable=True))
        if "recovery_setup_expires_at" not in columns:
            batch.add_column(sa.Column("recovery_setup_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("recovery_setup_expires_at")
        batch.drop_column("recovery_setup_nonce_hash")

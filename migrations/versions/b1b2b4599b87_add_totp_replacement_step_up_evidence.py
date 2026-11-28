"""Add TOTP replacement step-up challenge, consumed-token and retention columns.

SPEC-IDEN-002 v1.4 §V "TOTP replacement step-up evidence" and §VI, DOM-CORE-002:
the single-use step-up challenge a TOTP replacement stores before its passkey
ceremony (verifier, issue instant ``t0``, window end ``c``), the consumed provider
token id (unique across every row, so a replay is refused for as long as the row
exists) and the instant until which a terminal row must be kept so that token
cannot qualify again (``step_up_retain_until``). Adds the ``awaiting_step_up``
stage. Schema only: no data is backfilled and no existing row changes meaning.

Revision ID: b1b2b4599b87
Revises: e9eff14d6cae
Create Date: 2026-11-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b1b2b4599b87'
down_revision = 'e9eff14d6cae'
branch_labels = None
depends_on = None

TABLE = 'credential_operations'
STAGE_ENUM = 'credential_operation_stage_enum'
NEW_STAGE = 'awaiting_step_up'
OLD_STAGES = (
    'authorized', 'registration_pending', 'candidate_verified',
    'retirement_committed', 'provider_uncertain', 'completed', 'cancelled',
)
LIVE_INDEX = 'uq_credential_operations_one_open_per_user'
TOKEN_INDEX = 'uq_credential_operations_step_up_token_id'

COLUMNS = (
    ('step_up_challenge_hash', lambda: sa.Column('step_up_challenge_hash', sa.String(length=64), nullable=True)),
    ('step_up_issued_at', lambda: sa.Column('step_up_issued_at', sa.DateTime(timezone=True), nullable=True)),
    ('step_up_challenge_expires_at', lambda: sa.Column('step_up_challenge_expires_at', sa.DateTime(timezone=True), nullable=True)),
    ('step_up_token_id', lambda: sa.Column('step_up_token_id', sa.Uuid(as_uuid=False), nullable=True)),
    ('step_up_retain_until', lambda: sa.Column('step_up_retain_until', sa.DateTime(timezone=True), nullable=True)),
)


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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


def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


def _enum_has_value(value):
    conn = op.get_bind()
    return bool(conn.execute(
        sa.text(
            "SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = :name AND e.enumlabel = :label"
        ),
        {"name": STAGE_ENUM, "label": value},
    ).scalar())


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if not table_exists(TABLE):
        print("Table 'credential_operations' does not exist, skipping...")
        return

    if not _enum_has_value(NEW_STAGE):
        op.execute(f"ALTER TYPE {STAGE_ENUM} ADD VALUE IF NOT EXISTS '{NEW_STAGE}'")
        print("Added awaiting_step_up to the stage enum")

    for name, make in COLUMNS:
        if not column_exists(TABLE, name):
            op.add_column(TABLE, make())
            print(f"Added {name} to credential_operations")
        else:
            print(f"Column '{name}' already exists on 'credential_operations', skipping...")

    # Unique across every row, not a partial index: a consumed token id stays refused for
    # as long as any row (live, terminal or retained receipt) still carries it.
    if not index_exists(TABLE, TOKEN_INDEX):
        op.create_index(TOKEN_INDEX, TABLE, ['step_up_token_id'], unique=True)
        print("Created the consumed step-up token id unique index")


def downgrade():
    if not table_exists(TABLE):
        print("Table 'credential_operations' does not exist, skipping...")
        return

    if index_exists(TABLE, TOKEN_INDEX):
        op.drop_index(TOKEN_INDEX, table_name=TABLE)
    for name, _make in reversed(COLUMNS):
        if column_exists(TABLE, name):
            op.drop_column(TABLE, name)
            print(f"Dropped {name} from credential_operations")

    if _enum_has_value(NEW_STAGE):
        # A value cannot be removed from a Postgres enum: rebuild the type. A row still
        # waiting for step-up evidence holds no authority, so it becomes cancelled.
        op.execute(f"UPDATE {TABLE} SET stage = 'cancelled' WHERE stage = '{NEW_STAGE}'")
        if index_exists(TABLE, LIVE_INDEX):
            op.drop_index(LIVE_INDEX, table_name=TABLE)
        op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN stage TYPE text USING stage::text")
        op.execute(f"DROP TYPE {STAGE_ENUM}")
        postgresql.ENUM(*OLD_STAGES, name=STAGE_ENUM).create(op.get_bind(), checkfirst=False)
        op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN stage TYPE {STAGE_ENUM} USING stage::{STAGE_ENUM}")
        if not index_exists(TABLE, LIVE_INDEX):
            op.create_index(
                LIVE_INDEX, TABLE, ['user_id'], unique=True,
                postgresql_where=sa.text("stage NOT IN ('completed', 'cancelled')"),
            )
        print("Removed awaiting_step_up from the stage enum")

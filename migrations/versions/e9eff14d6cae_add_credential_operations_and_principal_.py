"""Add credential operations and principal credential generation.

SPEC-IDEN-002 §VI, DOM-IDEN-003 §VII.A, DOM-CORE-002 (1.22): Identity's monotonic
``users.credential_generation`` and the per-principal ``credential_operations``
table, with a partial unique index that permits one open operation per principal.
Schema only: no data is backfilled and no existing row changes meaning.

Revision ID: e9eff14d6cae
Revises: 4fad9d362d0d
Create Date: 2026-11-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e9eff14d6cae'
down_revision = '4fad9d362d0d'
branch_labels = None
depends_on = None

TABLE = 'credential_operations'
LIVE_INDEX = 'uq_credential_operations_one_open_per_user'
USER_INDEX = 'ix_credential_operations_user_id'
DEADLINE_INDEX = 'ix_credential_operations_deadline_at'
PURPOSE_ENUM = 'credential_operation_purpose_enum'
STAGE_ENUM = 'credential_operation_stage_enum'
PURPOSES = ('totp_replace', 'passkey_enroll', 'passkey_replace', 'passkey_revoke')
STAGES = (
    'authorized', 'registration_pending', 'candidate_verified',
    'retirement_committed', 'provider_uncertain', 'completed', 'cancelled',
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


def _enum(name, values):
    return postgresql.ENUM(*values, name=name, create_type=False)


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if not column_exists('users', 'credential_generation'):
        op.add_column(
            'users',
            sa.Column('credential_generation', sa.Integer(), nullable=False, server_default='1'),
        )
        print("Added credential_generation to users")
    else:
        print("Column 'credential_generation' already exists on 'users', skipping...")

    bind = op.get_bind()
    postgresql.ENUM(*PURPOSES, name=PURPOSE_ENUM).create(bind, checkfirst=True)
    postgresql.ENUM(*STAGES, name=STAGE_ENUM).create(bind, checkfirst=True)

    if not table_exists(TABLE):
        op.create_table(
            TABLE,
            sa.Column('id', sa.Uuid(as_uuid=False), nullable=False,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
            sa.Column('purpose', _enum(PURPOSE_ENUM, PURPOSES), nullable=False),
            sa.Column('stage', _enum(STAGE_ENUM, STAGES), nullable=False),
            sa.Column('authorized_generation', sa.Integer(), nullable=False),
            sa.Column('session_binding_hash', sa.String(length=64), nullable=False),
            sa.Column('deadline_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('pending_totp_encrypted', sa.String(length=200), nullable=True),
            sa.Column('old_credential_id', sa.Text(), nullable=True),
            sa.Column('new_credential_id', sa.Text(), nullable=True),
            sa.Column('retirement_intent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('retry_after_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('error_category', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        print("Created credential_operations")
    else:
        print("Table 'credential_operations' already exists, skipping...")

    if not index_exists(TABLE, USER_INDEX):
        op.create_index(USER_INDEX, TABLE, ['user_id'])
    if not index_exists(TABLE, DEADLINE_INDEX):
        op.create_index(DEADLINE_INDEX, TABLE, ['deadline_at'])
    if not index_exists(TABLE, LIVE_INDEX):
        op.create_index(
            LIVE_INDEX, TABLE, ['user_id'], unique=True,
            postgresql_where=sa.text("stage NOT IN ('completed', 'cancelled')"),
        )
        print("Created one-open-operation-per-principal index")


def downgrade():
    if table_exists(TABLE):
        for index in (LIVE_INDEX, DEADLINE_INDEX, USER_INDEX):
            if index_exists(TABLE, index):
                op.drop_index(index, table_name=TABLE)
        for fk in get_foreign_keys_by_column(TABLE, 'user_id'):
            if fk.get('name'):
                op.drop_constraint(fk['name'], TABLE, type_='foreignkey')
        op.drop_table(TABLE)
        print("Dropped credential_operations")
    else:
        print("Table 'credential_operations' does not exist, skipping...")

    bind = op.get_bind()
    postgresql.ENUM(name=STAGE_ENUM).drop(bind, checkfirst=True)
    postgresql.ENUM(name=PURPOSE_ENUM).drop(bind, checkfirst=True)

    if column_exists('users', 'credential_generation'):
        op.drop_column('users', 'credential_generation')
        print("Dropped credential_generation from users")
    else:
        print("Column 'credential_generation' does not exist on 'users', skipping...")

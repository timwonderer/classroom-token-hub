"""users.id becomes a random UUID; passkey rows require a credential id

Revision ID: f4b8d2a6c1e9
Revises: e1c7a4b9d2f3
Create Date: 2026-09-28

users.id was a sequential integer. After the 2026-09-26 launch wipe restarted
it at 1, passwordless.dev still held pre-launch passkeys registered as
"user_<id>", and sign-in trusted that id: an old passkey for user_3 would sign
in whoever is user 3 now. A random UUID cannot be reissued to someone else.

INV-ARC-019 §VI allows exactly four persisted references to users.id. This
migration converts users.id and those four together, keeping each FK's delete
rule, and refuses to run if the database holds any other reference to users.

It also:
- drops feature_settings.economy_last_rebalanced_by, an integer user id that
  nothing reads or writes and that sits outside the allowlist;
- deletes passkey_credentials rows with no credential_id. Those rows cannot be
  matched at sign-in under the new rule, so they are dead; the owner registers
  again. credential_id becomes NOT NULL and UNIQUE.

Downgrade restores integer ids numbered by created_at. The original integers
are not recoverable, and passkeys registered under the UUID must be
registered again.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4b8d2a6c1e9'
down_revision = 'e1c7a4b9d2f3'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists.

    Args:
        table_name: Name of the table to check

    Returns:
        bool: True if table exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column to check

    Returns:
        bool: True if column exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        # Table doesn't exist
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table.

    Args:
        table_name: Name of the table
        index_name: Name of the index to check

    Returns:
        bool: True if index exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        # Table doesn't exist
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table.

    Args:
        table_name: Name of the table
        fk_name: Name of the foreign key to check

    Returns:
        bool: True if foreign key exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        # Table doesn't exist
        return False


def constraint_exists(table_name, constraint_name):
    """Check if a unique constraint exists on a table.

    Args:
        table_name: Name of the table
        constraint_name: Name of the constraint to check

    Returns:
        bool: True if constraint exists, False otherwise
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        # Table doesn't exist
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign key constraints that reference a specific column.

    Use this in downgrade() instead of hardcoding FK names, which vary
    across environments and can cause migration failures.


    Args:
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        list: List of foreign key constraint dicts
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# ============================================================================
# MIGRATION OPERATIONS
# ============================================================================

# (table, column, nullable, ondelete, fk name, index name) — INV-ARC-019 §VI.
REFERENCES = (
    ('seats', 'user_id', True, 'RESTRICT', 'fk_seats_user_id_users', 'ix_seats_user_id'),
    ('classes', 'teacher_user_id', True, 'CASCADE', 'classes_teacher_user_id_fkey', 'ix_classes_teacher_user_id'),
    ('passkey_credentials', 'user_id', False, 'CASCADE', 'passkey_credentials_user_id_fkey', 'ix_passkey_credentials_user_id'),
    ('recovery_requests', 'user_id', False, None, 'recovery_requests_user_id_fkey', 'ix_recovery_requests_user_id'),
)


def _users_id_type():
    return op.get_bind().execute(sa.text(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'id'"
    )).scalar()


def _references_to_users():
    """Every (table, column) with a foreign key into users, read from the catalog."""
    rows = op.get_bind().execute(sa.text(
        "SELECT c.conrelid::regclass::text, a.attname"
        " FROM pg_constraint c"
        " JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)"
        " WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass"
    )).fetchall()
    return {(table, column) for table, column in rows}


def _drop_foreign_keys_into_users(table, column):
    for fk in get_foreign_keys_by_column(table, column):
        if fk.get('referred_table') == 'users':
            op.drop_constraint(fk['name'], table, type_='foreignkey')


def _drop_unique_constraints_on(table, columns):
    for uc in sa.inspect(op.get_bind()).get_unique_constraints(table):
        if list(uc['column_names']) == list(columns):
            op.drop_constraint(uc['name'], table, type_='unique')


def _swap_reference_columns(new_type, fill_sql):
    """Replace each allowlisted reference column with a column of ``new_type``
    filled through ``fill_sql`` (which maps old users.id to the new id)."""
    for table, column, nullable, ondelete, fk_name, index_name in REFERENCES:
        staged = f'{column}__new'
        if not column_exists(table, staged):
            op.add_column(table, sa.Column(staged, new_type, nullable=True))
        op.execute(fill_sql.format(table=table, column=column, staged=staged))
        _drop_foreign_keys_into_users(table, column)
        # Dropping the column also drops its index and uq_seats_user_class.
        op.drop_column(table, column)
        op.alter_column(table, staged, new_column_name=column, nullable=nullable)


def _restore_reference_constraints():
    for table, column, _nullable, ondelete, fk_name, index_name in REFERENCES:
        if not index_exists(table, index_name):
            op.create_index(index_name, table, [column])
        if not foreign_key_exists(table, fk_name):
            op.create_foreign_key(fk_name, table, 'users', [column], ['id'], ondelete=ondelete)
    if not constraint_exists('seats', 'uq_seats_user_class'):
        op.create_unique_constraint('uq_seats_user_class', 'seats', ['user_id', 'class_id'])


def upgrade():
    if _users_id_type() == 'uuid':
        print("⚠️  users.id is already a UUID, skipping")
    else:
        expected = {(t, c) for t, c, *_ in REFERENCES}
        found = _references_to_users()
        if found != expected:
            raise RuntimeError(
                "users.id has references outside the INV-ARC-019 §VI allowlist, or is missing "
                f"one; refusing to guess. Unexpected: {sorted(found - expected)}; "
                f"missing: {sorted(expected - found)}"
            )

        if not column_exists('users', 'id__new'):
            op.add_column('users', sa.Column(
                'id__new', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()'),
            ))
        _swap_reference_columns(
            sa.Uuid(),
            "UPDATE {table} t SET {staged} = u.id__new FROM users u WHERE t.{column} = u.id",
        )
        # Nothing references users.id now. Dropping it drops its primary key and
        # its sequence, which the column owns.
        op.drop_column('users', 'id')
        op.alter_column('users', 'id__new', new_column_name='id')
        op.create_primary_key('users_pkey', 'users', ['id'])
        if not constraint_exists('users', 'uq_users_id'):
            op.create_unique_constraint('uq_users_id', 'users', ['id'])
        _restore_reference_constraints()
        print("✅ users.id and its four references are UUIDs")

    if column_exists('feature_settings', 'economy_last_rebalanced_by'):
        op.drop_column('feature_settings', 'economy_last_rebalanced_by')
        print("❌ Dropped unused feature_settings.economy_last_rebalanced_by")

    removed = op.get_bind().execute(sa.text(
        "DELETE FROM passkey_credentials WHERE credential_id IS NULL"
    )).rowcount
    print(f"❌ Removed {removed} passkey rows with no credential id")
    op.alter_column('passkey_credentials', 'credential_id', existing_type=sa.Text(), nullable=False)
    if not constraint_exists('passkey_credentials', 'uq_passkey_credentials_credential_id'):
        op.create_unique_constraint(
            'uq_passkey_credentials_credential_id', 'passkey_credentials', ['credential_id'],
        )


def downgrade():
    _drop_unique_constraints_on('passkey_credentials', ['credential_id'])
    op.alter_column('passkey_credentials', 'credential_id', existing_type=sa.Text(), nullable=True)

    if not column_exists('feature_settings', 'economy_last_rebalanced_by'):
        op.add_column('feature_settings', sa.Column('economy_last_rebalanced_by', sa.Integer(), nullable=True))

    if _users_id_type() != 'uuid':
        print("⚠️  users.id is already an integer, skipping")
        return

    # Number the users by creation order. The pre-upgrade integers are gone.
    if not column_exists('users', 'id__new'):
        op.add_column('users', sa.Column('id__new', sa.Integer(), nullable=True))
    op.execute(
        "UPDATE users u SET id__new = n.rn FROM ("
        " SELECT id, row_number() OVER (ORDER BY created_at, id) AS rn FROM users"
        ") n WHERE u.id = n.id"
    )
    _swap_reference_columns(
        sa.Integer(),
        "UPDATE {table} t SET {staged} = u.id__new FROM users u WHERE t.{column} = u.id",
    )
    op.drop_column('users', 'id')  # takes users_pkey and uq_users_id with it
    op.alter_column('users', 'id__new', new_column_name='id', nullable=False)
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_id_seq OWNED BY users.id")
    op.execute("SELECT setval('users_id_seq', COALESCE((SELECT max(id) FROM users), 0) + 1, false)")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_id_seq')")
    op.create_primary_key('users_pkey', 'users', ['id'])
    _restore_reference_constraints()
    print("❌ users.id restored to integers numbered by created_at")

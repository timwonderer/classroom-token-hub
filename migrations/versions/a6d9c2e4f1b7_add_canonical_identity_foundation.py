"""Add canonical identity foundation fields.

Revision ID: a6d9c2e4f1b7
Revises: 4e85bf5c5594
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a6d9c2e4f1b7"
down_revision = "4e85bf5c5594"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [index["name"] for index in inspector.get_indexes(table_name)]
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return constraint_name in [
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
        ]
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk
            for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def null_count(table_name, column_name):
    bind = op.get_bind()
    result = bind.execute(
        sa.text(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{column_name}" IS NULL')
    )
    return result.scalar_one()


def _add_column(table_name, column):
    if not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _create_index(table_name, index_name, columns, *, unique=False):
    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _create_fk(table_name, fk_name, referred_table, local_columns, remote_columns, *, ondelete=None):
    if not foreign_key_exists(table_name, fk_name):
        op.create_foreign_key(
            fk_name,
            table_name,
            referred_table,
            local_columns,
            remote_columns,
            ondelete=ondelete,
        )


def _require_not_null(table_name, column_name, existing_type):
    if null_count(table_name, column_name):
        raise RuntimeError(
            f"Cannot make {table_name}.{column_name} required while NULL rows exist; "
            "backfill or remove the incomplete token rows before upgrading."
        )
    op.alter_column(
        table_name,
        column_name,
        existing_type=existing_type,
        nullable=False,
    )


def upgrade():
    bind = op.get_bind()
    user_role_enum = postgresql.ENUM(
        "student",
        "teacher",
        "sysadmin",
        name="user_role_enum",
        create_type=False,
    )
    user_role_enum.create(bind, checkfirst=True)

    _add_column("users", sa.Column("user_role", user_role_enum, nullable=True))
    _add_column("users", sa.Column("username_lookup_hash", sa.String(length=64), nullable=True))
    _add_column("users", sa.Column("totp_secret_encrypted", sa.String(length=200), nullable=True))
    _add_column("users", sa.Column("pin_hash", sa.Text(), nullable=True))
    _add_column("users", sa.Column("passphrase_hash", sa.Text(), nullable=True))
    _add_column("users", sa.Column("current_session_started_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("users", sa.Column("current_session_expires_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("users", sa.Column("current_session_nonce", sa.String(length=128), nullable=True))
    _add_column("users", sa.Column("money_action_cooldown_until", sa.DateTime(timezone=True), nullable=True))
    _add_column(
        "users",
        sa.Column("has_completed_setup", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column("users", sa.Column("last_active_seat_id", sa.Integer(), nullable=True))

    _create_index("users", "ix_users_user_role", ["user_role"])
    _create_index("users", "ix_users_username_lookup_hash", ["username_lookup_hash"], unique=True)
    _create_index("users", "ix_users_current_session_nonce", ["current_session_nonce"])
    _create_index("users", "ix_users_last_active_seat_id", ["last_active_seat_id"])
    _create_fk(
        "users",
        "fk_users_last_active_seat_id_seats",
        "seats",
        ["last_active_seat_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if column_exists("users", "password_hash"):
        op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)

    _add_column("seats", sa.Column("claim_first_name_hash", sa.String(length=128), nullable=True))
    _add_column("seats", sa.Column("claim_last_name_hash", sa.String(length=128), nullable=True))
    _create_index("seats", "ix_seats_claim_first_name_hash", ["claim_first_name_hash"])
    _create_index("seats", "ix_seats_claim_last_name_hash", ["claim_last_name_hash"])

    _add_column("identity_profiles", sa.Column("seat_id", sa.Integer(), nullable=True))
    _create_index("identity_profiles", "ix_identity_profiles_seat_id", ["seat_id"], unique=True)
    _create_fk(
        "identity_profiles",
        "fk_identity_profiles_seat_id_seats",
        "seats",
        ["seat_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _add_column("classes", sa.Column("join_code_token", sa.String(length=20), nullable=True))
    _add_column("classes", sa.Column("section", sa.String(length=50), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE classes
            SET join_code_token = join_code
            WHERE join_code_token IS NULL
              AND join_code IS NOT NULL
            """
        )
    )
    _create_index("classes", "ix_classes_join_code_token", ["join_code_token"], unique=True)

    if not table_exists("user_invite_tokens"):
        op.create_table(
            "user_invite_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("user_role", user_role_enum, nullable=False),
            sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_user_invite_tokens_token_hash"),
        )
    else:
        _add_column("user_invite_tokens", sa.Column("token_hash", sa.String(length=128), nullable=True))
        _add_column("user_invite_tokens", sa.Column("user_role", user_role_enum, nullable=True))
        _add_column("user_invite_tokens", sa.Column("issued_by_user_id", sa.Integer(), nullable=True))
        _add_column("user_invite_tokens", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        _add_column("user_invite_tokens", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
        _add_column("user_invite_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        _create_fk(
            "user_invite_tokens",
            "fk_user_invite_tokens_issued_by_user_id_users",
            "users",
            ["issued_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    _require_not_null("user_invite_tokens", "token_hash", sa.String(length=128))
    _require_not_null("user_invite_tokens", "user_role", user_role_enum)
    _require_not_null("user_invite_tokens", "expires_at", sa.DateTime(timezone=True))
    _create_index("user_invite_tokens", "ix_user_invite_tokens_token_hash", ["token_hash"], unique=True)
    _create_index("user_invite_tokens", "ix_user_invite_tokens_issued_by_user_id", ["issued_by_user_id"])
    _create_index("user_invite_tokens", "ix_user_invite_tokens_expires_at", ["expires_at"])

    if not table_exists("user_recovery_tokens"):
        op.create_table(
            "user_recovery_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_user_recovery_tokens_token_hash"),
        )
    else:
        _add_column("user_recovery_tokens", sa.Column("user_id", sa.Integer(), nullable=True))
        _add_column("user_recovery_tokens", sa.Column("token_hash", sa.String(length=128), nullable=True))
        _add_column("user_recovery_tokens", sa.Column("issued_by_user_id", sa.Integer(), nullable=True))
        _add_column("user_recovery_tokens", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        _add_column("user_recovery_tokens", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
        _add_column("user_recovery_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        _create_fk(
            "user_recovery_tokens",
            "fk_user_recovery_tokens_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        _create_fk(
            "user_recovery_tokens",
            "fk_user_recovery_tokens_issued_by_user_id_users",
            "users",
            ["issued_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    _require_not_null("user_recovery_tokens", "user_id", sa.Integer())
    _require_not_null("user_recovery_tokens", "token_hash", sa.String(length=128))
    _require_not_null("user_recovery_tokens", "expires_at", sa.DateTime(timezone=True))
    _create_index("user_recovery_tokens", "ix_user_recovery_tokens_user_id", ["user_id"])
    _create_index("user_recovery_tokens", "ix_user_recovery_tokens_token_hash", ["token_hash"], unique=True)
    _create_index("user_recovery_tokens", "ix_user_recovery_tokens_issued_by_user_id", ["issued_by_user_id"])
    _create_index("user_recovery_tokens", "ix_user_recovery_tokens_expires_at", ["expires_at"])


def downgrade():
    for table_name, index_name in (
        ("user_recovery_tokens", "ix_user_recovery_tokens_expires_at"),
        ("user_recovery_tokens", "ix_user_recovery_tokens_issued_by_user_id"),
        ("user_recovery_tokens", "ix_user_recovery_tokens_token_hash"),
        ("user_recovery_tokens", "ix_user_recovery_tokens_user_id"),
        ("user_invite_tokens", "ix_user_invite_tokens_expires_at"),
        ("user_invite_tokens", "ix_user_invite_tokens_issued_by_user_id"),
        ("user_invite_tokens", "ix_user_invite_tokens_token_hash"),
        ("classes", "ix_classes_join_code_token"),
        ("identity_profiles", "ix_identity_profiles_seat_id"),
        ("seats", "ix_seats_claim_last_name_hash"),
        ("seats", "ix_seats_claim_first_name_hash"),
        ("users", "ix_users_last_active_seat_id"),
        ("users", "ix_users_current_session_nonce"),
        ("users", "ix_users_username_lookup_hash"),
        ("users", "ix_users_user_role"),
    ):
        if index_exists(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name, column_name in (
        ("user_recovery_tokens", "issued_by_user_id"),
        ("user_recovery_tokens", "user_id"),
        ("user_invite_tokens", "issued_by_user_id"),
        ("identity_profiles", "seat_id"),
        ("users", "last_active_seat_id"),
    ):
        for fk in get_foreign_keys_by_column(table_name, column_name):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")

    for table_name, columns in (
        (
            "user_recovery_tokens",
            ("revoked_at", "used_at", "expires_at", "issued_by_user_id", "token_hash", "user_id"),
        ),
        (
            "user_invite_tokens",
            ("revoked_at", "used_at", "expires_at", "issued_by_user_id", "user_role", "token_hash"),
        ),
        ("classes", ("section", "join_code_token")),
        ("identity_profiles", ("seat_id",)),
        ("seats", ("claim_last_name_hash", "claim_first_name_hash")),
        (
            "users",
            (
                "last_active_seat_id",
                "has_completed_setup",
                "money_action_cooldown_until",
                "current_session_nonce",
                "current_session_expires_at",
                "current_session_started_at",
                "passphrase_hash",
                "pin_hash",
                "totp_secret_encrypted",
                "username_lookup_hash",
                "user_role",
            ),
        ),
    ):
        for column_name in columns:
            if column_exists(table_name, column_name):
                op.drop_column(table_name, column_name)

    if column_exists("users", "password_hash"):
        if null_count("users", "password_hash"):
            raise RuntimeError(
                "Cannot restore users.password_hash to NOT NULL while credentialless users exist."
            )
        op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)

    user_role_enum = postgresql.ENUM(name="user_role_enum")
    user_role_enum.drop(op.get_bind(), checkfirst=True)

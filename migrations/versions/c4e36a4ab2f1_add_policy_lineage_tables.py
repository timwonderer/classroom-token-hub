"""add policy lineage tables

Revision ID: c4e36a4ab2f1
Revises: 8357d4036478
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e36a4ab2f1"
down_revision = "8357d4036478"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def upgrade():
    if not table_exists("policy_versions"):
        op.create_table(
            "policy_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("domain", sa.String(length=32), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("policy_payload_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_transition_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "class_id",
                "domain",
                "version_number",
                name="uq_policy_versions_class_domain_version",
            ),
        )

    if not table_exists("policy_transitions"):
        op.create_table(
            "policy_transitions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("domain", sa.String(length=32), nullable=False),
            sa.Column("source_policy_version_id", sa.Integer(), nullable=True),
            sa.Column("target_policy_version_id", sa.Integer(), nullable=False),
            sa.Column("activation_mode", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=True),
            sa.Column("superseded_by_transition_id", sa.Integer(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_policy_version_id"], ["policy_versions.id"]),
            sa.ForeignKeyConstraint(["target_policy_version_id"], ["policy_versions.id"]),
            sa.ForeignKeyConstraint(["superseded_by_transition_id"], ["policy_transitions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not foreign_key_exists(
        "policy_versions",
        "fk_policy_versions_created_by_transition_id",
    ):
        with op.batch_alter_table("policy_versions", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_policy_versions_created_by_transition_id",
                "policy_transitions",
                ["created_by_transition_id"],
                ["id"],
            )

    if not index_exists("policy_versions", "ix_policy_versions_class_id"):
        op.create_index("ix_policy_versions_class_id", "policy_versions", ["class_id"], unique=False)

    if not index_exists("policy_versions", "ix_policy_versions_class_domain_active"):
        op.create_index(
            "ix_policy_versions_class_domain_active",
            "policy_versions",
            ["class_id", "domain", "is_active"],
            unique=False,
        )

    if not index_exists("policy_transitions", "ix_policy_transitions_class_id"):
        op.create_index("ix_policy_transitions_class_id", "policy_transitions", ["class_id"], unique=False)

    if not index_exists("policy_transitions", "ix_policy_transitions_correlation_id"):
        op.create_index(
            "ix_policy_transitions_correlation_id",
            "policy_transitions",
            ["correlation_id"],
            unique=False,
        )

    if not index_exists("policy_transitions", "ix_policy_transitions_class_domain_status"):
        op.create_index(
            "ix_policy_transitions_class_domain_status",
            "policy_transitions",
            ["class_id", "domain", "status"],
            unique=False,
        )


def downgrade():
    for fk in get_foreign_keys_by_column("policy_versions", "created_by_transition_id"):
        with op.batch_alter_table("policy_versions", schema=None) as batch_op:
            batch_op.drop_constraint(fk["name"], type_="foreignkey")

    for index_name in (
        "ix_policy_transitions_class_domain_status",
        "ix_policy_transitions_correlation_id",
        "ix_policy_transitions_class_id",
    ):
        if index_exists("policy_transitions", index_name):
            op.drop_index(index_name, table_name="policy_transitions")

    for index_name in (
        "ix_policy_versions_class_domain_active",
        "ix_policy_versions_class_id",
    ):
        if index_exists("policy_versions", index_name):
            op.drop_index(index_name, table_name="policy_versions")

    if table_exists("policy_transitions"):
        op.drop_table("policy_transitions")

    if table_exists("policy_versions"):
        op.drop_table("policy_versions")

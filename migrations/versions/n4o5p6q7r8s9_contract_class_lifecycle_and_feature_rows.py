"""Contract class lifecycle and move feature enablement to row existence

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-09 22:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


FEATURE_COLUMNS = (
    ("payroll", "payroll_enabled"),
    ("insurance", "insurance_enabled"),
    ("banking", "banking_enabled"),
    ("rent", "rent_enabled"),
    ("hall_pass", "hall_pass_enabled"),
    ("store", "store_enabled"),
)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists("class_features"):
        op.create_table(
            "class_features",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("feature_name", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["class_id"], ["class_economies.class_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("class_id", "feature_name", name="uq_class_features_class_feature"),
            sa.CheckConstraint(
                "feature_name IN ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')",
                name="ck_class_features_feature_name",
            ),
        )
    if not _index_exists("class_features", "ix_class_features_class_id"):
        op.create_index("ix_class_features_class_id", "class_features", ["class_id"], unique=False)
    if not _index_exists("class_features", "ix_class_features_feature_name"):
        op.create_index("ix_class_features_feature_name", "class_features", ["feature_name"], unique=False)

    for feature_name, column_name in FEATURE_COLUMNS:
        if _column_exists("feature_settings", column_name):
            bind.execute(
                sa.text(f"""
                    INSERT INTO class_features (class_id, feature_name, created_at)
                    SELECT ce.class_id, :feature_name, COALESCE(fs.updated_at, ce.created_at, CURRENT_TIMESTAMP)
                    FROM class_economies ce
                    LEFT JOIN feature_settings fs ON fs.class_id = ce.class_id
                    WHERE fs.class_id IS NULL OR fs.{column_name} IS TRUE
                    ON CONFLICT (class_id, feature_name) DO NOTHING
                """),
                {"feature_name": feature_name},
            )
        else:
            bind.execute(
                sa.text("""
                    INSERT INTO class_features (class_id, feature_name, created_at)
                    SELECT ce.class_id, :feature_name, COALESCE(ce.created_at, CURRENT_TIMESTAMP)
                    FROM class_economies ce
                    ON CONFLICT (class_id, feature_name) DO NOTHING
                """),
                {"feature_name": feature_name},
            )

    with op.batch_alter_table("feature_settings") as batch_op:
        for _, column_name in FEATURE_COLUMNS:
            if _column_exists("feature_settings", column_name):
                batch_op.drop_column(column_name)
        if _column_exists("feature_settings", "bug_reports_enabled"):
            batch_op.drop_column("bug_reports_enabled")
        if _column_exists("feature_settings", "bug_rewards_enabled"):
            batch_op.drop_column("bug_rewards_enabled")

    with op.batch_alter_table("class_memberships") as batch_op:
        if _column_exists("class_memberships", "status"):
            batch_op.drop_column("status")

    with op.batch_alter_table("class_economies") as batch_op:
        if _column_exists("class_economies", "status"):
            batch_op.drop_column("status")
        if _column_exists("class_economies", "is_active"):
            batch_op.drop_column("is_active")
        if _column_exists("class_economies", "archived_at"):
            batch_op.drop_column("archived_at")


def downgrade() -> None:
    with op.batch_alter_table("class_economies") as batch_op:
        if not _column_exists("class_economies", "archived_at"):
            batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        if not _column_exists("class_economies", "is_active"):
            batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        if not _column_exists("class_economies", "status"):
            batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))

    with op.batch_alter_table("class_memberships") as batch_op:
        if not _column_exists("class_memberships", "status"):
            batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))

    with op.batch_alter_table("feature_settings") as batch_op:
        for _, column_name in FEATURE_COLUMNS:
            if not _column_exists("feature_settings", column_name):
                batch_op.add_column(sa.Column(column_name, sa.Boolean(), nullable=False, server_default=sa.text("true")))
        if not _column_exists("feature_settings", "bug_reports_enabled"):
            batch_op.add_column(sa.Column("bug_reports_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        if not _column_exists("feature_settings", "bug_rewards_enabled"):
            batch_op.add_column(sa.Column("bug_rewards_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    for feature_name, column_name in FEATURE_COLUMNS:
        bind = op.get_bind()
        bind.execute(
            sa.text(f"""
                UPDATE feature_settings fs
                SET {column_name} = EXISTS (
                    SELECT 1
                    FROM class_features cf
                    WHERE cf.class_id = fs.class_id
                      AND cf.feature_name = :feature_name
                )
            """),
            {"feature_name": feature_name},
        )

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE feature_settings SET bug_reports_enabled = TRUE, bug_rewards_enabled = TRUE"))

    if _index_exists("class_features", "ix_class_features_feature_name"):
        op.drop_index("ix_class_features_feature_name", table_name="class_features")
    if _index_exists("class_features", "ix_class_features_class_id"):
        op.drop_index("ix_class_features_class_id", table_name="class_features")
    if _table_exists("class_features"):
        op.drop_table("class_features")

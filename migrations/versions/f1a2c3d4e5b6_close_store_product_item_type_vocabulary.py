"""close the store_products.item_type vocabulary with a check constraint

Every read path projects ``item_type`` through
``StorePolicyResolver._ITEM_TYPE_TO_ENTITLEMENT_TYPE``. An unmapped value
therefore raises ``PolicyValidationError`` for the whole class's policy list,
not just for the row that carries it, so the catalog vocabulary is closed at the
schema level as well as at the publication seam
(``store_service._validate_definition``).

``b7c41e9a2f30`` now carries the same constraint in its ``create_table``, which
covers a database built from scratch. This revision is what carries it to a
database that already ran that revision.

Revision ID: f1a2c3d4e5b6
Revises: e1f2a3b4c5d7
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2c3d4e5b6"
down_revision = "e1f2a3b4c5d7"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "ck_store_products_item_type"
CANONICAL_ITEM_TYPES = ("immediate", "delayed", "collective", "hall_pass", "privilege")


def table_exists(table_name):
    """Check if a table exists."""
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def check_constraint_exists(table_name, constraint_name):
    """Check if a named CHECK constraint exists on a table."""
    try:
        rows = op.get_bind().execute(
            sa.text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_name = :t AND constraint_name = :c "
                "AND constraint_type = 'CHECK'"
            ),
            {"t": table_name, "c": constraint_name},
        )
        return rows.first() is not None
    except Exception:
        return False


def _values_sql():
    return ", ".join(f"'{value}'" for value in CANONICAL_ITEM_TYPES)


def upgrade():
    if not table_exists("store_products"):
        print("⚠️  store_products does not exist, skipping...")
        return
    if check_constraint_exists("store_products", CONSTRAINT_NAME):
        print(f"⚠️  {CONSTRAINT_NAME} already exists, skipping...")
        return

    # A row outside the vocabulary cannot be repaired automatically — no other
    # column says what the teacher meant — and it is already unreadable through
    # the resolver. Fail loudly with the offending values rather than adding the
    # constraint NOT VALID and leaving the class broken but unmarked.
    offenders = op.get_bind().execute(
        sa.text(
            "SELECT DISTINCT item_type FROM store_products "
            f"WHERE item_type NOT IN ({_values_sql()})"
        )
    ).fetchall()
    if offenders:
        raise RuntimeError(
            "store_products holds item_type values outside the catalog "
            f"vocabulary: {sorted(row[0] for row in offenders)}. These rows are "
            "already unresolvable through StorePolicyResolver and must be "
            "corrected before this constraint can be applied."
        )

    op.create_check_constraint(
        CONSTRAINT_NAME,
        "store_products",
        f"item_type IN ({_values_sql()})",
    )
    print(f"✅ Added {CONSTRAINT_NAME} to store_products")


def downgrade():
    if table_exists("store_products") and check_constraint_exists(
        "store_products", CONSTRAINT_NAME
    ):
        op.drop_constraint(CONSTRAINT_NAME, "store_products", type_="check")
        print(f"❌ Dropped {CONSTRAINT_NAME} from store_products")
    else:
        print(f"⚠️  {CONSTRAINT_NAME} does not exist, skipping...")

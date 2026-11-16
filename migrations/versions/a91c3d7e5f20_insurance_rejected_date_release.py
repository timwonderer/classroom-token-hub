"""Release rejected insurance dates without deleting evidence.

Revision ID: a91c3d7e5f20
Revises: e3b7c1d9a2f4
DOM-STORE-001 v5.9: active reservations serialize on the GRANTED row.
Downgrade refuses if historical re-filings cannot satisfy the old uniqueness.
"""
from alembic import op
import sqlalchemy as sa

revision = "a91c3d7e5f20"
down_revision = "e3b7c1d9a2f4"
branch_labels = None
depends_on = None

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



def upgrade():
    for constraint in sa.inspect(op.get_bind()).get_unique_constraints("insurance_claim_productivity_dates"):
        if set(constraint["column_names"]) == {"entitlement_id", "claim_date"}:
            op.drop_constraint(constraint["name"], "insurance_claim_productivity_dates", type_="unique")


def downgrade():
    if not constraint_exists("insurance_claim_productivity_dates", "uq_icpd_entitlement_date"):
        duplicate = op.get_bind().execute(sa.text(
            "SELECT 1 FROM insurance_claim_productivity_dates "
            "GROUP BY entitlement_id, claim_date HAVING count(*) > 1 LIMIT 1"
        )).first()
        if duplicate:
            raise RuntimeError("Cannot restore permanent date uniqueness: re-filed claim history exists")
        op.create_unique_constraint("uq_icpd_entitlement_date", "insurance_claim_productivity_dates", ["entitlement_id", "claim_date"])

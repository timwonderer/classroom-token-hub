"""Allow waiting_period_days on every insurance type

ck_insurance_policies_type_subset previously forbade waiting_period_days for
TRANSACTION and PRODUCTIVITY policies, citing "SPEC §4.5.3-§4.5.5" in both the
model comment and the mirroring FEAT-CLASS-003 per-type gate. That section
does not exist in any document under docs/ -- the restriction was invented in
the same commit that introduced this schema, with no normative document
backing it.

Operator decision 2026-09-21: waiting_period_days should be settable on every
insurance type, not necessarily enforced on every type. Only NON_MONETARY
currently gates claim eligibility on it (FEAT-STOR-003); TRANSACTION and
PRODUCTIVITY may now store a value without it being forbidden, and without
anything yet reading it for those two types.

This is a constraint RELAX (widen what is permitted), so no existing row can
violate it -- every row that satisfied the old, narrower constraint still
satisfies this one. The downgrade restores the narrower constraint, which
CAN fail if a TRANSACTION or PRODUCTIVITY row has since been saved with
waiting_period_days set; that data loss is inherent to the downgrade
direction, not to this migration.

Revision ID: f2b8c7e4a916
Revises: e7a4c2d9f013
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'f2b8c7e4a916'
down_revision = 'e7a4c2d9f013'
branch_labels = None
depends_on = None


CONSTRAINT_NAME = 'ck_insurance_policies_type_subset'

OLD_CONDITION = (
    "("
    "  insurance_type = 'TRANSACTION' AND"
    "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
    "  claims_per_week_equivalent IS NOT NULL AND claim_window_days IS NOT NULL AND"
    "  claimable_dates_per_week_equivalent IS NULL AND waiting_period_days IS NULL"
    ") OR ("
    "  insurance_type = 'PRODUCTIVITY' AND"
    "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
    "  claimable_dates_per_week_equivalent IS NOT NULL AND"
    "  claims_per_week_equivalent IS NULL AND claim_window_days IS NULL AND"
    "  waiting_period_days IS NULL"
    ") OR ("
    "  insurance_type = 'NON_MONETARY' AND"
    "  claims_per_week_equivalent IS NOT NULL AND waiting_period_days IS NOT NULL AND"
    "  reimbursement_percentage IS NULL AND payout_multiple IS NULL AND"
    "  claim_window_days IS NULL AND claimable_dates_per_week_equivalent IS NULL"
    ")"
)

NEW_CONDITION = (
    "("
    "  insurance_type = 'TRANSACTION' AND"
    "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
    "  claims_per_week_equivalent IS NOT NULL AND claim_window_days IS NOT NULL AND"
    "  claimable_dates_per_week_equivalent IS NULL"
    ") OR ("
    "  insurance_type = 'PRODUCTIVITY' AND"
    "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
    "  claimable_dates_per_week_equivalent IS NOT NULL AND"
    "  claims_per_week_equivalent IS NULL AND claim_window_days IS NULL"
    ") OR ("
    "  insurance_type = 'NON_MONETARY' AND"
    "  claims_per_week_equivalent IS NOT NULL AND waiting_period_days IS NOT NULL AND"
    "  reimbursement_percentage IS NULL AND payout_multiple IS NULL AND"
    "  claim_window_days IS NULL AND claimable_dates_per_week_equivalent IS NULL"
    ")"
)


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def check_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = :t AND constraint_name = :c AND constraint_type = 'CHECK'"
        ),
        {"t": table_name, "c": constraint_name},
    ).scalar()
    return result is not None


def upgrade():
    if not table_exists('insurance_policies'):
        print("⚠️  insurance_policies does not exist, skipping...")
        return

    if check_constraint_exists('insurance_policies', CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, 'insurance_policies', type_='check')
        print(f"❌ Dropped {CONSTRAINT_NAME} (narrow form)")
    else:
        print(f"ℹ️  {CONSTRAINT_NAME} not present, nothing to drop")

    op.create_check_constraint(CONSTRAINT_NAME, 'insurance_policies', NEW_CONDITION)
    print(f"✅ Created {CONSTRAINT_NAME} (waiting_period_days permitted on every type)")


def downgrade():
    if not table_exists('insurance_policies'):
        print("⚠️  insurance_policies does not exist, skipping...")
        return

    if check_constraint_exists('insurance_policies', CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, 'insurance_policies', type_='check')
        print(f"❌ Dropped {CONSTRAINT_NAME} (permissive form)")

    # This can fail if a TRANSACTION/PRODUCTIVITY row has waiting_period_days
    # set -- that is inherent to narrowing the constraint back, not a defect
    # in this migration. SOP-DB-001 SS XIV: restore the pre-upgrade snapshot
    # rather than treating a downgrade failure here as something to work
    # around.
    op.create_check_constraint(CONSTRAINT_NAME, 'insurance_policies', OLD_CONDITION)
    print(f"✅ Restored {CONSTRAINT_NAME} (narrow form)")

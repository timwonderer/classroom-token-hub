"""Immutable attributable recovery and exact version-three creation evidence.

DOM-LED-001 VII.1A, DOM-OPS-002 5.4. Historical rows receive no fabricated
recovery lineage or signatures; NULL metadata remains unavailable evidence.
"""

from alembic import op
import sqlalchemy as sa
from importlib import import_module

revision = "f8b2d6e0a410"
down_revision = "e7c2a9d4f610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ledger_transaction",
        sa.Column("compensation_origin_locator", sa.String(128), nullable=True),
    )
    op.add_column(
        "ledger_transaction",
        sa.Column("compensation_amount_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ledger_transaction",
        sa.Column("correction_intent_locator", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_ledger_transaction_compensation_origin_locator",
        "ledger_transaction",
        ["compensation_origin_locator"],
    )
    op.create_check_constraint(
        "ck_ledger_attributable_recovery",
        "ledger_transaction",
        "compensation_amount_cents IS NULL OR (compensation_amount_cents >= 0 AND (compensation_amount_cents = 0 OR (amount_cents = -compensation_amount_cents AND compensation_origin_locator IS NOT NULL AND correction_intent_locator IS NOT NULL)))",
    )
    op.create_index(
        "uq_ledger_recovery_intent",
        "ledger_transaction",
        [
            "class_id",
            "target_seat_id",
            "compensation_origin_locator",
            "correction_intent_locator",
        ],
        unique=True,
        postgresql_where=sa.text("compensation_amount_cents > 0"),
    )
    if op.get_bind().dialect.name != "postgresql":
        return
    prior = import_module(
        "migrations.versions.e7c2a9d4f610_derive_ledger_posting_from_reconciliation"
    )
    immutable = prior.IMMUTABLE + (
        "compensation_origin_locator",
        "compensation_amount_cents",
        "correction_intent_locator",
    )
    checks = "\n".join(
        f"IF OLD.{f} IS DISTINCT FROM NEW.{f} THEN RAISE EXCEPTION 'Immutable Ledger field: {f}'; END IF;"
        for f in immutable
    )
    checks += "\n" + "\n".join(
        f"IF OLD.{f} IS NOT NULL AND OLD.{f} IS DISTINCT FROM NEW.{f} THEN RAISE EXCEPTION 'Write-once Ledger field: {f}'; END IF;"
        for f in prior.WRITE_ONCE
    )
    op.execute(
        sa.text(
            f"CREATE OR REPLACE FUNCTION prevent_ledger_transaction_rewrite() RETURNS TRIGGER AS $$ BEGIN {checks} RETURN NEW; END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            """CREATE FUNCTION enforce_ledger_recovery_cap() RETURNS TRIGGER AS $$
    DECLARE origin ledger_transaction%ROWTYPE; recovered bigint;
    BEGIN
      IF NEW.compensation_amount_cents IS NULL OR NEW.compensation_amount_cents < 0 THEN
        RAISE EXCEPTION 'New Ledger effect requires explicit attributable recovery';
      END IF;
      IF NEW.compensation_amount_cents = 0 THEN
        IF NEW.type='REVERSAL' AND NEW.amount_cents<0 THEN RAISE EXCEPTION 'Credit reversal requires attributable recovery'; END IF;
        IF NEW.compensation_origin_locator IS NOT NULL OR NEW.correction_intent_locator IS NOT NULL THEN
          RAISE EXCEPTION 'Non-recovery Ledger effect cannot claim recovery lineage';
        END IF; RETURN NEW;
      END IF;
      IF NEW.compensation_origin_locator !~ '^ledger-credit:v1:[1-9][0-9]*$' THEN RAISE EXCEPTION 'Invalid Ledger origin locator'; END IF;
      SELECT * INTO origin FROM ledger_transaction WHERE id=split_part(NEW.compensation_origin_locator,':',3)::bigint
        AND class_id=NEW.class_id AND target_seat_id=NEW.target_seat_id AND seat_id=NEW.seat_id FOR UPDATE;
      IF NOT FOUND OR origin.amount_cents <= 0 OR origin.account_type IS DISTINCT FROM NEW.account_type
        OR NEW.amount_cents <> -NEW.compensation_amount_cents THEN RAISE EXCEPTION 'Invalid attributable Ledger recovery'; END IF;
      IF EXISTS(SELECT 1 FROM ledger_transaction prior WHERE prior.class_id=NEW.class_id AND prior.seat_id=NEW.seat_id
        AND prior.amount_cents<0 AND prior.posting_sequence>origin.posting_sequence AND COALESCE(prior.lineage_version,0)<3
        AND (prior.type IN ('REVERSAL','payroll','payroll_correction') OR prior.correlation_id=origin.correlation_id
          OR prior.id=origin.reversal_transaction_id OR prior.original_transaction_id=origin.id)) THEN
        RAISE EXCEPTION 'Historical Ledger recovery provenance unavailable'; END IF;
      SELECT COALESCE(SUM(compensation_amount_cents),0) INTO recovered FROM ledger_transaction
        WHERE class_id=NEW.class_id AND target_seat_id=NEW.target_seat_id AND compensation_origin_locator=NEW.compensation_origin_locator;
      IF NEW.type='REVERSAL' AND (recovered<>0 OR NEW.compensation_amount_cents<>origin.amount_cents
        OR NEW.original_transaction_id IS DISTINCT FROM origin.id) THEN
        RAISE EXCEPTION 'Credit REVERSAL requires the uncompensated whole original transaction'; END IF;
      IF recovered + NEW.compensation_amount_cents > origin.amount_cents THEN RAISE EXCEPTION 'Ledger recovery cap exceeded'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql"""
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER ledger_recovery_cap BEFORE INSERT ON ledger_transaction FOR EACH ROW EXECUTE FUNCTION enforce_ledger_recovery_cap()"
        )
    )
    op.execute(
        sa.text(
            """CREATE FUNCTION require_ledger_v3_creation_lineage() RETURNS TRIGGER AS $$
    DECLARE saved ledger_transaction%ROWTYPE;
    BEGIN
      SELECT * INTO saved FROM ledger_transaction WHERE id=NEW.id;
      IF NOT FOUND THEN RETURN NEW; END IF;
      IF saved.lineage_event_id IS NULL OR saved.lineage_token IS NULL OR saved.lineage_version <> 3
        OR NOT EXISTS(SELECT 1 FROM audit_events a WHERE a.id=saved.lineage_event_id AND a.table_name='ledger_transaction'
          AND a.row_pk=saved.id::text AND a.class_id=saved.class_id AND a.operation='INSERT'
          AND a.chain_scope='class:'||saved.class_id AND a.signature_version=3 AND a.hmac_signature=saved.lineage_token)
        THEN RAISE EXCEPTION 'New Ledger effect requires canonical version-three creation lineage'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql"""
        )
    )
    op.execute(
        sa.text(
            "CREATE CONSTRAINT TRIGGER ledger_v3_creation_lineage_required AFTER INSERT ON ledger_transaction DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_ledger_v3_creation_lineage()"
        )
    )


def downgrade():
    raise RuntimeError(
        "Immutable recovery provenance cannot be removed; use a reviewed forward migration."
    )

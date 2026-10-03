"""Protect payroll creation lineage without rewriting historical evidence.

DOM-PROD-001 XI.3; DOM-OPS-002 5.4 / 6.1; INV-ARC-016 V / IX.
Nullable columns retain historical UNVERIFIED rows. No backfill is performed.
The only UPDATE permitted is complete linkage initialization on the INSERT's
creating transaction, with all business columns byte-for-byte unchanged.
A deferred INSERT trigger reads the final row at commit; failures roll back
payroll, audit chain, and monetary effects together. Existing delete guards
continue to govern seat/class destruction.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd6b1e0c4a825'
down_revision = 'a4b50fee84c3'
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column('lineage_event_id', sa.Integer(), nullable=True),
        sa.Column('lineage_token', sa.String(64), nullable=True),
        sa.Column('lineage_version', sa.Integer(), nullable=True),
    ):
        op.add_column('payroll_event', column)
    op.create_index('ix_payroll_event_lineage_event_id', 'payroll_event', ['lineage_event_id'])
    op.execute("""
        CREATE FUNCTION payroll_creator_is_uncommitted(row_xid xid)
        RETURNS boolean AS $$
        DECLARE current_xid bigint := txid_current();
                distance bigint;
                expanded bigint;
        BEGIN
            -- Expand PostgreSQL's 32-bit row xmin to the nearest xid8 epoch.
            -- A savepoint xid can be greater than its parent's txid_current;
            -- snapshot xmax is the parent xid and is not an allocation bound.
            distance := row_xid::text::bigint - (current_xid % 4294967296);
            IF distance > 2147483647 THEN distance := distance - 4294967296; END IF;
            IF distance < -2147483648 THEN distance := distance + 4294967296; END IF;
            expanded := current_xid + distance;
            IF expanded < 3 THEN RETURN false; END IF;
            RETURN COALESCE(pg_xact_status(expanded::text::xid8) = 'in progress', false);
        END;
        $$ LANGUAGE plpgsql;
        CREATE OR REPLACE FUNCTION prevent_payroll_event_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NOT payroll_creator_is_uncommitted(OLD.xmin)
               OR OLD.lineage_event_id IS NOT NULL
               OR OLD.lineage_token IS NOT NULL
               OR OLD.lineage_version IS NOT NULL
               OR NEW.lineage_event_id IS NULL
               OR NEW.lineage_token IS NULL
               OR NEW.lineage_version IS NULL
               OR NEW.summary_json::text IS DISTINCT FROM OLD.summary_json::text
               OR (to_jsonb(NEW) - ARRAY['lineage_event_id','lineage_token','lineage_version'])
                    IS DISTINCT FROM
                  (to_jsonb(OLD) - ARRAY['lineage_event_id','lineage_token','lineage_version'])
            THEN
                RAISE EXCEPTION 'payroll_event is append-only; lineage initializes once in the creating transaction only';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE FUNCTION require_payroll_lineage_at_insert()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.lineage_event_id IS NOT NULL OR NEW.lineage_token IS NOT NULL
               OR NEW.lineage_version IS NOT NULL THEN
                RAISE EXCEPTION 'payroll lineage must initialize after INSERT';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER payroll_event_lineage_initially_empty
        BEFORE INSERT ON payroll_event FOR EACH ROW
        EXECUTE FUNCTION require_payroll_lineage_at_insert();
        CREATE FUNCTION require_payroll_lineage_at_commit()
        RETURNS TRIGGER AS $$
        DECLARE final_row payroll_event%ROWTYPE;
        BEGIN
            SELECT * INTO final_row FROM payroll_event WHERE id = NEW.id;
            -- Existing lifecycle guards alone authorize removal; an INSERT
            -- followed by lawful seat/class destruction leaves no row to attest.
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF final_row.lineage_event_id IS NULL
               OR final_row.lineage_token IS NULL
               OR final_row.lineage_version IS NULL
               OR NOT EXISTS (
                   SELECT 1 FROM audit_events a
                   WHERE a.id = final_row.lineage_event_id
                     AND payroll_creator_is_uncommitted(a.xmin)
                     AND a.table_name = 'payroll_event'
                     AND a.row_pk = final_row.id::text
                     AND a.operation = 'INSERT'
                     AND a.class_id = final_row.class_id
                     AND a.chain_scope = 'class:' || final_row.class_id
                     AND a.hmac_signature = final_row.lineage_token
                     AND a.signature_version = final_row.lineage_version
                     AND (a.feat_id IN ('FEAT-PROD-003','FEAT-PROD-004','FEAT-PROD-005')
                          OR (a.feat_id = 'FEAT-STOR-003' AND final_row.payroll_event_type = 'manual_credit'))
               ) THEN
                RAISE EXCEPTION 'new payroll_event requires matching creation audit lineage before commit';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        CREATE CONSTRAINT TRIGGER payroll_event_creation_lineage_required
        AFTER INSERT ON payroll_event DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION require_payroll_lineage_at_commit();
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER payroll_event_creation_lineage_required ON payroll_event;
        DROP TRIGGER payroll_event_lineage_initially_empty ON payroll_event;
        DROP FUNCTION require_payroll_lineage_at_commit();
        DROP FUNCTION require_payroll_lineage_at_insert();
        DROP FUNCTION payroll_creator_is_uncommitted(xid);
        CREATE OR REPLACE FUNCTION prevent_payroll_event_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'payroll_event is append-only (DOM-PROD-001 XI.3)';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.drop_index('ix_payroll_event_lineage_event_id', table_name='payroll_event')
    for name in ('lineage_version', 'lineage_token', 'lineage_event_id'):
        op.drop_column('payroll_event', name)

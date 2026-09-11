"""Enforce INV-LED-002 immutable facts on ledger_transaction in the database

`_guard_ledger_immutability` in `app/models.py` is a SQLAlchemy `before_update`
listener, and a mapper-level listener only fires for ORM unit-of-work updates.
A Core `update()`, a bulk `Query.update()`, `db.session.execute(text(...))`, a
migration, a maintenance script, or a `psql` session all bypass it completely.
That is not hypothetical here: `tests/test_insurance_transaction_economics.py`
backdates a posted row precisely by going around the mapper, and it works.

DOM-LED-001 §VII states the protected fields are immutable "once inserted",
without qualifying by access path, so the enforcement has to live where the
write lands. This mirrors the ORM guard in plpgsql:

  * the monetary and identity facts may not change at all;
  * the write-once columns may go NULL -> value exactly once (INV-LED-007 for
    `posting_sequence`/`posted_at`, INV-LED-013 for `reversal_transaction_id`,
    plus `idempotency_key` and the three lineage columns);
  * `status` may only advance PENDING -> POSTED, which is the sole transition
    `ledger_settlement_service` performs. INV-LED-003 requires a void or a
    reversal to arrive as a **new linked row**, so an in-place standing change
    is a correction with its history deleted;
  * `feat_code` is free, because `_enforce_transaction_integrity` restamps it
    with the FEAT performing the lawful update.

Scope note (INV-ARC-017): this covers UPDATE only, and per DOM-LED-001 §VII.2
that is the correct and complete scope rather than an unfinished one.
Immutability is a rule about *mutating a surviving class universe*.
`ledger_transaction.seat_id`, `target_seat_id` and
`actor_seat_id` all carry `ON DELETE CASCADE`, so lawful seat destruction
(`delete_seat_with_profile`, reached from `remove_pending_student_seat` and
from FEAT-CLASS-002) removes the actor and every economic effect attributable
to that actor atomically. That is lifecycle destruction, not an edit to
surviving financial history: there is never a state in which the seat is gone
but the seat's money remains. A generic `BEFORE DELETE` guard here would
encode the inverse rule — that ledger history must outlive the entity whose
existence gives it meaning — and would abort lawful student removal.

`status` is compared as the enum **label**, which is the member NAME:
`db.Enum(TransactionStatus)` is declared with no `values_callable`, so the
`transactionstatus` labels are PENDING / POSTED / VOID, not the lowercase
`.value` strings.

Refs C-1.

Revision ID: f1a9c3e60b72
Revises: b7d3e2064c15
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'f1a9c3e60b72'
down_revision = 'b7d3e2064c15'
branch_labels = None
depends_on = None


# --------------------------------------------------------------------------
# Idempotency helpers (see migrations/migration_template.py.mako)
# --------------------------------------------------------------------------

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def trigger_exists(table_name, trigger_name):
    """Check whether a trigger exists ON THIS TABLE.

    Scoped by table on purpose: Postgres enforces trigger-name uniqueness per
    relation, not per database, so a name-only match could report a same-named
    trigger on another table as this one and skip installing the protection
    here.
    """
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgrelid = to_regclass(:table_name) "
                "AND tgname = :trigger_name "
                "AND NOT tgisinternal"
            ),
            {"table_name": table_name, "trigger_name": trigger_name},
        ).fetchone()
        return result is not None
    except Exception:
        return False


def function_exists(function_name):
    """Check whether the zero-argument trigger function of this name exists.

    Matched by exact identity via `to_regprocedure` rather than by name;
    `pg_proc.proname` repeats across schemas and overloads.
    """
    conn = op.get_bind()
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM pg_proc p "
                "WHERE p.oid = to_regprocedure(:signature) "
                "AND p.prorettype = 'trigger'::regtype"
            ),
            {"signature": f"{function_name}()"},
        ).fetchone()
        return result is not None
    except Exception:
        return False


UPDATE_TRIGGER = "ledger_transaction_no_rewrite"
GUARD_FUNCTION = "prevent_ledger_transaction_rewrite"

# Kept in the same order as `_LEDGER_IMMUTABLE_FIELDS` / `_LEDGER_WRITE_ONCE_FIELDS`
# in app/models.py. `tests/dom/ledger/test_ledger_immutable_facts.py` asserts the
# two stay in agreement, so drift fails a test rather than silently opening a
# column at one layer and not the other.
_IMMUTABLE_COLUMNS = (
    'account_type', 'actor_seat_id', 'amount', 'amount_cents', 'class_id',
    'command_reservation_id', 'compensation_subtype', 'correlation_id',
    'date_funds_available', 'description', 'effective_at', 'join_code',
    'mechanism', 'original_transaction_id', 'policy_id', 'seat_id',
    'target_seat_id', 'timestamp', 'type', 'user_id',
)

_WRITE_ONCE_COLUMNS = (
    'idempotency_key', 'lineage_event_id', 'lineage_token', 'lineage_version',
    'posted_at', 'posting_sequence', 'reversal_transaction_id',
)


def _guard_body():
    """Compose the plpgsql body from the two column sets."""
    immutable_checks = "\n".join(
        f"""
                IF OLD.{column} IS DISTINCT FROM NEW.{column} THEN
                    RAISE EXCEPTION
                        'ledger_transaction.{column} is immutable (INV-LED-002). '
                        'Record a linked correcting transaction instead of editing this row.';
                END IF;"""
        for column in _IMMUTABLE_COLUMNS
    )

    write_once_checks = "\n".join(
        f"""
                IF OLD.{column} IS NOT NULL
                   AND OLD.{column} IS DISTINCT FROM NEW.{column} THEN
                    RAISE EXCEPTION
                        'ledger_transaction.{column} is write-once (INV-LED-002). '
                        'It may be assigned to a NULL column once and never rewritten.';
                END IF;"""
        for column in _WRITE_ONCE_COLUMNS
    )

    return f"""
            CREATE FUNCTION {GUARD_FUNCTION}()
            RETURNS TRIGGER AS $$
            BEGIN
{immutable_checks}
{write_once_checks}

                -- Settlement advances PENDING to POSTED. Every other change of
                -- standing is recorded as a new linked transaction (INV-LED-003),
                -- never as an edit to the row whose standing changed.
                IF OLD.status IS DISTINCT FROM NEW.status
                   AND NOT (OLD.status = 'PENDING' AND NEW.status = 'POSTED') THEN
                    RAISE EXCEPTION
                        'ledger_transaction.status may not move % -> % (INV-LED-002). '
                        'Settlement advances PENDING to POSTED; every other change of '
                        'standing is recorded as a new linked transaction.',
                        OLD.status, NEW.status;
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
    """


def upgrade():
    """Attach the field-level rewrite guard to ledger_transaction."""
    conn = op.get_bind()

    if not function_exists(GUARD_FUNCTION):
        conn.execute(text(_guard_body()))
        print(f"✅ Created function {GUARD_FUNCTION}()")
    else:
        print(f"ℹ️  Function {GUARD_FUNCTION}() already exists, leaving as-is...")

    if not table_exists("ledger_transaction"):
        print("⚠️  ledger_transaction not found; skipping trigger creation")
        return

    if not trigger_exists("ledger_transaction", UPDATE_TRIGGER):
        conn.execute(text(
            f"CREATE TRIGGER {UPDATE_TRIGGER} "
            "BEFORE UPDATE ON ledger_transaction "
            f"FOR EACH ROW EXECUTE FUNCTION {GUARD_FUNCTION}();"
        ))
        print(f"✅ Created TRIGGER {UPDATE_TRIGGER}")
    else:
        print(f"ℹ️  TRIGGER {UPDATE_TRIGGER} already exists, skipping...")


def downgrade():
    """Drop only what this migration created.

    Both the trigger and the function are introduced here and used by nothing
    else, so removing them is a truthful inverse.
    """
    conn = op.get_bind()

    if table_exists("ledger_transaction"):
        conn.execute(text(f"DROP TRIGGER IF EXISTS {UPDATE_TRIGGER} ON ledger_transaction;"))
        print(f"❌ Dropped TRIGGER {UPDATE_TRIGGER}")

    conn.execute(text(f"DROP FUNCTION IF EXISTS {GUARD_FUNCTION}();"))
    print(f"❌ Dropped function {GUARD_FUNCTION}()")

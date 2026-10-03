from app.services.ledger_balance_query_service import (
    get_account_posting_boundary,
    reconstruct_available_balance,
    reconstruct_posted_balance,
    verify_available_balance,
    verify_posted_balance,
)
from app.services.ledger_transfer_service import verify_transfer
from app.feats.base import FEATContext
from app.extensions import db
from app.models import LedgerBalanceSnapshot
from app.services.ledger_posting_service import create_pending_transaction
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.ledger import provision_ledger_classroom, create_ledger_transfer_pair


def test_reconstruct_posted_balance_rejects_incomplete_scope():
    result = reconstruct_posted_balance("", 1, "checking")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"
    assert result.complete is False


def test_reconstruct_available_balance_rejects_incomplete_scope():
    result = reconstruct_available_balance("class-a", 1, "reserve")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"


def test_projection_verification_compares_against_canonical_history(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:projection"):
        create_pending_transaction(
            seat_id=seat.id, class_id=classroom.class_id,
            target_seat_id=seat.id, actor_seat_id=seat.id,
            mechanism="self",  amount=12,
            account_type="checking", type="Deposit", description="proof projection",
        )
        settle_balances(seat.id, classroom.class_id)

    assert verify_posted_balance(classroom.class_id, seat.id, "checking", get_account_posting_boundary(seat.id,classroom.class_id,"checking")).outcome == "PASS"
    assert verify_available_balance(classroom.class_id, seat.id, "checking", get_account_posting_boundary(seat.id,classroom.class_id,"checking")).outcome == "PASS"

    snapshot = LedgerBalanceSnapshot.query.filter_by(
        class_id=classroom.class_id, seat_id=seat.id, account_type="checking"
    ).one()
    with FEATContext("FEAT-LED-001", idempotency_key="proof:projection-corrupt"):
        snapshot.posted_balance_cents += 1
        db.session.flush()
    assert verify_posted_balance(classroom.class_id, seat.id, "checking", get_account_posting_boundary(seat.id,classroom.class_id,"checking")).code == "posted_balance_mismatch"


def test_verify_transfer_requires_scoped_correlation():
    result = verify_transfer("", "")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"


def test_verify_transfer_passes_for_posted_two_leg_transfer(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:valid-transfer"):
        withdrawal, deposit = create_ledger_transfer_pair(
            seat_id=seat.id,
            class_id=classroom.class_id,
            amount=10,
            from_account="checking",
            to_account="savings",
            withdraw_description="proof withdrawal",
            deposit_description="proof deposit",
        )
        settle_balances(seat.id, classroom.class_id)
        result = verify_transfer(classroom.class_id, withdrawal.correlation_id, {a:get_account_posting_boundary(seat.id,classroom.class_id,a) for a in ("checking","savings")})

    assert result.outcome == "PASS"
    assert result.leg_count == 2
    assert result.scope_consistent is True
    assert result.account_pair_valid is True
    assert result.equal_magnitude is True
    assert result.zero_sum is True
    assert result.posting_consistent is True


def test_reconstruct_posted_balance_does_not_depend_on_snapshot(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:balance-history"):
        transaction = create_pending_transaction(
            seat_id=seat.id,
            class_id=classroom.class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=12,
            account_type="checking",
            type="Deposit",
            description="proof balance history",
        )
        settle_balances(seat.id, classroom.class_id)

    snapshot = LedgerBalanceSnapshot.query.filter_by(
        class_id=classroom.class_id, seat_id=seat.id, account_type="checking"
    ).one()
    with FEATContext("FEAT-LED-001", idempotency_key="proof:corrupt-snapshot"):
        snapshot.posted_balance_cents = -999999
        db.session.flush()

    result = reconstruct_posted_balance(classroom.class_id, seat.id, "checking", transaction.posting_sequence)
    assert result.outcome == "PASS"
    assert result.reconstructed_cents == int(transaction.amount_cents)


def test_proof_requires_explicit_nonnegative_integer_boundary(app):
    classroom = provision_ledger_classroom("chemistry_p1",app)
    seat = classroom.students[0].seat
    for boundary in (None, True, False, -1, "1", 1.5):
        assert reconstruct_posted_balance(classroom.class_id,seat.id,"checking",boundary).outcome == "UNAVAILABLE"
        assert reconstruct_available_balance(classroom.class_id,seat.id,"checking",boundary).outcome == "UNAVAILABLE"
    assert reconstruct_posted_balance(classroom.class_id,seat.id,"checking",0).reconstructed_cents == 0


def test_stored_status_column_is_absent(app):
    from sqlalchemy import inspect
    assert "status" not in {column["name"] for column in inspect(db.engine).get_columns("ledger_transaction")}


def test_cursor_admission_is_scoped_and_rollback_preserves_pending(app):
    import pytest
    from app.models import TransactionStatus
    from app.utils.audit_verifier import verify_record_creation_lineage
    classroom = provision_ledger_classroom("chemistry_p1",app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001",idempotency_key="proof:scoped-cursor"):
        checking = create_pending_transaction(seat_id=seat.id,class_id=classroom.class_id,
            target_seat_id=seat.id,actor_seat_id=seat.id,mechanism="self",amount=5,
            account_type="checking",type="Deposit",description="Checking scope")
        savings = create_pending_transaction(seat_id=seat.id,class_id=classroom.class_id,
            target_seat_id=seat.id,actor_seat_id=seat.id,mechanism="self",amount=7,
            account_type="savings",type="Deposit",description="Savings scope")
    assert checking.posting_state == savings.posting_state == TransactionStatus.PENDING
    assert verify_record_creation_lineage("ledger_transaction",checking,classroom.class_id)
    with pytest.raises(RuntimeError,match="rollback admission"):
        with FEATContext("FEAT-LED-003",idempotency_key="proof:rollback-cursor"):
            settle_balances(seat.id,classroom.class_id)
            assert checking.posting_state == TransactionStatus.POSTED
            raise RuntimeError("rollback admission")
    assert checking.posting_state == savings.posting_state == TransactionStatus.PENDING
    assert checking.posted_at is None and savings.posted_at is None
    assert verify_record_creation_lineage("ledger_transaction",checking,classroom.class_id)
    with FEATContext("FEAT-LED-003",idempotency_key="proof:admit"):
        settle_balances(seat.id,classroom.class_id)
    checking_boundary=get_account_posting_boundary(seat.id,classroom.class_id,"checking")
    savings_boundary=get_account_posting_boundary(seat.id,classroom.class_id,"savings")
    assert checking_boundary == checking.posting_sequence
    assert savings_boundary == savings.posting_sequence
    assert reconstruct_posted_balance(classroom.class_id,seat.id,"checking",checking_boundary).reconstructed_cents == 500
    assert verify_record_creation_lineage("ledger_transaction",checking,classroom.class_id)
    assert verify_record_creation_lineage("ledger_transaction",savings,classroom.class_id)
    assert verify_posted_balance(classroom.class_id,seat.id,"checking",checking_boundary+1).code == "snapshot_boundary_mismatch"


import pytest

@pytest.mark.parametrize("sequence,state,cursor", [(None,"POSTED",None),(0,"PENDING",None),(1,"VOID",1),(2,"POSTED",1),(1,"POSTED",None),(1,"PENDING",1)])
def test_migration_preflight_locks_and_rejects_unproven_historical_state(app, monkeypatch,sequence,state,cursor):
    from importlib import import_module
    import pytest
    from sqlalchemy import text
    migration = import_module("migrations.versions.e7c2a9d4f610_derive_ledger_posting_from_reconciliation")
    with db.engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE ledger_transaction(class_id text,seat_id int,account_type text,posting_sequence bigint,status text) ON COMMIT DROP"))
        conn.execute(text("CREATE TEMP TABLE ledger_balance_snapshot(class_id text,seat_id int,account_type text,reconciled_through_posting_sequence bigint) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO ledger_transaction VALUES ('historical',1,'checking',:sequence,:state)"),dict(sequence=sequence,state=state))
        if cursor is not None:
            conn.execute(text("INSERT INTO ledger_balance_snapshot VALUES ('historical',1,'checking',:cursor)"),dict(cursor=cursor))
        monkeypatch.setattr(migration.op,"get_bind",lambda:conn)
        monkeypatch.setattr(migration.op,"execute",conn.execute)
        with pytest.raises(RuntimeError,match="historical sequence/admission evidence"):
            migration.upgrade()
        assert conn.execute(text("SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND mode='AccessExclusiveLock' AND relation IN ('pg_temp.ledger_transaction'::regclass,'pg_temp.ledger_balance_snapshot'::regclass)")).scalar() == 2
    with pytest.raises(RuntimeError,match="cannot be downgraded"):
        migration.downgrade()


def test_concurrent_creations_and_admission_preserve_sequence_and_audit(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.models import Transaction,TransactionStatus
    from app.utils.audit_verifier import verify_record_creation_lineage
    classroom = provision_ledger_classroom("chemistry_p1",app)
    seat_id,class_id=classroom.students[0].seat.id,classroom.class_id
    db.session.commit()
    rendezvous=Barrier(2)
    def create(index):
        with app.app_context():
            try:
                rendezvous.wait(timeout=10)
                with FEATContext("FEAT-LED-001",idempotency_key=f"concurrent-ledger:{index}"):
                    effect=create_pending_transaction(seat_id=seat_id,class_id=class_id,target_seat_id=seat_id,
                        actor_seat_id=seat_id,mechanism="self",amount=index+1,account_type="checking",
                        type="Deposit",description=f"Concurrent creation {index}")
                    settle_balances(seat_id,class_id)
                    effect_id=effect.id
                return effect_id
            finally:
                db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids=list(executor.map(create,(0,1)))
    db.session.expire_all()
    rows=Transaction.query.filter(Transaction.id.in_(ids)).all()
    assert len({row.posting_sequence for row in rows}) == 2
    assert all(row.posting_state == TransactionStatus.POSTED for row in rows)
    assert all(verify_record_creation_lineage("ledger_transaction",row,class_id) for row in rows)
    boundary=get_account_posting_boundary(seat_id,class_id,"checking")
    assert boundary == max(row.posting_sequence for row in rows)
    assert verify_posted_balance(class_id,seat_id,"checking",boundary).reconstructed_cents == 300


def test_migration_preflight_accepts_proven_admission_without_rewriting_data(app, monkeypatch):
    from importlib import import_module
    from sqlalchemy import text
    migration=import_module("migrations.versions.e7c2a9d4f610_derive_ledger_posting_from_reconciliation")
    with db.engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE ledger_transaction(class_id text,seat_id int,account_type text,posting_sequence bigint,status text) ON COMMIT DROP"))
        conn.execute(text("CREATE TEMP TABLE ledger_balance_snapshot(class_id text,seat_id int,account_type text,reconciled_through_posting_sequence bigint) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO ledger_transaction VALUES ('proven',1,'checking',1,'POSTED'),('proven',1,'checking',2,'PENDING')"))
        conn.execute(text("INSERT INTO ledger_balance_snapshot VALUES ('proven',1,'checking',1)"))
        before=conn.execute(text("SELECT * FROM ledger_transaction ORDER BY posting_sequence")).all()
        monkeypatch.setattr(migration.op,"get_bind",lambda:conn)
        monkeypatch.setattr(migration.op,"execute",conn.execute)
        for method in ("drop_index","drop_column","create_index"):
            monkeypatch.setattr(migration.op,method,lambda *args,**kwargs:None)
        monkeypatch.setattr(migration,"_install_guard",lambda:None)
        migration.upgrade()
        assert conn.execute(text("SELECT * FROM ledger_transaction ORDER BY posting_sequence")).all() == before


@pytest.mark.parametrize("populated",[False,True])
def test_actual_migration_upgrade_preserves_evidence_and_enforces_creation_guard(app,monkeypatch,populated):
    from importlib import import_module
    from uuid import uuid4
    from sqlalchemy import text,inspect
    from sqlalchemy.exc import DBAPIError
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration=import_module("migrations.versions.e7c2a9d4f610_derive_ledger_posting_from_reconciliation")
    schema="posting_migration_"+uuid4().hex
    with db.engine.connect() as conn:
        outer=conn.begin()
        try:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}",public'))
            conn.execute(text("CREATE TABLE ledger_transaction (LIKE public.ledger_transaction INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
            conn.execute(text("ALTER TABLE ledger_transaction ADD COLUMN status transactionstatus"))
            conn.execute(text("CREATE TABLE ledger_balance_snapshot (LIKE public.ledger_balance_snapshot INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
            conn.execute(text("CREATE INDEX ix_transaction_seat_ledger ON ledger_transaction(join_code,seat_id,status,account_type)"))
            conn.execute(text("CREATE INDEX ix_ledger_transaction_reconstruction_scope ON ledger_transaction(class_id,seat_id,account_type,posting_sequence,status)"))
            conn.execute(text("CREATE FUNCTION prevent_ledger_transaction_rewrite() RETURNS TRIGGER AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql"))
            conn.execute(text("CREATE TRIGGER ledger_transaction_no_rewrite BEFORE UPDATE ON ledger_transaction FOR EACH ROW EXECUTE FUNCTION prevent_ledger_transaction_rewrite()"))
            if populated:
                conn.execute(text("INSERT INTO ledger_transaction(id,seat_id,target_seat_id,actor_seat_id,class_id,amount,amount_cents,timestamp,account_type,type,correlation_id,posting_sequence,status,lineage_event_id,lineage_token,lineage_version) VALUES (1,1,1,1,'old',5,500,now(),'checking','Deposit','corr_original',1,'POSTED',123,'original-signature',1)"))
                conn.execute(text("INSERT INTO ledger_balance_snapshot(class_id,seat_id,account_type,posted_balance_cents,reconciled_through_posting_sequence) VALUES ('old',1,'checking',500,1)"))
            operations=Operations(MigrationContext.configure(conn))
            monkeypatch.setattr(migration,"op",operations)
            migration.upgrade()
            assert "status" not in {c["name"] for c in inspect(conn).get_columns("ledger_transaction",schema=schema)}
            if populated:
                assert conn.execute(text("SELECT amount_cents,posting_sequence,lineage_event_id,lineage_token,lineage_version FROM ledger_transaction WHERE id=1")).one() == (500,1,123,'original-signature',1)
                with pytest.raises(DBAPIError,match="Immutable Ledger field: posting_sequence"):
                    with conn.begin_nested():
                        conn.execute(text("UPDATE ledger_transaction SET posting_sequence=2 WHERE id=1"))
            with pytest.raises(DBAPIError,match="immutable creation sequence"):
                with conn.begin_nested():
                    conn.execute(text("INSERT INTO ledger_transaction(id,seat_id,target_seat_id,actor_seat_id,class_id,amount,amount_cents,timestamp,account_type,type) VALUES (2,1,1,1,'old',1,100,now(),'checking','Deposit')"))
        finally:
            outer.rollback()

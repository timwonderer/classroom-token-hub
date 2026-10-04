"""SPEC-PROD-001 exact proportional monetary allocation acceptance."""
from decimal import Decimal
import pytest
from app.services.ledger_payroll_allocation import allocate_payroll_cents, AllocationIntegrityError


def source(opening, closing, seconds, timestamp="2026-10-01T12:00:00+00:00"):
    return {"opening_event_id": opening, "closing_event_id": closing,
        "credited_seconds": seconds, "closing_timestamp": timestamp}


def test_largest_remainder_ties_use_ids_not_query_order():
    shares = [{"seconds":60,"pay_rate_per_minute":"0.05", "intervals":
        [source(5,6,20),source(1,2,20),source(3,4,20)]}]
    assert allocate_payroll_cents(shares, original_credit=Decimal("0.05"), allocation_version=1) == {(5,6):1,(1,2):2,(3,4):2}


def test_setting_shares_quantize_once_and_preserve_total():
    shares = [{"seconds":30,"pay_rate_per_minute":"0.05", "intervals":[source(1,2,10),source(3,4,20)]},
        {"seconds":60,"pay_rate_per_minute":"0.13", "intervals":[source(5,6,60)]}]
    result = allocate_payroll_cents(shares,original_credit=Decimal("0.15"),allocation_version=1)
    assert sum(result.values()) == 15
    assert result[(5,6)] == 13


@pytest.mark.parametrize("credit,version", [("0.06",1),("-0.05",1),("0.05",2)])
def test_unproven_or_inconsistent_original_credit_denied(credit,version):
    shares = [{"seconds":60,"pay_rate_per_minute":"0.05", "intervals":[source(1,2,60)]}]
    with pytest.raises(AllocationIntegrityError):
        allocate_payroll_cents(shares,original_credit=credit,allocation_version=version)


def test_duplicate_pair_and_missing_seconds_denied():
    for intervals in [[source(1,2,30),source(1,2,30)],[source(1,2,30)]]:
        with pytest.raises(AllocationIntegrityError):
            allocate_payroll_cents([{"seconds":60,"pay_rate_per_minute":"0.05","intervals":intervals}],
                original_credit="0.05",allocation_version=1)


def test_due_system_close_has_persisted_ids_and_is_recorded_once(app):
    from datetime import timedelta
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.services.attendance_service import close_due_attendance_intervals, list_attendance_intervals
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, classroom_ctx
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    ctx = classroom_ctx(classroom)
    _attendance(classroom, seat_id, ("active", _at(0)))
    with FEATContext("FEAT-PROD-004", idempotency_key="provenance-closure"):
        rows = close_due_attendance_intervals(ctx=ctx,seat_id=seat_id,as_of_utc=_at(0)+timedelta(days=1))
        assert len(rows) == 1
        assert rows[0].mechanism == "system"
        assert close_due_attendance_intervals(ctx=ctx,seat_id=seat_id,as_of_utc=_at(0)+timedelta(days=1)) == ()
        intervals = list_attendance_intervals(seat_id,classroom.class_id,ctx=ctx,as_of_utc=_at(0)+timedelta(days=1))
        assert intervals[0].closing_event_id == rows[0].id
        assert intervals[0].as_evidence()["opening_event_id"]
    db.session.commit()


def test_system_close_and_provenance_roll_back_together(app):
    from datetime import timedelta
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import AttendanceSession, PayrollEvent
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, _run
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1",app)
    seat_id = classroom.students[0].seat.id
    _attendance(classroom,seat_id,("active",_at(0)))
    db.session.commit()
    from app.services.payroll.settlement import settle_class_payroll_cycle
    with pytest.raises(RuntimeError,match="failure after provenance"):
        with FEATContext("FEAT-PROD-004",idempotency_key="rollback-provenance"):
            result = settle_class_payroll_cycle(class_id=classroom.class_id, payroll_cycle_id="rollback-cycle",
                boundary_utc=_at(0)+timedelta(days=1), run_mechanism="TEACHER")
            summary = result.events[0].summary_json
            assert summary["allocation_version"] == 1
            assert summary["pricing"][0]["intervals"][0]["closing_event_id"]
            raise RuntimeError("failure after provenance")
    assert AttendanceSession.query.filter_by(class_id=classroom.class_id,status="inactive").count() == 0
    assert PayrollEvent.query.filter_by(class_id=classroom.class_id).count() == 0
    from app.models import AuditEvent, Transaction, LedgerCommandReservation
    assert Transaction.query.filter_by(class_id=classroom.class_id).count() == 0
    assert LedgerCommandReservation.query.filter_by(class_id=classroom.class_id).count() == 0
    assert AuditEvent.query.filter_by(class_id=classroom.class_id).count() == 0


def test_posted_credit_preserves_immutable_creation_digest(app):
    """Creation v2 evidence remains lawful after scoped reconciliation."""
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import AuditEvent
    from app.services.ledger_posting_service import _TRANSACTION_AUDIT_FIELDS
    from app.services.ledger_settlement_service import settle_balances
    from app.services.audit_service import _compute_payload_digest
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, _run
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1",app)
    seat_id = classroom.students[0].seat.id
    _attendance(classroom,seat_id,("active",_at(0)),("inactive",_at(10)))
    result = _run(classroom.class_id,_at(20))
    transaction = result.events[0]
    from app.models import Transaction
    credit = Transaction.query.filter_by(class_id=classroom.class_id, target_seat_id=seat_id,
        idempotency_key=transaction.idempotency_key).one()
    audit = db.session.get(AuditEvent,credit.lineage_event_id)
    fields = {field:getattr(credit,field) for field in _TRANSACTION_AUDIT_FIELDS}
    assert _compute_payload_digest(audit.table_name,audit.row_pk,audit.operation,audit.class_id,fields) == audit.payload_digest
    original_amount = credit.amount
    with FEATContext("FEAT-LED-003",idempotency_key="proof-gate-settlement"):
        settle_balances(seat_id,classroom.class_id)
        db.session.flush()
    assert credit.amount == original_amount
    fields = {field:getattr(credit,field) for field in _TRANSACTION_AUDIT_FIELDS}
    assert _compute_payload_digest(audit.table_name,audit.row_pk,audit.operation,audit.class_id,fields) == audit.payload_digest
    from app.utils.audit_verifier import verify_record_creation_lineage
    assert verify_record_creation_lineage("ledger_transaction", credit, classroom.class_id)


def test_concurrent_due_closure_writers_emit_one_source_event(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from datetime import timedelta
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import AttendanceSession
    from app.services.attendance_service import close_due_attendance_intervals
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, classroom_ctx
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1",app)
    seat_id, class_id = classroom.students[0].seat.id, classroom.class_id
    ctx = classroom_ctx(classroom)
    _attendance(classroom,seat_id,("active",_at(0)))
    db.session.commit()
    rendezvous = Barrier(2)
    def writer(index):
        with app.app_context():
            rendezvous.wait(timeout=5)
            with FEATContext("FEAT-PROD-004",idempotency_key=f"concurrent-close-{index}"):
                rows = close_due_attendance_intervals(ctx=ctx,seat_id=seat_id,as_of_utc=_at(0)+timedelta(days=1))
                return len(rows)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer,index) for index in range(2)]
        counts = [future.result(timeout=15) for future in futures]
    assert sorted(counts) == [0,1]
    assert AttendanceSession.query.filter_by(class_id=class_id,target_seat_id=seat_id,status="inactive").count() == 1


def test_prospective_membership_does_not_skip_later_recorded_backdated_close(app):
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, _run
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1",app)
    seat_id = classroom.students[0].seat.id
    _attendance(classroom,seat_id,("active",_at(0)),("inactive",_at(10)),("active",_at(15)))
    first = _run(classroom.class_id,_at(20))
    _attendance(classroom,seat_id,("inactive",_at(18)))
    second = _run(classroom.class_id,_at(30))
    assert second.events[0].summary_json["pricing"][0]["seconds"] == 180
    first_pairs = first.events[0].summary_json["pricing"][0]["intervals"]
    second_pairs = second.events[0].summary_json["pricing"][0]["intervals"]
    assert first_pairs[0]["opening_event_id"] != second_pairs[0]["opening_event_id"]


@pytest.mark.parametrize("seconds,expected",[(90,"0.08"),(30,"0.02")])
def test_half_even_share_quantization_agrees_with_allocation(seconds,expected):
    from app.services.payroll.pricing import amount_for
    assert amount_for(seconds,"0.05") == Decimal(expected)
    shares = [{"seconds":seconds,"pay_rate_per_minute":"0.05","intervals":[source(1,2,seconds)]}]
    assert allocate_payroll_cents(shares,original_credit=expected,allocation_version=1)[(1,2)] == int(Decimal(expected)*100)


def test_malformed_original_summary_is_inspectable_and_blocks_new_payment(app):
    from app.extensions import db
    from app.feats.base import FEATContext, audit_protected
    from app.models import PayrollEvent
    from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE
    from app.services.attendance_service import calculate_seat_payroll_intervals
    from app.services.payroll_interval_provenance import payroll_interval_memberships, payroll_provenance_history_limitations
    from app.services.payroll.settings import first_payroll_setting
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance, _at, classroom_ctx
    from tests.helpers.classroom_initializer import initialize
    classroom = initialize("chemistry_p1",app)
    seat_id, cid = classroom.students[0].seat.id, classroom.class_id
    ctx = classroom_ctx(classroom)
    _attendance(classroom,seat_id,("active",_at(0)),("inactive",_at(10)))
    for index, summary in enumerate(["malformed", ["malformed"], {"allocation_version":1,"pricing":["bad"]},
            {"allocation_version":1,"pricing":[]}, {"allocation_version":1,"pricing":[{"intervals":[]}]}]):
        key = f"malformed-original-{index}"
        with FEATContext("FEAT-PROD-003",idempotency_key=key):
            event = PayrollEvent(class_id=cid,target_seat_id=seat_id,actor_seat_id=classroom.teacher_seat_id,
                correlation_id=key,idempotency_key=key,policy_uuid=first_payroll_setting(cid).policy_uuid,
                mechanism="TEACHER",payroll_event_type="payroll",recorded_at=_at(20),summary_json=summary)
            db.session.add(event)
            db.session.flush()
            audit_protected("payroll_event",event,"INSERT",PROTECTED_FIELDS_BY_TABLE["payroll_event"])
        assert payroll_provenance_history_limitations(seat_id,cid,ctx=ctx)
        result = payroll_interval_memberships(seat_id,cid,ctx=ctx,as_of_utc=_at(30))
        assert all(i["status"] in {"historical_unavailable","provenance_unavailable"} for i in result.values())
        intervals = calculate_seat_payroll_intervals(seat_id,cid,ctx=ctx,as_of_utc=_at(30))
        assert intervals.payable == ()
        assert intervals.unprovable

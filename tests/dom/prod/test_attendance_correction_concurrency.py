"""Real two-session serialization for FEAT-PROD-003/005, INV-ARC-021."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, current_thread
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import AttendanceIntervalInvalidation, PayrollEvent, Transaction, TransactionStatus
from app.services.attendance_invalidation_service import AttendanceCorrectionDenied
from app.feats import prod
from app.feats import attendance_interval_invalidation_feat as command
from tests.dom.prod.test_attendance_invalidation_command import _args, _paid_sources
from tests.dom.prod.test_attendance_invalidation_lineage import _sources


def _ordered_race(app, monkeypatch, first, second, hooks):
    """Hold the first lawful lock; prove the other DB session waits on it."""
    acquired, attempted, release = Event(), Event(), Event()
    pids, seen = {}, set()
    for owner, name in hooks:
        original = getattr(owner, name)
        def gate(*args, _original=original, **kwargs):
            role = 'first' if current_thread().name.endswith('_0') else 'second'
            if role in seen:
                return _original(*args, **kwargs)
            seen.add(role)
            pids[role] = db.session.execute(text('SELECT pg_backend_pid()')).scalar_one()
            if role == 'second':
                attempted.set()
                return _original(*args, **kwargs)
            result = _original(*args, **kwargs)
            acquired.set()
            if not release.wait(10):
                raise AssertionError('Second command did not reach the contested lock.')
            return result
        monkeypatch.setattr(owner, name, gate)

    def run(action):
        with app.app_context():
            try:
                return ('accepted', action())
            except (AttendanceCorrectionDenied, ValueError) as error:
                db.session.rollback()
                return ('denied', str(error))
            finally:
                db.session.remove()

    # The fixture's read autobegin must not retain an obsolete snapshot.
    db.session.rollback()
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='attendance_race') as pool:
        winner = pool.submit(run, first)
        try:
            assert acquired.wait(10), 'First command did not acquire its canonical scope lock.'
            loser = pool.submit(run, second)
            assert attempted.wait(10), 'Second command did not attempt its canonical scope lock.'
            deadline = monotonic() + 5
            while True:
                with db.engine.connect() as connection:
                    blockers = connection.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid':pids['second']}).scalar_one()
                if pids['first'] in blockers:
                    break
                assert monotonic() < deadline, 'Independent sessions did not contend on the canonical lock.'
                Event().wait(.01)
        finally:
            release.set()
        result = winner.result(timeout=15), loser.result(timeout=15)
    db.session.expire_all()
    return result


def _invalidate(args, identity):
    return lambda: command.invalidate_attendance_interval(**args, idempotency_key=str(uuid4()), expected_preview_identity=identity)


def _recover(ctx, event_id, identity):
    return lambda: command.recover_payroll_payment(ctx=ctx, payroll_event_id=event_id,
        idempotency_key=str(uuid4()), expected_preview_identity=identity)


def _pay(ctx, target):
    return prod.record_payroll_event(ctx=ctx, target_seat_id=target, payroll_event_type='payroll',
        correlation_id='corr_race_payment', idempotency_key='race-payment', mechanism='TEACHER',
        reference_time_utc=datetime(2026,8,3,18,tzinfo=timezone.utc))


@pytest.mark.parametrize('first_kind', ['payroll', 'invalidation'])
def test_payroll_and_unpaid_invalidation_serialize_same_source(app, monkeypatch, first_kind):
    _,ctx,target,pairs = _sources(app)
    from app.feats.base import FEATContext
    from tests.helpers.ledger import record_ledger_fixture
    with FEATContext('FEAT-LED-001', idempotency_key='unpaid-race-zero-snapshot'):
        record_ledger_fixture(seat_id=target, class_id=ctx.class_id, amount=0, posted=True)
    args = _args(ctx,target,pairs[0])
    invalidate = _invalidate(args, command.preview_attendance_interval_invalidation(**args).identity)
    payroll = lambda: _pay(ctx,target)
    # Payroll closes due intervals under the same seat lock before pricing.
    first, second = (payroll,invalidate) if first_kind=='payroll' else (invalidate,payroll)
    results = _ordered_race(app,monkeypatch,first,second,
        [(prod,'close_due_attendance_intervals'),(command,'lock_recovery_scope')])
    assert results[0][0]=='accepted'
    assert results[1][0]=='denied'
    if first_kind=='payroll':
        assert results[1][1] in {'PAYROLL_PENDING','PREVIEW_CHANGED'}
        assert PayrollEvent.query.count()==1 and AttendanceIntervalInvalidation.query.count()==0
        assert Transaction.query.filter(Transaction.amount_cents>0).count()==1
    else:
        assert 'no payable attendance' in results[1][1]
        assert PayrollEvent.query.count()==0 and Transaction.query.filter(Transaction.amount_cents!=0).count()==0
        assert AttendanceIntervalInvalidation.query.count()==1


@pytest.mark.parametrize('first_kind', ['interval', 'payment'])
def test_full_and_interval_recovery_race_cannot_overrecover(app, monkeypatch, first_kind):
    _,ctx,target,pairs,event = _paid_sources(app)
    event_id = event.id
    credit = Transaction.query.filter_by(idempotency_key='correction-original').one()
    original_cents = credit.amount_cents
    args = _args(ctx,target,pairs[0])
    interval = _invalidate(args,command.preview_attendance_interval_invalidation(**args).identity)
    payment = _recover(ctx,event_id,command.preview_payroll_recovery(ctx=ctx,payroll_event_id=event_id).identity)
    first,second = (interval,payment) if first_kind=='interval' else (payment,interval)
    results = _ordered_race(app,monkeypatch,first,second,[(command,'lock_recovery_scope')])
    assert results[0][0]=='accepted' and results[1]==('denied','PREVIEW_CHANGED')
    recovered = sum(row.compensation_amount_cents or 0 for row in Transaction.query.all())
    assert 0 < recovered <= original_cents
    if recovered < original_cents:
        remaining = command.preview_payroll_recovery(ctx=ctx,payroll_event_id=event_id)
        assert remaining.disposition=='RESIDUAL'
        _recover(ctx,event_id,remaining.identity)()
    assert sum(row.compensation_amount_cents or 0 for row in Transaction.query.all())==original_cents
    # New recovery effects remain pending; the cap must include them already.
    assert all(row.posting_state==TransactionStatus.PENDING for row in Transaction.query.filter(Transaction.compensation_amount_cents>0).all())
    with pytest.raises(AttendanceCorrectionDenied,match='ALREADY_RECOVERED'):
        command.preview_payroll_recovery(ctx=ctx,payroll_event_id=event_id)


@pytest.mark.parametrize('first_kind', ['interval', 'residual'])
def test_partial_then_residual_and_remaining_interval_race_counts_pending(app, monkeypatch, first_kind):
    _,ctx,target,pairs,event = _paid_sources(app)
    event_id = event.id
    first_args = _args(ctx,target,pairs[0])
    _invalidate(first_args,command.preview_attendance_interval_invalidation(**first_args).identity)()
    args = _args(ctx,target,pairs[1])
    interval = _invalidate(args,command.preview_attendance_interval_invalidation(**args).identity)
    residual_preview = command.preview_payroll_recovery(ctx=ctx,payroll_event_id=event_id)
    assert residual_preview.disposition=='RESIDUAL'
    residual = _recover(ctx,event_id,residual_preview.identity)
    first,second = (interval,residual) if first_kind=='interval' else (residual,interval)
    results = _ordered_race(app,monkeypatch,first,second,[(command,'lock_recovery_scope')])
    assert results[0][0]=='accepted'
    assert results[1][0]=='denied' and results[1][1] in {'PREVIEW_CHANGED','ALREADY_RECOVERED'}
    credit = Transaction.query.filter_by(idempotency_key='correction-original').one()
    effects = Transaction.query.filter(Transaction.compensation_amount_cents>0).all()
    assert len(effects)==2 and sum(row.compensation_amount_cents for row in effects)==credit.amount_cents
    assert all(row.posting_state==TransactionStatus.PENDING for row in effects)

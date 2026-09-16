"""Frozen class-local witnesses; private confirmations and one aggregate result."""
from datetime import timedelta
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pyotp
import pytest
import sqlalchemy as sa
from app import db
from app.feats.base import FEATContext
from app.feats.teacher_recovery_feat import (begin_attempt, prove_class, select_class_recipients,
    issue_confirmation, confirm_class, authorize_setup, complete_setup, save_progress, resume_attempt, attempt_status)
from app.models import ClassEconomy, PasskeyCredential, User, Seat
from app.services.recovery_service import get_recovery_request_by_id, list_recovery_codes_for_request
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.encryption import decrypt_totp
from tests.helpers.classroom_initializer import initialize


def call(fn, **kwargs):
    return fn(**kwargs, correlation_id='recovery-test', idempotency_key='recovery-test:'+fn.__name__)


@pytest.fixture
def recovery(app, monkeypatch):
    classes=[initialize('chemistry_p1', app), initialize('ap_csp_p3', app)]
    monkeypatch.setattr('secrets.SystemRandom.sample', lambda self, population, k: population[-k:])
    attempt=call(begin_attempt, join_code=classes[0].join_code)
    for c in classes:
        assert call(prove_class, request_id=attempt['id'], attempt_nonce=attempt['nonce'], join_code=c.join_code, username=c.students[0].username)
    for c in classes:
        assert call(select_class_recipients, request_id=attempt['id'], attempt_nonce=attempt['nonce'], class_id=c.class_id)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='recovery:passkey'):
        db.session.add(PasskeyCredential(user_id=classes[0].teacher_user.id, credential_id='old-key'))
    return SimpleNamespace(id=attempt['id'], access=attempt['nonce'], classes=classes, teacher=classes[0].teacher_user)


def rows(r, index=0):
    return [c for c in list_recovery_codes_for_request(r.id) if c.class_id==r.classes[index].class_id]


def generate(r, index=0, recipient=0):
    code=rows(r,index)[recipient]
    student=next(s for s in r.classes[index].students if s.seat.id==code.seat_id)
    return call(issue_confirmation, request_id=r.id, class_id=code.class_id, code_id=code.id,
                seat_id=code.seat_id, principal_id=student.user.id, passphrase=student.passphrase)


def submit(r, code, index=0):
    return call(confirm_class, request_id=r.id, attempt_nonce=r.access, class_id=r.classes[index].class_id, code=code)


def authorize(r):
    return call(authorize_setup, request_id=r.id, attempt_nonce=r.access, username='recovered-teacher')


def setup(r):
    for i in range(len(r.classes)):
        assert submit(r, generate(r,i),i)
    return authorize(r)


def finish(r, grant, **changes):
    args=dict(request_id=r.id, nonce=grant['nonce'], totp_code=pyotp.TOTP(grant['secret']).now())
    args.update(changes)
    return call(complete_setup, **args)


def test_selection_is_random_hidden_and_frozen(recovery):
    r=recovery
    for i,c in enumerate(r.classes):
        chosen=rows(r,i)
        assert len(chosen)==2
        assert c.students[0].seat.id not in {x.seat_id for x in chosen}
        before=[x.seat_id for x in chosen]
        assert call(select_class_recipients, request_id=r.id, attempt_nonce=r.access, class_id=c.class_id)
        assert before==[x.seat_id for x in rows(r,i)]
    assert call(begin_attempt, join_code=r.classes[0].join_code) is None
    assert 'seat_id' not in str(attempt_status(r.id,r.access))


def test_one_of_two_satisfies_class_privately_and_invalidates_both(recovery):
    first,second=generate(recovery),generate(recovery,recipient=1)
    assert submit(recovery,second)
    assert all(c.code_hash is None for c in rows(recovery))
    assert submit(recovery,first) # Same receipt even for consumed code.
    assert authorize(recovery) is None # Other class missing: one generic failure.


def test_code_expiry_and_regeneration_never_rerolls(recovery):
    code=generate(recovery)
    table=db.metadata.tables['student_recovery_codes']
    before=[x.seat_id for x in rows(recovery)]
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='expire'):
        db.session.execute(sa.update(table).where(table.c.recovery_request_id==recovery.id).values(code_expires_at=utc_now()-timedelta(seconds=1)))
    assert submit(recovery,code)
    assert submit(recovery,generate(recovery,1),1)
    assert authorize(recovery) is None
    assert before==[x.seat_id for x in rows(recovery)]
    assert setup(recovery)


def test_correct_and_incorrect_code_receipts_are_identical(recovery,client):
    with client.session_transaction() as session:
        session['recovery_request_id']=recovery.id
        session['teacher_recovery_attempt_nonce']=recovery.access
    valid=generate(recovery)
    bad=client.post('/admin/recovery/submit-class-code',json={'class_ref':db.session.get(ClassEconomy, recovery.classes[0].class_id).class_public_id,'code':'bad'})
    bad_status=client.get('/admin/recovery-status').get_data(as_text=True)
    good=client.post('/admin/recovery/submit-class-code',json={'class_ref':db.session.get(ClassEconomy, recovery.classes[0].class_id).class_public_id,'code':valid})
    good_status=client.get('/admin/recovery-status').get_data(as_text=True)
    assert bad.status_code==good.status_code==200 and bad.get_json()==good.get_json()=={'received':True}
    assert bad_status==good_status
    assert 'Verified' not in good_status
    assert recovery.classes[0].class_id not in good_status
    assert client.post('/admin/recovery/submit-class-code', json=['invalid']).get_json()=={'received':False}


def test_class_confirmation_persists_after_30_minutes(recovery,monkeypatch):
    now=utc_now()
    assert submit(recovery,generate(recovery))
    monkeypatch.setattr('app.feats.teacher_recovery_feat.utc_now',lambda:now+timedelta(days=1))
    assert submit(recovery,generate(recovery,1),1)
    assert authorize(recovery)


def test_codes_are_bound_to_class_and_attempt(recovery):
    code=generate(recovery)
    assert submit(recovery,code,1)
    assert submit(recovery,code,0)
    assert authorize(recovery) is None


def test_complete_revokes_passkeys_and_replay(recovery):
    grant=setup(recovery)
    assert grant and finish(recovery,grant)
    db.session.refresh(recovery.teacher)
    assert decrypt_totp(recovery.teacher.totp_secret_encrypted)==grant['secret']
    assert PasskeyCredential.query.filter_by(user_id=recovery.teacher.id).count()==0
    assert not finish(recovery,grant)
    assert get_recovery_request_by_id(recovery.id).status=='verified'


@pytest.mark.parametrize('change',['expired','cancelled','nonce','wrong_totp','missing_class_proof'])
def test_completion_rechecks_server_state(recovery,change):
    grant=setup(recovery)
    original=recovery.teacher.username_lookup_hash
    table=db.metadata.tables['recovery_requests']
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='change'):
        if change=='expired':db.session.execute(sa.update(table).where(table.c.id==recovery.id).values(expires_at=utc_now()-timedelta(seconds=1)))
        elif change=='cancelled':db.session.execute(sa.update(table).where(table.c.id==recovery.id).values(status='cancelled'))
        elif change=='missing_class_proof':
            proofs=db.metadata.tables['recovery_class_challenges']
            db.session.execute(sa.delete(proofs).where(proofs.c.recovery_request_id==recovery.id,proofs.c.class_id==recovery.classes[0].class_id))
    overrides=dict(nonce='wrong') if change=='nonce' else dict(totp_code='bad') if change=='wrong_totp' else {}
    assert not finish(recovery,grant,**overrides)
    db.session.refresh(recovery.teacher)
    assert recovery.teacher.username_lookup_hash==original
    assert PasskeyCredential.query.filter_by(user_id=recovery.teacher.id).count()==1


def test_failed_aggregate_requires_fresh_codes_but_keeps_recipients(recovery):
    old=[generate(recovery,i) for i in range(2)]
    submit(recovery,old[0]);submit(recovery,'bad',1)
    before=[c.seat_id for c in list_recovery_codes_for_request(recovery.id)]
    assert authorize(recovery) is None
    for i in range(2):submit(recovery,old[i],i)
    assert authorize(recovery) is None
    assert before==[c.seat_id for c in list_recovery_codes_for_request(recovery.id)]
    assert setup(recovery)


def test_resume_preserves_private_confirmations_and_replaces_access(recovery):
    submit(recovery,generate(recovery))
    pin=call(save_progress,request_id=recovery.id,attempt_nonce=recovery.access)
    resumed=call(resume_attempt,pin=pin)
    assert resumed and resumed['nonce']!=recovery.access
    assert attempt_status(recovery.id,recovery.access) is None
    recovery.access=resumed['nonce']
    submit(recovery,generate(recovery,1),1)
    assert authorize(recovery)


def test_concurrent_class_submission_and_completion(recovery,app):
    code=generate(recovery)
    second_code=generate(recovery,1)
    second_class_id=recovery.classes[1].class_id
    request_id,access,class_id=recovery.id,recovery.access,recovery.classes[0].class_id
    db.session.remove()
    barrier=Barrier(2)
    def worker(_):
        with app.app_context():
            barrier.wait(timeout=15)
            return call(confirm_class,request_id=request_id,attempt_nonce=access,class_id=class_id,code=code)
    with ThreadPoolExecutor(max_workers=2) as pool:assert all(pool.map(worker,range(2)))
    call(confirm_class,request_id=request_id,attempt_nonce=access,class_id=second_class_id,code=second_code)
    grant=authorize(recovery)
    db.session.remove();barrier=Barrier(2)
    def complete(_):
        with app.app_context():
            barrier.wait(timeout=15)
            return call(complete_setup,request_id=request_id,nonce=grant['nonce'],totp_code=pyotp.TOTP(grant['secret']).now())
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(complete,range(2)))==1


def test_completion_failure_rolls_back(recovery):
    grant=setup(recovery);original=recovery.teacher.username_lookup_hash;engine=db.engine
    def fail(_c,_cu,sql,_p,_ctx,_many):
        if sql.startswith('UPDATE recovery_requests') and 'completed_at' in sql:raise RuntimeError('injected')
    sa.event.listen(engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError,match='injected'):finish(recovery,grant)
    finally:sa.event.remove(engine,'before_cursor_execute',fail)
    db.session.expire_all()
    assert recovery.teacher.username_lookup_hash==original
    assert PasskeyCredential.query.filter_by(user_id=recovery.teacher.id).count()==1
    assert finish(recovery,grant)


def test_unclaim_removes_recipient_without_reroll_or_losing_class_proof(recovery):
    from app.services.recovery_service import invalidate_recovery_participation_for_seat
    chosen=rows(recovery)
    submit(recovery,generate(recovery))
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='unclaim-revoke'):
        invalidate_recovery_participation_for_seat(chosen[0].seat_id)
    assert len(rows(recovery))==1
    submit(recovery,generate(recovery,1),1)
    assert authorize(recovery)


def test_both_recipients_receive_prompt_until_private_confirmation(recovery):
    from app.services.recovery_service import get_pending_recovery_code_for_seat
    chosen=rows(recovery)
    scope=recovery.classes[0].class_id
    for c in chosen:
        assert get_pending_recovery_code_for_seat(c.seat_id,utc_now(),class_id=scope)
    assert not get_pending_recovery_code_for_seat(recovery.classes[0].students[0].seat.id,utc_now(),class_id=scope)
    code=generate(recovery)
    assert get_pending_recovery_code_for_seat(chosen[0].seat_id,utc_now(),class_id=scope)
    submit(recovery,code)
    assert all(get_pending_recovery_code_for_seat(c.seat_id,utc_now(),class_id=scope) is None for c in chosen)


def test_staged_proof_then_selection_is_class_scoped(app):
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    attempt=call(begin_attempt,join_code=classes[0].join_code)
    args=dict(request_id=attempt['id'],attempt_nonce=attempt['nonce'])
    assert call(prove_class,**args,join_code=classes[0].join_code,username=classes[0].students[0].username)
    assert not call(select_class_recipients,**args,class_id=classes[0].class_id)
    assert list_recovery_codes_for_request(attempt['id'])==[]
    assert call(prove_class,**args,join_code=classes[1].join_code,username=classes[1].students[0].username)
    assert call(select_class_recipients,**args,class_id=classes[0].class_id)
    assert {x.class_id for x in list_recovery_codes_for_request(attempt['id'])}=={classes[0].class_id}


def test_route_preparation_and_completion(recovery,client):
    with client.session_transaction() as session:
        session['recovery_request_id']=recovery.id
        session['teacher_recovery_attempt_nonce']=recovery.access
    for i in range(2):
        response=client.post('/admin/recovery/submit-class-code',json={'class_ref':db.session.get(ClassEconomy, recovery.classes[i].class_id).class_public_id,'code':generate(recovery,i)})
        assert response.get_json()=={'received':True}
    response=client.post('/admin/reset-credentials',data={'new_username':'route-teacher'})
    assert response.status_code==200
    with client.session_transaction() as session:
        assert 'teacher_recovery_setup_nonce' in session and 'reset_totp_secret' not in session
    requests=db.metadata.tables['recovery_requests']
    row=db.session.execute(sa.select(requests).where(requests.c.id==recovery.id)).first()
    assert row.setup_username!='route-teacher' and decrypt_totp(row.setup_username)=='route-teacher'
    response=client.post('/admin/confirm-reset',data={'totp_code':pyotp.TOTP(decrypt_totp(row.setup_totp_encrypted)).now()})
    assert response.status_code==302 and '/admin/login' in response.location


def test_single_eligible_student_is_selected(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    from app.utils.student_deletion import remove_student_from_teacher_scope
    c=initialize_as_teacher('chemistry_p1',client,app)
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='single-witness'):
        for s in c.students[1:]:remove_student_from_teacher_scope(s.seat.id,c.teacher_user.id)
    attempt=call(begin_attempt,join_code=c.join_code)
    args=dict(request_id=attempt['id'],attempt_nonce=attempt['nonce'])
    assert call(prove_class,**args,join_code=c.join_code,username=c.students[0].username)
    assert call(select_class_recipients,**args,class_id=c.class_id)
    assert len(list_recovery_codes_for_request(attempt['id']))==1

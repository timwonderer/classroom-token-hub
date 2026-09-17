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
from app.feats.teacher_recovery_feat import (begin_attempt, select_class_recipients,
    issue_confirmation, confirm_class, authorize_setup, complete_setup, save_progress, resume_attempt, attempt_status)
from app.models import ClassEconomy, PasskeyCredential, User, Seat
from app.services.recovery_service import get_recovery_request_by_id, list_recovery_codes_for_request
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.encryption import decrypt_totp
from tests.helpers.classroom_initializer import initialize


def call(fn, **kwargs):
    return fn(**kwargs, correlation_id='recovery-test', idempotency_key='recovery-test:'+fn.__name__)


def proof_pairs(classes, per_class=None):
    """Distinct students per class; a student seated in two classes backs one pair."""
    from app.feats.teacher_recovery_feat import usernames_required_per_class
    need=per_class or usernames_required_per_class(len(classes))
    used, pairs=set(), []
    for c in reversed(classes):  # later classes have fewer unshared students
        chosen=[s for s in c.students if s.user.id not in used][:need]
        used.update(s.user.id for s in chosen)
        pairs+=[(c.join_code, s.username) for s in chosen]
    return pairs


@pytest.fixture
def recovery(app, monkeypatch):
    classes=[initialize('chemistry_p1', app), initialize('ap_csp_p3', app)]
    monkeypatch.setattr('secrets.SystemRandom.sample', lambda self, population, k: population[-k:])
    attempt=call(begin_attempt, pairs=proof_pairs(classes))
    assert attempt
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
    assert call(begin_attempt, pairs=proof_pairs(r.classes)) is None
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


def test_incomplete_proof_creates_nothing_then_selection_is_class_scoped(app):
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    requests=db.metadata.tables['recovery_requests']
    count=lambda: db.session.execute(sa.select(sa.func.count()).select_from(requests)).scalar()
    pairs=proof_pairs(classes)
    # Missing an owned class: no attempt exists to reserve or resume.
    assert call(begin_attempt,pairs=[p for p in pairs if p[0]==classes[0].join_code]) is None
    assert count()==0
    attempt=call(begin_attempt,pairs=pairs)
    assert attempt and count()==1
    args=dict(request_id=attempt['id'],attempt_nonce=attempt['nonce'])
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


def _shrink_class(c, keep):
    from app.utils.student_deletion import remove_student_from_teacher_scope
    with FEATContext('FEAT-TEST-SETUP',idempotency_key=f'recovery:shrink:{keep}'):
        for s in c.students[keep:]:remove_student_from_teacher_scope(s.seat.id,c.teacher_user.id)
    return c.students[:keep]


def test_DOM_IDEN_003__class_below_three_claimed_students_blocks_recovery(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    c=initialize_as_teacher('chemistry_p1',client,app)
    remaining=_shrink_class(c,2)
    requests=db.metadata.tables['recovery_requests']
    assert call(begin_attempt,pairs=[(c.join_code,s.username) for s in remaining]) is None
    assert db.session.execute(sa.select(sa.func.count()).select_from(requests)).scalar()==0


def test_DOM_IDEN_003__three_claimed_students_select_exactly_two(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    c=initialize_as_teacher('chemistry_p1',client,app)
    remaining=_shrink_class(c,3)
    attempt=call(begin_attempt,pairs=[(c.join_code,s.username) for s in remaining])
    assert attempt
    args=dict(request_id=attempt['id'],attempt_nonce=attempt['nonce'])
    assert call(select_class_recipients,**args,class_id=c.class_id)
    assert len(list_recovery_codes_for_request(attempt['id']))==2


def test_DOM_IDEN_003__selection_fails_closed_if_class_drops_below_three(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    from app.utils.student_deletion import remove_student_from_teacher_scope
    c=initialize_as_teacher('chemistry_p1',client,app)
    remaining=_shrink_class(c,3)
    attempt=call(begin_attempt,pairs=[(c.join_code,s.username) for s in remaining])
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='recovery:drop-after-proof'):
        remove_student_from_teacher_scope(remaining[-1].seat.id,c.teacher_user.id)
    args=dict(request_id=attempt['id'],attempt_nonce=attempt['nonce'])
    assert not call(select_class_recipients,**args,class_id=c.class_id)
    assert list_recovery_codes_for_request(attempt['id'])==[]


def test_recovery_minimum_is_stated_on_teacher_surfaces(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    c=initialize_as_teacher('chemistry_p1',client,app)
    roster=client.get('/admin/students').get_data(as_text=True)
    assert 'recovery-readiness-warning' not in roster  # four claimed students
    assert '3 students per class' in client.get('/admin/recover').get_data(as_text=True)
    assert 'at least 3 claimed students in every class' in client.get('/admin/setup-recovery').get_data(as_text=True)
    _shrink_class(c,2)
    roster=client.get('/admin/students').get_data(as_text=True)
    assert 'recovery-readiness-warning' in roster and 'This class has 2.' in roster


def test_DOM_IDEN_003__two_classes_require_three_usernames_each(app):
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    assert call(begin_attempt,pairs=proof_pairs(classes,per_class=2)) is None
    assert call(begin_attempt,pairs=proof_pairs(classes,per_class=3))


def test_DOM_IDEN_003__one_student_backs_only_one_pair_across_classes(app):
    from app.services.classroom_setup import create_roster_student_seat
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    shared=classes[0].students[0]
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='recovery:shared-student'):
        seat=create_roster_student_seat(class_id=classes[1].class_id, first_name='Shared', last_name='Student',
                                        claimed_at=utc_now())
        seat.user_id=shared.user.id
    pairs=[(classes[0].join_code,s.username) for s in classes[0].students[:3]]
    others=[(classes[1].join_code,s.username) for s in classes[1].students[:2]]
    # The shared student already backs a class-A pair, so it cannot be class B's third.
    assert call(begin_attempt,pairs=pairs+others+[(classes[1].join_code,shared.username)]) is None
    assert call(begin_attempt,pairs=pairs+others+[(classes[1].join_code,classes[1].students[2].username)])


def test_DOM_IDEN_003__recipient_selection_ignores_cross_class_identity(app, monkeypatch):
    from app.services.classroom_setup import create_roster_student_seat
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    shared=max(classes[0].students, key=lambda s: s.seat.id)
    with FEATContext('FEAT-TEST-SETUP',idempotency_key='recovery:shared-recipient'):
        seat=create_roster_student_seat(class_id=classes[1].class_id, first_name='Shared', last_name='Recipient',
                                        claimed_at=utc_now())
        seat.user_id=shared.user.id
        shared_b=seat.id
    # Deterministic "random": each class takes its highest seat ids, which include the shared student.
    monkeypatch.setattr('secrets.SystemRandom.sample', lambda self, population, k: population[-k:])
    others=[s for s in classes[0].students if s.user.id!=shared.user.id]
    pairs=[(classes[0].join_code,s.username) for s in others[:3]]+[(classes[1].join_code,s.username) for s in classes[1].students[:3]]
    attempt=call(begin_attempt,pairs=pairs)
    assert attempt
    for c in classes:
        assert call(select_class_recipients,request_id=attempt['id'],attempt_nonce=attempt['nonce'],class_id=c.class_id)
    chosen=list_recovery_codes_for_request(attempt['id'])
    assert shared.seat.id in {x.seat_id for x in chosen if x.class_id==classes[0].class_id}
    assert shared_b in {x.seat_id for x in chosen if x.class_id==classes[1].class_id}


def test_DOM_IDEN_003__single_class_with_fewer_than_six_students_needs_all(client,app):
    from tests.helpers.classroom_initializer import initialize_as_teacher
    c=initialize_as_teacher('chemistry_p1',client,app)
    pairs=[(c.join_code,s.username) for s in c.students]
    assert len(pairs) < 6
    assert call(begin_attempt,pairs=pairs[:-1]) is None
    assert call(begin_attempt,pairs=pairs[:-1]+[pairs[0]]) is None
    assert call(begin_attempt,pairs=pairs)


def test_recover_form_rejects_a_username_reused_across_pairs(app,client):
    classes=[initialize('chemistry_p1',app),initialize('ap_csp_p3',app)]
    requests=db.metadata.tables['recovery_requests']
    count=lambda: db.session.execute(sa.select(sa.func.count()).select_from(requests)).scalar()
    def post(pairs):
        return client.post('/admin/recover',data={
            'join_code[]':[p[0] for p in pairs],'student_username[]':[p[1] for p in pairs]})
    app.config['WTF_CSRF_ENABLED']=False
    try:
        pairs=proof_pairs(classes)
        rejected=post(pairs[:-1]+[pairs[0]])
        assert b'Unable to begin recovery' in rejected.data and count()==0
        accepted=post(pairs)
        assert b'Preparing account recovery' in accepted.data and count()==1
    finally:
        app.config['WTF_CSRF_ENABLED']=True

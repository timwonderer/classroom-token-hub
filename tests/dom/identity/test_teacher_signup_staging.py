"""Pending signup confidentiality, expiration, replay and atomic provisioning."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pyotp
import pytest
import sqlalchemy as sa
from app import db
from app.feats.base import FEATContext
from app.feats.teacher_signup_feat import (stage_signup, prepare_totp, complete_signup,
    read_signup, purge_expired_signups)
from app.models import TeacherSignupAttempt, User, ClassEconomy, Seat, IdentityProfile
from app.utils.canonical_temporal_resolver import utc_now


def call(fn, **kwargs):
    return fn(**kwargs, correlation_id='signup-test', idempotency_key='signup-test:'+fn.__name__)


def stage(previous=None):
    return call(stage_signup, previous_nonce=previous, metadata=dict(
        class_display_name='Physics test', section='Period A', class_timezone='America/Los_Angeles',
        teacher_first_name='SignupFirst', teacher_last_name='SignupLast'))


def prepared():
    nonce=stage()
    return nonce, call(prepare_totp, nonce=nonce, username='signup_teacher')


def complete(nonce, secret):
    return call(complete_signup, nonce=nonce, username='signup_teacher', totp_code=pyotp.TOTP(secret).now())


def test_cookie_contains_only_nonce_and_completion_consumes_staging(app, client, monkeypatch):
    monkeypatch.setattr('app.routes.admin.verify_turnstile_token', lambda *a: True)
    response=client.post('/admin/signup', data=dict(signup_step='class_setup',
        class_display_name='Physics test', section='Period A', first_name='SignupFirst',
        last_name='SignupLast', class_timezone='America/Los_Angeles', tos_agreed='true'))
    assert response.status_code==200
    response=client.post('/admin/signup', data={'username':'signup_teacher'})
    assert response.status_code==200
    with client.session_transaction() as session:
        assert set(session) <= {'teacher_signup_nonce', 'csrf_token', '_flashes'}
        nonce=session['teacher_signup_nonce']
    payload=read_signup(nonce)
    assert payload['username']=='signup_teacher'
    raw=db.session.execute(sa.text('SELECT payload_encrypted FROM teacher_signup_attempts')).scalar_one()
    assert all(value not in raw for value in ('SignupFirst','SignupLast','signup_teacher',payload['totp_secret']))
    assert User.query.count()==ClassEconomy.query.count()==Seat.query.count()==0
    response=client.post('/admin/signup', data=dict(username='signup_teacher',
        totp_code=pyotp.TOTP(payload['totp_secret']).now(), tos_agreed='true'))
    assert response.status_code==302 and response.location.endswith('/admin/login')
    assert TeacherSignupAttempt.query.count()==0
    assert User.query.count()==ClassEconomy.query.count()==Seat.query.count()==IdentityProfile.query.count()==1
    assert not complete(nonce,payload['totp_secret'])


def test_restart_and_expiry_revoke_server_authority(app):
    nonce,secret=prepared()
    replacement=stage(nonce)
    assert read_signup(nonce) is None and not complete(nonce,secret)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='expire-signup'):
        TeacherSignupAttempt.query.one().expires_at=utc_now()-timedelta(seconds=1)
    assert read_signup(replacement) is None
    assert call(prepare_totp, nonce=replacement, username='signup_teacher') is None
    assert call(purge_expired_signups)==1
    assert TeacherSignupAttempt.query.count()==0


def test_wrong_nonce_username_and_totp_cannot_provision(app):
    nonce,secret=prepared()
    assert not complete('x'*43,secret)
    assert not call(complete_signup, nonce=nonce, username='different', totp_code=pyotp.TOTP(secret).now())
    assert not call(complete_signup, nonce=nonce, username='signup_teacher', totp_code='bad')
    expiry=TeacherSignupAttempt.query.one().expires_at
    assert call(prepare_totp, nonce=nonce, username='signup_teacher')==secret
    assert call(prepare_totp, nonce=nonce, username='different')!=secret
    assert TeacherSignupAttempt.query.one().expires_at==expiry
    assert User.query.count()==0


def test_provisioning_failure_preserves_attempt_and_rolls_back_identity(app,monkeypatch):
    nonce,secret=prepared()
    def fail(*args,**kwargs):
        raise RuntimeError('injected class failure')
    monkeypatch.setattr('app.feats.teacher_signup_feat.create_class',fail)
    with pytest.raises(RuntimeError,match='injected'):
        complete(nonce,secret)
    assert User.query.count()==ClassEconomy.query.count()==0
    assert read_signup(nonce)['totp_secret']==secret


def test_concurrent_completion_has_one_winner(app):
    nonce,secret=prepared()
    db.session.remove()
    barrier=Barrier(2)
    def worker():
        with app.app_context():
            barrier.wait()
            return complete(nonce,secret)
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _:worker(), range(2)))==[False,True]
    assert User.query.count()==ClassEconomy.query.count()==1
    assert TeacherSignupAttempt.query.count()==0


def test_another_browser_cannot_continue_signup(app,client):
    nonce,secret=prepared()
    response=client.post('/admin/signup',data=dict(username='signup_teacher',
        totp_code=pyotp.TOTP(secret).now(),tos_agreed='true'))
    assert response.status_code==302 and response.location.endswith('/admin/signup')
    assert User.query.count()==0 and read_signup(nonce)


def test_username_collision_rolls_back_without_consuming_attempt(app):
    nonce,secret=prepared()
    second=stage()
    second_secret=call(prepare_totp,nonce=second,username='signup_teacher')
    assert complete(nonce,secret)
    with pytest.raises(ValueError,match='Username'):
        complete(second,second_secret)
    assert read_signup(second)
    assert User.query.count()==ClassEconomy.query.count()==1


def test_migration_creates_encrypted_staging_and_is_repeatable(app):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location('signup_migration',
        'migrations/versions/a1e1f2a3b4c5_teacher_signup_staging.py')
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    db.session.remove()
    with db.engine.begin() as connection:
        TeacherSignupAttempt.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        columns={c['name'] for c in sa.inspect(connection).get_columns('teacher_signup_attempts')}
        assert columns=={'nonce_hash','payload_encrypted','expires_at'}
    nonce,secret=prepared()
    assert complete(nonce,secret)

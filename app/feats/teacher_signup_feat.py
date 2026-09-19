"""Encrypted initial signup staging under INV-ARC-018 and FEAT-IDEN-101."""
from datetime import timedelta
from hashlib import sha256
import json
import secrets

import pyotp
from app import db
from app.feats.base import requires_feat_context
from app.models import TeacherSignupAttempt
from app.services.classroom_setup import create_teacher, create_class
from app.utils.auth_username import normalize_auth_username
from app.utils.canonical_temporal_resolver import utc_now, ensure_utc
from app.utils.encryption import encrypt_totp, decrypt_totp
from app.utils.join_code import generate_join_code


def _digest(nonce):
    if not isinstance(nonce, str) or len(nonce) != 43:
        return None
    return sha256(('teacher-signup:v1\0' + nonce).encode()).hexdigest()


def _load(nonce, *, lock=False):
    digest = _digest(nonce)
    if digest is None:
        return None
    query = TeacherSignupAttempt.query.filter_by(nonce_hash=digest).populate_existing()
    row = (query.with_for_update() if lock else query).first()
    if row is None or ensure_utc(row.expires_at) <= utc_now():
        return None
    return row


def read_signup(nonce):
    row = _load(nonce)
    return json.loads(decrypt_totp(row.payload_encrypted)) if row else None


@requires_feat_context('FEAT-IDEN-101')
def stage_signup(*, previous_nonce, metadata, correlation_id, idempotency_key):
    # Explicit inventory; no arbitrary request fields are persisted.
    payload = {key: metadata[key] for key in (
        'class_display_name', 'section', 'class_timezone', 'teacher_first_name', 'teacher_last_name')}
    old = TeacherSignupAttempt.query.filter_by(nonce_hash=_digest(previous_nonce)).with_for_update().first()
    if old:
        db.session.delete(old)
    nonce = secrets.token_urlsafe(32)
    db.session.add(TeacherSignupAttempt(nonce_hash=_digest(nonce),
        payload_encrypted=encrypt_totp(json.dumps(payload)), expires_at=utc_now()+timedelta(minutes=30)))
    return nonce


@requires_feat_context('FEAT-IDEN-101')
def prepare_totp(*, nonce, username, correlation_id, idempotency_key):
    row = _load(nonce, lock=True)
    if row is None:
        return None
    payload = json.loads(decrypt_totp(row.payload_encrypted))
    username = normalize_auth_username(username)
    if payload.get('username') != username:
        payload.update(username=username, totp_secret=pyotp.random_base32())
        row.payload_encrypted = encrypt_totp(json.dumps(payload))
    return payload['totp_secret']


@requires_feat_context('FEAT-IDEN-101')
def complete_signup(*, nonce, username, totp_code, correlation_id, idempotency_key):
    row = _load(nonce, lock=True)
    if row is None:
        return False
    payload = json.loads(decrypt_totp(row.payload_encrypted))
    if (payload.get('username') != normalize_auth_username(username)
            or not payload.get('totp_secret')
            or not pyotp.TOTP(payload['totp_secret']).verify(totp_code)):
        return False
    user = create_teacher(payload['username'], totp_secret=payload['totp_secret'])
    create_class(user.id, join_code=generate_join_code(),
        display_name=payload['class_display_name'], section=payload['section'],
        class_timezone=payload['class_timezone'], teacher_first_name=payload['teacher_first_name'],
        teacher_last_name=payload['teacher_last_name'])
    db.session.delete(row)
    return True


@requires_feat_context('FEAT-IDEN-101')
def purge_expired_signups(*, correlation_id, idempotency_key):
    return TeacherSignupAttempt.query.filter(TeacherSignupAttempt.expires_at <= utc_now()).delete(synchronize_session=False)

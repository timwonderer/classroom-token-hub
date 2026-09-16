"""User-owned recovery coordination and explicitly class-scoped challenges."""
from datetime import timedelta
from hashlib import sha256
import hmac
import secrets

import pyotp
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app import db
from app.feats.base import requires_feat_context
from app.hash_utils import _get_pepper, verify_password, hash_username_lookup
from app.models import User, Seat, ClassEconomy, PasskeyCredential
from app.services.recovery_service import _tables
from app.utils.auth_username import build_hashed_username_fields, normalize_auth_username
from app.utils.canonical_temporal_resolver import utc_now, ensure_utc
from app.utils.encryption import encrypt_totp, decrypt_totp


def _challenges():
    return db.metadata.tables['recovery_class_challenges']


def code_digest(value, request_id, class_id):
    import json
    payload = json.dumps(['teacher-recovery-code:v2', request_id, class_id, value], separators=(',', ':')).encode()
    return hmac.new(_get_pepper(), payload, sha256).hexdigest()


def resume_digest(value):
    return hmac.new(_get_pepper(), ('teacher-recovery-resume:v1\0' + value).encode(), sha256).hexdigest()


def _nonce_digest(value):
    return sha256(('teacher-recovery-setup:v1\0' + value).encode()).hexdigest()


def _attempt_digest(value):
    return sha256(('teacher-recovery-attempt:v1\0' + value).encode()).hexdigest()


def _lock(request_id):
    requests, _ = _tables()
    owner = db.session.execute(sa.select(requests.c.user_id).where(requests.c.id == request_id)).scalar_one_or_none()
    user = User.query.filter_by(id=owner, user_role='teacher').populate_existing().with_for_update().one_or_none() if owner else None
    row = db.session.execute(sa.select(requests).where(requests.c.id == request_id).with_for_update()).first() if user else None
    return user, row


def _active(user, row):
    return bool(user and row and row.status == 'pending' and row.completed_at is None and ensure_utc(row.expires_at) > utc_now())


def _access(row, nonce):
    return bool(row and row.attempt_nonce_hash and isinstance(nonce, str)
                and hmac.compare_digest(row.attempt_nonce_hash, _attempt_digest(nonce)))


def _clear(request_id, **extra):
    requests, _ = _tables()
    db.session.execute(sa.update(requests).where(requests.c.id == request_id).values(
        setup_nonce_hash=None, setup_totp_encrypted=None, setup_username=None,
        partial_codes=None, resume_pin_hash=None, resume_new_username=None, **extra))


def _coverage(user, row, *, confirmed=False):
    # Only principal ownership metadata and deposited proof results; never roster rows.
    owned = {c.class_id for c in ClassEconomy.query.filter_by(teacher_user_id=user.id).all()}
    required = set(row.required_class_ids or [])
    table = _challenges()
    proofs = db.session.execute(sa.select(table).where(table.c.recovery_request_id == row.id)).all()
    return bool(required and owned == required and {p.class_id for p in proofs} == required
                and (not confirmed or all(p.satisfied_at is not None and p.satisfied_round == row.submission_round for p in proofs)))


def _class_row(row, class_id):
    if class_id not in (row.required_class_ids or []):
        return None
    table = _challenges()
    return db.session.execute(sa.select(table).where(table.c.recovery_request_id == row.id,
        table.c.class_id == class_id).with_for_update()).first()


@requires_feat_context('FEAT-IDEN-103')
def begin_attempt(*, join_code, current_request_id=None, attempt_nonce=None, correlation_id, idempotency_key):
    classroom = ClassEconomy.query.filter_by(join_code=join_code.strip().upper()).first()
    if not classroom:
        return None
    user = User.query.filter_by(id=classroom.teacher_user_id, user_role='teacher').populate_existing().with_for_update().one_or_none()
    if not user:
        return None
    requests, _ = _tables()
    existing = db.session.execute(sa.select(requests).where(requests.c.user_id == user.id,
        requests.c.status == 'pending', requests.c.expires_at > utc_now(),
        requests.c.selection_started_at.isnot(None))).first()
    if existing:
        return dict(id=existing.id, nonce=attempt_nonce, existing=True) if existing.id == current_request_id and _access(existing, attempt_nonce) else None
    nonce = secrets.token_urlsafe(32)
    required = sorted(c.class_id for c in ClassEconomy.query.filter_by(teacher_user_id=user.id).all())
    request_id = db.session.execute(sa.insert(requests).values(user_id=user.id, status='pending',
        expires_at=utc_now()+timedelta(days=5), required_class_ids=required,
        attempt_nonce_hash=_attempt_digest(nonce)).returning(requests.c.id)).scalar_one()
    return dict(id=request_id, nonce=nonce, existing=False)


@requires_feat_context('FEAT-IDEN-103')
def prove_class(*, request_id, attempt_nonce, join_code, username, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row) or not _access(row, attempt_nonce):
        return False
    classroom = ClassEconomy.query.filter_by(join_code=join_code.strip().upper(), teacher_user_id=user.id).first()
    if not classroom or classroom.class_id not in row.required_class_ids:
        return False
    class_id = classroom.class_id
    match = Seat.query.join(User, User.id == Seat.user_id).filter(Seat.class_id == class_id,
        Seat.role == 'student', Seat.claimed_at.isnot(None), User.username_lookup_hash == hash_username_lookup(username)).first()
    if not match:
        return False
    if not _class_row(row, class_id):
        db.session.execute(sa.insert(_challenges()).values(recovery_request_id=row.id,
            class_id=class_id, proof_verified_at=utc_now()))
    return True


@requires_feat_context('FEAT-IDEN-103')
def select_class_recipients(*, request_id, attempt_nonce, class_id, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row) or not _access(row, attempt_nonce) or not _coverage(user, row):
        return False
    challenge = _class_row(row, class_id)
    if not challenge:
        return False
    if challenge.selected_at:
        return True
    requests, codes = _tables()
    # Freeze one ceremony per principal; failed proof staging cannot reserve/reroll it.
    other = db.session.execute(sa.select(requests.c.id).where(requests.c.user_id == user.id,
        requests.c.id != row.id, requests.c.status == 'pending', requests.c.expires_at > utc_now(),
        requests.c.selection_started_at.isnot(None))).first()
    if other:
        return False
    eligible = [s.id for s in Seat.query.filter_by(class_id=class_id, role='student').filter(
        Seat.user_id.isnot(None), Seat.claimed_at.isnot(None)).order_by(Seat.id).all()]
    if not eligible:
        return False
    selected = secrets.SystemRandom().sample(eligible, min(2, len(eligible)))
    db.session.execute(sa.insert(codes), [dict(recovery_request_id=row.id, class_id=class_id, seat_id=s) for s in selected])
    table = _challenges()
    db.session.execute(sa.update(table).where(table.c.recovery_request_id == row.id, table.c.class_id == class_id).values(
        selected_at=utc_now(), selected_count=len(selected)))
    db.session.execute(sa.update(requests).where(requests.c.id == row.id).values(selection_started_at=row.selection_started_at or utc_now()))
    return True


@requires_feat_context('FEAT-IDEN-104')
def issue_confirmation(*, request_id, class_id, code_id, seat_id, principal_id, passphrase, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row):
        return None
    challenge = _class_row(row, class_id)
    if not challenge or not challenge.selected_at or challenge.satisfied_round == row.submission_round:
        return None
    _, codes = _tables()
    selected = db.session.execute(sa.select(codes).where(codes.c.recovery_request_id == row.id,
        codes.c.class_id == class_id, codes.c.id == code_id, codes.c.seat_id == seat_id).with_for_update()).first()
    seat = Seat.query.filter_by(id=seat_id, class_id=class_id, user_id=principal_id, role='student').first()
    principal = User.query.filter_by(id=principal_id).populate_existing().with_for_update().one_or_none()
    if not selected or not seat or not seat.claimed_at or not principal or not verify_password(passphrase, principal.passphrase_hash):
        return None
    value = f'{secrets.randbelow(1000000):06d}'
    db.session.execute(sa.update(codes).where(codes.c.id == code_id, codes.c.class_id == class_id).values(
        code_hash=code_digest(value, row.id, class_id), verified_at=utc_now(), issued_round=row.submission_round,
        code_expires_at=min(utc_now()+timedelta(minutes=30), ensure_utc(row.expires_at)), dismissed=False))
    return value


@requires_feat_context('FEAT-IDEN-105')
def confirm_class(*, request_id, attempt_nonce, class_id, code, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row) or not _access(row, attempt_nonce):
        return False
    challenge = _class_row(row, class_id)
    if not challenge or not challenge.selected_at:
        return False
    table = _challenges()
    db.session.execute(sa.update(table).where(table.c.recovery_request_id==row.id,
        table.c.class_id==class_id).values(received_round=row.submission_round))
    # Return the same receipt for every code. Validity remains server-private.
    if challenge.satisfied_round == row.submission_round:
        return True
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        return True
    _, codes = _tables()
    digest = code_digest(code, row.id, class_id)
    candidates = db.session.execute(sa.select(codes).where(codes.c.recovery_request_id == row.id,
        codes.c.class_id == class_id, codes.c.code_hash == digest, codes.c.issued_round==row.submission_round,
        codes.c.code_expires_at > utc_now()).with_for_update()).all()
    if any(Seat.query.filter_by(id=c.seat_id, class_id=class_id, role='student').filter(
        Seat.user_id.isnot(None), Seat.claimed_at.isnot(None)).first() for c in candidates):
        db.session.execute(sa.update(table).where(table.c.recovery_request_id == row.id, table.c.class_id == class_id).values(
            satisfied_at=utc_now(), satisfied_round=row.submission_round))
        db.session.execute(sa.update(codes).where(codes.c.recovery_request_id == row.id, codes.c.class_id == class_id).values(code_hash=None, code_expires_at=None))
    return True


@requires_feat_context('FEAT-IDEN-105')
def authorize_setup(*, request_id, attempt_nonce, username, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row) or not _access(row, attempt_nonce) or row.setup_nonce_hash:
        return None
    if not _coverage(user, row, confirmed=True):
        _clear(row.id, submission_round=row.submission_round + 1)
        return None
    username = normalize_auth_username(username)
    if not username or len(username)>100 or User.query.filter(User.username_lookup_hash==hash_username_lookup(username), User.id!=user.id).first():
        return None
    nonce, secret = secrets.token_urlsafe(32), pyotp.random_base32()
    requests, _ = _tables()
    # Keep attempt resume authority; accepted class proofs outlive a browser session.
    db.session.execute(sa.update(requests).where(requests.c.id==row.id).values(setup_nonce_hash=_nonce_digest(nonce),
        setup_totp_encrypted=encrypt_totp(secret), setup_username=encrypt_totp(username)))
    return dict(nonce=nonce, secret=secret, username=username)


@requires_feat_context('FEAT-IDEN-106')
def complete_setup(*, request_id, nonce, totp_code, correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if (not _active(user, row) or not isinstance(nonce, str) or not row.setup_nonce_hash
            or not hmac.compare_digest(row.setup_nonce_hash, _nonce_digest(nonce))):
        return False
    if not _coverage(user, row, confirmed=True):
        return False
    try:
        secret = decrypt_totp(row.setup_totp_encrypted)
        username = decrypt_totp(row.setup_username)
    except ValueError:
        return False
    if not secret or not username or not pyotp.TOTP(secret).verify(totp_code):
        return False
    if User.query.filter(User.username_lookup_hash == hash_username_lookup(username), User.id != user.id).first():
        return False
    savepoint = db.session.begin_nested()
    try:
        _, user.username_hash, user.username_lookup_hash = build_hashed_username_fields(username)
        user.totp_secret_encrypted = row.setup_totp_encrypted
        user.current_session_nonce = secrets.token_hex(32)
        PasskeyCredential.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        _clear(row.id, status='verified', completed_at=utc_now(), attempt_nonce_hash=None)
        db.session.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        return False
    return True



def read_setup(request_id, nonce):
    """Pure read for re-displaying an authorized enrollment form."""
    requests, _ = _tables()
    row = db.session.execute(sa.select(requests).where(requests.c.id == request_id)).first()
    if (not row or row.status != 'pending' or row.completed_at is not None or ensure_utc(row.expires_at) <= utc_now()
            or not isinstance(nonce, str) or not row.setup_nonce_hash
            or not hmac.compare_digest(row.setup_nonce_hash, _nonce_digest(nonce))):
        return None
    try:
        secret = decrypt_totp(row.setup_totp_encrypted)
        username = decrypt_totp(row.setup_username)
    except ValueError:
        return None
    return dict(secret=secret, username=username) if secret and username else None


@requires_feat_context('FEAT-IDEN-105')
def save_progress(*, request_id, attempt_nonce, username='', correlation_id, idempotency_key):
    user, row = _lock(request_id)
    if not _active(user, row) or not _access(row, attempt_nonce):
        return None
    requests, _ = _tables()
    for _ in range(20):
        pin = f'{secrets.randbelow(1000000):06d}'
        digest = resume_digest(pin)
        if not db.session.execute(sa.select(requests.c.id).where(requests.c.resume_pin_hash==digest)).first():
            break
    else:
        return None
    db.session.execute(sa.update(requests).where(requests.c.id==row.id).values(resume_pin_hash=digest,
        partial_codes=None, resume_new_username=encrypt_totp(username) if username else None))
    return pin


@requires_feat_context('FEAT-IDEN-105')
def resume_attempt(*, pin, correlation_id, idempotency_key):
    from app.services.recovery_service import find_recovery_request_by_resume_pin
    found = find_recovery_request_by_resume_pin(resume_digest(pin), utc_now())
    if not found:
        return None
    user, row = _lock(found.id)
    if not _active(user, row) or row.resume_pin_hash != resume_digest(pin):
        return None
    nonce = secrets.token_urlsafe(32)
    requests, _ = _tables()
    db.session.execute(sa.update(requests).where(requests.c.id==row.id).values(attempt_nonce_hash=_attempt_digest(nonce),
        setup_nonce_hash=None, setup_totp_encrypted=None, setup_username=None))
    return dict(id=row.id, nonce=nonce)


def attempt_status(request_id, nonce):
    requests, _ = _tables()
    row = db.session.execute(sa.select(requests).where(requests.c.id==request_id)).first()
    if not row or not _access(row, nonce) or row.status!='pending' or ensure_utc(row.expires_at)<=utc_now():
        return None
    table = _challenges()
    proofs = {p.class_id:p for p in db.session.execute(sa.select(table).where(table.c.recovery_request_id==row.id))}
    if set(proofs) != set(row.required_class_ids) or not all(p.selected_at for p in proofs.values()):
        return None
    classes = {c.class_id:c for c in ClassEconomy.query.filter_by(teacher_user_id=row.user_id).all()}
    if not set(row.required_class_ids).issubset(classes):
        return None
    # Received is solely an input receipt; no correctness, generation times or recipients.
    return dict(expires_at=row.expires_at, classes=[dict(class_ref=classes[c].class_public_id, number=i+1, label=classes[c].display_name or classes[c].section or classes[c].join_code,
        received=c in proofs and proofs[c].received_round==row.submission_round,
        selected=c in proofs and proofs[c].selected_at is not None) for i,c in enumerate(row.required_class_ids)])

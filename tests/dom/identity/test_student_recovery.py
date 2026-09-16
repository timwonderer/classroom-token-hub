"""
Tests for the student account recovery flow (DOM-IDEN-002 v2.1).

Recovery flow:
  Step 1 — Teacher generates a reset code → written to User.reset_code /
            reset_code_generated_at / reset_code_expires_at
  Step 2 — Student submits ONLY the reset_code at /recovery/lookup
            (no join_code required). Backend finds User by reset_code,
            consumes the code, preserves credentials, binds setup to this session.
  Step 3 — Student creates a new username at /student/create-username
  Step 4 — Student sets new PIN + passphrase at /student/setup-pin-passphrase
            (atomically updates User credentials, nulls reset fields)

`seat.user_id IS NOT NULL` is the sole indicator that a student has claimed.
`user.pin_hash IS NOT NULL` means credentials are set.
No `has_completed_setup` flag. No recovery fields on IdentityProfile.
"""
import re
import pytest
from datetime import timedelta

from app import db
from app.models import Seat, IdentityProfile, User, UserRole, Transaction
from app.utils.money_guard import check_financial_cooldown
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import (
    admin_generate_recovery_code,
    student_create_username,
    student_lookup_recovery_code,
    student_setup_pin_passphrase,
)


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def recovery_data(client):
    """Set up a teacher, class, and a claimed student for recovery tests."""
    class_row = initialize("chemistry_p1", client.application)
    teacher = class_row.teacher_user
    teacher_seat = class_row.teacher_seat
    seat = class_row.students[0].seat
    user = class_row.students[0].user
    profile = class_row.students[0].profile
    with FEATContext("FEAT-IDEN-001", idempotency_key="recovery:fixture:name-override"):
        profile.first_name = "Original"
        profile.last_name = "Student"
        db.session.flush()
    class_row.students[0].first_name = "Original"
    class_row.students[0].last_name = "Student"

    return {
        "teacher": teacher,
        "teacher_seat": teacher_seat,
        "user": user,
        "seat": seat,
        "join_code": class_row.join_code,
        "class_id": class_row.class_id,
    }


# ------------------------------------------------------------------
# Step 1 — Teacher Initiates Reset
# ------------------------------------------------------------------

def test_DOM_IDEN_002__teacher_generates_reset_code(client, recovery_data):
    """Teacher posts to generate-code -> reset_code written to User."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    resp = admin_generate_recovery_code(client, seat.id)
    # Redirects back to student detail on success
    assert resp.status_code == 302

    linked_user = db.session.get(User, seat.user_id)
    assert linked_user is not None
    assert linked_user.reset_code is not None
    assert len(linked_user.reset_code) == 8
    assert ensure_utc(linked_user.reset_code_expires_at) > utc_now()


def test_DOM_IDEN_002__multiple_resets_invalidate_prior_codes(client, recovery_data):
    """Multiple reset requests overwrite the previous reset code."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    admin_generate_recovery_code(client, seat.id)
    linked_user = db.session.get(User, seat.user_id)
    db.session.refresh(linked_user)
    first_code = linked_user.reset_code

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(linked_user)
    second_code = linked_user.reset_code

    assert first_code != second_code
    assert linked_user.reset_code_expires_at is not None


# ------------------------------------------------------------------
# Step 2 — Student Submits Reset Code
# ------------------------------------------------------------------

def test_DOM_IDEN_002__student_lookup_success(client, recovery_data):
    """Acceptance consumes the code; credentials remain until completion."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_success"):
        db.session.flush()

    resp = student_lookup_recovery_code(client, "RESET123", follow_redirects=False)

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    with client.session_transaction() as sess:
        assert "onboarding_seat_ref" not in sess
        assert sess.get("onboarding_user_ref") == user.id

    # Acceptance consumes the code without interrupting existing credentials.
    db.session.refresh(user)
    assert user.pin_hash is not None
    assert user.passphrase_hash is not None
    assert user.reset_code is None
    assert user.reset_code_expires_at is None
    assert user.recovery_setup_nonce_hash is not None


def test_DOM_IDEN_002__student_lookup_expired_code(client, recovery_data):
    """Expired reset_code -> generic error."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now() - timedelta(minutes=20)
    user.reset_code_expires_at = utc_now() - timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_expired_code"):
        db.session.flush()

    resp = student_lookup_recovery_code(client, "RESET123")

    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__student_lookup_nonexistent_code(client, recovery_data):
    """Completely invalid code -> generic error, no identity revealed."""
    resp = student_lookup_recovery_code(client, "NOTEXIST")

    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__recovery_does_not_create_new_user_row(client, recovery_data):
    """Recovering an account must not create a new User row."""
    user = recovery_data["user"]
    original_user_count = User.query.filter_by(user_role=UserRole.STUDENT).count()

    user.reset_code = "ROWTEST1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_does_not_create_new_user_row"):
        db.session.flush()

    student_lookup_recovery_code(client, "ROWTEST1")

    assert User.query.filter_by(user_role=UserRole.STUDENT).count() == original_user_count


def test_DOM_IDEN_002__recovery_preserves_seat_binding(client, recovery_data):
    """Recovery lookup must not disturb seat.user_id binding."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "KEEPCLM1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_seat_binding"):
        db.session.flush()

    student_lookup_recovery_code(client, "KEEPCLM1", follow_redirects=False)

    db.session.refresh(seat)
    assert seat.user_id == user.id
    assert seat.claimed_at is not None


def test_DOM_IDEN_002__recovery_preserves_identity(client, recovery_data):
    """Recovery lookup preserves IdentityProfile first_name/last_name."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "IDTEST01"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_identity"):
        db.session.flush()

    student_lookup_recovery_code(client, "IDTEST01")

    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert profile is not None
    assert profile.first_name == "Original"


# ------------------------------------------------------------------
# Economic Invariance
# ------------------------------------------------------------------

def test_DOM_IDEN_002__recovery_preserves_balance_and_transactions(client, recovery_data):
    """Transaction count unchanged through recovery lookup."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]
    join_code = recovery_data["join_code"]

    tx = Transaction(
        user_id=user.id,
        seat_id=seat.id,
        class_id=recovery_data["class_id"],
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        amount=200.0,
        type="deposit",
        description="Initial deposit",
        account_type="checking",
        join_code=join_code,
    )
    with FEATContext("FEAT-LED-001", idempotency_key="recovery:preserve_transactions"):
        db.session.add(tx)
        db.session.flush()

    tx_count_before = Transaction.query.filter_by(seat_id=seat.id, class_id=recovery_data["class_id"]).count()

    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:reset_code_preserve"):
        user.reset_code = "PRESRV01"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()

    student_lookup_recovery_code(client, "PRESRV01")

    tx_count_after = Transaction.query.filter_by(seat_id=seat.id, class_id=recovery_data["class_id"]).count()
    assert tx_count_after == tx_count_before


# ------------------------------------------------------------------
# Reset Code Security
# ------------------------------------------------------------------

def test_DOM_IDEN_002__reset_code_invalid_after_credential_setup(client, recovery_data):
    """Reset code is consumed and nulled after setup_pin_passphrase completes."""
    user = recovery_data["user"]
    join_code = recovery_data["join_code"]

    user.reset_code = "ONETIME1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_reset_code_invalid_after_setup"):
        db.session.flush()

    student_lookup_recovery_code(client, "ONETIME1")
    student_create_username(client, "planet")
    student_setup_pin_passphrase(
        client,
        pin="1234",
        confirm_pin="1234",
        passphrase="updated-passphrase",
        confirm_passphrase="updated-passphrase",
    )

    db.session.refresh(user)
    assert user.reset_code is None
    assert user.reset_code_expires_at is None
    assert user.pin_hash is not None

    # Attempt reuse
    resp = student_lookup_recovery_code(client, "ONETIME1")
    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__only_one_active_reset_code_per_user(client, recovery_data):
    """Generating a second reset code overwrites the first on the User row."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]
    user = recovery_data["user"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(user)
    first_code = user.reset_code

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(user)

    assert user.reset_code != first_code
    # Only one reset_code column on User — no way for both to coexist
    users_with_first = User.query.filter_by(reset_code=first_code).count()
    assert users_with_first == 0


# ------------------------------------------------------------------
# Edge Cases
# ------------------------------------------------------------------

def test_DOM_IDEN_002__interrupting_reclaim_after_lookup(client, recovery_data):
    """Interrupted setup leaves existing credentials and identity intact."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]
    join_code = recovery_data["join_code"]

    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:midflow_guard"):
        user.reset_code = "MIDFLOW1"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()

    resp = student_lookup_recovery_code(client, "MIDFLOW1", follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(user)
    db.session.refresh(seat)

    # Seat binding preserved
    assert seat.user_id == user.id
    # Credentials preserved until successful setup.
    assert user.pin_hash is not None
    assert user.passphrase_hash is not None
    # Identity profile intact
    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert profile is not None
    assert profile.first_name == "Original"


def test_DOM_IDEN_002__recovery_username_uses_random_segment(client, recovery_data):
    """Recovery username generation stores a generated username in session."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "RAND4001"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_username_random_segment"):
        db.session.flush()

    student_lookup_recovery_code(client, "RAND4001", follow_redirects=False)

    resp = student_create_username(client, "galaxy", follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        generated_username = sess.get("generated_username")

    assert generated_username is not None
    assert "galaxy" in generated_username
    assert len(generated_username) > len("galaxy"), "Username must include generated segments beyond the base word"


def test_DOM_IDEN_006__claim_account_resolves_join_code_to_class_id(client):
    class_row = initialize("chemistry_p1", client.application)
    from app.models import Seat, User, UserRole
    with FEATContext("FEAT-IDEN-001", idempotency_key="claim_account:test_unclaimed_seat"):
        student = User(user_role=UserRole.STUDENT, username_hash="claim-student")
        db.session.add(student)
        db.session.flush()
        seat = Seat(
            user_id=None,
            class_id=class_row.class_id,
            role="student",
            claimed_at=None,
            claim_first_name_hash=hash_username_lookup("First".lower()),
            claim_last_name_hash=hash_username_lookup("Last".lower()),
        )
        db.session.add(seat)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=seat.id,
                class_id=class_row.class_id,
                profile_type="student_unclaimed",
                first_name="First",
                last_name="Last",
            )
        )
        db.session.flush()

    resp = client.post(
        "/student/claim-account",
        data={
            "join_code": class_row.join_code,
            "first_name": "First",
            "last_name": "Last",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    with client.session_transaction() as sess:
        assert sess.get("onboarding_seat_ref") == seat.id


# ------------------------------------------------------------------
# Financial Cooldown Utility (money_guard.check_financial_cooldown)
# ------------------------------------------------------------------

def test_DOM_IDEN_002__financial_cooldown_always_permits(recovery_data):
    """check_financial_cooldown always returns (True, '') after field removal."""
    seat = recovery_data["seat"]
    allowed, msg = check_financial_cooldown(seat)
    assert allowed is True
    assert msg == ""


def test_DOM_IDEN_002__recovery_never_queries_participation(client, recovery_data):
    """Code redemption and credential replacement use only the principal."""
    from sqlalchemy import event

    user = recovery_data["user"]
    seat = recovery_data["seat"]
    before = (seat.user_id, seat.claimed_at, seat.claim_first_name_hash,
              seat.claim_last_name_hash, seat.roster_fingerprint, seat.dedupe_code)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:principal-only"):
        user.reset_code = "SCOPE001"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()
    with client.session_transaction() as sess:
        sess["onboarding_seat_ref"] = seat.id
        sess["generated_username"] = "stale-claim-username"

    participation_statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if re.search(r"\b(seats|identity_profiles|classes)\b", statement, re.I):
            participation_statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        response = student_lookup_recovery_code(client, "SCOPE001")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert "onboarding_seat_ref" not in sess
            assert "generated_username" not in sess
            assert sess["onboarding_user_ref"] == user.id
        assert student_create_username(client, "planet").status_code == 200
        response = student_setup_pin_passphrase(
            client, pin="4826", confirm_pin="4826",
            passphrase="updated-passphrase7", confirm_passphrase="updated-passphrase7",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "setup-complete" in response.location
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert participation_statements == []
    db.session.refresh(user)
    assert user.pin_hash is not None
    assert user.passphrase_hash is not None
    db.session.refresh(seat)
    assert (seat.user_id, seat.claimed_at, seat.claim_first_name_hash,
            seat.claim_last_name_hash, seat.roster_fingerprint, seat.dedupe_code) == before


def test_DOM_IDEN_002__setup_rejects_mixed_claim_and_recovery_context(client, recovery_data):
    from app.routes.student import _get_credential_setup_state
    from flask import session

    with client.application.test_request_context():
        session["onboarding_user_ref"] = recovery_data["user"].id
        session["onboarding_seat_ref"] = recovery_data["seat"].id
        assert _get_credential_setup_state() == (None, None)


def test_DOM_IDEN_002__recovery_setup_rejects_already_credentialed_user(client, recovery_data):
    from app.feats.identity_feat import activate_student_credentials

    result = activate_student_credentials(
        seat_id=None, user_id=recovery_data["user"].id,
        username="replacement", pin="4826", passphrase="replacement-passphrase7",
        correlation_id="recovery-replay-test", idempotency_key="recovery:replay-test",
    )
    assert not result.success
    assert result.error_code == "INVALID_RECOVERY_STATE"


def _authorize_recovery(user):
    from app.feats.identity_feat import validate_recovery_code
    with FEATContext("FEAT-IDEN-003", idempotency_key="recovery:atomic:seed"):
        user.reset_code = "ATOMIC01"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()
    result = validate_recovery_code(
        reset_code="ATOMIC01", correlation_id="corr_recovery_validate",
        idempotency_key="recovery:atomic:validate",
    )
    assert result.success
    return result.setup_authorization


def _complete_recovery(user_id, authorization, username="recovered-student"):
    from app.feats.identity_feat import activate_student_credentials
    return activate_student_credentials(
        seat_id=None, user_id=user_id, recovery_authorization=authorization,
        username=username, pin="4826", passphrase="new-passphrase7",
        correlation_id="corr_recovery_complete", idempotency_key=f"recovery:complete:{username}",
    )


def _credential_state(user):
    return (user.username_hash, user.username_lookup_hash, user.pin_hash,
            user.passphrase_hash, user.current_session_nonce, user.reset_code,
            user.reset_code_generated_at, user.reset_code_expires_at,
            user.recovery_setup_nonce_hash, user.recovery_setup_expires_at)


def test_recovery_acceptance_preserves_credentials_and_completion_consumes_nonce(client, recovery_data):
    from app.hash_utils import verify_password
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    before = _credential_state(user)
    assert user.reset_code is None
    assert user.recovery_setup_nonce_hash is not None
    assert authorization != user.recovery_setup_nonce_hash
    assert _complete_recovery(user.id, authorization).success
    db.session.refresh(user)
    assert user.username_lookup_hash == hash_username_lookup("recovered-student")
    assert verify_password("4826", user.pin_hash)
    assert verify_password("new-passphrase7", user.passphrase_hash)
    assert user.current_session_nonce != before[4]
    assert user.reset_code is None
    assert user.reset_code_generated_at is None
    assert user.reset_code_expires_at is None
    assert user.recovery_setup_nonce_hash is None
    assert user.recovery_setup_expires_at is None
    after = _credential_state(user)
    assert not _complete_recovery(user.id, authorization, "replay-student").success
    db.session.refresh(user)
    assert _credential_state(user) == after


@pytest.mark.parametrize("reason", ["expired", "reissued", "missing", "wrong_user"])
def test_recovery_completion_rechecks_authorization(client, recovery_data, monkeypatch, reason):
    from app.feats import identity_feat
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    if reason == "expired":
        deadline = ensure_utc(user.recovery_setup_expires_at)
        monkeypatch.setattr(identity_feat, "utc_now", lambda: deadline)
    elif reason == "reissued":
        from app.feats.identity_feat import generate_teacher_reset_code
        result = generate_teacher_reset_code(
            seat_id=recovery_data["seat"].id, teacher_user_id=recovery_data["teacher"].id,
            correlation_id="corr_recovery_reissue", idempotency_key="recovery:reissue",
        )
        assert result.success
    elif reason == "missing":
        authorization = None
    elif reason == "wrong_user":
        user = User.query.filter(User.user_role == "student", User.id != user.id).first()
    before = _credential_state(user)
    assert not _complete_recovery(user.id, authorization).success
    db.session.refresh(user)
    assert _credential_state(user) == before


def test_recovery_username_collision_preserves_code_and_credentials(client, recovery_data):
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    other = User.query.filter(User.user_role == "student", User.id != user.id).first()
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:duplicate"):
        other.username_lookup_hash = hash_username_lookup("duplicate-student")
        db.session.flush()
    before = _credential_state(user)
    result = _complete_recovery(user.id, authorization, "duplicate-student")
    assert not result.success
    assert result.error_code == "USERNAME_TAKEN"
    db.session.refresh(user)
    assert _credential_state(user) == before
    assert _complete_recovery(user.id, authorization).success


def test_recovery_concurrent_completion_has_one_winner(client, recovery_data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import event
    from app.hash_utils import hash_username_lookup

    if db.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row-lock semantics")
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    user_id = user.id
    engine = db.engine
    app = client.application
    db.session.remove()
    barrier = Barrier(2)

    def synchronize(_conn, _cursor, statement, _params, _context, _many):
        if "FOR UPDATE" in statement and "users" in statement:
            barrier.wait(timeout=15)

    def complete(username):
        with app.app_context():
            return username, _complete_recovery(user_id, authorization, username).success

    event.listen(engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(complete, ["concurrent-one", "concurrent-two"]))
    finally:
        event.remove(engine, "before_cursor_execute", synchronize)
    assert sum(success for _, success in results) == 1
    winner = next(name for name, success in results if success)
    user = db.session.get(User, user_id)
    assert user.username_lookup_hash == hash_username_lookup(winner)
    assert user.reset_code is None


def test_recovery_duplicate_code_fails_closed(client, recovery_data):
    from app.feats.identity_feat import validate_recovery_code
    user = recovery_data["user"]
    _authorize_recovery(user)
    other = User.query.filter(User.user_role == "student", User.id != user.id).first()
    with FEATContext("FEAT-IDEN-003", idempotency_key="recovery:ambiguous"):
        user.reset_code = other.reset_code = "ATOMIC01"
        user.reset_code_generated_at = other.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = other.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()
    result = validate_recovery_code(
        reset_code="ATOMIC01", correlation_id="corr_recovery_ambiguous",
        idempotency_key="recovery:ambiguous:validate",
    )
    assert not result.success
    assert result.error_message == "Invalid or expired recovery code."


def test_recovery_new_session_cannot_use_consumed_code(client, recovery_data):
    user = recovery_data["user"]
    with FEATContext("FEAT-IDEN-003", idempotency_key="recovery:session:seed"):
        user.reset_code = "SESSION1"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()
    before_credentials = _credential_state(user)[:5]
    student_lookup_recovery_code(client, "SESSION1", follow_redirects=False)
    with client.session_transaction() as sess:
        nonce = sess["recovery_setup_authorization"]
        assert not sess.permanent
    other_client = client.application.test_client()
    response = student_lookup_recovery_code(other_client, "SESSION1")
    assert b"Invalid or expired recovery code" in response.data
    with other_client.session_transaction() as sess:
        assert "recovery_setup_authorization" not in sess
    assert other_client.get("/student/create-username").status_code == 302
    db.session.refresh(user)
    assert _credential_state(user)[:5] == before_credentials
    # The authorized original session can still finish.
    assert student_create_username(client, "galaxy").status_code == 200
    response = student_setup_pin_passphrase(
        client, pin="4826", confirm_pin="4826", passphrase="updated-passphrase7",
        confirm_passphrase="updated-passphrase7", follow_redirects=False,
    )
    assert "setup-complete" in response.location
    db.session.refresh(user)
    assert user.recovery_setup_nonce_hash is None


def test_recovery_concurrent_acceptance_has_one_session_winner(client, recovery_data):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import event
    from app.feats.identity_feat import validate_recovery_code

    if db.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row-lock semantics")
    user = recovery_data["user"]
    with FEATContext("FEAT-IDEN-003", idempotency_key="recovery:race:seed"):
        user.reset_code = "RACECODE"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()
    user_id = user.id
    before = _credential_state(user)[:5]
    engine = db.engine
    app = client.application
    db.session.remove()
    barrier = Barrier(2)

    def synchronize(_conn, _cursor, statement, _params, _context, _many):
        if "FOR UPDATE" in statement and "users" in statement:
            barrier.wait(timeout=15)

    def accept(number):
        with app.app_context():
            return validate_recovery_code(
                reset_code="RACECODE", correlation_id=f"corr_accept_{number}",
                idempotency_key=f"recovery:race:{number}",
            )
    event.listen(engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, [1, 2]))
    finally:
        event.remove(engine, "before_cursor_execute", synchronize)
    assert sum(result.success for result in results) == 1
    user = db.session.get(User, user_id)
    assert user.reset_code is None
    assert _credential_state(user)[:5] == before
    winner = next(result for result in results if result.success)
    assert _complete_recovery(user_id, winner.setup_authorization).success


def test_recovery_server_revocation_blocks_each_setup_step(client, recovery_data):
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    with client.session_transaction() as sess:
        sess["onboarding_user_ref"] = user.id
        sess["recovery_setup_authorization"] = authorization
        sess["generated_username"] = "revoked-student"
    with FEATContext("FEAT-IDEN-003", idempotency_key="recovery:server-revoke"):
        user.recovery_setup_nonce_hash = None
        user.recovery_setup_expires_at = None
        db.session.flush()
    before = _credential_state(user)
    for path in ("/student/create-username", "/student/setup-pin-passphrase"):
        # A valid signed cookie cannot restore authority deleted on the server.
        with client.session_transaction() as sess:
            sess["onboarding_user_ref"] = user.id
            sess["recovery_setup_authorization"] = authorization
        response = client.get(path)
        assert response.status_code == 302
        assert "/recovery/lookup" in response.location
    db.session.refresh(user)
    assert _credential_state(user) == before


def test_teacher_edit_reissuance_revokes_recovery_session(client, recovery_data):
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=recovery_data["teacher"].id,
                              class_id=recovery_data["class_id"],
                              seat_id=recovery_data["teacher_seat"].id, role="admin")
    response = client.post("/admin/student/edit", data={
        "seat_id": recovery_data["seat"].id,
        "first_name": "Original", "last_name": "Student", "reset_login": "on",
    })
    assert response.status_code == 302
    db.session.refresh(user)
    assert user.reset_code is not None
    assert user.recovery_setup_nonce_hash is None
    assert user.recovery_setup_expires_at is None
    assert not _complete_recovery(user.id, authorization).success


def test_recovery_completion_failure_rolls_back_nonce_and_credentials(client, recovery_data, monkeypatch):
    user = recovery_data["user"]
    authorization = _authorize_recovery(user)
    before = _credential_state(user)
    original_flush = db.session.flush

    def fail_replacement(*args, **kwargs):
        if user.recovery_setup_nonce_hash is None and user in db.session.dirty:
            raise RuntimeError("simulated credential transaction failure")
        return original_flush(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(db.session, "flush", fail_replacement)
        with pytest.raises(RuntimeError, match="simulated credential"):
            _complete_recovery(user.id, authorization)
    db.session.refresh(user)
    assert _credential_state(user) == before
    assert _complete_recovery(user.id, authorization).success

from app.models import IdentityProfile, Seat, User, UserInviteToken, UserRecoveryToken
from app.models_canonical import (
    IdentityProfile as CanonicalIdentityProfile,
    Seat as CanonicalSeat,
    User as CanonicalUser,
)


def _foreign_key_targets(model, column_name):
    return {
        foreign_key.target_fullname
        for foreign_key in model.__table__.c[column_name].foreign_keys
    }


def test_runtime_identity_schema_separates_auth_claim_and_display_ownership():
    user_columns = set(User.__table__.c.keys())
    seat_columns = set(Seat.__table__.c.keys())
    profile_columns = set(IdentityProfile.__table__.c.keys())

    assert {
        "user_role",
        "username_lookup_hash",
        "totp_secret_encrypted",
        "pin_hash",
        "passphrase_hash",
        "current_session_nonce",
        "last_active_seat_id",
    } <= user_columns
    assert {"claim_first_name_hash", "claim_last_name_hash"} <= seat_columns
    assert "seat_id" in profile_columns

    assert "claim_first_name_hash" not in user_columns
    assert "claim_last_name_hash" not in user_columns
    assert "username_lookup_hash" not in seat_columns

    assert _foreign_key_targets(User, "last_active_seat_id") == {"seats.id"}
    assert _foreign_key_targets(IdentityProfile, "seat_id") == {"seats.id"}
    assert IdentityProfile.__table__.c.seat_id.unique is True


def test_runtime_recovery_and_invite_capabilities_have_lifecycle_fields():
    assert {
        "token_hash",
        "user_role",
        "issued_by_user_id",
        "expires_at",
        "used_at",
        "revoked_at",
    } <= set(UserInviteToken.__table__.c.keys())
    assert {
        "user_id",
        "token_hash",
        "issued_by_user_id",
        "expires_at",
        "used_at",
        "revoked_at",
    } <= set(UserRecoveryToken.__table__.c.keys())

    assert _foreign_key_targets(UserRecoveryToken, "user_id") == {"users.id"}
    assert _foreign_key_targets(UserRecoveryToken, "issued_by_user_id") == {"users.id"}


def test_canonical_reference_identity_schema_matches_runtime_ownership():
    assert "username_lookup_hash" in CanonicalUser.__table__.c
    assert "last_active_seat_id" in CanonicalUser.__table__.c
    assert "claim_first_name_hash" in CanonicalSeat.__table__.c
    assert "claim_last_name_hash" in CanonicalSeat.__table__.c
    assert "seat_id" in CanonicalIdentityProfile.__table__.c

    assert "claim_first_name_hash" not in CanonicalUser.__table__.c
    assert "claim_last_name_hash" not in CanonicalUser.__table__.c

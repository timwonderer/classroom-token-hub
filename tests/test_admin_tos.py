"""
Tests for Terms of Service (ToS) acknowledgment during admin signup.

Ensures that:
1. Admins cannot sign up without agreeing to ToS
2. ToS agreement is properly stored in the database
3. Database schema includes tos_accepted and tos_accepted_at fields
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, AdminInviteCode
from hash_utils import get_random_salt, hash_hmac
from app.utils.encryption import encrypt_totp


def test_admin_signup_without_tos_agreement_fails(client):
    """Test that signup fails when ToS is not agreed to."""
    # Create an invite code
    invite = AdminInviteCode(code="TEST123", used=False)
    db.session.add(invite)
    db.session.commit()

    # Attempt signup without agreeing to ToS
    response = client.post(
        "/admin/signup",
        data={
            "invite_code": "TEST123",
            "username": "newteacher",
            "dob_sum": "2000-01-01",
            "tos_agreed": "false"  # Not agreed
        },
        follow_redirects=False,
    )

    # Should redirect back to signup
    assert response.status_code == 302
    assert "/admin/signup" in response.headers.get("Location", "")

    # Admin should not be created
    admin = Admin.query.filter_by(username="newteacher").first()
    assert admin is None


def test_admin_signup_with_tos_agreement_proceeds_to_totp(client):
    """Test that signup proceeds to TOTP step when ToS is agreed."""
    # Create an invite code
    invite = AdminInviteCode(code="TEST456", used=False)
    db.session.add(invite)
    db.session.commit()

    # Attempt signup with ToS agreement
    response = client.post(
        "/admin/signup",
        data={
            "invite_code": "TEST456",
            "username": "newteacher2",
            "dob_sum": "2000-01-01",
            "tos_agreed": "true"  # Agreed
        },
        follow_redirects=False,
    )

    # Should return 200 with TOTP setup page (not redirect)
    assert response.status_code == 200
    assert b"Set Up Your" in response.data or b"authenticator" in response.data.lower()


def test_admin_signup_complete_saves_tos_acceptance(client):
    """Test that completed signup saves ToS acceptance with timestamp."""
    # Create an invite code
    invite = AdminInviteCode(code="TEST789", used=False)
    db.session.add(invite)
    db.session.commit()

    # Step 1: Initial signup with ToS agreement
    response = client.post(
        "/admin/signup",
        data={
            "invite_code": "TEST789",
            "username": "teacher_tos_test",
            "dob_sum": "2000-01-01",
            "tos_agreed": "true"
        },
        follow_redirects=False,
    )

    # Get TOTP secret from session
    with client.session_transaction() as sess:
        totp_secret = sess.get("admin_totp_secret")
        assert totp_secret is not None

    # Step 2: Submit TOTP code to complete signup
    totp = pyotp.TOTP(totp_secret)
    response = client.post(
        "/admin/signup",
        data={
            "username": "teacher_tos_test",
            "invite_code": "TEST789",
            "dob_sum": "2000-01-01",
            "totp_code": totp.now(),
            "tos_agreed": "true"
        },
        follow_redirects=False,
    )

    # Should redirect to dashboard or welcome page
    assert response.status_code == 302

    # Verify admin was created with ToS acceptance
    admin = Admin.query.filter_by(username="teacher_tos_test").first()
    assert admin is not None
    assert admin.tos_accepted is True
    assert admin.tos_accepted_at is not None
    assert isinstance(admin.tos_accepted_at, datetime)

    # Verify timestamp is recent (within last minute)
    # Handle both naive and timezone-aware datetimes safely
    tos_time = admin.tos_accepted_at
    if tos_time.tzinfo is None:
        tos_time = tos_time.replace(tzinfo=timezone.utc)
    time_diff = datetime.now(timezone.utc) - tos_time
    assert time_diff.total_seconds() < 60


def test_admin_model_has_tos_fields(client):
    """Test that Admin model has the required ToS fields."""
    # Check that the fields exist on the model
    assert hasattr(Admin, 'tos_accepted')
    assert hasattr(Admin, 'tos_accepted_at')

    # Create an admin and verify defaults
    totp_secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp(totp_secret)
    salt = get_random_salt()
    dob_sum = 2000
    dob_sum_hash = hash_hmac(str(dob_sum).encode(), salt)

    admin = Admin(
        username="test_schema_check",
        totp_secret=encrypted_secret,
        dob_sum_hash=dob_sum_hash,
        salt=salt
    )
    db.session.add(admin)
    db.session.commit()

    # Verify default values
    assert admin.tos_accepted is False  # Should default to False
    assert admin.tos_accepted_at is None

    # Update and verify
    admin.tos_accepted = True
    admin.tos_accepted_at = datetime.now(timezone.utc)
    db.session.commit()

    # Refresh from database
    db.session.refresh(admin)
    assert admin.tos_accepted is True
    assert admin.tos_accepted_at is not None


def test_tos_validation_prevents_empty_string(client):
    """Test that empty or invalid tos_agreed values are rejected."""
    # Create an invite code
    invite = AdminInviteCode(code="TESTINVALID", used=False)
    db.session.add(invite)
    db.session.commit()

    # Test with empty string
    response = client.post(
        "/admin/signup",
        data={
            "invite_code": "TESTINVALID",
            "username": "invalidtos",
            "dob_sum": "2000-01-01",
            "tos_agreed": ""
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/signup" in response.headers.get("Location", "")

    # Test with invalid value
    response = client.post(
        "/admin/signup",
        data={
            "invite_code": "TESTINVALID",
            "username": "invalidtos2",
            "dob_sum": "2000-01-01",
            "tos_agreed": "yes"  # Should be "true"
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/signup" in response.headers.get("Location", "")

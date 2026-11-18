"""Operator CLI boundary, execution attribution and retry behavior."""

import logging
from concurrent.futures import ThreadPoolExecutor

import click
import pytest
from sqlalchemy import event

from app.cli_commands import create_sysadmin_command
from app.feats.sysadmin_bootstrap import provision_sysadmin
from app.models import ClassEconomy, Seat, User, UserRole
from app.utils.encryption import decrypt_totp
from tests.helpers.operation_routes import login_sysadmin


def test_FEAT_IDEN_008__cli_creates_one_system_principal(app, client, caplog):
    caplog.set_level(logging.INFO)
    runner = app.test_cli_runner()
    assert User.query.count() == ClassEconomy.query.count() == Seat.query.count() == 0
    result = runner.invoke(args=["create-sysadmin", "--username", "bootstrap_operator"])
    assert result.exit_code == 0
    user = User.query.one()
    assert user.user_role == UserRole.SYSADMIN
    assert user.last_active_class_id is None and user.last_active_seat_id is None
    assert ClassEconomy.query.count() == Seat.query.count() == 0
    assert "FEAT-ENTRY: feat=FEAT-IDEN-008" in caplog.text
    assert "FEAT-ENTRY: feat=FEAT-IDEN-001" not in caplog.text
    secret = decrypt_totp(user.totp_secret_encrypted)
    enrollment_delivered_privately = secret in result.output and secret not in caplog.text
    assert enrollment_delivered_privately

    retry = runner.invoke(args=["create-sysadmin", "--username", " bootstrap_operator "])
    assert retry.exit_code == 0
    replay_disclosed_enrollment = "otpauth://" in retry.output
    assert not replay_disclosed_enrollment
    invalid = runner.invoke(args=["create-sysadmin", "--username", "   "])
    assert invalid.exit_code == 2
    credentials_preserved = decrypt_totp(User.query.one().totp_secret_encrypted) == secret
    assert credentials_preserved

    login_sysadmin(client, username="bootstrap_operator", totp_secret=secret)
    with client.session_transaction() as session:
        assert session["role"] == "sysadmin"
        assert "class_id" not in session and "seat_id" not in session
    assert client.get("/admin/").status_code == 302
    assert client.get("/student/dashboard").status_code == 302


def test_FEAT_IDEN_008__rejects_request_execution(app):
    with app.test_request_context(method="POST"), pytest.raises(PermissionError):
        provision_sysadmin("http_attempt")
    assert User.query.count() == 0


def test_FEAT_IDEN_008__claimed_student_login_is_preserved(app):
    from tests.helpers.classroom_initializer import initialize

    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    original_id = student.user.id
    original_hash = student.user.passphrase_hash
    result = app.test_cli_runner().invoke(args=["create-sysadmin", "--username", student.username])
    assert result.exit_code == 0
    collision_disclosed_enrollment = "otpauth://" in result.output
    assert not collision_disclosed_enrollment
    assert User.query.filter_by(user_role=UserRole.SYSADMIN).count() == 0
    saved = User.query.filter_by(id=original_id).one()
    assert saved.user_role == UserRole.STUDENT and saved.passphrase_hash == original_hash


def test_FEAT_IDEN_008__concurrent_login_collision_rolls_back_loser(app):
    # The second operator wins after the first operator's lookup but before
    # its INSERT. Separate threads give each invocation a real transaction.
    username = "racing_operator"
    winning_secrets = []

    def competing_command():
        with app.app_context(), click.Context(create_sysadmin_command):
            return provision_sysadmin(username)

    def before_insert(mapper, connection, target):
        with ThreadPoolExecutor(max_workers=1) as executor:
            winning_secrets.append(executor.submit(competing_command).result(timeout=10))

    event.listen(User, "before_insert", before_insert, once=True)
    try:
        result = app.test_cli_runner().invoke(args=["create-sysadmin", "--username", username])
    finally:
        event.remove(User, "before_insert", before_insert)

    assert result.exit_code == 0
    collision_reported = result.output.strip() == "Username already exists."
    assert collision_reported
    winner_preserved = decrypt_totp(User.query.one().totp_secret_encrypted) == winning_secrets[0]
    assert winner_preserved

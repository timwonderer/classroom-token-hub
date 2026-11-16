"""
Flask CLI commands for database operations and administration.

Commands here are registered via ``init_app`` (called from ``app/__init__.py``),
so they are available on every app instance — including the test runner — rather
than only when a specific entrypoint module (e.g. ``wsgi.py``) is imported.
"""

import os
import sys
import time

import click
from flask.cli import with_appcontext


def _wait_for_enter_or_timeout(timeout_seconds=180):
    """Wait until Enter is pressed or ``timeout_seconds`` elapses.

    Used after the plaintext TOTP secret is displayed so the operator can clear
    it from the terminal as soon as they've stored it. Returns "enter",
    "timeout", or "non_interactive".
    """
    if not sys.stdin or not sys.stdin.isatty():
        return "non_interactive"

    print(
        f"\nPress ENTER to clear this screen now, "
        f"or it will auto-clear in {timeout_seconds // 60} minutes."
    )
    deadline = time.monotonic() + timeout_seconds

    if os.name == "nt":
        import msvcrt

        while True:
            remaining = int(deadline - time.monotonic())
            if remaining <= 0:
                print("\nTimeout reached. Clearing screen...")
                return "timeout"

            mins, secs = divmod(remaining, 60)
            print(
                f"\rAuto-clear in {mins:02d}:{secs:02d} "
                "(Press ENTER to clear now.)",
                end="",
                flush=True,
            )

            tick_end = time.monotonic() + 1
            while time.monotonic() < tick_end:
                if msvcrt.kbhit() and msvcrt.getwch() in ("\r", "\n"):
                    print()
                    return "enter"
                time.sleep(0.05)
    else:
        import select

        while True:
            remaining = int(deadline - time.monotonic())
            if remaining <= 0:
                print("\nTimeout reached. Clearing screen...")
                return "timeout"

            mins, secs = divmod(remaining, 60)
            print(
                f"\rAuto-clear in {mins:02d}:{secs:02d} "
                "(Press ENTER to clear now.)",
                end="",
                flush=True,
            )

            ready, _, _ = select.select([sys.stdin], [], [], 1)
            if ready:
                sys.stdin.readline()
                print()
                return "enter"


@click.command('normalize-claim-credentials')
def normalize_claim_credentials_command():
    """No-op: seat claim credential normalization is no longer needed.

    Seat claim credentials are managed via Seat.claim_first_name_hash /
    Seat.claim_last_name_hash.
    """
    click.echo("normalize-claim-credentials: no-op")


@click.command('create-sysadmin')
@click.option('--username', prompt='Enter system admin username', help='System admin login username.')
@with_appcontext
def create_sysadmin_command(username):
    """Create a system admin account (infrastructure operator).

    Sysadmin is the infrastructure operator role; it has no publicly exposed
    creation surface and is provisioned out-of-band at/after deployment. Authority
    lives entirely on ``User.user_role = SYSADMIN``. This command mints that user
    and prints a TOTP secret + QR code for the operator's authenticator app.
    """
    import pyotp
    import qrcode
    from sqlalchemy.exc import IntegrityError

    from app.feats.sysadmin_bootstrap import provision_sysadmin
    from app.utils.auth_username import normalize_auth_username

    username = normalize_auth_username(username)
    if not username:
        raise click.BadParameter("Username is required.", param_hint="--username")

    try:
        totp_secret = provision_sysadmin(username)
    except IntegrityError as exc:
        # Another invocation can reserve the login between the check and flush.
        # The FEAT has rolled back. Treat only that unique collision as a replay.
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != "ix_users_username_lookup_hash":
            raise
        totp_secret = None
    if totp_secret is None:
        click.echo("Username already exists.")
        return

    totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
        name=username,
        issuer_name="Classroom Token Hub",
    )
    click.echo(f"\nSystem admin '{username}' created successfully.")
    click.echo("\n" + "=" * 70)
    click.echo("SCAN THIS QR CODE WITH YOUR AUTHENTICATOR APP")
    click.echo("=" * 70)

    qr = qrcode.QRCode(border=2)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    click.echo("\n" + "=" * 70)
    click.echo("TOTP SECRET (store this securely as backup):")
    click.echo(f"   {totp_secret}")
    click.echo("=" * 70)
    click.echo("\nIMPORTANT: Save this secret in a secure location!")
    click.echo("   This is the ONLY time it will be displayed in plaintext.")
    click.echo("   The secret is encrypted in the database for security.")
    click.echo("\n   Manual entry URI:")
    click.echo(f"   {totp_uri}")
    click.echo("=" * 70)

    # Clear the plaintext secret from the terminal once the operator has stored
    # it (or after a 3-minute timeout on interactive terminals).
    wait_result = _wait_for_enter_or_timeout(timeout_seconds=180)
    os.system('cls' if os.name == 'nt' else 'clear')

    click.echo("\nSystem admin account created and screen cleared for security.")
    click.echo(f"   Username: {username}")
    click.echo("   TOTP secret has been encrypted and stored in the database.\n")
    if wait_result == "timeout":
        click.echo("   Screen auto-cleared after 3 minutes.")
    elif wait_result == "non_interactive":
        click.echo("   Non-interactive terminal detected; screen cleared immediately.")


def init_app(app):
    """Register CLI commands with Flask app."""
    from app.migration_cli import guard_revision_generation

    guard_revision_generation(app)
    app.cli.add_command(normalize_claim_credentials_command)
    app.cli.add_command(create_sysadmin_command)

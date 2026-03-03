"""
Flask CLI commands for database operations and migrations.

WARNING: These migration commands reference the deprecated Student.teacher_id column.
They are designed to run BEFORE migration 1e07c37d3c7c (which drops teacher_id).
After that migration is applied, these commands will fail with AttributeError.
These are pre-migration utility tools only.
"""

import click
import time
from datetime import datetime, timezone

from app.extensions import db
from app.models import Student, StudentTeacher, TeacherBlock
from app.utils.join_code import generate_join_code
from app.routes.admin import (
    MAX_JOIN_CODE_RETRIES,
    FALLBACK_BLOCK_PREFIX_LENGTH,
    FALLBACK_CODE_MODULO,
    LEGACY_PLACEHOLDER_FIRST_NAME,
)
from app.utils.claim_credentials import normalize_claim_hash


@click.command('normalize-claim-credentials')
def normalize_claim_credentials_command():
    """Backfill canonical claim hashes for roster seats when possible."""

    click.echo("Normalizing roster claim credentials to canonical format...")

    updated = 0

    # Normalize TeacherBlock entries
    for seat in TeacherBlock.query.yield_per(100):
        # Skip placeholder rows that only store join codes
        if seat.first_name == LEGACY_PLACEHOLDER_FIRST_NAME:
            continue

        first_initial = seat.first_name.strip()[0].upper() if seat.first_name else None
        updated_hash, changed = normalize_claim_hash(
            seat.first_half_hash,
            first_initial,
            seat.last_initial,
            None,
            seat.salt,
        )
        if changed and updated_hash:
            seat.first_half_hash = updated_hash
            updated += 1

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        click.echo(f"Failed to normalize claim credentials: {exc}", err=True)
        raise click.Abort()

    if updated == 0:
        click.echo(
            "No records were updated. Canonical normalization requires plaintext DOB sums, "
            "which are no longer stored."
        )
    else:
        click.echo(f"Updated {updated} record(s) to use canonical claim hashes.")


def init_app(app):
    """Register CLI commands with Flask app."""
    app.cli.add_command(normalize_claim_credentials_command)

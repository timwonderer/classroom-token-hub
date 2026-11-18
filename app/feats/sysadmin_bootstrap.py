"""Operator-only provision of a system authentication principal (FEAT-IDEN-008)."""

import click

from app.feats.base import requires_feat_context
from app.services.identity_service import create_system_principal


@requires_feat_context("FEAT-IDEN-008", key_per_call=True)
def provision_sysadmin(username: str) -> str | None:
    """Return enrollment material only to the CLI that creates the principal."""
    from app.cli_commands import create_sysadmin_command

    invocation = click.get_current_context(silent=True)
    if invocation is None or invocation.command is not create_sysadmin_command:
        raise PermissionError("Sysadmin bootstrap requires the create-sysadmin command.")
    return create_system_principal(username)

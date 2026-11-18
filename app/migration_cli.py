"""Choose unclaimed IDs before Flask-Migrate writes a revision file."""

from copy import copy
from functools import wraps

import click
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from flask import current_app, g

from scripts.generate_revision_id import generate_revision_id


def _with_unused_revision(callback):
    @wraps(callback)
    def generate(*, directory=None, rev_id=None, **options):
        migrate = current_app.extensions["migrate"].migrate
        config = migrate.get_config(directory or g.directory)
        try:
            scripts = ScriptDirectory.from_config(config)
            existing = {revision.revision for revision in scripts.walk_revisions()}
            rev_id = generate_revision_id(existing, requested=rev_id)
        except (CommandError, ValueError) as error:
            raise click.ClickException(str(error)) from error
        return callback(directory=directory, rev_id=rev_id, **options)

    return generate


def guard_revision_generation(app):
    """Keep upstream command options and scope the guard to this Flask app."""
    group = copy(app.cli.commands["db"])
    group.commands = group.commands.copy()
    for name in ("revision", "migrate", "merge"):
        command = copy(group.commands[name])
        command.callback = _with_unused_revision(command.callback)
        group.add_command(command, name=name)
    app.cli.add_command(group, name="db")

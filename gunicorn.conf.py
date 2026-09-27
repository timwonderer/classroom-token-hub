"""Gunicorn configuration, loaded automatically from the working directory.

Production runs ``gunicorn wsgi:app`` from the repository root (the systemd
unit's WorkingDirectory), and gunicorn reads ``./gunicorn.conf.py`` by default.
Bind address, worker count and timeouts stay on the command line; this file only
carries the scheduler hook.

The server is the only process type that runs scheduled jobs. Starting them
here, rather than in ``create_app()``, keeps them out of every flask command,
migration, script and shell that imports the application. The advisory lock
inside ``start_scheduler_when_owner`` keeps them to one process even when there
are several workers or two servers overlap during a restart.
"""


def post_worker_init(worker):
    from app import app
    from app.scheduler_ownership import start_scheduler_when_owner

    start_scheduler_when_owner(app)

"""Routes the status service's own log records to stderr, where Cloud Run collects them."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Emit INFO and above from ``status_service`` loggers.

    Gunicorn configures only its own loggers. Without a handler here, Python's
    last-resort handler prints WARNING and above and silently drops INFO, which
    includes the line recording how each operator authenticated.
    """
    service_logger = logging.getLogger("status_service")
    if not service_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        service_logger.addHandler(handler)
    service_logger.setLevel(logging.INFO)

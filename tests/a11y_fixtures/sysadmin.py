"""Fixture states for sysadmin templates."""

from __future__ import annotations

from tests.a11y_fixtures import register

_SYSADMIN = "sysadmin-example"
_LOGS = [
    {"timestamp": "2030-01-01 12:00:00", "level": "INFO", "module": "app.routes.main", "message": "Request served"},
    {"timestamp": "2030-01-01 12:00:05", "level": "WARNING", "module": "app.auth", "message": "Session expired"},
    {"timestamp": "2030-01-01 12:00:09", "level": "ERROR", "module": "app.feats.base", "message": "Example failure<br>second line"},
]

register("system_admin_logs.html", "populated", lambda: {
    "logs": _LOGS, "current_page": "sysadmin_logs", "current_sysadmin_display_name": _SYSADMIN,
}, path="/sysadmin/logs")
register("system_admin_logs.html", "empty", lambda: {
    "logs": [], "current_page": "sysadmin_logs", "current_sysadmin_display_name": _SYSADMIN,
}, path="/sysadmin/logs")

import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_ACCESS_LOG_TIMEZONE = "America/Los_Angeles"


def _resolve_access_log_timezone():
    tz_name = os.getenv("GUNICORN_ACCESS_LOG_TIMEZONE", DEFAULT_ACCESS_LOG_TIMEZONE).strip() or DEFAULT_ACCESS_LOG_TIMEZONE
    try:
        return tz_name, ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return DEFAULT_ACCESS_LOG_TIMEZONE, ZoneInfo(DEFAULT_ACCESS_LOG_TIMEZONE)


def _format_local_access_timestamp(created):
    _, target_tz = _resolve_access_log_timezone()
    local_dt = datetime.fromtimestamp(created, tz=timezone.utc).astimezone(target_tz)
    return local_dt.strftime("[%d/%b/%Y:%H:%M:%S %z]")


def _format_access_message(atoms, timestamp_local):
    remote_addr = atoms.get("h", "-")
    user = atoms.get("u", "-")
    request_line = atoms.get("r")
    if not request_line:
        method = atoms.get("m", "-")
        path = atoms.get("U", "-")
        query_string = atoms.get("q")
        target = f"{path}{query_string}" if query_string and query_string != "-" else path
        protocol = atoms.get("H", "-")
        request_line = f"{method} {target} {protocol}"
    status = atoms.get("s", "-")
    response_bytes = atoms.get("B", "-")
    referer = atoms.get("f", "-")
    user_agent = atoms.get("a", "-")
    return (
        f'{remote_addr} - {user} {timestamp_local} '
        f'"{request_line}" {status} {response_bytes} '
        f'"{referer}" "{user_agent}"'
    )


class GunicornJsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
            "process": getattr(record, "process", None),
        }

        if record.name == "gunicorn.access" and isinstance(record.args, dict):
            atoms = record.args
            timestamp_local = _format_local_access_timestamp(record.created)
            query_string = atoms.get("q")
            if query_string == "-":
                query_string = ""

            payload.update({
                "timestamp_local": timestamp_local,
                "remote_addr": atoms.get("h"),
                "user": atoms.get("u"),
                "request_line": atoms.get("r"),
                "method": atoms.get("m"),
                "path": atoms.get("U"),
                "query_string": query_string,
                "protocol": atoms.get("H"),
                "status": atoms.get("s"),
                "response_bytes": atoms.get("B"),
                "referer": atoms.get("f"),
                "user_agent": atoms.get("a"),
                "duration_seconds": atoms.get("L"),
                "duration_microseconds": atoms.get("D"),
                "pid": atoms.get("p"),
                "message": _format_access_message(atoms, timestamp_local),
            })

        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

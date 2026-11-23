"""Observed response totals, never reliability verdicts (SPEC-OPS-006 §VII)."""
from datetime import datetime, timedelta, timezone

from status.measurements import classify_component, parse_time

COUNT_KEYS = ("windows", "requests", "4xx", "5xx")
LAST_KEYS = ("last_4xx", "last_5xx")


def error_window(snapshot):
    """Select fixed UTC five-minute windows, never overlapping minute samples."""
    sampled = parse_time(snapshot["sampled_at"])
    if sampled.minute % 5 or sampled.second or sampled.microsecond:
        return None
    service = next(c for c in snapshot["components"] if c["key"] == "service")
    if classify_component(service, snapshot, now=sampled)["state"] in {"STALE", "MONITOR_UNAVAILABLE"}:
        return None
    return {"windows": 1, "requests": service["request_count"],
            "4xx": service["http_4xx_count"], "5xx": service["http_5xx_count"],
            **{f"last_{code}": snapshot["sampled_at"] if service[f"http_{code}_count"] else None
               for code in ("4xx", "5xx")}}


def add_window(previous, window):
    """Called once per immutable source minute inside the persistence transaction."""
    previous = previous or dict.fromkeys(COUNT_KEYS, 0)
    result = {key: previous[key] + window[key] for key in COUNT_KEYS}
    for key in LAST_KEYS:
        candidates = [value for value in (previous.get(key), window[key]) if value]
        result[key] = max(candidates, key=parse_time) if candidates else None
    return result


def _valid_day(value, day):
    """Old reliability counters and malformed derivatives are missing evidence."""
    if not isinstance(value, dict) or set(value) != set(COUNT_KEYS + LAST_KEYS):
        return False
    if any(type(value[key]) is not int or not 0 <= value[key] <= 288_000_000_000 for key in COUNT_KEYS):
        return False
    if not 1 <= value["windows"] <= min(288, day["scheduled_windows"]):
        return False
    if value["4xx"] + value["5xx"] > value["requests"]:
        return False
    start = datetime.fromisoformat(day["date"]).replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=5 * day["scheduled_windows"])
    for code in ("4xx", "5xx"):
        last = value[f"last_{code}"]
        if not value[code]:
            if last is not None:
                return False
        else:
            try:
                stamp = parse_time(last)
            except (TypeError, ValueError):
                return False
            if not start < stamp <= end or stamp.minute % 5 or stamp.second or stamp.microsecond:
                return False
    return True


def error_summary(days):
    totals = dict.fromkeys(COUNT_KEYS, 0)
    totals.update(dict.fromkeys(LAST_KEYS))
    gap_days = 0
    for day in days:
        value = day.get("errors")
        if not _valid_day(value, day):
            gap_days += int(day["scheduled_windows"] > 0)
            continue
        totals = add_window(totals, value)
        gap_days += int(value["windows"] < day["scheduled_windows"])
    scheduled = sum(day["scheduled_windows"] for day in days)
    total = totals["4xx"] + totals["5xx"]
    return {"start": days[0]["date"] if days else "", "end": days[-1]["date"] if days else "",
            "total": total, "requests": totals["requests"], "observed": totals["windows"],
            "scheduled": scheduled, "gap_days": gap_days,
            "coverage": 100 * totals["windows"] / scheduled if scheduled else 0,
            "share_4xx": 100 * totals["4xx"] / total if total else 0,
            "categories": [{"key": code, "label": label, "count": totals[code], "last": totals[f"last_{code}"]}
                           for code, label in (("4xx", "4xx — Request errors"), ("5xx", "5xx — Server errors"))]}

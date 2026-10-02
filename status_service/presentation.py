"""Plain-language presentation of status evidence (SPEC-OPS-006 §VIII).

Teachers and students read these pages. Everything here turns persisted
evidence into words they can act on; nothing here decides what the evidence
means beyond the precedence the specification fixes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from status.measurements import parse_time, retained_activity

AREAS = {
    "service": {"name": "Whole site", "icon": "language", "scope": "Every page of Classroom Token Hub"},
    "login": {"name": "Signing in", "icon": "login", "scope": "Teacher and student sign-in"},
    "attendance": {"name": "Attendance", "icon": "schedule", "scope": "Tap in, tap out and attendance history"},
    "payroll": {"name": "Payroll", "icon": "payments", "scope": "Running payroll and payroll history"},
    "roster": {"name": "Student roster", "icon": "group", "scope": "Adding, editing and exporting students"},
    "classroom_economy": {"name": "Store, rent & insurance", "icon": "storefront",
                          "scope": "Purchases, transfers, rent and insurance"},
}

# Notice stages as readers see them. The stored value never changes; only its words do.
STAGES = {
    "AWARE": {"label": "Checking reports", "tone": "quiet", "icon": "hearing",
              "headline": "we're checking reports of a problem", "meaning": "Something may be up; not confirmed"},
    "INVESTIGATING": {"label": "Looking into it", "tone": "quiet", "icon": "search",
                      "headline": "we're looking into it", "meaning": "Confirmed; finding the cause"},
    "IDENTIFIED": {"label": "Fix underway", "tone": "warn", "icon": "build",
                   "headline": "we've found the cause", "meaning": "Cause found, fix underway"},
    "MONITORING": {"label": "Fixed, watching it", "tone": "info", "icon": "visibility",
                   "headline": "a fix is out and we're watching it", "meaning": "Fix is out, watching it"},
    "RESOLVED": {"label": "Resolved", "tone": "ok", "icon": "task_alt", "headline": "resolved", "meaning": ""},
}

HERO = {
    "maintenance": {"tone": "maint", "label": "Under maintenance"},
    "unavailable": {"tone": "down", "label": "Mostly unavailable"},
    "degraded": {"tone": "problems", "label": "Detected problems"},
    "available": {"tone": "ok", "label": "No known issues"},
    "unknown": {"tone": "unknown", "label": "Unknown"},
}


# ─── Time ───

def as_utc(value) -> datetime | None:
    """An aware UTC datetime, or None when the value carries no timezone."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def iso_utc(value) -> str:
    """Machine-readable UTC for a <time datetime>; empty when no timezone is known."""
    moment = as_utc(value)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else ""


def format_status_time(value: datetime | str) -> str:
    """Present notice times without inferring a missing timezone."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return "Time unavailable"
    if not isinstance(value, datetime):
        return "Time unavailable"
    if value.utcoffset() is None:
        return value.strftime("%Y-%m-%d %H:%M") + " (timezone not provided)"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def time_ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return ""
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''} ago"


def duration_text(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None or end < start:
        return ""
    minutes = int((end - start).total_seconds() // 60)
    if minutes < 1:
        return "lasted under a minute"
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"lasted {minutes} min"
    return f"lasted {hours} h {minutes} min" if minutes else f"lasted {hours} h"


# ─── Hero ───

def overall_observation(checks, measurements, notices, *, now: datetime | None = None) -> dict:
    """One hero state; precedence is fixed by SPEC-OPS-006 §VIII."""
    now = now or datetime.now(timezone.utc)
    rows = {row["key"]: row for row in checks}
    core = [rows[key] for key in ("endpoint", "database") if key in rows]
    checked = [parse_time(row["checked_at"]) for row in core
               if row["state"] in {"PASS", "FAIL"} and row["checked_at"]]
    checked_at = min(checked) if checked else None
    gate = rows.get("gate")
    if gate and gate["state"] == "FAIL":
        # Gate messaging (DOM-OPS-001): an access restriction, never a health claim.
        state, detail = "maintenance", "Access is temporarily restricted while we work on Classroom Token Hub."
    elif any(row["state"] == "FAIL" for row in core):
        state, detail = "unavailable", "An application or database availability check failed."
    elif notices or any(item["collection_state"] == "OK" and item["http_5xx_count"] for item in measurements):
        state, detail = "degraded", "An operator notice or recent server errors need attention."
    elif len(core) == 2 and all(row["state"] == "PASS" for row in core):
        state, detail = "available", "The app is responding and its database connection check passed."
    else:
        state, detail = "unknown", "The latest availability checks could not verify the app."
    return {"state": state, **HERO[state], "detail": detail, "checked_at": checked_at,
            "last_checked": time_ago(checked_at, now) if checked_at else "awaiting availability checks"}


# ─── Area cards ───

def request_outcome(item) -> dict:
    """Bounded response observations, never a business-success verdict."""
    if item["http_5xx_count"]:
        # Automatic, at the Aware level: it never creates or implies a notice.
        return {"tone": "checking", "icon": "hearing", "label": "Checking: errors seen"}
    if item["p95_ms"] > 1500:
        return {"tone": "warn", "icon": "hourglass_top", "label": "Slower than usual"}
    if item["http_2xx_count"] + item["http_3xx_count"]:
        return {"tone": "ok", "icon": "check_circle", "label": "Working"}
    return {"tone": "quiet", "icon": "remove", "label": "Nothing to report"}


def area_cards(measurements, attempt, notices, *, now: datetime, maintenance: bool = False) -> list[dict]:
    activity = retained_activity(attempt.get("last_activity") if attempt else None, now=now)
    latest_notice = {}
    for notice in notices:  # newest first
        latest_notice.setdefault(notice.get("capability"), notice)
    cards = []
    for item in measurements:
        key = item["key"]
        if key == "service":
            continue
        outcome = {"tone": "unknown", "icon": "help", "label": "Status unknown"}
        detail = "We couldn't collect recent measurements."
        if item["state"] == "NO_TRAFFIC":
            outcome = {"tone": "quiet", "icon": "bedtime", "label": "Quiet"}
            detail = "No one has used this in the last five minutes."
        elif item["state"] == "STALE":
            detail = "Our recent measurements are out of date."
        elif item["collection_state"] == "OK":
            outcome = request_outcome(item)
            count = item["request_count"]
            detail = f"{count} {'request' if count == 1 else 'requests'} in the last five minutes."
        notice = latest_notice.get(key)
        if notice:
            # Human interpretation of this area outranks the automatic observation.
            if notice.get("state") == "AWARE":
                outcome = {"tone": "quiet", "icon": "hearing", "label": "Checking reports"}
            else:
                outcome = {"tone": "bad", "icon": "error", "label": "Having problems"}
            detail = "See the current issue above."
        if maintenance:
            # Nobody can enter while the gate is closed, whatever requests behind it show.
            outcome = {"tone": "info", "icon": "construction", "label": "Closed for maintenance"}
            detail = "Not available until access reopens."
        last = None
        value = activity.get(key)
        # History fills in only when there is no current window to show.
        if value and item["state"] in {"NO_TRAFFIC", "STALE", "MONITOR_UNAVAILABLE"}:
            last = {"label": request_outcome(value["component"])["label"], "sampled_at": value["sampled_at"]}
        area = AREAS[key]
        cards.append({"key": key, "name": area["name"], "scope": area["scope"], "area_icon": area["icon"],
                      "tone": outcome["tone"], "chip_icon": outcome["icon"], "label": outcome["label"],
                      "detail": detail, "last": last})
    return cards


# ─── Notices and incidents ───

def notice_view(notice: dict) -> dict:
    stage = STAGES.get(notice.get("state"), STAGES["INVESTIGATING"])
    area = AREAS.get(notice.get("capability"), AREAS["service"])
    return {**notice, "stage": stage, "area": area,
            "headline": f"{area['name']}: {stage['headline']}"}


def history_summary(card: dict | None) -> dict:
    """The 90-day strip beside the main column, summarised in words."""
    days = card["history"] if card else []
    bars, ok_days, gap_days = [], 0, 0
    for day in days:
        if day["percent"] is None:
            gap_days += 1
            bars.append({"date": day["date"], "tone": "gap"})
        elif day["percent"] == 100:
            ok_days += 1
            bars.append({"date": day["date"], "tone": "ok"})
        else:
            bars.append({"date": day["date"], "tone": "elevated"})
    return {"bars": bars, "ok_days": ok_days, "gap_days": gap_days, "total": len(days)}


def incident_entry(notice: dict, events: list[dict]) -> dict:
    view = notice_view(notice)
    ended = as_utc(notice.get("updated_at"))
    started = min((moment for moment in (as_utc(e.get("published_at")) for e in events) if moment),
                  default=None)
    timeline = [{**event, "stage": STAGES.get(event.get("state"), STAGES["INVESTIGATING"])}
                for event in events]
    return {**view, "started": started, "ended": ended, "duration": duration_text(started, ended),
            "month": ended.strftime("%B %Y") if ended else "", "timeline": timeline,
            "resolution": notice.get("impact_statement", "")}


def detections(measurements, notices, sampled_at=None) -> list[dict]:
    """Fresh server errors no operator notice covers yet: drafts, never notices."""
    covered = {notice.get("capability") for notice in notices}
    found = []
    for item in measurements:
        if item["collection_state"] == "OK" and item["http_5xx_count"] and item["key"] not in covered:
            found.append({"key": item["key"], "name": AREAS[item["key"]]["name"],
                          "percent": item.get("http_5xx_percent"), "sampled_at": sampled_at})
    return found


def suggest_reference(notices, now: datetime) -> str:
    prefix = f"ops-{now:%Y-%m-%d}-"
    taken = {notice.get("incident_ref", "") for notice in notices}
    number = 1
    while f"{prefix}{number:03d}" in taken:
        number += 1
    return f"{prefix}{number:03d}"


def parse_offset(value) -> timedelta | None:
    """The operator's browser offset east of UTC, bounded to real time zones."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None
    return timedelta(minutes=minutes) if -840 <= minutes <= 840 else None


def resolve_next_update(choice: str, now: datetime) -> tuple[bool, datetime | None] | None:
    """Quick picks; None means the explicit fields decide."""
    if choice in {"30", "60", "120"}:
        return False, now + timedelta(minutes=int(choice))
    if choice == "none":
        return True, None
    return None

"""IAP-protected operator console and public projection reader."""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from .contracts import ExternalStatusNoticeEvent, NoticeState, RecoveryExpectationState
from .identity import authenticated_operator_email
from .log_setup import configure_logging
from status.measurements import (COMPONENT_KEYS, parse_time, classify_component,
                                 retained_activity, unavailable_component, validate_snapshot)
from status.platform import platform_rows
from .store import FirestoreNoticeStore

COMPONENT_NAMES = {"service": "Application requests", "login": "Login requests",
                   "attendance": "Attendance requests", "payroll": "Payroll requests",
                   "roster": "Roster requests", "classroom_economy": "Classroom economy requests"}
STATE_LABELS = {"NORMAL": "Within expected range", "ELEVATED_ERRORS": "Elevated response errors",
                "HIGH_LATENCY": "High latency",
                "NO_TRAFFIC": "No recent requests", "MONITOR_UNAVAILABLE": "Monitoring unavailable",
                "STALE": "Monitoring out of date"}


def measurement_cards(attempt, history, *, now):
    snapshot = attempt.get("snapshot") if attempt else None
    if snapshot is not None:
        try:
            snapshot = validate_snapshot(snapshot)
        except (ValueError, TypeError):
            snapshot = None
    cards = []
    for key in COMPONENT_KEYS:
        component = next((item for item in snapshot["components"] if item["key"] == key), None) if snapshot else None
        result = classify_component(component, snapshot, now=now) if component else {
            "state": "MONITOR_UNAVAILABLE", "reasons": [], "http_404_percent": None,
            "http_500_percent": None, "http_5xx_percent": None}
        if result["state"] in {"STALE", "MONITOR_UNAVAILABLE"}:
            component = unavailable_component(key)
        daily = []
        for day in history:
            counts = day["components"].get(key, {})
            measured = counts.get("measured", 0)
            daily.append({"date": day["date"], **counts,
                          "percent": 100 * counts.get("normal", 0) / measured if measured else None,
                          "coverage": min(100, 100 * measured / day["scheduled_minutes"]) if day["scheduled_minutes"] else 0})
        cards.append({**(component or unavailable_component(key)), **result, "name": COMPONENT_NAMES[key],
                      "label": STATE_LABELS[result["state"]], "history": daily})
    return cards


SERVICE_NAMES = {
    "login": "Login", "attendance": "Attendance", "payroll": "Payroll",
    "roster": "Class roster", "classroom_economy": "Classroom economy",
}


def request_outcome(item):
    """Bounded response observations, never a business-success verdict."""
    if item["http_5xx_count"]:
        return "degraded", "Server errors observed"
    if item["p95_ms"] > 1500:
        return "degraded", "Slow responses observed"
    if item["http_2xx_count"] + item["http_3xx_count"]:
        return "available", "Requests responding"
    return "unknown", "Requests declined or not found"


def teacher_cards(measurements, attempt, *, now):
    activity = retained_activity(attempt.get("last_activity") if attempt else None, now=now)
    cards = []
    for item in measurements:
        if item["key"] == "service":
            continue
        key = item["key"]
        state, label = "unknown", "Monitoring unavailable"
        detail = "Recent request evidence could not be collected."
        if item["state"] == "NO_TRAFFIC":
            label, detail = "No recent activity", "No matching requests in the last five minutes."
        elif item["state"] == "STALE":
            label, detail = "Monitoring out of date", "Recent request evidence is out of date."
        elif item["collection_state"] == "OK":
            state, label = request_outcome(item)
            count = item["request_count"]
            detail = f"{count} {'request' if count == 1 else 'requests'} in the last five minutes."
        last = None
        value = activity.get(key)
        if value:
            last = {"label": request_outcome(value["component"])[1], "sampled_at": value["sampled_at"]}
        cards.append({"key": key, "name": SERVICE_NAMES[key], "state": state,
                      "label": label, "detail": detail, "last": last})
    return cards


def overall_observation(checks, measurements, notices):
    """Availability follows active checks; request failures and notices qualify it."""
    checked = [row["checked_at"] for row in checks
               if row["state"] in {"PASS", "FAIL"} and row["checked_at"]]
    result = {"state": "unknown", "label": "AVAILABILITY NOT VERIFIED",
              "checked_at": min(checked, key=parse_time) if checked else None,
              "detail": "The latest availability checks could not verify the app."}
    if any(row["state"] == "FAIL" for row in checks):
        result.update(state="unavailable", label="AVAILABILITY CHECK FAILED",
                      detail="An application or database availability check failed.")
    elif notices or any(item["collection_state"] == "OK" and item["http_5xx_count"]
                        for item in measurements):
        result.update(state="degraded", label="ISSUES REPORTED",
                      detail="An operator notice or recent server errors need attention.")
    elif len(checks) == 2 and all(row["state"] == "PASS" for row in checks):
        result.update(state="available", label="APP REACHABLE",
                      detail="The app is responding and its database connection check passed.")
    return result


def parse_notice_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("Invalid notice timestamp.") from None
    if parsed.utcoffset() is None:
        # Operator form explicitly labels datetime-local inputs as UTC.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def create_app(store=None) -> Flask:
    configure_logging()
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.jinja_env.filters["status_time"] = format_status_time
    app.config["STATUS_SERVICE_MODE"] = os.environ.get("STATUS_SERVICE_MODE", "operator").strip().lower()
    if app.config["STATUS_SERVICE_MODE"] not in {"public", "operator"}:
        raise RuntimeError("STATUS_SERVICE_MODE must be public or operator")
    app.config["SECRET_KEY"] = os.environ.get("STATUS_SESSION_SECRET", "")
    app.config["STATUS_CAPABILITIES"] = COMPONENT_KEYS
    if store is None:
        from google.cloud import firestore
        store = FirestoreNoticeStore(firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "cth-status-prod")))
    app.extensions["notice_store"] = store

    def operator_identity() -> str | None:
        return authenticated_operator_email(
            request.headers.get("X-Goog-IAP-JWT-Assertion"),
            request.headers.get("X-Goog-Authenticated-User-Email"),
        )

    def require_operator() -> str:
        actor = operator_identity()
        if not actor or not app.config["SECRET_KEY"]:
            abort(401)
        return actor

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/")
    def public_status():
        if app.config["STATUS_SERVICE_MODE"] != "public":
            abort(404)
        active_notices = store.list_active_notices()
        now = datetime.now(timezone.utc)
        attempt = store.current_snapshot()
        if attempt and attempt.get("snapshot") is not None:
            try:
                validate_snapshot(attempt["snapshot"])
            except (ValueError, TypeError):
                attempt = None
        measurements = measurement_cards(attempt, store.measurement_history(), now=now)
        services = teacher_cards(measurements, attempt, now=now)
        checks = platform_rows(store.current_platform(), now=now)
        return render_template("public_status.html", notices=active_notices,
                               attempt=attempt, snapshot=attempt.get("snapshot") if attempt else None,
                               capability_cards=services, measurements=measurements,
                               platform_checks=checks,
                               overall_status=overall_observation(checks, measurements, active_notices))

    @app.get("/operator/notices")
    def operator_notices_get():
        if app.config["STATUS_SERVICE_MODE"] != "operator":
            abort(404)
        require_operator()
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        signer = URLSafeSerializer(app.secret_key, salt="notice-resolution")
        open_notices = store.list_active_notices()
        for notice in open_notices:
            notice["resolution_token"] = signer.dumps([notice["id"], notice["last_event_id"]]) if (
                notice.get("incident_ref") and notice.get("last_event_id")) else None
        return render_template("operator_notices.html", notices=store.list_notices(), open_notices=open_notices, capabilities=app.config["STATUS_CAPABILITIES"], csrf_token=session["csrf_token"])

    @app.post("/operator/notices/resolve")
    def operator_notices_resolve():
        if app.config["STATUS_SERVICE_MODE"] != "operator":
            abort(404)
        actor = require_operator()
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(request.form.get("csrf_token", ""), expected):
            abort(403)
        tokens = request.form.getlist("selected_issue")
        message = request.form.get("resolution_message", "").strip()
        if not tokens or len(tokens) > 100 or not message or len(message) > 500:
            abort(400, description="Select 1–100 open issues and enter a resolution (maximum 500 characters).")
        signer = URLSafeSerializer(app.secret_key, salt="notice-resolution")
        selections = {}
        try:
            for token in tokens:
                key, version = signer.loads(token)
                if key in selections:
                    abort(400)
                selections[key] = version
        except (BadSignature, ValueError, TypeError):
            abort(400, description="Invalid selection. Refresh the issue list.")
        try:
            store.resolve_notices(selections, message, actor)
        except ValueError:
            abort(409, description="No issues were resolved. An issue changed or lacks required lineage. Refresh and review the selection.")
        return redirect(url_for("operator_notices_get"))

    @app.post("/operator/notices")
    def operator_notices_post():
        if app.config["STATUS_SERVICE_MODE"] != "operator":
            abort(404)
        actor = require_operator()
        supplied = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            abort(403)
        payload = request.form
        if payload.get("state") == NoticeState.RESOLVED.value:
            abort(400, description="Use Resolve issues to select an existing open issue.")
        next_update_unavailable = payload.get("next_update_unavailable") == "on"
        recovery_state = payload.get("recovery_state", RecoveryExpectationState.UNAVAILABLE.value)
        source_ids = tuple(value.strip() for value in payload.get("source_observation_ids", "").split(",") if value.strip())
        try:
            recovery_value = parse_notice_time(payload.get("recovery_expectation"))
            next_update = None if next_update_unavailable else parse_notice_time(payload.get("next_update_at"))
        except ValueError:
            abort(400, description="Enter a valid UTC time.")
        if recovery_state == RecoveryExpectationState.UNAVAILABLE.value and recovery_value is not None:
            abort(400, description="Clear the recovery time or select a known or estimated recovery state.")
        if recovery_state != RecoveryExpectationState.UNAVAILABLE.value and not recovery_value:
            abort(400)
        incident_ref = payload.get("incident_ref", "").strip()
        if not incident_ref:
            abort(400)
        notice = {"external_notice_id": payload.get("external_notice_id") or None, "incident_ref": incident_ref, "state": payload.get("state", NoticeState.INVESTIGATING.value), "capability": payload.get("capability", ""), "impact_statement": payload.get("impact_statement", ""), "recommended_user_action": payload.get("recommended_user_action", ""), "recovery_state": recovery_state, "recovery_expectation": recovery_value, "next_update_at": next_update, "next_update_unavailable": next_update_unavailable, "source_observation_ids": source_ids}
        try:
            record = ExternalStatusNoticeEvent(external_notice_id=notice["external_notice_id"] or "pending", incident_ref=incident_ref, event_id="pending", event_type="PUBLISHED", published_at=datetime.now(timezone.utc), state=NoticeState(notice["state"]), capability=notice["capability"], impact_statement=notice["impact_statement"], recommended_user_action=notice["recommended_user_action"], recovery_state=RecoveryExpectationState(recovery_state), recovery_expectation=recovery_value, next_update_at=notice["next_update_at"], next_update_unavailable=next_update_unavailable, source_observation_ids=source_ids)
            record.validate()
        except ValueError:
            abort(400, description="Invalid notice fields or missing update time.")
        if notice["capability"] not in COMPONENT_KEYS:
            abort(400, description="Unknown request group.")
        store.append_event(notice, "PUBLISHED", actor)
        return redirect(url_for("operator_notices_get"))

    return app


app = create_app()

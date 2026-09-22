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
from status.measurements import COMPONENT_KEYS, classify_component, unavailable_component, validate_snapshot
from status.platform import platform_rows
from .store import FirestoreNoticeStore

COMPONENT_NAMES = {"service": "Application requests", "login": "Login requests",
                   "attendance": "Attendance requests", "payroll": "Payroll requests",
                   "roster": "Roster requests", "classroom_economy": "Classroom economy requests"}
STATE_LABELS = {"NORMAL": "Within expected range", "ELEVATED_ERRORS": "Elevated response errors",
                "HIGH_LATENCY": "High latency", "LOW_TRAFFIC": "Limited recent traffic",
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


SERVICE_QUESTIONS = {
    "service": ("Application", "Can I use Classroom Token Hub?"),
    "login": ("Login", "Can I sign in?"),
    "attendance": ("Attendance", "Can students clock in and out?"),
    "payroll": ("Payroll", "Can I run payroll?"),
    "roster": ("Class roster", "Can I manage my students?"),
    "classroom_economy": ("Classroom economy", "Can students use their classroom money?"),
}


def teacher_cards(measurements, *, include_service=False):
    """Present the versioned request proxy in the original simple card vocabulary."""
    cards = []
    for item in measurements:
        if item["key"] not in SERVICE_QUESTIONS or (item["key"] == "service" and not include_service):
            continue
        state, label = "unknown", "Not recently verified"
        if item["state"] == "NORMAL":
            state, label = "available", "Yes"
        elif item["state"] in {"ELEVATED_ERRORS", "HIGH_LATENCY"}:
            state, label = "degraded", "Probably not"
            if (item["request_count"] or 0) >= 10 and (item["http_5xx_percent"] or 0) >= 50:
                state, label = "unavailable", "Possibly down"
        name, question = SERVICE_QUESTIONS[item["key"]]
        cards.append({"key": item["key"], "name": name, "question": question,
                      "state": state, "label": label})
    return cards


def overall_observation(cards, notices):
    if any(card["state"] == "unavailable" for card in cards):
        return {"state": "unavailable", "label": "POSSIBLY DOWN"}
    if notices or any(card["state"] == "degraded" for card in cards):
        return {"state": "degraded", "label": "SERVICE ISSUES"}
    if cards and all(card["state"] == "available" for card in cards):
        return {"state": "available", "label": "LOOKING GOOD"}
    return {"state": "unknown", "label": "NOT RECENTLY VERIFIED"}


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
        services = teacher_cards(measurements)
        return render_template("public_status.html", notices=active_notices,
                               attempt=attempt, snapshot=attempt.get("snapshot") if attempt else None,
                               capability_cards=services, measurements=measurements,
                               platform_checks=platform_rows(store.current_platform(), now=now),
                               overall_status=overall_observation(teacher_cards(measurements, include_service=True), active_notices))

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

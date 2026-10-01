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
from .presentation import (AREAS, STAGES, area_cards, detections, format_status_time, history_summary,
                           incident_entry, iso_utc, notice_view, overall_observation, parse_offset,
                           resolve_next_update, suggest_reference)
from status.measurements import (COMPONENT_KEYS, classify_component, unavailable_component,
                                 validate_snapshot)
from status.platform import platform_rows
from .store import FirestoreNoticeStore, ResolutionTooLarge

COMPONENT_NAMES = {"service": "Application requests", "login": "Login requests",
                   "attendance": "Attendance requests", "payroll": "Payroll requests",
                   "roster": "Roster requests", "classroom_economy": "Classroom economy requests"}
STATE_LABELS = {"NORMAL": "Within expected range", "ELEVATED_ERRORS": "Elevated response errors",
                "HIGH_LATENCY": "High latency",
                "NO_TRAFFIC": "No recent requests", "MONITOR_UNAVAILABLE": "Monitoring unavailable",
                "STALE": "Monitoring out of date"}
# Notice stages an operator may publish; resolving has its own form.
PUBLISHABLE_STAGES = ("AWARE", "INVESTIGATING", "IDENTIFIED", "MONITORING")


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


def parse_notice_time(value, offset=None):
    """An aware UTC time from an operator form field.

    A value without an offset is the operator's local time when the browser
    reported its offset, and UTC otherwise; the form says which.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("Invalid notice timestamp.") from None
    if parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone(offset) if offset is not None else timezone.utc)
    return parsed.astimezone(timezone.utc)


def create_app(store=None) -> Flask:
    configure_logging()
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.jinja_env.filters["status_time"] = format_status_time
    app.jinja_env.filters["iso_utc"] = iso_utc
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

    def current_attempt():
        attempt = store.current_snapshot()
        if attempt and attempt.get("snapshot") is not None:
            try:
                validate_snapshot(attempt["snapshot"])
            except (ValueError, TypeError):
                attempt = None
        return attempt

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/")
    def public_status():
        if app.config["STATUS_SERVICE_MODE"] != "public":
            abort(404)
        active_notices = store.list_active_notices()
        now = datetime.now(timezone.utc)
        attempt = current_attempt()
        measurements = measurement_cards(attempt, store.measurement_history(), now=now)
        checks = platform_rows(store.current_platform(), now=now)
        recent, _ = store.list_resolved_notices(page=1, page_size=3)
        service = next((card for card in measurements if card["key"] == "service"), None)
        overall = overall_observation(checks, measurements, active_notices, now=now)
        cards = area_cards(measurements, attempt, active_notices, now=now,
                           maintenance=overall["state"] == "maintenance")
        return render_template("public_status.html", notices=[notice_view(n) for n in active_notices],
                               attempt=attempt, snapshot=attempt.get("snapshot") if attempt else None,
                               capability_cards=cards, measurements=measurements, platform_checks=checks,
                               history=history_summary(service),
                               recent_incidents=[notice_view(n) for n in recent],
                               overall_status=overall)

    @app.get("/incidents")
    def incident_history():
        if app.config["STATUS_SERVICE_MODE"] == "operator":
            require_operator()
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            abort(400)
        if page < 1:
            abort(400)
        notices, has_more = store.list_resolved_notices(page=page)
        if page > 1 and not notices:
            abort(404)
        months = []  # newest first, in the order the store returned them
        for notice in notices:
            entry = incident_entry(notice, store.list_notice_events(notice["id"]))
            if not months or months[-1]["month"] != entry["month"]:
                months.append({"month": entry["month"], "entries": []})
            months[-1]["entries"].append(entry)
        return render_template("incident_history.html", months=months, page=page,
                               has_more=has_more,
                               operator=app.config["STATUS_SERVICE_MODE"] == "operator")

    @app.get("/operator/notices")
    def operator_notices_get():
        if app.config["STATUS_SERVICE_MODE"] != "operator":
            abort(404)
        require_operator()
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        now = datetime.now(timezone.utc)
        signer = URLSafeSerializer(app.secret_key, salt="notice-resolution")
        open_notices = [notice_view(n) for n in store.list_active_notices()]
        for notice in open_notices:
            notice["resolution_token"] = signer.dumps([notice["id"], notice["last_event_id"]]) if (
                notice.get("incident_ref") and notice.get("last_event_id")) else None
        attempt = current_attempt()
        measurements = measurement_cards(attempt, [], now=now)
        found = detections(measurements, open_notices,
                           (attempt.get("snapshot") or {}).get("sampled_at") if attempt else None)

        # One issue at a time: an open issue, a draft from a detection, or a new one.
        wanted, ref = request.args.get("issue", ""), request.args.get("ref", "")
        selected = next((n for n in open_notices if n["id"] == wanted
                         or (ref and n.get("incident_ref") == ref)), None)
        draft = next((item for item in found if wanted == f"auto-{item['key']}"), None)
        if selected is None and draft is None and wanted != "new" and open_notices:
            selected = open_notices[0]
        mode = "resolve" if selected and request.args.get("action") == "resolve" else "update"
        events = store.list_notice_events(selected["id"]) if selected else []
        preview = selected or notice_view({
            "capability": draft["key"] if draft else "service", "state": "AWARE",
            "impact_statement": "", "recommended_user_action": ""})
        return render_template("operator_notices.html", open_notices=open_notices, detections=found,
                               selected=selected, draft=draft, mode=mode, preview=preview,
                               events=[{**event, "stage": STAGES.get(event.get("state"), STAGES["AWARE"])}
                                       for event in reversed(events)],
                               areas=AREAS, stages=STAGES, publishable=PUBLISHABLE_STAGES,
                               capabilities=app.config["STATUS_CAPABILITIES"],
                               suggested_ref=suggest_reference(store.list_notices(), now),
                               csrf_token=session["csrf_token"])

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
        if not tokens or len(tokens) > 100 or not message:
            abort(400, description="Select 1–100 open issues and enter a resolution.")
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
        except ResolutionTooLarge as exc:
            return render_template("resolution_error.html", message=message, error=str(exc)), 413
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
        now = datetime.now(timezone.utc)
        offset = parse_offset(payload.get("tz_offset_minutes"))
        next_update_unavailable = payload.get("next_update_unavailable") == "on"
        recovery_state = payload.get("recovery_state", RecoveryExpectationState.UNAVAILABLE.value)
        source_ids = tuple(value.strip() for value in payload.get("source_observation_ids", "").split(",") if value.strip())
        try:
            recovery_value = parse_notice_time(payload.get("recovery_expectation"), offset)
            quick = resolve_next_update(payload.get("next_update_choice", ""), now)
            if quick is not None:
                next_update_unavailable, next_update = quick
            else:
                next_update = None if next_update_unavailable else parse_notice_time(payload.get("next_update_at"), offset)
        except ValueError:
            abort(400, description="Enter a valid time.")
        if recovery_state == RecoveryExpectationState.UNAVAILABLE.value and recovery_value is not None:
            abort(400, description="Clear the recovery time or select a known or estimated recovery state.")
        if recovery_state != RecoveryExpectationState.UNAVAILABLE.value and not recovery_value:
            abort(400)
        incident_ref = payload.get("incident_ref", "").strip()
        if not incident_ref:
            abort(400)
        notice = {"external_notice_id": payload.get("external_notice_id") or None, "incident_ref": incident_ref, "state": payload.get("state", NoticeState.INVESTIGATING.value), "capability": payload.get("capability", ""), "impact_statement": payload.get("impact_statement", ""), "recommended_user_action": payload.get("recommended_user_action", ""), "recovery_state": recovery_state, "recovery_expectation": recovery_value, "next_update_at": next_update, "next_update_unavailable": next_update_unavailable, "source_observation_ids": source_ids}
        try:
            record = ExternalStatusNoticeEvent(external_notice_id=notice["external_notice_id"] or "pending", incident_ref=incident_ref, event_id="pending", event_type="PUBLISHED", published_at=now, state=NoticeState(notice["state"]), capability=notice["capability"], impact_statement=notice["impact_statement"], recommended_user_action=notice["recommended_user_action"], recovery_state=RecoveryExpectationState(recovery_state), recovery_expectation=recovery_value, next_update_at=notice["next_update_at"], next_update_unavailable=next_update_unavailable, source_observation_ids=source_ids)
            record.validate()
        except ValueError:
            abort(400, description="Invalid notice fields or missing update time.")
        if notice["capability"] not in COMPONENT_KEYS:
            abort(400, description="Unknown request group.")
        store.append_event(notice, "PUBLISHED", actor)
        return redirect(url_for("operator_notices_get", ref=incident_ref))

    return app


app = create_app()

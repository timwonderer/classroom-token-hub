"""IAP-protected operator console and public projection reader."""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from .contracts import ExternalStatusNoticeEvent, NoticeState, RecoveryExpectationState
from .identity import authenticated_operator_email
from .store import FirestoreNoticeStore


def create_app(store=None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["STATUS_SERVICE_MODE"] = os.environ.get("STATUS_SERVICE_MODE", "operator").strip().lower()
    if app.config["STATUS_SERVICE_MODE"] not in {"public", "operator"}:
        raise RuntimeError("STATUS_SERVICE_MODE must be public or operator")
    app.config["SECRET_KEY"] = os.environ.get("STATUS_SESSION_SECRET", "")
    app.config["STATUS_CAPABILITIES"] = tuple(item.strip() for item in os.environ.get("STATUS_CAPABILITIES", "public_service_reachability").split(",") if item.strip())
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
        return render_template("public_status.html", notices=store.list_notices(limit=20))

    @app.get("/operator/notices")
    def operator_notices_get():
        if app.config["STATUS_SERVICE_MODE"] != "operator":
            abort(404)
        require_operator()
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return render_template("operator_notices.html", notices=store.list_notices(), capabilities=app.config["STATUS_CAPABILITIES"], csrf_token=session["csrf_token"])

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
        next_update_unavailable = payload.get("next_update_unavailable") == "on"
        recovery_state = payload.get("recovery_state", RecoveryExpectationState.UNAVAILABLE.value)
        source_ids = tuple(value.strip() for value in payload.get("source_observation_ids", "").split(",") if value.strip())
        recovery_value = payload.get("recovery_expectation") or None
        if recovery_state != RecoveryExpectationState.UNAVAILABLE.value and not recovery_value:
            abort(400)
        notice = {"external_notice_id": payload.get("external_notice_id") or None, "state": payload.get("state", NoticeState.INVESTIGATING.value), "capability": payload.get("capability", ""), "impact_statement": payload.get("impact_statement", ""), "recommended_user_action": payload.get("recommended_user_action", ""), "recovery_state": recovery_state, "recovery_expectation": recovery_value, "next_update_at": None if next_update_unavailable else payload.get("next_update_at") or datetime.now(timezone.utc), "next_update_unavailable": next_update_unavailable, "source_observation_ids": source_ids}
        record = ExternalStatusNoticeEvent(external_notice_id=notice["external_notice_id"] or "pending", event_id="pending", event_type="PUBLISHED", published_at=datetime.now(timezone.utc), state=NoticeState(notice["state"]), capability=notice["capability"], impact_statement=notice["impact_statement"], recommended_user_action=notice["recommended_user_action"], recovery_state=RecoveryExpectationState(recovery_state), recovery_expectation=datetime.now(timezone.utc) if recovery_value else None, next_update_at=notice["next_update_at"], next_update_unavailable=next_update_unavailable, source_observation_ids=source_ids)
        record.validate()
        store.append_event(notice, "PUBLISHED", actor)
        return redirect(url_for("operator_notices_get"))

    return app


app = create_app()

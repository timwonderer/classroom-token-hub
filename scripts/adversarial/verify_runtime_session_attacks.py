#!/usr/bin/env python3
"""Current-v2 context attacks against an isolated Phase 1 topology.

INV-ARC-019 / DOM-IDEN-006: User owns active class/seat pointers, not session aliases.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import ClassEconomy, Seat, User
from app.services.context_resolver import ContextResolutionError, resolve_canonical_context
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_session import set_canonical_context


def artifact_root():
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / os.getenv("ADVERSARIAL_RUN_ID", "current")
    root.mkdir(parents=True, exist_ok=True)
    return root


def context_attack(app, user, seat_id, class_id):
    original = user.last_active_seat_id, user.last_active_class_id
    try:
        # Deliberately corrupt resolver inputs in memory; never persist this attack.
        user.last_active_seat_id, user.last_active_class_id = seat_id, class_id
        with db.session.no_autoflush, app.test_request_context("/student/dashboard"):
            from flask import session
            session["user_id"] = user.id
            try:
                resolve_canonical_context()
            except ContextResolutionError:
                return "PASS"
            return "FAIL"
    finally:
        user.last_active_seat_id, user.last_active_class_id = original


def establish_session(client, user, seat):
    with client.session_transaction() as sess:
        sess.clear()
        set_canonical_context(sess, user_id=user.id, class_id=seat.class_id, seat_id=seat.id, role="student")
        sess["role"] = "student"


def response_result(response, expected):
    if response.status_code >= 500:
        return "BLOCKED"
    return "PASS" if response.status_code in expected else "FAIL"


def run_attacks(app, topology):
    a1, a2, b1 = [db.session.get(ClassEconomy, topology[key]) for key in ("ADVA1", "ADVA2", "ADVB1")]
    if not all((a1, a2, b1)) or len({a1.class_id, a2.class_id, b1.class_id}) != 3:
        raise ValueError("Three distinct seeded classes are required")
    alice = Seat.query.filter_by(class_id=a1.class_id, role="student").filter(Seat.claimed_at.isnot(None)).first()
    other = Seat.query.filter_by(class_id=b1.class_id, role="student").filter(Seat.claimed_at.isnot(None)).first()
    unclaimed = Seat.query.filter_by(class_id=a2.class_id, role="student", user_id=None, claimed_at=None).first()
    if not all((alice, other, unclaimed)) or alice.user_id == other.user_id:
        raise ValueError("Seed requires two distinct claimed principals and an unclaimed seat")
    user = db.session.get(User, alice.user_id)
    checks = []
    # Positive control: denial is not evidence if the resolver is broken for lawful state.
    with app.test_request_context("/student/dashboard"):
        from flask import session
        session["user_id"] = user.id
        ctx = resolve_canonical_context()
        if (ctx.seat_id, ctx.class_id) != (alice.id, a1.class_id):
            raise ValueError("Lawful context control failed")
    for name, seat_id, class_id in (
        ("unclaimed_seat", unclaimed.id, a2.class_id),
        ("foreign_owner", other.id, b1.class_id),
        ("cross_class_pointer", alice.id, b1.class_id),
        ("missing_seat", -1, a1.class_id),
    ):
        checks.append({"attack": name, "result": context_attack(app, user, seat_id, class_id)})
    with app.test_client() as client:
        establish_session(client, user, alice)
        control = client.get("/api/student-status", follow_redirects=False)
        checks.append({"attack": "authenticated_route_control", "result": response_result(control, {200}), "http_status": control.status_code})
        if control.status_code == 200:
            # A response denied by CSRF cannot prove class authorization. Disable CSRF
            # only for this isolated test client; the production configuration is restored.
            csrf = app.config.get("WTF_CSRF_ENABLED", True)
            try:
                app.config["WTF_CSRF_ENABLED"] = False
                response = client.post(f"/student/switch-class/{b1.class_id}", follow_redirects=False)
            finally:
                app.config["WTF_CSRF_ENABLED"] = csrf
            checks.append({"attack": "cross_class_switch", "result": response_result(response, {403}), "http_status": response.status_code})
            establish_session(client, user, alice)
            response = client.get(f"/api/hall-pass/available-types?class_id={b1.class_id}", follow_redirects=False)
            checks.append({"attack": "foreign_class_api", "result": response_result(response, {403}), "http_status": response.status_code})
            establish_session(client, user, alice)
            response = client.get(f"/api/hall-pass/available-types?class_id={a1.class_id}", follow_redirects=False)
            result = response_result(response, {403})
            if result == "PASS" and (response.get_json() or {}).get("message") != "Hall pass is disabled for this class":
                result = "FAIL"
            checks.append({"attack": "disabled_hall_pass", "result": result, "http_status": response.status_code})
            establish_session(client, user, alice)
            response = client.get("/student/select-class-context", follow_redirects=False)
            checks.append({"attack": "class_selection_control", "result": response_result(response, {200}), "http_status": response.status_code})
        else:
            checks.append({"attack": "authenticated_route_attacks", "result": "BLOCKED"})
    return checks


def main():
    root = artifact_root()
    topology = json.loads((root / "topology.json").read_text(encoding="utf-8"))
    app = create_app()
    with app.app_context():
        checks = run_attacks(app, topology)
    failures = [check for check in checks if check["result"] == "FAIL"]
    status = "FAIL" if failures else "BLOCKED" if any(check["result"] == "BLOCKED" for check in checks) else "PASS"
    report = {"generated_at": utc_now().isoformat(), "check": "runtime_session_attacks", "status": status,
              "violation_count": len(failures), "findings": failures, "checks": checks}
    (root / "runtime_attacks_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "violation_count": len(failures)}))
    return 1 if status == "FAIL" else 2 if status == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

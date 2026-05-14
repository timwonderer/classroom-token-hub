#!/usr/bin/env python3
"""Runtime session attack battery for Phase 1 adversarial validation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.auth import get_current_seat, get_current_student_seat
from app.models import ClassEconomy, Seat, Student


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_root() -> Path:
    run_id = os.getenv("ADVERSARIAL_RUN_ID", "current")
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def append_violation(payload: dict) -> None:
    out = artifact_root() / "violations.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def main() -> int:
    app = create_app()
    findings: list[dict] = []
    failed_closed: list[dict] = []

    with app.app_context():
        a1 = ClassEconomy.query.filter_by(join_code="ADVA1").first()
        a2 = ClassEconomy.query.filter_by(join_code="ADVA2").first()
        b1 = ClassEconomy.query.filter_by(join_code="ADVB1").first()
        if not (a1 and a2 and b1):
            raise SystemExit("Seed classes ADVA1/ADVA2/ADVB1 are required")

        unclaimed = Seat.query.filter_by(class_id=a2.class_id).filter(Seat.claimed_at.is_(None)).first()
        alice_a1 = Seat.query.filter_by(class_id=a1.class_id).filter(Seat.claimed_at.isnot(None)).first()
        b1_other = (
            Seat.query.filter_by(class_id=b1.class_id)
            .filter(Seat.claimed_at.isnot(None))
            .filter(Seat.student_id != alice_a1.student_id if alice_a1 else True)
            .first()
        )
        deleted_student = Student.query.filter(Student.username_lookup_hash.isnot(None)).filter_by(join_code="ADVB1").order_by(Student.id.desc()).first()

        with app.test_client() as client:
            # VULN-001: unclaimed seat authority bypass
            if unclaimed:
                with client.session_transaction() as sess:
                    now = now_iso()
                    sess["student_id"] = unclaimed.student_id
                    sess["current_seat_id"] = unclaimed.id
                    sess["seat_id"] = unclaimed.id
                    sess["current_class_id"] = unclaimed.class_id
                    sess["class_id"] = unclaimed.class_id
                    sess["current_join_code"] = unclaimed.join_code
                    sess["login_time"] = now
                    sess["last_activity"] = now
                r1 = client.get("/student/dashboard", follow_redirects=False)
                r2 = client.get("/api/student-status", follow_redirects=False)
                r3 = client.get("/student/payroll", follow_redirects=False)
                if any(r.status_code == 200 for r in (r1, r2, r3)):
                    findings.append({
                        "vuln_id": "VULN-001",
                        "severity": "P1",
                        "invariant": "Scope is explicit and fail-closed (INV-SCOPE-001)",
                        "title": "Unclaimed seat bypasses claim gate — grants full class authority",
                        "status": "CONFIRMED",
                        "root_cause_file": "app/auth.py",
                        "root_cause_function": "get_current_student_seat / sync_student_session_context",
                        "root_cause_detail": "Unclaimed seat was accepted in runtime session context.",
                        "observed": f"dashboard {r1.status_code}, /api/student-status {r2.status_code}, /student/payroll {r3.status_code}.",
                    })

            # VULN-002: seat ownership injection
            if alice_a1 and b1_other:
                with app.test_request_context("/student/payroll"):
                    from flask import session
                    session["student_id"] = alice_a1.student_id
                    session["current_seat_id"] = b1_other.id
                    session["seat_id"] = b1_other.id
                    session["current_class_id"] = b1_other.class_id
                    session["class_id"] = b1_other.class_id
                    session["current_join_code"] = "ADVB1"
                    if get_current_student_seat() is not None or get_current_seat() is not None:
                        findings.append({
                            "vuln_id": "VULN-002",
                            "severity": "P1",
                            "invariant": "Membership exists only through surviving association (INV-MEM-001)",
                            "title": "Seat ownership check bypass via injected current_seat_id",
                            "status": "CONFIRMED",
                            "root_cause_file": "app/auth.py",
                            "root_cause_function": "get_current_student_seat / get_current_seat",
                            "root_cause_detail": "Session seat_id accepted without matching student ownership.",
                            "observed": "Cross-user seat anchor resolved successfully.",
                        })

            # VULN-003: hall pass feature gate bypass
            if a1:
                if alice_a1:
                    with client.session_transaction() as sess:
                        now = now_iso()
                        sess["student_id"] = alice_a1.student_id
                        sess["current_seat_id"] = alice_a1.id
                        sess["seat_id"] = alice_a1.id
                        sess["current_class_id"] = a1.class_id
                        sess["class_id"] = a1.class_id
                        sess["current_join_code"] = "ADVA1"
                        sess["login_time"] = now
                        sess["last_activity"] = now
                r = client.get(f"/api/hall-pass/available-types?class_id={a1.class_id}", follow_redirects=False)
                if r.status_code == 200:
                    findings.append({
                        "vuln_id": "VULN-003",
                        "severity": "P2",
                        "invariant": "Feature toggles are the sole authority gate (INV-FEAT-001)",
                        "title": "hall_pass API endpoints lack ClassFeature guard",
                        "status": "CONFIRMED",
                        "root_cause_file": "app/routes/api.py",
                        "root_cause_function": "get_available_hall_pass_types",
                        "root_cause_detail": "Feature gate absent for hall_pass available-types endpoint.",
                        "observed": f"/api/hall-pass/available-types returned {r.status_code} for ADVA1.",
                    })

            # VULN-004: FEAT transaction nesting issue on select class context
            if unclaimed:
                with client.session_transaction() as sess:
                    now = now_iso()
                    sess["student_id"] = unclaimed.student_id
                    sess["current_seat_id"] = unclaimed.id
                    sess["seat_id"] = unclaimed.id
                    sess["current_class_id"] = unclaimed.class_id
                    sess["class_id"] = unclaimed.class_id
                    sess["current_join_code"] = unclaimed.join_code
                    sess["login_time"] = now
                    sess["last_activity"] = now
                r = client.get("/student/select-class-context", follow_redirects=False)
                if r.status_code >= 500:
                    findings.append({
                        "vuln_id": "VULN-004",
                        "severity": "P3",
                        "invariant": "FEAT layer maintains transactional integrity (INV-ARC-003)",
                        "title": "FEAT transaction nesting error — 500 on select_class_context",
                        "status": "CONFIRMED",
                        "root_cause_file": "app/feats/base.py",
                        "root_cause_function": "FEATContext.__enter__",
                        "root_cause_detail": "Top-level FEAT could not safely enter with existing transaction state.",
                        "observed": f"GET /student/select-class-context returned {r.status_code}.",
                    })

            # ATK-01: Ghost login path should fail closed
            if deleted_student:
                with client.session_transaction() as sess:
                    now = now_iso()
                    sess["student_id"] = deleted_student.id
                    sess["current_seat_id"] = 999999999
                    sess["current_class_id"] = b1.class_id
                    sess["current_join_code"] = "ADVB1"
                    sess["login_time"] = now
                    sess["last_activity"] = now
                ghost = client.get("/student/dashboard", follow_redirects=False)
                failed_closed.append({
                    "attack": "ATK-01: Ghost login (deleted seat)",
                    "result": "PASS" if ghost.status_code in (302, 401, 403) else "FAIL",
                    "detail": f"/student/dashboard returned {ghost.status_code}",
                })

            # ATK-06: switch-class should deny out-of-scope class
            if alice_a1:
                with client.session_transaction() as sess:
                    now = now_iso()
                    sess["student_id"] = alice_a1.student_id
                    sess["current_seat_id"] = alice_a1.id
                    sess["seat_id"] = alice_a1.id
                    sess["current_class_id"] = a1.class_id
                    sess["class_id"] = a1.class_id
                    sess["current_join_code"] = "ADVA1"
                    sess["login_time"] = now
                    sess["last_activity"] = now
                switch_resp = client.post(f"/student/switch-class/{b1.class_id}", follow_redirects=False)
                failed_closed.append({
                    "attack": "ATK-06: Cross-class context switch via POST",
                    "result": "PASS" if switch_resp.status_code in (400, 401, 403) else "FAIL",
                    "detail": f"/student/switch-class/{b1.class_id} returned {switch_resp.status_code}",
                })

    report = {
        "generated_at": now_iso(),
        "check": "runtime_session_attacks",
        "status": "FAIL" if findings else "PASS",
        "violation_count": len(findings),
        "attack_battery": "Operation CLASS-BREAK Phase 1",
        "findings": findings,
        "attacks_that_failed_closed": failed_closed,
    }

    for finding in findings:
        append_violation({
            "timestamp": now_iso(),
            "vuln_id": finding["vuln_id"],
            "event_type": "runtime_session_attack_confirmed",
            "severity": finding["severity"],
            "title": finding["title"],
            "detail": finding["observed"],
            "reproducible": True,
        })

    out = artifact_root() / "runtime_attacks_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "violation_count": report["violation_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

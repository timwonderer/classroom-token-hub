"""Current-v2 proof-harness controls (INV-ARC-019, SPEC-TEST-001)."""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts.adversarial import (
    inject_impossible_state,
    build_evidence_bundle,
    render_constitutional_scorecard,
    seed_phase1_minimal,
    verify_cross_class_isolation,
    verify_lineage_lawfulness,
    verify_runtime_session_attacks,
)
from app.extensions import db
from app.models import ClassEconomy, LedgerBalanceSnapshot, Seat, User


def test_seed_and_runtime_attacks_use_live_canonical_context(app, monkeypatch):
    topology = seed_phase1_minimal.seed(app)
    assert len(set(topology.values())) == 3
    classrooms = [db.session.get(ClassEconomy, topology[name]) for name in ("ADVA1", "ADVA2", "ADVB1")]
    assert classrooms[0].teacher_user_id == classrooms[1].teacher_user_id
    assert classrooms[0].teacher_user_id != classrooms[2].teacher_user_id
    checks = verify_runtime_session_attacks.run_attacks(app, topology)
    assert len(checks) == 9
    assert all(check["result"] == "PASS" for check in checks), checks
    with pytest.raises(ValueError, match="empty isolated database"):
        seed_phase1_minimal.seed(app)
    seat = Seat.query.filter_by(class_id=topology["ADVA1"], role="student").first()
    user = db.session.get(User, seat.user_id)
    original = user.last_active_seat_id, user.last_active_class_id
    # A resolver that accepts bad context must turn the proof red.
    monkeypatch.setattr(verify_runtime_session_attacks, "resolve_canonical_context", lambda: object())
    assert verify_runtime_session_attacks.context_attack(app, user, -1, seat.class_id) == "FAIL"
    assert (user.last_active_seat_id, user.last_active_class_id) == original


def test_injection_and_verifier_require_and_recognize_seeded_proof(app, tmp_path, monkeypatch):
    topology = seed_phase1_minimal.seed(app)
    monkeypatch.setenv("ADVERSARIAL_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("ADVERSARIAL_RUN_ID", "proof")
    root = tmp_path / "proof"
    root.mkdir()
    (root / "topology.json").write_text(json.dumps(topology))
    for module in (inject_impossible_state, verify_cross_class_isolation,
                   verify_lineage_lawfulness, verify_runtime_session_attacks):
        monkeypatch.setattr(module, "create_app", lambda: app)
    # No injection is BLOCKED, not a passing guard proof.
    assert verify_cross_class_isolation.main() == 2
    assert inject_impossible_state.main() == 0
    db.session.expire_all()
    assert verify_cross_class_isolation.main() == 0
    report = json.loads((root / "cross_class_report.json").read_text())
    assert report["expected_injection_count"] == 1
    assert report["violation_count"] == 0
    assert LedgerBalanceSnapshot.query.filter(LedgerBalanceSnapshot.class_id.in_(topology.values())).count() == 1
    monkeypatch.setattr("sys.argv", ["verify_lineage_lawfulness", "--lookback-days", "0"])
    assert verify_lineage_lawfulness.main() == 2
    monkeypatch.setattr("sys.argv", ["verify_lineage_lawfulness"])
    assert verify_lineage_lawfulness.main() == 0
    assert verify_runtime_session_attacks.main() == 0
    assert render_constitutional_scorecard.main() == 0
    monkeypatch.setattr("sys.argv", ["build_evidence_bundle", "--run-id", "proof", "--artifact-dir", str(tmp_path)])
    assert build_evidence_bundle.main() == 0
    summary = json.loads((tmp_path / "sanitized/proof/summary.json").read_text())
    assert all(check["status"] == "PASS" for check in summary["checks"].values())


def test_server_error_is_blocked_and_scorecard_fails(tmp_path, monkeypatch):
    assert verify_runtime_session_attacks.response_result(SimpleNamespace(status_code=500), {403}) == "BLOCKED"
    assert verify_runtime_session_attacks.response_result(SimpleNamespace(status_code=404), {403}) == "FAIL"
    monkeypatch.setenv("ADVERSARIAL_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("ADVERSARIAL_RUN_ID", "blocked")
    root = tmp_path / "blocked"
    root.mkdir()
    for name in ("cross_class", "lineage", "runtime_attacks"):
        (root / f"{name}_report.json").write_text(json.dumps({"status": "BLOCKED", "violation_count": 0}))
    (root / "injection_report.json").write_text('{}')
    assert render_constitutional_scorecard.main() == 1
    assert "Overall: **FAIL**" in (root / "scorecard.md").read_text()


def test_phase1_runner_keeps_evidence_but_propagates_failed_verifier(tmp_path):
    interpreter = tmp_path / "python"
    interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$2" >> "$INVOCATIONS"\n'
                           'case "$2" in *verify_runtime_session_attacks) exit 2;; esac\n')
    interpreter.chmod(0o700)
    log = tmp_path / "invocations"
    root = tmp_path / "runner"
    root.mkdir()
    stale = root / "runtime_attacks_report.json"
    stale.write_text('{"status": "PASS"}')
    runner = Path(__file__).resolve().parents[1] / "scripts/adversarial/run_phase1.sh"
    result = subprocess.run(["bash", str(runner)], capture_output=True, text=True,
                            env={**os.environ, "PYTHON_BIN": str(interpreter), "INVOCATIONS": str(log),
                                 "ADVERSARIAL_ARTIFACT_DIR": str(tmp_path), "ADVERSARIAL_RUN_ID": "runner"})
    assert result.returncode == 1
    assert not stale.exists()
    invocations = log.read_text().splitlines()
    assert "scripts.adversarial.render_constitutional_scorecard" in invocations
    assert invocations[-1] == "scripts.adversarial.build_evidence_bundle"

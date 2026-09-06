from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci_classifier import classify, load_manifest
from scripts.ci_evidence_runner import (
    ALLOWED_AUXILIARY,
    aggregate_status,
    execute_selection,
    manifest_self_check,
    run_family,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".ci" / "invariant_families.yml"


def completed(returncode=0, stdout="ok", stderr=""):
    return subprocess.CompletedProcess(["pytest"], returncode, stdout, stderr)


def test_aggregate_fail_closed_precedence():
    assert aggregate_status([]) == "NOT_EVALUATED"
    assert aggregate_status([{"status": "PASS"}, {"status": "NOT_EVALUATED"}]) == "NOT_EVALUATED"
    assert aggregate_status([{"status": "BLOCKED"}, {"status": "NOT_EVALUATED"}]) == "BLOCKED"
    assert aggregate_status([{"status": "FAIL"}, {"status": "BLOCKED"}]) == "FAIL"


def test_family_without_evidence_is_not_evaluated():
    family = {
        "family_id": "CI-XDOMAIN", "mandatory": True,
        "governing_authority": ["INV-ARC-021"], "evidence_commands": [],
    }
    result = run_family(family, root=ROOT, pytest_executable="pytest")
    assert result["status"] == "NOT_EVALUATED"


def test_family_command_success_is_pass():
    family = {
        "family_id": "CI-ARC-EXEC", "mandatory": True,
        "governing_authority": ["INV-ARC-006"], "evidence_commands": ["tests/example.py"],
    }
    result = run_family(
        family, root=ROOT, pytest_executable="pytest",
        runner=lambda *args, **kwargs: completed(),
    )
    assert result["status"] == "PASS"
    # Evidence must be collected by pytest, not executed as a bare script.
    assert result["executions"][0]["command"] == ["pytest", "-m", "pytest", "-q", "tests/example.py"]


def test_family_command_failure_is_fail():
    family = {
        "family_id": "CI-ARC-EXEC", "mandatory": True,
        "governing_authority": ["INV-ARC-006"], "evidence_commands": ["tests/example.py"],
    }
    result = run_family(
        family, root=ROOT, pytest_executable="pytest",
        runner=lambda *args, **kwargs: completed(returncode=1, stderr="failure"),
    )
    assert result["status"] == "FAIL"


def test_committed_manifest_passes_self_check():
    """Every path rule must select a real surface at the current revision.

    A rule that matches nothing selects no evidence, which the aggregator cannot
    distinguish from a satisfied gate. This test is the guard against that
    silent-pass failure mode.
    """
    result = manifest_self_check(root=ROOT, manifest=MANIFEST)
    assert result["status"] == "PASS", result["problems"]


def test_self_check_reports_a_path_rule_that_matches_nothing(tmp_path):
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-DEAD\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/nonexistent_surface/**]\n"
        "    evidence_kind: [static]\n"
        "    evidence_commands: []\n"
        "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n",
        encoding="utf-8",
    )
    result = manifest_self_check(root=ROOT, manifest=manifest)
    assert result["status"] == "FAIL"
    assert result["problems"] == [
        {
            "family_id": "CI-DEAD",
            "kind": "path_rule_matches_nothing",
            "detail": "app/nonexistent_surface/**",
        }
    ]


@pytest.mark.parametrize(
    ("field", "value", "kind", "detail"),
    [
        ("evidence_commands", "[tests/deleted_evidence.py]",
         "evidence_command_missing", "tests/deleted_evidence.py"),
        ("auxiliary_evidence", "[not_a_real_validator]",
         "auxiliary_evidence_unknown", "not_a_real_validator"),
    ],
)
def test_self_check_reports_dangling_evidence_references(tmp_path, field, value, kind, detail):
    manifest = tmp_path / "manifest.yml"
    extra = f"    {field}: {value}\n"
    manifest.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-DANGLING\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/models.py]\n"
        "    evidence_kind: [static]\n"
        + ("" if field == "evidence_commands" else "    evidence_commands: []\n")
        + extra
        + "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n",
        encoding="utf-8",
    )
    result = manifest_self_check(root=ROOT, manifest=manifest)
    assert result["status"] == "FAIL"
    assert {"family_id": "CI-DANGLING", "kind": kind, "detail": detail} in result["problems"]


def test_selection_with_missing_families_is_not_evaluated(tmp_path):
    """One unevidenced family drags the whole selection down, even beside passing ones.

    This is asserted against a synthetic manifest on purpose. It used to be
    asserted against the committed one, which worked only because some real
    family happened to declare no evidence — first CI-XDOMAIN, then CI-PII. Both
    are closed now, so the live manifest can no longer express the condition and
    the test silently inverted to PASS the moment the second closure merged. The
    fail-closed guarantee is a property of the aggregator, not of whichever
    family is currently unfinished, so it is pinned to a fixture that cannot be
    closed out from under it.
    """
    manifest = tmp_path / "manifest.yml"
    manifest.write_text(
        "version: 1\nfamilies:\n"
        "  - family_id: CI-EVIDENCED\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/models.py]\n"
        "    evidence_kind: [runtime]\n"
        "    evidence_commands: [tests/test_ci_evidence_runner.py]\n"
        "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n"
        "  - family_id: CI-BARE\n"
        "    governing_authority: [INV-ARC-000]\n"
        "    path_rules: [app/models.py]\n"
        "    evidence_kind: [static]\n"
        "    evidence_commands: []\n"
        "    mandatory: true\n"
        "    pass_contract: none\n"
        "    known_limits: none\n",
        encoding="utf-8",
    )
    selection = classify(["app/models.py"], manifest)
    result = execute_selection(selection, root=ROOT, pytest_executable="pytest", manifest=manifest,
                               runner=lambda *args, **kwargs: completed())
    statuses = {item["family_id"]: item["status"] for item in result["family_results"]}
    assert statuses["CI-EVIDENCED"] == "PASS"
    assert statuses["CI-BARE"] == "NOT_EVALUATED"
    assert result["status"] == "NOT_EVALUATED"


def test_every_committed_family_declares_evidence():
    """No family may sit in the manifest declaring nothing.

    A family with neither evidence_commands nor auxiliary_evidence reports
    NOT_EVALUATED forever, which fails every PR that selects it for a reason
    unrelated to the change. Both families that did this have been closed; this
    keeps a third from being added without evidence.
    """
    bare = [
        family["family_id"]
        for family in load_manifest(MANIFEST)
        if not family.get("evidence_commands") and not family.get("auxiliary_evidence")
    ]
    assert bare == [], f"families declaring no evidence: {bare}"


def test_cross_domain_evidence_is_declared_and_runnable():
    """The family must not be able to drift back to a declared-nothing PASS."""
    family = next(f for f in load_manifest(MANIFEST) if f["family_id"] == "CI-XDOMAIN")
    assert family["auxiliary_evidence"] == ["cross_domain_validator"]
    assert ALLOWED_AUXILIARY["cross_domain_validator"] == ["scripts/validate-cross-domain.py"]
    result = run_family(family, root=ROOT, pytest_executable=sys.executable)
    assert result["status"] == "PASS"
    assert result["executions"][0]["returncode"] == 0


def test_cross_domain_failure_propagates_to_the_aggregate():
    """A failing validator must turn the family, and the run, red."""
    family = next(f for f in load_manifest(MANIFEST) if f["family_id"] == "CI-XDOMAIN")
    result = run_family(
        family, root=ROOT, pytest_executable="pytest",
        runner=lambda *args, **kwargs: completed(returncode=1),
    )
    assert result["status"] == "FAIL"
    assert aggregate_status([result, {"status": "PASS"}]) == "FAIL"

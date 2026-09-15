"""deploy-status.yml must not strip the operator service's auth configuration."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-status.yml"
SERVICES = {"cth-status-public", "cth-status-operator"}
# Each removes every env var or secret on the service that it does not name.
REPLACING_FLAGS = ("--set-env-vars", "--set-secrets", "--env-vars-file", "--clear-env-vars", "--clear-secrets")
AUTH_CHECK_STEP = "Verify operator auth configuration survived the deploy"
AUDIENCE = "/projects/123456789012/locations/us-west2/services/cth-status-operator"
OPERATOR = "operator@example.com"


def _deploy_steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["deploy"]["steps"]


def _gcloud_deploys():
    deploys = {}
    for step in _deploy_steps():
        match = re.search(r"gcloud run deploy (\S+)", step.get("run", ""))
        if match:
            deploys[match.group(1)] = step["run"]
    return deploys


def _auth_check_script():
    step = next(step for step in _deploy_steps() if step.get("name") == AUTH_CHECK_STEP)
    assert "gcloud run services describe cth-status-operator" in step["run"]
    return re.search(r"<<'PY'\n(.*?)\nPY\s*$", step["run"], re.S).group(1)


def _run_auth_check(tmp_path, env):
    described = tmp_path / "operator-service.json"
    described.write_text(json.dumps({"spec": {"template": {"spec": {"containers": [{"image": "cth-status", "env": env}]}}}}))
    return subprocess.run(
        [sys.executable, "-", str(described)], input=_auth_check_script(), capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("flag", REPLACING_FLAGS)
def test_status_deploy_workflow_never_replaces_service_configuration(flag):
    deploys = _gcloud_deploys()
    # Without this, a renamed service or reshaped step would match no command
    # and the flag check below would pass having inspected nothing.
    assert set(deploys) == SERVICES
    for service, command in deploys.items():
        assert flag not in command, f"{service} deploy uses {flag}"


def test_status_deploy_workflow_checks_operator_auth_after_operator_deploy():
    steps = _deploy_steps()
    names = [step.get("name") for step in steps]
    operator_deploy = next(i for i, step in enumerate(steps) if "gcloud run deploy cth-status-operator" in step.get("run", ""))
    assert AUTH_CHECK_STEP in names
    assert names.index(AUTH_CHECK_STEP) > operator_deploy


def test_status_deploy_workflow_auth_check_passes_for_configured_service(tmp_path):
    result = _run_auth_check(tmp_path, [
        {"name": "STATUS_SERVICE_MODE", "value": "operator"},
        {"name": "IAP_AUDIENCE", "value": AUDIENCE},
        {"name": "STATUS_OPERATOR_ALLOWLIST", "value": f"{OPERATOR},second@example.com"},
        {"name": "IAP_TRUSTED_EMAIL_HEADER", "value": "true"},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fallback: on" in result.stdout


def test_status_deploy_workflow_auth_check_accepts_allowlist_from_secret_manager(tmp_path):
    result = _run_auth_check(tmp_path, [
        {"name": "IAP_AUDIENCE", "value": AUDIENCE},
        {"name": "STATUS_OPERATOR_ALLOWLIST", "valueFrom": {"secretKeyRef": {"name": "status-operator-allowlist", "key": "latest"}}},
    ])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "env, missing",
    [
        ([{"name": "STATUS_SERVICE_MODE", "value": "operator"}], {"IAP_AUDIENCE", "STATUS_OPERATOR_ALLOWLIST"}),
        ([{"name": "IAP_AUDIENCE", "value": AUDIENCE}], {"STATUS_OPERATOR_ALLOWLIST"}),
        ([{"name": "IAP_AUDIENCE", "value": " "}, {"name": "STATUS_OPERATOR_ALLOWLIST", "value": OPERATOR}], {"IAP_AUDIENCE"}),
    ],
    ids=["stripped-by-set-env-vars", "no-allowlist", "blank-audience"],
)
def test_status_deploy_workflow_auth_check_fails_for_missing_configuration(tmp_path, env, missing):
    result = _run_auth_check(tmp_path, env)
    assert result.returncode == 1
    reported = set(re.findall(r"::error::cth-status-operator has no (\w+)", result.stdout))
    assert reported == missing


def test_status_deploy_workflow_auth_check_never_prints_values(tmp_path):
    result = _run_auth_check(tmp_path, [
        {"name": "IAP_AUDIENCE", "value": AUDIENCE},
        {"name": "STATUS_OPERATOR_ALLOWLIST", "value": OPERATOR},
    ])
    output = result.stdout + result.stderr
    assert OPERATOR not in output
    assert AUDIENCE not in output

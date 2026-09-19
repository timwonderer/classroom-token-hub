"""deploy-status.yml must not strip the operator service's auth configuration, and must verify the deploy it made."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-status.yml"
DOCKERFILE = Path(__file__).resolve().parent.parent / "status_service" / "Dockerfile"
SERVICES = {"cth-status-public", "cth-status-operator"}
# Each removes every env var or secret on the service that it does not name.
REPLACING_FLAGS = ("--set-env-vars", "--set-secrets", "--env-vars-file", "--clear-env-vars", "--clear-secrets")
AUTH_CHECK_STEP = "Verify operator auth configuration survived the deploy"
READINESS_STEP = "Verify both services are serving this commit"
PROJECT = "cth-production-status"
AUDIENCE = "/projects/123456789012/locations/us-west2/services/cth-status-operator"
OPERATOR = "operator@example.com"
ALLOWLIST_SECRET = {"secretKeyRef": {"name": "status-operator-allowlist", "key": "latest"}}
IMAGE = f"us-west2-docker.pkg.dev/{PROJECT}/status/cth-status:1eeaaa8e346c74a6a64493fb81954c045db571ed"
COLLECTOR_JOB = "cth-status-app-health-collector"

# Stands in for `gcloud secrets versions access`: serves the payloads it is
# given, and refuses any other secret, project or command the way a missing
# permission would.
FAKE_GCLOUD = """
import json
import sys

args = sys.argv[1:]
with open(sys.argv[0] + ".json") as handle:
    payloads = json.load(handle)
if args[:3] != ["secrets", "versions", "access"] or "--project" not in args or args[args.index("--project") + 1] != {project!r}:
    sys.exit(2)
name = args[args.index("--secret") + 1] if "--secret" in args else None
if name not in payloads:
    sys.exit("PERMISSION_DENIED")
sys.stdout.write(payloads[name])
"""


def _deploy_steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["deploy"]["steps"]


def test_focused_status_job_runs_collector_and_workflow_tests():
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["test"]["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Run focused status tests")
    assert "tests/test_status_collector.py" in command
    assert "tests/test_status_deploy_workflow.py" in command


def test_collector_job_uses_shared_image_scoped_identity_and_secret_references():
    step = _step("Deploy app health collector job")
    command = step["run"]
    assert f"gcloud run jobs deploy {COLLECTOR_JOB}" in command
    assert '--image "$IMAGE_URI"' in command
    assert '--region "$GCP_REGION"' in command
    assert '--project "$GCP_PROJECT_ID"' in command
    assert '--service-account "status-probe@cth-production-status.iam.gserviceaccount.com"' in command
    assert "--command python" in command
    assert "--args=-m,status_service.collector" in command
    assert "FIRESTORE_DATABASE=cth-status-prod" in command
    assert "CF_ACCESS_CLIENT_ID=cth-status-cf-access-client-id:latest" in command
    assert "CF_ACCESS_CLIENT_SECRET=cth-status-cf-access-client-secret:latest" in command
    assert not any(flag in command for flag in REPLACING_FLAGS)


def test_collector_job_requires_explicit_opt_in():
    step = _step("Deploy app health collector job")
    assert step["if"] == "${{ vars.STATUS_APP_HEALTH_COLLECTOR_ENABLED == 'true' }}"
    assert sum(
        other.get("run", "").count(f"gcloud run jobs deploy {COLLECTOR_JOB}")
        for other in _deploy_steps()
    ) == 1


def test_duplicate_collector_step_with_same_name_is_rejected(monkeypatch):
    steps = _deploy_steps()
    duplicate = next(step for step in steps if step.get("name") == "Deploy app health collector job")
    monkeypatch.setattr(sys.modules[__name__], "_deploy_steps", lambda: [*steps, duplicate])
    with pytest.raises(AssertionError):
        test_collector_job_requires_explicit_opt_in()


def test_status_image_contains_shared_projection_package():
    build = _step("Build and push status image")["run"]
    dockerfile = DOCKERFILE.read_text()

    assert 'docker build -f status_service/Dockerfile -t "$IMAGE_URI" .' in build
    assert "COPY status /app/status" in dockerfile
    assert "COPY status_service /app/status_service" in dockerfile


def _step(name):
    return next(step for step in _deploy_steps() if step.get("name") == name)


def _gcloud_deploys():
    deploys = {}
    for step in _deploy_steps():
        match = re.search(r"gcloud run deploy (\S+)", step.get("run", ""))
        if match:
            deploys[match.group(1)] = step["run"]
    return deploys


def _step_script(name):
    return re.search(r"<<'PY'\n(.*?)\nPY\s*$", _step(name)["run"], re.S).group(1)


def _run_auth_check(tmp_path, env, secrets=None):
    assert "gcloud run services describe cth-status-operator" in _step(AUTH_CHECK_STEP)["run"]
    described = tmp_path / "operator-service.json"
    described.write_text(json.dumps({"spec": {"template": {"spec": {"containers": [{"image": "cth-status", "env": env}]}}}}))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "fake_gcloud.py"
    fake.write_text(FAKE_GCLOUD.format(project=PROJECT))
    (bin_dir / "fake_gcloud.py.json").write_text(json.dumps(secrets or {}))
    gcloud = bin_dir / "gcloud"
    gcloud.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
    gcloud.chmod(0o755)
    return subprocess.run(
        [sys.executable, "-", str(described)], input=_step_script(AUTH_CHECK_STEP), capture_output=True, text=True, check=False,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}", "GCP_PROJECT_ID": PROJECT},
    )


def _described(name, revision="00016-abc", created=None, ready="True", traffic=None, image=IMAGE):
    revision_name = f"{name}-{revision}" if revision else None
    status = {
        "conditions": [{"type": "Ready", "status": ready}, {"type": "RoutesReady", "status": ready}],
        "latestCreatedRevisionName": f"{name}-{created}" if created else revision_name,
        "traffic": [{"revisionName": revision_name, "percent": 100, "latestRevision": True}] if traffic is None else traffic,
    }
    if revision_name:
        status["latestReadyRevisionName"] = revision_name
    return {"metadata": {"name": name}, "spec": {"template": {"spec": {"containers": [{"image": image}]}}}, "status": status}


def _run_readiness_check(tmp_path, public, operator):
    paths = []
    for service in (public, operator):
        path = tmp_path / f"{service['metadata']['name']}.json"
        path.write_text(json.dumps(service))
        paths.append(str(path))
    return subprocess.run(
        [sys.executable, "-", *paths], input=_step_script(READINESS_STEP), capture_output=True, text=True, check=False,
        env={**os.environ, "IMAGE_URI": IMAGE},
    )


def _reported_missing(result):
    return set(re.findall(r"::error::cth-status-operator has no (\w+)", result.stdout))


def _reported_unreadable(result):
    return set(re.findall(r"::error::cth-status-operator reads (\w+) from Secret Manager", result.stdout))


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


def test_status_deploy_workflow_operator_auth_check_runs_after_an_earlier_check_fails():
    # Steps after a failure are skipped unless their condition says otherwise;
    # run 34928799354 deployed the operator service and never checked it.
    operator_deploy = next(step for step in _deploy_steps() if "gcloud run deploy cth-status-operator" in step.get("run", ""))
    condition = _step(AUTH_CHECK_STEP).get("if", "")
    assert operator_deploy.get("id") == "deploy_operator"
    assert "!cancelled()" in condition
    assert "steps.deploy_operator.outcome == 'success'" in condition


def test_status_deploy_workflow_does_not_probe_services_over_http():
    # Both services run with restricted ingress, so a request from a GitHub
    # runner gets Google's 404 whatever the service's health.
    for step in _deploy_steps():
        assert "curl" not in step.get("run", ""), step.get("name")


def test_status_deploy_workflow_checks_readiness_after_both_deploys():
    steps = _deploy_steps()
    names = [step.get("name") for step in steps]
    last_deploy = max(i for i, step in enumerate(steps) if "gcloud run deploy" in step.get("run", ""))
    assert names.index(READINESS_STEP) > last_deploy
    for service in SERVICES:
        assert f"$RUNNER_TEMP/{service}.json" in _step(READINESS_STEP)["run"]


def test_status_deploy_workflow_readiness_passes_when_both_services_serve_this_commit(tmp_path):
    result = _run_readiness_check(tmp_path, _described("cth-status-public"), _described("cth-status-operator"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count(" serving") == 2


@pytest.mark.parametrize(
    "operator, problem",
    [
        (_described("cth-status-operator", ready="False"), "is not Ready"),
        (_described("cth-status-operator", created="00017-new"), "has a newer revision that did not become ready"),
        (_described("cth-status-operator", revision=None), "has a newer revision that did not become ready"),
        (
            _described("cth-status-operator", traffic=[
                {"revisionName": "cth-status-operator-00016-abc", "percent": 50},
                {"revisionName": "cth-status-operator-00015-old", "percent": 50},
            ]),
            "does not route all traffic to its ready revision",
        ),
        (
            _described("cth-status-operator", traffic=[{"revisionName": "cth-status-operator-00015-old", "percent": 100}]),
            "does not route all traffic to its ready revision",
        ),
        (_described("cth-status-operator", image=IMAGE.replace("1eeaaa8e3", "0000000")), "is not running this commit's image"),
    ],
    ids=["not-ready", "newer-revision-failed", "no-ready-revision", "traffic-split", "traffic-on-old-revision", "old-image"],
)
def test_status_deploy_workflow_readiness_fails_for_a_service_not_serving_this_commit(tmp_path, operator, problem):
    result = _run_readiness_check(tmp_path, _described("cth-status-public"), operator)
    assert result.returncode == 1
    errors = re.findall(r"::error::(\S+) (.+)\.$", result.stdout, re.M)
    assert ("cth-status-operator", problem) in errors
    # The healthy service is not blamed for the other one.
    assert not any(service == "cth-status-public" for service, _ in errors)


def test_status_deploy_workflow_auth_check_passes_for_configured_service(tmp_path):
    result = _run_auth_check(tmp_path, [
        {"name": "STATUS_SERVICE_MODE", "value": "operator"},
        {"name": "IAP_AUDIENCE", "value": AUDIENCE},
        {"name": "STATUS_OPERATOR_ALLOWLIST", "value": f"{OPERATOR},second@example.com"},
        {"name": "IAP_TRUSTED_EMAIL_HEADER", "value": "true"},
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fallback: on" in result.stdout


def test_status_deploy_workflow_auth_check_accepts_populated_secret(tmp_path):
    result = _run_auth_check(
        tmp_path,
        [{"name": "IAP_AUDIENCE", "value": AUDIENCE}, {"name": "STATUS_OPERATOR_ALLOWLIST", "valueFrom": ALLOWLIST_SECRET}],
        secrets={"status-operator-allowlist": f"{OPERATOR}\n"},
    )
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
    assert _reported_missing(result) == missing


def test_status_deploy_workflow_auth_check_fails_for_blank_secret(tmp_path):
    # A reference to a secret whose payload is blank configures nothing: the
    # service reads an empty allowlist and refuses every operator.
    result = _run_auth_check(
        tmp_path,
        [{"name": "IAP_AUDIENCE", "value": AUDIENCE}, {"name": "STATUS_OPERATOR_ALLOWLIST", "valueFrom": ALLOWLIST_SECRET}],
        secrets={"status-operator-allowlist": " \n"},
    )
    assert result.returncode == 1
    assert _reported_missing(result) == {"STATUS_OPERATOR_ALLOWLIST"}


def test_status_deploy_workflow_auth_check_fails_when_secret_cannot_be_read(tmp_path):
    result = _run_auth_check(
        tmp_path,
        [{"name": "IAP_AUDIENCE", "value": AUDIENCE}, {"name": "STATUS_OPERATOR_ALLOWLIST", "valueFrom": ALLOWLIST_SECRET}],
        secrets={},
    )
    assert result.returncode == 1
    assert _reported_unreadable(result) == {"STATUS_OPERATOR_ALLOWLIST"}
    assert _reported_missing(result) == set()


def test_status_deploy_workflow_auth_check_never_prints_values(tmp_path):
    result = _run_auth_check(
        tmp_path,
        [{"name": "IAP_AUDIENCE", "value": AUDIENCE}, {"name": "STATUS_OPERATOR_ALLOWLIST", "valueFrom": ALLOWLIST_SECRET}],
        secrets={"status-operator-allowlist": OPERATOR},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert OPERATOR not in output
    assert AUDIENCE not in output

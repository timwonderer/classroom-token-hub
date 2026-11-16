"""Offline workflow integration using the actual lease store and disposable provider fixtures."""
import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

import controller
from digitalocean import LifecycleError
from lifecycle import Lifecycle


ROOT = Path(__file__).resolve().parents[2]
STAGES = next(ast.literal_eval(node.value) for node in ast.parse(
    (ROOT / "infra/self-hosting/install.py").read_text()).body
    if isinstance(node, ast.Assign) and node.targets[0].id == "STAGES")
REQUEST = ("7", "a"*40, controller.PROFILE, "b"*40)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        for directory in ("pending", "runs", "evidence"):
            (self.state / directory).mkdir()
        self.provider = Mock()
        self.provider.policy = dict(ssh_key_id=9, team_uuid="test-team", project_uuid="test-project",
                                    vpc_uuid="test-vpc", image_id=139, firewall_id="test-firewall")
        self.obj = {"id": 31, "networks": {"v4": [{"type": "private", "ip_address": "10.5.0.3"}]}}
        self.provider.create.return_value = 31
        self.provider.droplets.return_value = [self.obj]
        self.provider.get.return_value = self.obj
        self.provider.ready.return_value = True
        self.provider.resources.return_value = []

        def deleted(number):
            self.assertEqual(number, 31)
            self.provider.droplets.return_value = []
            self.provider.get.return_value = None
        self.provider.delete.side_effect = deleted
        self.now = int(time.time())
        self.life = Lifecycle(self.state/"db", self.provider, now=lambda:self.now)
        self.host = Mock()
        self.host.cloud_init.return_value = "public bootstrap"
        self.host.revoked.return_value = True
        self.prepare = lambda row: self.host

    def run_job(self):
        return controller.execute(REQUEST, self.life, self.state, self.prepare, 9, STAGES)

    def test_dispatch_calls_all_canonical_stages_then_retires(self):
        self.host.install.side_effect = lambda addr,n,record: [record(s, "ok") for s in STAGES + ("acceptance",)]
        result = self.run_job()
        self.assertEqual(result["stages"], list(STAGES))
        self.assertEqual(result["acceptance"], "passed")
        self.assertEqual(result["cleanup"], "verified")
        self.assertEqual(self.life.current("7")["state"], "closed")
        self.assertFalse(any((self.state / "pending").iterdir()))
        with self.assertRaises(LifecycleError):
            self.run_job()
        self.assertEqual(self.provider.create.call_count, 1)

    def test_interrupted_installer_emits_only_completed_stage_then_tears_down(self):
        def failing(addr,n,record):
            record("host", "ok")
            raise KeyboardInterrupt("private credential in guest diagnostics")
        self.host.install.side_effect = failing
        result = self.run_job()
        self.assertEqual((result["execution"], result["stages"], result["cleanup"]), ("failed", ["host"], "verified"))
        self.assertNotIn("private credential", (self.state / "evidence/7.json").read_text())

    def test_provider_timeout_and_revocation_retry(self):
        self.host.install.side_effect = lambda addr,n,record: [record(s, "ok") for s in STAGES]
        original_delete = self.provider.delete.side_effect
        self.provider.delete.side_effect = TimeoutError()
        result = self.run_job()
        self.assertEqual(result["cleanup"], "unresolved")
        self.assertEqual(self.life.current("7")["droplet_id"], 31)
        self.provider.delete.side_effect = original_delete
        self.host.revoked.return_value = False
        with self.assertRaises(ValueError):
            controller.sweep(self.life, self.state, self.prepare)
        self.assertTrue((self.state / "pending/7").exists())
        self.host.revoked.return_value = True
        controller.sweep(self.life, self.state, self.prepare)
        self.assertFalse((self.state / "pending/7").exists())
        self.assertTrue((self.state / "sweep-ok").exists())

    def test_runner_vanishes_before_bootstrap(self):
        self.life.reserve(*REQUEST[:3])
        controller.mark_pending(self.state / "pending/7")
        self.life.allocate("7", user_data="public", ssh_keys=[9])
        self.now += 7200
        controller.sweep(self.life, self.state, self.prepare)
        self.provider.delete.assert_called_once_with(31)
        self.host.install.assert_not_called()
        self.assertFalse((self.state / "pending/7").exists())

    def test_approval_binds_refs_run_profile_and_short_window(self):
        approval = dict(run_id="7", sha=REQUEST[1], profile=REQUEST[2], workflow_sha=REQUEST[3],
                        controller_sha="c"*40, dispatch_before=self.now+90)
        controller.approve(REQUEST, approval, "c"*40, self.now)
        for key in approval:
            changed = dict(approval)
            changed[key] = self.now if key == "dispatch_before" else "wrong"
            with self.subTest(key=key), self.assertRaises(ValueError):
                controller.approve(REQUEST, changed, "c"*40, self.now)
        command = "dispatch " + " ".join(REQUEST)
        self.assertEqual(controller.parse_request(command), REQUEST)
        for bad in (command+";", "sweep", command+"\n"):
            with self.assertRaises(ValueError):
                controller.parse_request(bad)

    def test_workflow_dispatch_boundary_matches_installer_and_independent_timer(self):
        text = (ROOT / ".github/workflows/staging-ephemeral.yml").read_text()
        self.assertIn("on:\n  workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn(" ".join(STAGES), text)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotIn("DIGITALOCEAN_TOKEN", text)
        self.assertIn("Persistent=true", (Path(__file__).with_name("cth-staging-cleanup.timer")).read_text())

    def test_runner_sanitizes_actual_workflow_evidence(self):
        workflow = (ROOT / ".github/workflows/staging-ephemeral.yml").read_text()
        python = textwrap.dedent(workflow.split("<<'PY'\n",1)[1].split("\n          PY\n",1)[0])
        env = dict(os.environ, GITHUB_RUN_ID=REQUEST[0], APP_SHA=REQUEST[1], PROFILE=REQUEST[2],
                   RUNNER_TEMP=str(self.state))
        complete = dict(run_id=REQUEST[0],sha=REQUEST[1],profile=REQUEST[2],stages=list(STAGES),
                        acceptance="unexecuted",execution="passed",cleanup="verified",phase="completed",
                        issued_at=self.now, stage_times=[self.now]*len(STAGES))
        partial = dict(complete, stages=["host"], stage_times=[self.now], phase="bootstrap", execution="failed")
        for payload, expected in ((json.dumps(complete),0), (json.dumps(partial),1),
                (json.dumps(dict(complete,log="sensitive-guest-record")),1),
                ("sensitive-guest-record" * 150,1), ("{broken",1)):
            input_file = self.state / "guest.out"
            input_file.write_text(payload)
            run = subprocess.run([sys.executable,"-",str(input_file)],input=python,text=True,
                                 capture_output=True,env=env)
            self.assertEqual(run.returncode, expected)
            output = (self.state/"cth-staging-result.json").read_text()
            self.assertNotIn("sensitive-guest-record", output + run.stdout + run.stderr)
            self.assertLess(len(output), 2048)
            report = json.loads(output)
            self.assertEqual(set(report), set(complete))
            if payload == json.dumps(complete):
                self.assertEqual(report, complete)
            elif payload == json.dumps(partial):
                self.assertEqual(report, partial)
            else:
                self.assertEqual((report["phase"], report["cleanup"]), ("dispatch", "unresolved"))

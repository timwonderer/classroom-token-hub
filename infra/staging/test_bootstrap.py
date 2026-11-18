"""Attended staging bootstrap tests. Local Git fixture, simulated SSH."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bootstrap


class GuestTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name) / "private"
        self.work.mkdir(mode=0o700)
        root = Path(tmp.name) / "source"
        root.mkdir()

        def git(*args):
            return subprocess.check_output(["git", "-C", root, *args], stderr=subprocess.DEVNULL).decode().strip()

        git("init", "-q")
        self.hook = b"exit 0\n"
        (root / "check.sh").write_bytes(self.hook)
        git("add", "check.sh")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "test")
        self.args = SimpleNamespace(
            sha=git("rev-parse", "HEAD"),
            release=root,
            droplet_id=19,
            address="8.8.8.8",
            installation_id="09fcea91-a937-4818-ba57-0250dd42787f",
            acceptance_script="",
            acceptance_sha256="",
        )
        self.key = "ssh-ed25519 " + base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + b"p" * 32).decode()
        self.env = {"STAGING_" + k: "synthetic-" + k for k in bootstrap.runtime.PROVIDERS}
        self.env.update(
            STAGING_HOST_PIN=json.dumps(
                {"installation_id": self.args.installation_id, "droplet_id": 19, "host_key": self.key}
            ),
            STAGING_HOSTNAME="app.staging.invalid",
            STAGING_ADMISSION_HOSTNAME="gate.staging.invalid",
            STAGING_MARKETING_URL="https://marketing.staging.invalid",
            STAGING_PASSWORDLESS_URL="https://api.staging.invalid",
            STAGING_SSH_PRIVATE_KEY="synthetic-private-key",
            STAGING_ORIGIN_CERT="synthetic-cert",
            STAGING_ORIGIN_KEY="synthetic-key",
            STAGING_ACCESS_CLIENT_ID="approved-test-access-key",
            STAGING_ACCESS_CLIENT_SECRET="approved-test-service-secret",
        )

    def test_cloud_init_contains_only_public_enrollment(self):
        cfg = json.loads(bootstrap.cloud_init(self.args.installation_id).split("\n", 1)[1])
        self.assertFalse(cfg["ssh_pwauth"])
        self.assertTrue(cfg["ssh_deletekeys"])
        self.assertEqual(cfg["write_files"][0]["content"].strip(), self.args.installation_id)
        self.assertIn("/etc/ssh/ssh_host_ed25519_key.pub", str(cfg["runcmd"]))
        self.assertNotIn("authorized_keys", str(cfg))
        self.assertNotIn("PRIVATE KEY", str(cfg))

    def test_console_pin_and_provider_ip_are_required(self):
        with self.assertRaises(ValueError):
            bootstrap.host_pin(self.env["STAGING_HOST_PIN"], 20, self.args.installation_id)
        with self.assertRaises(ValueError):
            bootstrap.host_pin(self.env["STAGING_HOST_PIN"], 19, "old-guest")
        original = self.args.address
        for addr in ("127.0.0.1", "169.254.169.254", "192.168.1.5", "250.1.2.3"):
            self.args.address = addr
            with self.assertRaises(ValueError):
                bootstrap.Guest(self.args, self.work, self.env)
        self.args.address = original
        guest = bootstrap.Guest(self.args, self.work, self.env)
        self.assertIn("StrictHostKeyChecking=yes", guest.ssh)
        self.assertIn("IdentityAgent=none", guest.ssh)
        self.assertEqual((self.work / "identity").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.work / "known_hosts").read_text(), original + " " + self.key + "\n")

    def simulate(self, failure="", accept=False):
        if accept:
            self.args.acceptance_script = "check.sh"
            self.args.acceptance_sha256 = hashlib.sha256(self.hook).hexdigest()
        commands = []
        uploads = {}
        statuses = []

        def receipt(command):
            commands.append(command)
            if "metadata/v1/id" in command:
                number = "7" if failure == "identity" else "19"
                return (self.args.installation_id + " " + number + " " + "2" * 32).encode()
            action, stage = command.split("install.py ")[1].split()[:2]
            result = {
                "action": action,
                "stage": stage,
                "result": "ok",
                "installation_id": self.args.installation_id,
                "release_sha": self.args.sha,
            }
            if failure == "interrupt" and stage == "redis":
                raise subprocess.TimeoutExpired("simulated", 5)
            if failure == "unfiltered" and stage == "services":
                result["auth"] = "sensitive fixture"
            return json.dumps(result).encode()

        with (
            patch.object(bootstrap.Guest, "receipt", side_effect=receipt),
            patch.object(bootstrap.Guest, "run", side_effect=commands.append),
            patch.object(bootstrap.Guest, "upload", side_effect=lambda k, v: uploads.update({k: v})),
        ):
            if failure:
                with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    bootstrap.install(self.args, self.work, self.env, statuses.append)
            else:
                bootstrap.install(self.args, self.work, self.env, statuses.append)
        return statuses, commands, uploads

    def test_exact_b2_stages_and_optional_scoped_acceptance(self):
        statuses, commands, uploads = self.simulate(accept=True)
        self.assertEqual(statuses, [*bootstrap.STAGES, "acceptance"])
        self.assertEqual(
            [c.split("python3 ", 1)[1] for c in commands if "install.py " in c],
            [
                "infra/self-hosting/install.py " + action + " " + stage + " --config " + bootstrap.MANIFEST
                for stage in bootstrap.STAGES
                for action in ("apply", "check")
            ],
        )
        self.assertIn("DynamicUser=yes", commands[-1])
        self.assertIn("LoadCredential=access.json:", commands[-1])
        cfg = json.loads(uploads[bootstrap.MANIFEST])
        values = bootstrap.runtime.parse_env(uploads[cfg["runtime_env"]].decode(), cfg)
        self.assertEqual(len({values[k] for k in bootstrap.runtime.KEYS}), 5)
        self.assertNotIn("connector", " ".join(commands) + str(uploads))
        self.assertNotIn("tunnel", " ".join(commands) + str(uploads))
        self.assertNotIn(self.env["STAGING_SSH_PRIVATE_KEY"], str(uploads))
        self.assertEqual(
            subprocess.check_output(["git", "bundle", "list-heads", self.work / "release.bundle"]).split()[0],
            self.args.sha.encode(),
        )

    def test_unfiltered_receipt_and_interruption_never_mark_stage_complete(self):
        for failure, stage in (("unfiltered", "services"), ("interrupt", "redis")):
            statuses, _, _ = self.simulate(failure)
            self.assertEqual(statuses, list(bootstrap.STAGES)[: bootstrap.STAGES.index(stage)])

    def test_identity_disagreement_prevents_transfer(self):
        for failure in ("identity",):
            statuses, _, uploads = self.simulate(failure)
            self.assertFalse(statuses)
            self.assertFalse(uploads)

    def test_optional_hook_and_provider_url_defaults(self):
        statuses, _, uploads = self.simulate()
        self.assertNotIn("acceptance", statuses)
        self.assertFalse(any("acceptance" in p for p in uploads))
        self.env["STAGING_MARKETING_URL"] = "https://www.classroomtokenhub.com"
        bootstrap.checked_runtime(self.args, "2" * 32, self.env)
        del self.env["STAGING_MARKETING_URL"]
        del self.env["STAGING_PASSWORDLESS_URL"]
        _, raw = bootstrap.checked_runtime(self.args, "2" * 32, self.env)
        self.assertNotIn(b"MARKETING_SITE_URL", raw)
        self.assertNotIn(b"PASSWORDLESS_API_URL", raw)

    def test_step_summary_accepts_only_verified_stage_names(self):
        summary = self.work / "summary"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), patch("builtins.print"):
            bootstrap.record_stage("database")
            with self.assertRaises(ValueError):
                bootstrap.record_stage("unsafe fixture content")
        self.assertEqual(summary.read_text(), "- Verified `database`\n")

    def test_oversized_ssh_output_is_rejected(self):
        guest = bootstrap.Guest(self.args, self.work, self.env)
        guest.ssh = ["/bin/sh", "-c"]
        with self.assertRaises(ValueError):
            guest.receipt("printf '%05000d' 0")

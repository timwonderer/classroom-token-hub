"""Exercise authorized and credential-free monitoring probes without network I/O."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test_monitoring.sh"
FAKE_CURL = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["CURL_CALL_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
endpoint = "/health/status" if args[-1].endswith("/health/status") else "/health"
if "-o" in args:
    codes = json.loads(os.environ["NEGATIVE_CODES"])
    print(codes[endpoint])
    print(os.environ.get("NEGATIVE_REDIRECT", ""))
else:
    print('{"signals":[{"key":"database"}]}' if endpoint.endswith("status") else "ok")
    print("200")
'''


class MonitoringScriptTests(unittest.TestCase):
    def run_script(self, codes, *, credentials=True, redirect="", partial=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            curl = root / "curl"
            curl.write_text(f"#!{sys.executable}\n" + FAKE_CURL)
            curl.chmod(0o755)
            log = root / "calls.jsonl"
            env = os.environ.copy()
            env.pop("CF_ACCESS_CLIENT_ID", None)
            env.pop("CF_ACCESS_CLIENT_SECRET", None)
            env.update(
                PATH=f"{root}:{env['PATH']}",
                CURL_CALL_LOG=str(log),
                NEGATIVE_CODES=json.dumps(dict(zip(("/health", "/health/status"), codes))),
                NEGATIVE_REDIRECT=redirect,
            )
            if credentials:
                env["CF_ACCESS_CLIENT_ID"] = "test-client"
                if not partial:
                    env["CF_ACCESS_CLIENT_SECRET"] = "test-secret"
            result = subprocess.run(
                ["bash", str(SCRIPT), "https://app.example.test"],
                env=env, capture_output=True, text=True, check=False,
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, calls

    def test_gated_requests_separate_authorized_and_anonymous_probes(self):
        result, calls = self.run_script([403, 403])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(calls), 4)
        for args in calls[:2]:
            self.assertIn("CF-Access-Client-Id: test-client", args)
            self.assertIn("CF-Access-Client-Secret: test-secret", args)
        for args in calls[2:]:
            self.assertFalse(any("CF-Access-" in arg for arg in args))
            self.assertIn("Cookie: ", args)
        for args in calls:
            self.assertEqual(args[0], "-q")
            self.assertNotIn("-L", args)

    def test_access_login_redirect_is_accepted(self):
        result, _ = self.run_script(
            [302, 302], redirect="https://team.cloudflareaccess.com/cdn-cgi/access/login/app.example.test"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_open_endpoint_fails_on_either_probe(self):
        for codes in ([200, 403], [403, 200]):
            with self.subTest(codes=codes):
                result, _ = self.run_script(codes)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("All tests passed!", result.stdout)

    def test_unrelated_redirect_and_server_error_do_not_prove_denial(self):
        for status, redirect in (
            (302, "https://app.example.test/login"),
            (302, "https://team.cloudflareaccess.com.evil.test/cdn-cgi/access/login/app"),
            (500, ""),
            (401, ""),
        ):
            with self.subTest(status=status, redirect=redirect):
                result, _ = self.run_script([status, status], redirect=redirect)
                self.assertNotEqual(result.returncode, 0)

    def test_direct_probes_work_without_service_tokens(self):
        result, calls = self.run_script([200, 200], credentials=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any("CF-Access-" in arg for call in calls for arg in call))

    def test_direct_probe_denial_is_a_failure(self):
        result, _ = self.run_script([403, 403], credentials=False)
        self.assertNotEqual(result.returncode, 0)

    def test_partial_credentials_fail_before_network_requests(self):
        result, calls = self.run_script([403, 403], partial=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

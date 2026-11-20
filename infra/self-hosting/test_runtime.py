"""Local, nonprivileged runtime-stage checks. No services, network or database."""
import base64
import configparser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(installation_id="a" * 36, machine_id="1" * 32, release_sha="f" * 40,
                        database="cth_fiction", hostname="hub.example.org",
                        admission_hostname="gate.example.org", runtime_env="/etc/cth/runtime.env",
                        tls_cert="/etc/cth/origin.crt", tls_key="/etc/cth/origin.key")
        self.env = {k: str(i) * 64 for i, k in enumerate(sorted(runtime.KEYS))}
        self.env.update(ENCRYPTION_KEY=base64.urlsafe_b64encode(bytes(range(32))).decode(),
                        FLASK_ENV="production", LOG_FILE="/var/log/cth-web/app.log",
                        DATABASE_URL="postgresql:///cth_fiction?host=/var/run/postgresql&port=5432",
                        STUDENT_SETUP_REDIS_URL="unix://" + runtime.SETUP_SOCKET,
                        RATELIMIT_STORAGE_URI="redis+unix://" + runtime.RATE_SOCKET,
                        PASSWORDLESS_API_URL="https://provider.example.org", MARKETING_SITE_URL="https://www.example.org")
        self.env.update({key: "synthetic-credential-" + key for key in runtime.PROVIDERS})

    def parse(self, values):
        return runtime.parse_env("\n".join(k + "=" + v for k, v in values.items()), self.cfg)

    def test_all_mandatory_fields_and_missing_config(self):
        self.assertEqual(self.parse(self.env), self.env)
        for key in runtime.REQUIRED:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                self.parse({k: v for k, v in self.env.items() if k != key})

    def test_overrides_separation_and_destinations(self):
        for key, bad in (("FLASK_ENV", "testing"), ("DATABASE_URL", "postgresql:///wrong"),
                         ("RATELIMIT_STORAGE_URI", self.env["STUDENT_SETUP_REDIS_URL"]),
                         ("STUDENT_SETUP_REDIS_URL", self.env["RATELIMIT_STORAGE_URI"]),
                         ("SECRET_KEY", self.env["PEPPER_KEY"]), ("ENCRYPTION_KEY", "synthetic-invalid-fernet"),
                         ("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA"),
                         ("PASSWORDLESS_API_URL", "https://app.classroomtokenhub.com"),
                         ("PASSWORDLESS_API_URL", "https://provider.example.org@elsewhere.example.org"),
                         ("LD_PRELOAD", "/somewhere/lib.so"), ("TURNSTILE_SECRET_KEY", "ab$HOME"),
                         ("LOG_FILE", "/opt/cth/app.log")):
            with self.subTest(key=key), self.assertRaises(ValueError) as err:
                self.parse(dict(self.env, **{key: bad}))
            self.assertNotIn(bad, str(err.exception))

    def test_deployment_identity_and_root_file_paths(self):
        runtime.validate_config(self.cfg)
        self.assertTrue(runtime.hostname("myclassroomtokenhub.com"))
        self.assertTrue(runtime.hostname("classroomtokenhub.com.other.example.org"))
        for key, bad in (("hostname", "app.classroomtokenhub.com"), ("hostname", "any.deep.classroomtokenhub.com"), ("hostname", "*.example.org"),
                         ("tls_cert", "/etc/cth/../private"), ("tls_key", self.cfg["tls_cert"]),
                         ("runtime_env", "/tmp/runtime.env"), ("admission_hostname", self.cfg["hostname"])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                runtime.validate_config(dict(self.cfg, **{key: bad}))

    def test_staging_subdomain_is_only_an_application_origin(self):
        staging = "staging.classroomtokenhub.com"
        runtime.validate_config(dict(self.cfg, hostname=staging))
        for host in ("classroomtokenhub.com", "status.classroomtokenhub.com", "other." + staging):
            with self.subTest(host=host), self.assertRaises(ValueError):
                runtime.validate_config(dict(self.cfg, hostname=host))
        with self.assertRaises(ValueError):
            runtime.validate_config(dict(self.cfg, admission_hostname=staging))
        for key in ("PASSWORDLESS_API_URL",):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(dict(self.env, **{key: "https://" + staging}))

    def test_public_information_uses_app_default_or_explicit_https(self):
        values = {k: v for k, v in self.env.items() if k != "MARKETING_SITE_URL"}
        self.assertNotIn("MARKETING_SITE_URL", self.parse(values))
        for key in runtime.INFORMATION_URLS:
            configured = dict(values, **{key: "https://classroomtokenhub.com"})
            self.assertEqual(self.parse(configured)[key], configured[key])
        self.parse({k: v for k, v in values.items() if k != "PASSWORDLESS_API_URL"})
        with self.assertRaises(ValueError):
            self.parse(dict(values, MARKETING_SITE_URL="http://classroomtokenhub.com"))

    def test_gate_does_not_follow_redirects_or_disclose_response(self):
        for status, destination, success in (
            (302, "https://gate.example.org/cdn-cgi/access/login/hub", True),
            (200, "", False), (302, "https://gate.example.org.evil.org/cdn-cgi/access/login/hub", False),
            (302, "https://gate.example.org/unrelated", False), (302, "http://gate.example.org/cdn-cgi/access/login/x", False),
        ):
            with self.subTest(status=status, destination=destination), patch.object(runtime, "command", return_value=f"{status} {destination}") as command:
                if success:
                    runtime.gate(self.cfg)
                else:
                    with self.assertRaises(ValueError):
                        runtime.gate(self.cfg)
                self.assertNotIn("--location", command.call_args.args)
                self.assertEqual(command.call_args.args[-1], "https://hub.example.org/admin/login")

    def test_managed_file_retries_or_refuses_drift(self):
        # Host ownership path checks have separate reference-host acceptance.
        with tempfile.TemporaryDirectory() as d, patch.object(runtime, "trusted_parents"), patch.object(runtime, "trusted"):
            target = Path(d) / "web.service"
            runtime.managed(target, "cth-web.service", self.cfg, True)
            data = target.read_bytes()
            runtime.managed(target, "cth-web.service", self.cfg, True)
            self.assertEqual(target.read_bytes(), data)
            target.write_bytes(b"operator file")
            with self.assertRaises(ValueError):
                runtime.managed(target, "cth-web.service", self.cfg, True)
            self.assertEqual(target.read_bytes(), b"operator file")

    def test_units_and_tls_template(self):
        templates = {n: runtime.template(n, self.cfg).decode() for n in
                     ("cth-web.service", "cth-ingress.service", "ingress.conf")}
        for text in templates.values():
            self.assertNotRegex(text, r"@[A-Z_]+@")
        for name in ("cth-web.service", "cth-ingress.service"):
            unit = configparser.ConfigParser(interpolation=None)
            unit.read_string(templates[name])
            self.assertTrue(unit.get("Service", "ExecStart").startswith("/"))
            self.assertEqual(unit.get("Install", "WantedBy"), "multi-user.target")
        web = templates["cth-web.service"]
        for value in ("--bind 127.0.0.1:8000", "wsgi:app", "LimitCORE=0", "MemorySwapMax=0",
                      "/gunicorn.conf.py", "EnvironmentFile=/etc/cth/runtime.env"):
            self.assertIn(value, web)
        self.assertIn("listen 0.0.0.0:443 ssl;", templates["ingress.conf"])
        self.assertIn("proxy_pass http://127.0.0.1:8000;", templates["ingress.conf"])

    def test_proxy_mode_peer_identity_and_local_readiness(self):
        cfg = dict(self.cfg, ingress_mode="cloudflare-proxy")
        config = runtime.template("ingress.conf", cfg).decode()
        for rule in ("listen 0.0.0.0:443 ssl;", "geo $realip_remote_addr $peer",
                     "default other;", "default 0;", "local:/health 1;", "local:/health/status 1;",
                     "if ($allowed = 0) { return 403; }", "proxy_set_header X-CF-Edge-IP $realip_remote_addr;",
                     'if ($ssl_server_name != "hub.example.org")', 'if ($host != "hub.example.org")'):
            self.assertIn(rule, config)
        for net in runtime.EDGE_IPV4:
            self.assertIn(f"set_real_ip_from {net};", config)
            self.assertIn(f"{net} edge;", config)
        self.assertNotIn("set_real_ip_from 0.0.0.0/0", config)
        with patch.object(runtime, "command", return_value="LISTEN 0 20 0.0.0.0:443 *:*"):
            runtime.inspect_ingress(cfg)
        with patch.object(runtime, "curl", return_value="bad") as curl, self.assertRaises(ValueError):
            runtime.local_health(cfg, tls=True)
        self.assertIn("hub.example.org:443:127.0.0.1:443", curl.call_args.args)

    def test_ownership_and_gate_failures(self):
        with patch.object(runtime, "command", return_value="0"):
            with self.assertRaisesRegex(ValueError, "one scheduler"):
                runtime.scheduler(self.cfg)
        with patch.object(runtime, "command", side_effect=("1", "a" * 32,
                "Scheduler started in pid 123: this process holds the scheduler lock.")) as command:
            runtime.scheduler(self.cfg)
        self.assertIn("--reverse", command.call_args.args)
        with patch.object(runtime, "command", return_value="LISTEN 0 20 0.0.0.0:8000 *:*"):
            with self.assertRaisesRegex(ValueError, "127.0.0.1"):
                runtime.inspect_listeners(8000)

    def test_startup_retry_only_before_failure_or_deadline(self):
        from unittest.mock import Mock
        check = Mock(side_effect=[ValueError("not ready"), True])
        with patch.object(runtime, "command", return_value="active"), patch.object(runtime.time, "sleep"):
            self.assertTrue(runtime.await_start("unit", check))
        with patch.object(runtime, "command", return_value="failed"), self.assertRaisesRegex(ValueError, "failed probe"):
            runtime.await_start("unit", Mock(side_effect=ValueError("failed probe")))


if __name__ == "__main__":
    unittest.main()

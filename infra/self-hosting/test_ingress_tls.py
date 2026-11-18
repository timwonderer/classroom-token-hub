"""Real Nginx peer, hostname and local-health regression. Requires nginx, openssl and curl."""
import http.server
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import runtime


class Backend(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.hits += 1
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"application reached")

    def log_message(self, *args):
        pass


@unittest.skipUnless(all(shutil.which(tool) for tool in ("nginx", "openssl", "curl")),
                     "requires nginx, openssl and curl")
class OriginIngressTests(unittest.TestCase):
    def test_cloudflare_peer_and_local_health_without_client_certificates(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)

            def openssl(*args):
                subprocess.run(["openssl", *map(str, args)], check=True, capture_output=True)

            openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=hub.example.org", "-addext", "subjectAltName=DNS:hub.example.org",
                    "-keyout", directory / "server.key", "-out", directory / "server.crt")
            cfg = dict(hostname="hub.example.org", installation_id="offline", release_sha="1" * 40,
                       runtime_env="unused", tls_cert=str(directory / "server.crt"),
                       tls_key=str(directory / "server.key"), ingress_mode="cloudflare-proxy")
            with http.server.HTTPServer(("127.0.0.1", 0), Backend) as backend:
                backend.hits = 0
                worker = threading.Thread(target=backend.serve_forever)
                worker.start()
                try:
                    for peer in ("edge", "local", "other"):
                        with self.subTest(peer=peer):
                            self.exercise_origin(directory, cfg, backend, peer)
                finally:
                    backend.shutdown()
                    worker.join()

    def exercise_origin(self, directory, cfg, backend, peer):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        # Simulate a shared Cloudflare peer using loopback; preserve the generated peer rules.
        networks = ("127.0.0.1/32",) if peer == "edge" else runtime.EDGE_IPV4
        with patch.object(runtime, "EDGE_IPV4", networks):
            config = runtime.template("ingress.conf", cfg).decode()
        if peer != "local":
            config = config.replace("127.0.0.1 local;", "127.0.0.2 local;")
        config = (config.replace("user www-data;", "")
                  .replace("/run/cth-ingress", str(directory))
                  .replace("0.0.0.0:443", f"127.0.0.1:{port}")
                  .replace("127.0.0.1:8000", f"127.0.0.1:{backend.server_port}"))
        config_path = directory / "nginx.conf"
        config_path.write_text(config)
        with (directory / "stderr").open("w+") as errors:
            process = subprocess.Popen(["nginx", "-p", str(directory), "-c", str(config_path),
                                        "-e", str(directory / "error.log"), "-g", "daemon off;"],
                                       stderr=errors)
            try:
                for attempt in range(100):
                    self.assertIsNone(process.poll(), "Nginx exited during startup")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.02)
                else:
                    self.fail("Nginx did not start")

                def request(path, host="hub.example.org"):
                    args = ["curl", "-q", "-sS", "--noproxy", "*", "--max-time", "3",
                            "--cacert", cfg["tls_cert"], "--resolve", f"hub.example.org:{port}:127.0.0.1",
                            "-H", "Host: " + host, "-H", "CF-Connecting-IP: 192.0.2.1",
                            "-H", "X-CF-Edge-IP: 173.245.48.1", "-w", "|%{http_code}"]
                    result = subprocess.run([*args, f"https://hub.example.org:{port}{path}"],
                                            capture_output=True, text=True, timeout=5)
                    return result.stdout.rsplit("|", 1)[-1]

                before = backend.hits
                if peer == "edge":
                    self.assertEqual(request("/admin/login"), "200")
                    self.assertEqual(request("/health"), "200")
                    self.assertEqual(request("/admin/login", "other.example.org"), "000")
                    self.assertEqual(backend.hits, before + 2)
                else:
                    # Spoofed Cloudflare headers cannot change the original TCP peer.
                    self.assertEqual(request("/admin/login"), "403")
                    self.assertEqual(backend.hits, before)
                    self.assertEqual(request("/health"), "200" if peer == "local" else "403")
                    self.assertEqual(request("/health/status"), "200" if peer == "local" else "403")
                    self.assertEqual(request("/health/other"), "403")
            finally:
                process.terminate()
                process.wait(timeout=5)

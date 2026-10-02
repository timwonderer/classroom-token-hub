"""Stand-ins for Flask's auth-check and for Grafana, used by test_harness.sh.

auth  : 200 + X-Auth-User when the request carries the cookie
        ``session=sysadmin``, otherwise 401 -- the contract of
        sysadmin.grafana_auth_check.
grafana: 200 and a one-line echo of the path and X-WEBAUTH-USER it received.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AuthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        if "session=sysadmin" in (self.headers.get("Cookie") or ""):
            self.send_response(200)
            self.send_header("X-Auth-User", "sysadmin_stub")
        else:
            self.send_response(401)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class Grafana(BaseHTTPRequestHandler):
    def _echo(self):
        body = f"grafana {self.path} user={self.headers.get('X-WEBAUTH-USER')}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _echo

    def log_message(self, *args):
        pass


def main():
    auth_port, grafana_port = int(sys.argv[1]), int(sys.argv[2])
    servers = [
        ThreadingHTTPServer(("127.0.0.1", auth_port), AuthCheck),
        ThreadingHTTPServer(("127.0.0.1", grafana_port), Grafana),
    ]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()


if __name__ == "__main__":
    main()

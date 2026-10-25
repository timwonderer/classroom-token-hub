"""Serve the unpublished artifact on loopback only. Stop with Ctrl-C."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        return super().translate_path(path.removeprefix('/docs'))

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    cache = Path(__file__).resolve().parent / '.cache'
    servers = []
    try:
        for label, port, site in [('Hugo + Hextra', 8766, cache / 'hugo/public')]:
            if not (site / 'index.html').is_file():
                raise SystemExit(f'Build {label} first')
            server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=str(site)))
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            print(f'{label}: http://127.0.0.1:{port}/docs/', flush=True)
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()

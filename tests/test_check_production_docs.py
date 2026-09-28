"""scripts/check_production_docs.py against a simulated docs host.

Each case reproduces a behaviour the scheduled `production-docs-smoke` job met on
app.classroomtokenhub.com and misreported:

- 2026-09-27 (gate open): relative links resolved against the pre-redirect URL
  invented /docs/learnmore.html, /docs/student_guide.md and ~150 more URLs,
  then the crawl tripped the 200/hour limiter and logged 100+ 429s.
- 2026-09-28 (Cloudflare Access window): the start page redirected to the
  Access login on another host, was logged "OK [200]", and the job failed only
  on --min-urls with no word about why.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_production_docs",
    Path(__file__).resolve().parents[1] / "scripts" / "check_production_docs.py",
)
cpd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpd)

ROOT = "https://app.example.test"


def _page(*hrefs):
    return "".join(f'<a href="{h}">x</a>' for h in hrefs).encode()


class FakeSite:
    """Maps a requested URL to (status, final_url, body). Records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def __call__(self, url, timeout, headers):
        self.requests.append((url, headers))
        status, final, body = self.routes.get(url, (404, url, b""))
        return status, final, body, "text/html" if body else None


def _run(site, **kw):
    lines = []
    reached, failures = cpd.crawl(ROOT, "/docs/", max_urls=kw.pop("max_urls", 100), timeout=1,
                                  fetcher=site, log=lines.append, **kw)
    return reached, failures, lines


def test_relative_links_resolve_against_the_post_redirect_url():
    """/docs/guides 301s to /docs/guides/; its `a.md` is /docs/guides/a.md, not /docs/a.md."""
    site = FakeSite({
        f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page("/docs/guides")),
        f"{ROOT}/docs/guides": (200, f"{ROOT}/docs/guides/", _page("a.md", "b.md")),
        f"{ROOT}/docs/guides/a.md": (200, f"{ROOT}/docs/guides/a.md", _page()),
        f"{ROOT}/docs/guides/b.md": (200, f"{ROOT}/docs/guides/b.md", _page()),
    })
    reached, failures, lines = _run(site)
    assert failures == 0, lines
    assert reached == 4
    requested = [u for u, _ in site.requests]
    assert f"{ROOT}/docs/a.md" not in requested


def test_off_site_redirect_is_not_crawled_with_the_wrong_base():
    """/docs/timeline 302s to the public site; its relative links are not /docs/*.html."""
    site = FakeSite({
        f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page("/docs/timeline")),
        f"{ROOT}/docs/timeline": (200, "https://public.example.test/timeline.html",
                                  _page("learnmore.html", "terms.html")),
    })
    reached, failures, lines = _run(site)
    assert failures == 0, lines
    assert [u for u, _ in site.requests] == [f"{ROOT}/docs/", f"{ROOT}/docs/timeline"]
    assert any("off-site; not crawled" in line for line in lines)


def test_variants_of_one_page_are_fetched_once():
    site = FakeSite({
        f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page(
            "/docs/g/a", "/docs/g/a.md", "/docs/g/", "/docs/g/index", "/docs/g/index.md", "/docs/g/README.md")),
        f"{ROOT}/docs/g/a": (200, f"{ROOT}/docs/g/a", _page()),
        f"{ROOT}/docs/g/": (200, f"{ROOT}/docs/g/", _page()),
    })
    reached, failures, _ = _run(site)
    assert failures == 0
    assert len(site.requests) == reached == 3


def test_page_key_collapses_only_same_file_variants():
    key = cpd.page_key
    assert key(f"{ROOT}/docs/g/a") == key(f"{ROOT}/docs/g/a.md")
    assert key(f"{ROOT}/docs/g") == key(f"{ROOT}/docs/g/") == key(f"{ROOT}/docs/g/index.md") == key(f"{ROOT}/docs/g/README")
    assert key(f"{ROOT}/docs/g/a") != key(f"{ROOT}/docs/g/b")
    assert key(f"{ROOT}/docs/g/indexer") != key(f"{ROOT}/docs/g")


def test_rate_limit_stops_the_crawl_with_one_failure():
    site = FakeSite({
        f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page("/docs/a", "/docs/b", "/docs/c")),
        f"{ROOT}/docs/a": (429, f"{ROOT}/docs/a", b""),
    })
    _, failures, lines = _run(site)
    assert failures == 1
    assert len(site.requests) == 2
    assert "rate limited" in lines[-1]


def test_start_page_redirected_off_host_is_a_named_failure():
    """The Access login answers 200 on another host; that is not the docs rendering."""
    site = FakeSite({
        f"{ROOT}/docs/": (200, "https://team.cloudflareaccess.com/cdn-cgi/access/login/app", _page("/x")),
    })
    reached, failures, lines = _run(site)
    assert (reached, failures) == (0, 1)
    assert "redirected off-host to https://team.cloudflareaccess.com" in lines[-1]
    assert "Cloudflare Access" in lines[-1]


def test_min_urls_floor_still_fails_a_crawl_that_found_nothing(monkeypatch):
    site = FakeSite({f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page())})
    monkeypatch.setattr(cpd, "fetch", site)
    assert cpd.main(["--base-url", ROOT, "--crawl", "--min-urls", "2"]) == 1


def test_http_errors_are_counted():
    site = FakeSite({f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page("/docs/missing"))})
    _, failures, lines = _run(site)
    assert failures == 1
    assert lines[-1].startswith("FAIL [404]")


def test_access_service_token_headers_are_sent_only_when_both_are_set():
    assert cpd.access_headers({}) == {}
    assert cpd.access_headers({"CF_ACCESS_CLIENT_ID": "id"}) == {}
    headers = cpd.access_headers({"CF_ACCESS_CLIENT_ID": "id", "CF_ACCESS_CLIENT_SECRET": "s"})
    assert headers == {"CF-Access-Client-Id": "id", "CF-Access-Client-Secret": "s"}
    site = FakeSite({f"{ROOT}/docs/": (200, f"{ROOT}/docs/", _page())})
    _run(site, headers=headers)
    assert site.requests[0][1] == headers


def test_fetch_follows_same_host_redirects_and_stops_at_cross_host_ones():
    """The other host is never contacted, so it never sees the Access service token."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.headers.get("Host"), self.path, self.headers.get("CF-Access-Client-Id")))
            routes = {
                "/docs/dir": (301, "/docs/dir/"),
                "/docs/away": (302, "http://elsewhere.invalid/timeline.html"),
            }
            if self.path in routes:
                code, location = routes[self.path]
                self.send_response(code)
                self.send_header("Location", location)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<a href='x.md'>x</a>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    token = {"CF-Access-Client-Id": "id", "CF-Access-Client-Secret": "s"}
    try:
        status, final, body, ctype = cpd.fetch(f"{base}/docs/dir", 5, token)
        assert (status, final, ctype) == (200, f"{base}/docs/dir/", "text/html")
        assert b"x.md" in body

        status, final, body, _ = cpd.fetch(f"{base}/docs/away", 5, token)
        assert (status, final, body) == (302, "http://elsewhere.invalid/timeline.html", b"")
    finally:
        server.shutdown()
    assert all(host.startswith("127.0.0.1") for host, _, _ in hits)
    assert [path for _, path, _ in hits] == ["/docs/dir", "/docs/dir/", "/docs/away"]

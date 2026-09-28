#!/usr/bin/env python3
"""Bounded smoke-check of the rendered production documentation surface.

The offline checkers verify that links resolve in the repository. This verifies
that the docs actually *render* in production, which is a different claim: the
docs route is audience-gated and template-driven, so a page can be present as a
file and still 404 or 500 when served.

It walks only same-host URLs under the start path, stops at `--max-urls`, and
sleeps `--delay` seconds between requests. Those bounds exist because this is
the one check in the suite that generates load on the live service.

Three properties of the live service shape the crawl:

- Redirects. Directory-style help pages 301 to a trailing-slash URL, and some
  paths (e.g. `/docs/timeline`) 302 to the public site. Relative links on a page
  are resolved against the URL the page was finally served from, not the one
  requested; resolving against the requested URL lands every relative link one
  level too high and invents hundreds of URLs that never existed.
- The rate limiter (200 requests/hour per client by default). The same page is
  linked as `x`, `x.md`, `x/` and `x/index`; they render one file, so the crawl
  fetches one of them. A 429 ends the crawl: every later request would also be
  refused, and a list of refusals says nothing about the docs.
- Cloudflare Access. During a maintenance window the host answers with a
  redirect to the Access login page on another host. That is reported as a
  failure naming the destination, rather than as a 200 with nothing to crawl.
  Set CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET (an Access service token)
  to crawl through the gate.
"""
from __future__ import annotations
import argparse
import os
import re
import time
from collections import deque
from html.parser import HTMLParser
from urllib import error, request
from urllib.parse import urldefrag, urljoin, urlparse

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for name, value in attrs if name == "href" and value)

_PAGE_SUFFIX = re.compile(r"(?:/(?:index|readme))?(?:\.md)?/?$", re.IGNORECASE)

def page_key(url):
    """One key per rendered file: `x`, `x.md`, `x/`, `x/index` and `x/index.md` collide."""
    parsed = urlparse(url)
    path = _PAGE_SUFFIX.sub("", parsed.path) or "/"
    return f"{parsed.netloc}{path}"

def access_headers(environ=os.environ):
    client_id, secret = environ.get("CF_ACCESS_CLIENT_ID"), environ.get("CF_ACCESS_CLIENT_SECRET")
    if client_id and secret:
        return {"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": secret}
    return {}

class _SameHostRedirects(request.HTTPRedirectHandler):
    """Follow redirects within a host; stop at one that leaves it.

    The check is about this host. A hand-off to another host (the public site,
    or the Access login during a maintenance window) is judged by the redirect
    itself, so the other host is never fetched and the service token is never
    sent to it.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).netloc != urlparse(req.full_url).netloc:
            return None  # urllib then raises HTTPError carrying the 3xx
        return super().redirect_request(req, fp, code, msg, headers, newurl)

_opener = request.build_opener(_SameHostRedirects)

def fetch(url, timeout, headers):
    """Return (status, final_url, body, content_type). final_url is after same-host redirects."""
    req = request.Request(url, headers={"User-Agent": "cth-docs-smoke/1.0", **headers})
    try:
        with _opener.open(req, timeout=timeout) as response:
            return response.status, response.geturl(), response.read(1_000_001), response.headers.get_content_type()
    except error.HTTPError as exc:
        location = exc.headers.get("Location") if 300 <= exc.code < 400 and exc.headers else None
        return exc.code, urljoin(exc.geturl() or url, location) if location else (exc.geturl() or url), b"", None
    except error.URLError:
        return None, url, b"", None

def crawl(root, start_path, *, max_urls, timeout, delay=0.0, follow=True, headers=None, fetcher=fetch, log=print):
    """Walk the docs surface. Returns (pages_reached, failures)."""
    headers = headers or {}
    host = urlparse(root).netloc
    start = urljoin(root + "/", start_path.lstrip("/"))
    queue, seen, reached, failures = deque([start]), set(), 0, 0
    while queue and reached < max_urls:
        url = urldefrag(queue.popleft()).url
        key = page_key(url)
        if key in seen:
            continue
        seen.add(key)
        if delay and reached:
            time.sleep(delay)
        reached += 1
        status, final_url, body, content_type = fetcher(url, timeout, headers)
        if status == 429:
            failures += 1
            log(f"FAIL [429] {url}: rate limited by production; stopping after {reached} request(s)")
            break
        if status is None or not 200 <= status < 400:
            failures += 1
            log(f"FAIL [{status or 'ERR'}] {url}")
            continue
        final = urlparse(final_url)
        if final.netloc != host:
            if url == start:
                failures += 1
                reached -= 1  # the docs were never reached; the gate was
                log(f"FAIL [{status}] {url}: redirected off-host to {final.scheme}://{final.netloc}{final.path}"
                    " (Cloudflare Access gate? set CF_ACCESS_CLIENT_ID/CF_ACCESS_CLIENT_SECRET)")
                break
            log(f"OK   [{status}] {url} -> {final_url} (off-site; not crawled)")
            continue
        seen.add(page_key(final_url))
        log(f"OK   [{status}] {url}" + (f" -> {final_url}" if final_url != url else ""))
        if not follow or content_type != "text/html":
            continue
        parser = LinkParser(); parser.feed(body.decode("utf-8", errors="replace"))
        for link in parser.links:
            candidate = urldefrag(urljoin(final_url, link)).url
            parsed = urlparse(candidate)
            if parsed.scheme in {"http", "https"} and parsed.netloc == host and parsed.path.startswith("/docs/") and page_key(candidate) not in seen:
                queue.append(candidate)
    if queue and reached >= max_urls:
        log(f"NOTE stopped at --max-urls {max_urls} with {len(queue)} link(s) still queued")
    return reached, failures

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--start-path", default="/docs/")
    parser.add_argument("--max-urls", type=int, default=300)
    parser.add_argument("--timeout", type=float, default=20.0)
    # `--crawl` and `--delay` are passed by .github/workflows/docs-links.yml.
    # They were absent here, so argparse would have exited 2 with "unrecognized
    # arguments" on every scheduled run — a gate that fails for a reason
    # unrelated to the thing it checks tells you nothing about production.
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Follow same-host links under the start path. Without it, only the start page is fetched.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to sleep between requests, to stay polite against the live service.",
    )
    # A crawl that reaches one page and finds no links reports success, which is
    # indistinguishable from a docs surface that renders correctly. Stating the
    # floor turns "found nothing" into a failure instead of a pass.
    parser.add_argument(
        "--min-urls",
        type=int,
        default=1,
        help="Fail if fewer than this many URLs were reached.",
    )
    args = parser.parse_args(argv)
    reached, failures = crawl(
        args.base_url.rstrip("/"), args.start_path,
        max_urls=args.max_urls, timeout=args.timeout, delay=args.delay,
        follow=args.crawl, headers=access_headers(), fetcher=fetch,
    )
    print(f"Checked {reached} production documentation page(s)")
    if reached < args.min_urls:
        print(f"FAIL reached {reached} page(s), expected at least {args.min_urls}")
        failures += 1
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())

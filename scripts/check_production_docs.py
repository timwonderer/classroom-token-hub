#!/usr/bin/env python3
"""Bounded smoke-check of the rendered production documentation surface.

The offline checkers verify that links resolve in the repository. This verifies
that the docs actually *render* in production, which is a different claim: the
docs route is audience-gated and template-driven, so a page can be present as a
file and still 404 or 500 when served.

It walks only same-host URLs under the start path, stops at `--max-urls`, and
sleeps `--delay` seconds between requests. Those bounds exist because this is
the one check in the suite that generates load on the live service.
"""
from __future__ import annotations
import argparse
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

def main():
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
    args = parser.parse_args()
    root = args.base_url.rstrip("/")
    host = urlparse(root).netloc
    queue, visited = deque([urljoin(root + "/", args.start_path.lstrip("/"))]), set()
    failures = 0
    while queue and len(visited) < args.max_urls:
        url = urldefrag(queue.popleft()).url
        if url in visited:
            continue
        visited.add(url)
        if args.delay and len(visited) > 1:
            time.sleep(args.delay)
        try:
            with request.urlopen(request.Request(url, headers={"User-Agent": "cth-docs-smoke/1.0"}), timeout=args.timeout) as response:
                status, body, content_type = response.status, response.read(1_000_001), response.headers.get_content_type()
        except (error.HTTPError, error.URLError) as exc:
            status, body, content_type = getattr(exc, "code", None), b"", None
        if status is None or not 200 <= status < 400:
            failures += 1
            print(f"FAIL [{status or 'ERR'}] {url}")
            continue
        print(f"OK   [{status}] {url}")
        if not args.crawl or content_type != "text/html":
            continue
        parser = LinkParser(); parser.feed(body.decode("utf-8", errors="replace"))
        for link in parser.links:
            candidate = urldefrag(urljoin(url, link)).url
            parsed = urlparse(candidate)
            if parsed.scheme in {"http", "https"} and parsed.netloc == host and parsed.path.startswith("/docs/") and candidate not in visited:
                queue.append(candidate)
    print(f"Checked {len(visited)} production documentation URL(s)")
    if len(visited) < args.min_urls:
        print(f"FAIL reached {len(visited)} URL(s), expected at least {args.min_urls}")
        failures += 1
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())

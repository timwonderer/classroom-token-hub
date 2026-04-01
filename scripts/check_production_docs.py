#!/usr/bin/env python3
"""Smoke-test documentation URLs, either from a curated manifest or by crawling docs."""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib import error, request
from urllib.parse import urljoin, urlparse, urlunparse


DEFAULT_HEADERS = {
    "User-Agent": "classroom-economy-docs-smoke/1.0",
}


class DocsLinkParser(HTMLParser):
    """Collect anchor href values from a rendered HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for attr_name, attr_value in attrs:
            if attr_name == "href" and attr_value:
                self.links.append(attr_value)
                break


def load_manifest(path: Path) -> list[str]:
    """Load newline-delimited URL paths, ignoring blank lines and comments."""
    paths: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        paths.append(candidate)
    return paths


def fetch_url(url: str, timeout: float) -> tuple[bool, int | None, str, str]:
    """Fetch a URL and return (ok, status_code, detail, response_text)."""
    req = request.Request(url, headers=DEFAULT_HEADERS, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            body = response.read().decode("utf-8", errors="replace")
            if 200 <= status < 400:
                return True, status, "OK", body
            return False, status, f"Unexpected status {status}", body
    except error.HTTPError as exc:
        detail = exc.reason or f"HTTP {exc.code}"
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return False, exc.code, detail, body
    except error.URLError as exc:
        return False, None, str(exc.reason), ""


def is_docs_url(url: str, docs_root: str) -> bool:
    """Return True when a URL stays on the same docs subtree."""
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc == urlparse(docs_root).netloc
        and parsed.path.startswith(urlparse(docs_root).path)
    )


def normalize_docs_url(candidate: str, source_url: str, docs_root: str) -> str | None:
    """Normalize an internal docs URL for de-duplication and safe crawling."""
    absolute = urljoin(source_url, candidate)
    parsed = urlparse(absolute)

    if not is_docs_url(absolute, docs_root):
        return None

    if parsed.path.startswith(f"{urlparse(docs_root).path}search"):
        return None

    if parsed.scheme not in {"http", "https"}:
        return None

    normalized = parsed._replace(fragment="")

    # Query-driven pages can create an unbounded crawl surface; only keep
    # documentation audience toggles, which redirect back into docs.
    if normalized.query and not normalized.path.endswith("/set-audience"):
        normalized = normalized._replace(query="")

    return urlunparse(normalized)


def run_checks(base_url: str, paths: Iterable[str], timeout: float, delay: float) -> int:
    """Check each manifest path in sequence to avoid rate limiting."""
    failures = 0
    checked = 0
    for path in paths:
        url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
        ok, status, detail, _ = fetch_url(url, timeout=timeout)
        checked += 1
        if ok:
            print(f"OK   [{status}] {url}")
        else:
            failures += 1
            code = status if status is not None else "ERR"
            print(f"FAIL [{code}] {url} :: {detail}")
        if delay > 0:
            time.sleep(delay)

    print(f"\nChecked {checked} production docs URL(s)")
    if failures:
        print(f"Found {failures} failing URL(s)")
        return 1
    print("All production docs smoke checks passed")
    return 0


def run_crawl(base_url: str, start_path: str, timeout: float, delay: float, max_urls: int) -> int:
    """Crawl same-origin docs links sequentially to avoid rate limiting."""
    docs_root = urljoin(base_url.rstrip("/") + "/", "docs/")
    start_url = normalize_docs_url(start_path, docs_root, docs_root)
    if start_url is None:
        print(f"Invalid crawl start path: {start_path}", file=sys.stderr)
        return 2

    queue: deque[str] = deque([start_url])
    visited: set[str] = set()
    failures = 0

    while queue:
        if len(visited) >= max_urls:
            print(f"Stopped after reaching max URL limit of {max_urls}")
            break

        url = queue.popleft()
        if url in visited:
            continue

        ok, status, detail, body = fetch_url(url, timeout=timeout)
        visited.add(url)

        if ok:
            print(f"OK   [{status}] {url}")
            parser = DocsLinkParser()
            parser.feed(body)
            for href in parser.links:
                normalized = normalize_docs_url(href, url, docs_root)
                if normalized and normalized not in visited and normalized not in queue:
                    queue.append(normalized)
        else:
            failures += 1
            code = status if status is not None else "ERR"
            print(f"FAIL [{code}] {url} :: {detail}")

        if delay > 0 and queue:
            time.sleep(delay)

    print(f"\nCrawled {len(visited)} docs URL(s)")
    if failures:
        print(f"Found {failures} failing URL(s)")
        return 1
    print("All crawled docs URLs passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="https://app.classroomtokenhub.com",
        help="Base site URL to prepend to manifest paths",
    )
    parser.add_argument(
        "--manifest",
        default="docs/production-docs-manifest.txt",
        help="Path to newline-delimited manifest of docs paths",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds",
    )
    parser.add_argument(
        "--crawl",
        action="store_true",
        help="Crawl same-origin docs links starting from --start-path instead of using a manifest",
    )
    parser.add_argument(
        "--start-path",
        default="/docs/",
        help="Initial docs path to crawl when --crawl is set",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=1000,
        help="Maximum number of docs URLs to crawl before stopping",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.crawl:
        return run_crawl(
            base_url=args.base_url,
            start_path=args.start_path,
            timeout=args.timeout,
            delay=args.delay,
            max_urls=args.max_urls,
        )

    manifest = Path(args.manifest)
    if not manifest.exists():
        print(f"Manifest not found: {manifest}", file=sys.stderr)
        return 2

    paths = load_manifest(manifest)
    if not paths:
        print(f"Manifest is empty: {manifest}", file=sys.stderr)
        return 2

    return run_checks(
        base_url=args.base_url,
        paths=paths,
        timeout=args.timeout,
        delay=args.delay,
    )


if __name__ == "__main__":
    raise SystemExit(main())

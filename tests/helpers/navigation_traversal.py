import urllib.parse
from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional, Callable
from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from sqlalchemy import event
from app import db


@dataclass
class DiagnosticReport:
    originating_url: str
    clicked_href: str
    status_code: int
    exception_traceback: Optional[str] = None
    redirect_chain: List[str] = field(default_factory=list)

    def to_string(self) -> str:
        parts = [
            f"Origin: {self.originating_url}",
            f"Clicked: {self.clicked_href}",
            f"Status: {self.status_code}",
        ]
        if self.redirect_chain:
            parts.append(f"Redirect Chain: {' -> '.join(self.redirect_chain)}")
        if self.exception_traceback:
            parts.append(f"Exception: {self.exception_traceback}")
        return "\n".join(parts)


@dataclass
class TraversalSummary:
    total_visited: int = 0
    total_skipped: int = 0
    max_depth_reached: int = 0
    redirect_anomalies: int = 0
    mutation_violations: int = 0
    total_failures: int = 0


class NavigationTester:
    def __init__(
        self,
        client: FlaskClient,
        max_depth: int = 3,
        allowlist: Optional[List[str]] = None,
        blocklist: Optional[List[str]] = None,
        preserve_query_params: Optional[List[str]] = None,
    ):
        self.client = client
        self.max_depth = max_depth
        self.allowlist = allowlist or []
        self.blocklist = blocklist or [
            "/logout",
            "/download",
            "/api/",
            "/export",
        ]
        self.preserve_query_params = preserve_query_params or []
        self.visited_urls: Set[str] = set()
        self.summary = TraversalSummary()

    def _setup_mutation_detection(self):
        """Enforces INV-ARC-007 (No write-on-read). Tracks INSERT/UPDATE/DELETE."""
        self._mutation_listener = lambda session, flush_context, instances: self._check_mutations(session)
        event.listen(db.session, 'before_flush', self._mutation_listener)

    def _teardown_mutation_detection(self):
        event.remove(db.session, 'before_flush', self._mutation_listener)

    def _check_mutations(self, session):
        if session.new or session.deleted or session.dirty:
            self.summary.mutation_violations += 1
            new_items = [repr(item) for item in session.new]
            deleted_items = [repr(item) for item in session.deleted]
            dirty_items = [repr(item) for item in session.dirty]
            
            msg_parts = []
            if new_items: msg_parts.append(f"New: {new_items}")
            if deleted_items: msg_parts.append(f"Deleted: {deleted_items}")
            if dirty_items: msg_parts.append(f"Dirty: {dirty_items}")
            
            raise RuntimeError(f"No-Write-On-Read Violation (INV-ARC-007): GET request attempted to mutate database state!\n" + "\n".join(msg_parts))

    def canonicalize_url(self, url: str) -> str:
        """Strips fragments, normalizes trailing slashes, and conditionally preserves query params."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
            
        if self.preserve_query_params and parsed.query:
            qs = urllib.parse.parse_qs(parsed.query)
            preserved_qs = {k: v for k, v in qs.items() if k in self.preserve_query_params}
            if preserved_qs:
                encoded_qs = urllib.parse.urlencode(preserved_qs, doseq=True)
                return f"{path}?{encoded_qs}"
                
        return path

    def is_allowed(self, url: str) -> bool:
        """Determines if a URL should be traversed."""
        if url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:") or url.startswith("javascript:"):
            self.summary.total_skipped += 1
            return False

        path = urllib.parse.urlparse(url).path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        
        for blocked in self.blocklist:
            if path.startswith(blocked) or path == blocked:
                self.summary.total_skipped += 1
                return False
                
        if self.allowlist:
            allowed = False
            for allowed_prefix in self.allowlist:
                if path.startswith(allowed_prefix) or path == allowed_prefix:
                    allowed = True
                    break
            if not allowed:
                self.summary.total_skipped += 1
                return False

        return True

    def traverse(self, start_url: str):
        """Begin scoped integrity traversal from start_url."""
        self.summary = TraversalSummary()
        self.visited_urls.clear()
        
        try:
            self._setup_mutation_detection()
            self._traverse_recursive(start_url, "INITIAL_ENTRY_POINT", 0)
        finally:
            self._teardown_mutation_detection()
            self._print_summary()

    def _print_summary(self):
        print("\n--- Scoped Integrity Traversal Summary ---")
        print(f"Total Visited Routes: {self.summary.total_visited}")
        print(f"Total Skipped Routes: {self.summary.total_skipped}")
        print(f"Max Depth Reached:    {self.summary.max_depth_reached}")
        print(f"Redirect Anomalies:   {self.summary.redirect_anomalies}")
        print(f"Mutation Violations:  {self.summary.mutation_violations}")
        print(f"Total Failures:       {self.summary.total_failures}")
        print("------------------------------------------\n")

    def _traverse_recursive(self, url: str, origin: str, depth: int):
        if depth > self.max_depth:
            return

        self.summary.max_depth_reached = max(self.summary.max_depth_reached, depth)

        canonical_url = self.canonicalize_url(url)
        if canonical_url in self.visited_urls:
            return
            
        self.visited_urls.add(canonical_url)
        self.summary.total_visited += 1

        redirect_chain = []
        current_url = url
        
        try:
            response = self.client.get(current_url, follow_redirects=False)
            
            redirect_depth = 0
            while response.status_code in (301, 302, 303, 307, 308):
                redirect_depth += 1
                if redirect_depth > 10:
                    self.summary.redirect_anomalies += 1
                    self.summary.total_failures += 1
                    report = DiagnosticReport(
                        originating_url=origin,
                        clicked_href=url,
                        status_code=response.status_code,
                        exception_traceback="Redirect loop detected",
                        redirect_chain=redirect_chain
                    )
                    raise AssertionError(f"Redirect Integrity Violation:\n{report.to_string()}")
                    
                target = response.headers.get("Location")
                redirect_chain.append(target)
                current_url = target
                
                response = self.client.get(current_url, follow_redirects=False)

            if response.status_code >= 400:
                self.summary.total_failures += 1
                report = DiagnosticReport(
                    originating_url=origin,
                    clicked_href=url,
                    status_code=response.status_code,
                    exception_traceback=f"HTTP {response.status_code} returned",
                    redirect_chain=redirect_chain
                )
                raise AssertionError(f"Navigation Integrity Violation:\n{report.to_string()}")

        except Exception as e:
            if isinstance(e, AssertionError):
                raise e 
            
            self.summary.total_failures += 1
            import traceback
            tb = traceback.format_exc()
            report = DiagnosticReport(
                originating_url=origin,
                clicked_href=url,
                status_code=500,
                exception_traceback=tb,
                redirect_chain=redirect_chain
            )
            raise AssertionError(f"Navigation Integrity Violation:\n{report.to_string()}")

        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            soup = BeautifulSoup(response.data, "html.parser")
            
            # Extract all hrefs, sort deterministically, and traverse
            hrefs = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if self.is_allowed(href):
                    hrefs.append(href)
                    
            # Preserve determinism
            for href in sorted(list(set(hrefs))):
                self._traverse_recursive(href, current_url, depth + 1)

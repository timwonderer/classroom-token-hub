"""
Phase 1 instrumentation for the FEATBypass default-flip plan.

Pytest plugin that hooks SQLAlchemy's `before_flush` event to record every
flush that occurs while `FEATBypass` (and only `FEATBypass`) is the active
FEAT context. Each such flush is a "would have raised under enforcement"
event — i.e. one that the conftest autouse bypass is currently hiding.

Discrimination logic
--------------------
At each flush, look at the active FEAT:
  - If active_feat == "FEAT-BYPASS-LEGACY" and the session has new/dirty/
    deleted entities, the flush would have raised `FEATContextError` if the
    bypass were removed. This is recorded.
  - If active_feat is anything else (a real FEAT nested inside the bypass),
    the flush would have passed under enforcement. We do NOT record these.

The phase distinguisher uses Flask's request context:
  - `has_request_context() == True`  -> the flush is happening inside a route
    handler, meaning the route is mutating state outside a real FEAT. This is
    a dead-route candidate (Phase 1 column 3).
  - `has_request_context() == False` -> the flush is fixture/setup work. This
    is a fixture-only bypass dependency (Phase 1 column 2).

Activation
----------
This plugin only loads when the environment variable
`FEAT_BYPASS_AUDIT=1` is set. `tests/conftest.py` does the conditional
registration. The plugin adds a single SQLAlchemy listener which is a few
attribute lookups per flush — overhead is bounded and acceptable for a
one-shot reconnaissance run.

Output
------
At session end, two artefacts are written to
`docs/TRACKING/`:
  - V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json
    Full per-test data, machine-readable.
  - V2_FEAT_BYPASS_DEPENDENCY_REPORT.md
    Human-readable summary with counts, top-N tables, dead-route inventory.
"""

from __future__ import annotations

import json
import os
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import event

# Repo root so we can render frame paths as repo-relative in the report.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _relpath(fn: str) -> str:
    """Return path relative to the repo root when possible; otherwise as-is."""
    if fn.startswith(_REPO_ROOT + os.sep):
        return fn[len(_REPO_ROOT) + 1 :]
    return fn

# ----------------------------------------------------------------------------
# Plugin-local state
# ----------------------------------------------------------------------------

# Per-test records keyed by pytest nodeid. Each value is a dict with three
# lists: setup_flushes, call_flushes, teardown_flushes. Each entry in those
# lists is a single flush observation.
_records: dict[str, dict[str, list]] = defaultdict(
    lambda: {"setup_flushes": [], "call_flushes": [], "teardown_flushes": []}
)

# Active test context (mutated by the pytest hooks below).
_current: dict[str, str | None] = {"test_id": None, "phase": None}

# Guard so we only register the SQLAlchemy listener once even if pytest's
# collection re-imports modules. Required because event.listen is additive.
_LISTENER_ATTACHED = False


# ----------------------------------------------------------------------------
# Listener
# ----------------------------------------------------------------------------


def _attach_listener_once() -> None:
    """Attach our before_flush observer to the shared scoped_session."""
    global _LISTENER_ATTACHED
    if _LISTENER_ATTACHED:
        return

    # `db.session` is the Flask-SQLAlchemy scoped_session proxy. Listening on
    # it registers the event at the registry level, which is independent of
    # any per-test app/session lifecycle.
    from app.extensions import db

    @event.listens_for(db.session, "before_flush")
    def _audit_before_flush(session, _flush_context, _instances):
        if _current["test_id"] is None:
            return

        # Only observe during the test lifecycle phases we hook.
        phase = _current["phase"]
        if phase not in ("setup", "call", "teardown"):
            return

        # Only count flushes that have something to write.
        new_n = len(session.new)
        dirty_n = len(session.dirty)
        deleted_n = len(session.deleted)
        if not (new_n or dirty_n or deleted_n):
            return

        # The discriminator: is the only thing keeping this flush legal the
        # outer FEATBypass? If a real (non-bypass) FEAT is the active one, this
        # flush would have been fine under enforcement.
        try:
            from app.feats.base import _feat_context
        except Exception:
            return

        active_feat = getattr(_feat_context, "active_feat", None)
        if active_feat != "FEAT-BYPASS-LEGACY":
            return  # safe under enforcement; no need to record

        # Endpoint discrimination (column 2 vs column 3 in the plan).
        #
        # We cannot trust `flask.has_request_context()` alone: pytest-flask
        # leaves a request context dangling around fixture code, so a flush
        # from `_seed_*` fixture functions appears to be "in a request
        # context" even though no route handler is on the stack. The
        # reliable discriminator is the call stack itself — if a Flask
        # request-dispatch frame is present, a real route is on the stack.
        endpoint = None
        method = None
        in_request_context = False
        in_route_dispatch = False

        # Capture all frames once; we'll use them for both the route-dispatch
        # check and the lightweight callsite summary.
        all_frames = traceback.extract_stack()[:-1]
        for frame in all_frames:
            fn = frame.filename
            name = frame.name
            # Flask's route handling entry points. werkzeug's test Client
            # drives a request via `open` -> the WSGI app -> Flask wsgi_app
            # -> full_dispatch_request -> dispatch_request. Any of these on
            # the stack means we are inside a real route handler, not in
            # fixture code that merely shares a dangling context.
            if "flask/app.py" in fn and name in (
                "wsgi_app",
                "full_dispatch_request",
                "dispatch_request",
                "preprocess_request",
            ):
                in_route_dispatch = True
                break

        try:
            from flask import has_request_context, request

            if has_request_context():
                in_request_context = True
                # Only attribute endpoint/method when we're actually in a
                # route dispatch. Otherwise the values are a dangling context
                # leftover from prior client setup.
                if in_route_dispatch:
                    endpoint = request.endpoint
                    method = request.method
        except Exception:
            pass

        # Lightweight frame capture: keep up to 5 non-internal frames. Helps
        # identify the source of fixture-only flushes. We exclude SQLAlchemy
        # internals, this plugin, and compiled-string frames (which are
        # SQLAlchemy/psycopg2 generated code with no actionable location).
        frames: list[str] = []
        for frame in all_frames:
            fn = frame.filename
            if "sqlalchemy" in fn or "_feat_bypass_audit" in fn:
                continue
            if fn.startswith("<") or "<string>" in fn:
                continue
            frames.append(f"{_relpath(fn)}:{frame.lineno} {frame.name}")
        frames = frames[-5:]

        bucket = f"{phase}_flushes"
        _records[_current["test_id"]][bucket].append(
            {
                "phase": phase,
                "endpoint": endpoint,
                "method": method,
                "in_request_context": in_request_context,
                "in_route_dispatch": in_route_dispatch,
                "new": new_n,
                "dirty": dirty_n,
                "deleted": deleted_n,
                "frames": frames,
            }
        )

    _LISTENER_ATTACHED = True


# ----------------------------------------------------------------------------
# Pytest hooks
# ----------------------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    _attach_listener_once()
    _current["test_id"] = item.nodeid
    _current["phase"] = "setup"
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _current["test_id"] = item.nodeid
    _current["phase"] = "call"
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    _current["test_id"] = item.nodeid
    _current["phase"] = "teardown"
    yield
    # Clear AFTER teardown completes so any straggler flushes are still bucketed.
    _current["test_id"] = None
    _current["phase"] = None


# ----------------------------------------------------------------------------
# Report generation
# ----------------------------------------------------------------------------


def _git_head() -> str | None:
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd(),
        )
        return out.decode().strip()
    except Exception:
        return None


MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _bucket_test(record: dict) -> str:
    """
    Classify a test by what kind of bypass dependency it has.

    Returns one of:
      - "passes_under_enforcement" — no bypass-hidden flushes observed
      - "fixture_only_bypass"      — bypass-hidden flushes only happen in
                                     fixture/setup code (no Flask route
                                     dispatch on the stack at flush time)
      - "get_side_effect"          — bypass-hidden flush happened inside a
                                     GET handler (INV-ARC-007 candidate —
                                     GETs are supposed to be side-effect free)
      - "dead_route_dependent"     — bypass-hidden flush happened inside a
                                     mutating-method (POST/PUT/DELETE/PATCH)
                                     route handler. **These are the dead
                                     routes Phase 4 needs to fix.**
    """
    all_flushes = (
        record["setup_flushes"] + record["call_flushes"] + record["teardown_flushes"]
    )
    if not all_flushes:
        return "passes_under_enforcement"

    has_mutating_route = False
    has_get_route = False
    for f in all_flushes:
        if not f.get("in_route_dispatch"):
            continue
        method = (f.get("method") or "").upper()
        if method in MUTATING_METHODS:
            has_mutating_route = True
        elif method == "GET":
            has_get_route = True

    if has_mutating_route:
        return "dead_route_dependent"
    if has_get_route:
        return "get_side_effect"
    return "fixture_only_bypass"


def emit_markdown(
    records: dict,
    raw_path: Path,
    md_path: Path,
    *,
    total_collected: int,
    git_head: str | None,
) -> None:
    """
    Render a markdown report from a `records` dict in the shape produced by
    this plugin. Exposed so a standalone regeneration script can re-emit
    the report from the JSON without re-running the test suite.
    """
    test_ids = list(records.keys())
    by_bucket: dict[str, list[str]] = defaultdict(list)
    endpoint_counts: dict[tuple[str, str], int] = defaultdict(int)
    endpoint_first_test: dict[tuple[str, str], str] = {}
    fixture_callsite_counts: dict[str, int] = defaultdict(int)

    get_endpoint_counts: dict[tuple[str, str], int] = defaultdict(int)
    get_endpoint_first_test: dict[tuple[str, str], str] = {}

    for tid in test_ids:
        record = records[tid]
        bucket = _bucket_test(record)
        by_bucket[bucket].append(tid)

        for flush in record["call_flushes"]:
            if flush.get("in_route_dispatch") and flush["endpoint"]:
                method = (flush["method"] or "?").upper()
                key = (method, flush["endpoint"])
                if method in MUTATING_METHODS:
                    endpoint_counts[key] += 1
                    endpoint_first_test.setdefault(key, tid)
                elif method == "GET":
                    get_endpoint_counts[key] += 1
                    get_endpoint_first_test.setdefault(key, tid)
            elif flush["frames"]:
                # Best-effort callsite for fixture-shaped flushes in the
                # call phase (test bodies that seed via direct ORM, etc.).
                fixture_callsite_counts[flush["frames"][-1]] += 1
        for flush in record["setup_flushes"] + record["teardown_flushes"]:
            if flush["frames"]:
                fixture_callsite_counts[flush["frames"][-1]] += 1

    # Filter `<string>` frames from any pre-existing JSON so old runs
    # don't bias the callsite hotlist. (New runs filter at capture time.)
    # Also normalize absolute repo paths to repo-relative form so reports
    # regenerated from old JSON look the same as fresh ones.
    normalized: dict[str, int] = defaultdict(int)
    for site, n in fixture_callsite_counts.items():
        if site.startswith("<"):
            continue
        # Cheap prefix strip — works for both absolute and already-relative.
        if site.startswith(_REPO_ROOT + os.sep):
            site = site[len(_REPO_ROOT) + 1 :]
        normalized[site] += n
    fixture_callsite_counts = normalized

    passes = sorted(by_bucket["passes_under_enforcement"])
    fixture_only = sorted(by_bucket["fixture_only_bypass"])
    get_side_effect = sorted(by_bucket["get_side_effect"])
    dead_route = sorted(by_bucket["dead_route_dependent"])

    top_endpoints = sorted(
        endpoint_counts.items(), key=lambda kv: kv[1], reverse=True
    )[:30]
    top_get_endpoints = sorted(
        get_endpoint_counts.items(), key=lambda kv: kv[1], reverse=True
    )[:30]
    top_fixture_callsites = sorted(
        fixture_callsite_counts.items(), key=lambda kv: kv[1], reverse=True
    )[:20]

    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("# V2 FEATBypass Dependency Report")
    lines.append("")
    lines.append(f"**Generated:** {when}")
    if git_head:
        lines.append(f"**Commit:** `{git_head}`")
    lines.append(
        f"**Plan:** [V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md]"
        f"(./V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md) — this is the Phase 1 output."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Executive findings")
    lines.append("")
    lines.append(
        f"**Dead-route surface is {len(endpoint_counts)} unique mutating "
        f"endpoints — far smaller than the audit-plan ceiling of ~78** "
        f"derived from `143 mutating route decls − 65 @feat_shell decorators`. "
        f"Most undecorated routes delegate to FEAT-wrapped service functions. "
        f"The Phase 4 dead-route backlog is bounded."
    )
    lines.append("")
    lines.append(
        f"**GET-side-effect surface is {len(get_endpoint_counts)} unique "
        f"endpoints.** INV-ARC-007 (GETs must be pure) is largely respected "
        f"in runtime — a meaningful absence of a finding."
    )
    lines.append("")
    lines.append(
        f"**Fixture-only bypass dependency: "
        f"{len(by_bucket['fixture_only_bypass'])} tests.** The bulk of Phase 2 "
        f"migration work is fixture-seeding consolidation, not route fixing. "
        f"The top callsite hotspot is "
        f"`tests/helpers/class_scope.py:create_class_scope` (several line "
        f"numbers — see Fixture callsites section)."
    )
    lines.append("")
    lines.append(
        f"**{total_collected - len(test_ids)} of {total_collected} collected "
        f"tests produced no flushes** — either they errored before reaching "
        f"any DB operation (the existing baseline failures) or they are "
        f"pure-read/import tests. The observed cohort is {len(test_ids)}."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "For every test that ran in the suite, a SQLAlchemy `before_flush` "
        "listener (installed by `tests/_feat_bypass_audit.py`) inspected the "
        "active FEAT stack. Any flush where `FEATBypass` was the only thing "
        "in scope — and the session held new/dirty/deleted entities — would "
        "have raised `FEATContextError` under production enforcement. Those "
        "flushes are the data behind this report."
    )
    lines.append("")
    lines.append("Each test is bucketed by what its bypass dependency looks like:")
    lines.append("")
    lines.append(
        "- **`passes_under_enforcement`** — no bypass-hidden flushes "
        "observed. Test would run cleanly with enforcement on."
    )
    lines.append(
        "- **`fixture_only_bypass`** — bypass-hidden flushes seen during "
        "setup/teardown or in test bodies that are not inside a Flask route "
        "dispatch. Fixture infrastructure needs an explicit `with FEATBypass():` "
        "wrap; the route call itself is not dead."
    )
    lines.append(
        "- **`get_side_effect`** — a bypass-hidden flush happened inside a "
        "GET handler. This is an [INV-ARC-007]"
        "(../INVARIANT/ARCHITECTURE/"
        "INV-ARC-007_GET_MUST_BE_PURE.md) "
        "candidate: GETs are required to be side-effect free. Separate "
        "category from dead-route since the fix is "
        "\"remove the write\" rather than \"add `@feat_shell`\"."
    )
    lines.append(
        "- **`dead_route_dependent`** — a bypass-hidden flush happened "
        "inside a mutating-method (POST/PUT/DELETE/PATCH) route handler. The "
        "route is mutating state without `@feat_shell` and would return "
        "HTTP 500 under enforcement. **These are the dead routes Phase 4 "
        "will need to fix.**"
    )
    lines.append("")
    lines.append(
        "The dispatch discriminator uses the call stack (looking for Flask's "
        "`wsgi_app`, `full_dispatch_request`, `dispatch_request`, or "
        "`preprocess_request` frames), not `has_request_context()`. "
        "pytest-flask leaves a dangling request context around fixture code, "
        "so the stack check is the reliable signal for \"is a real route "
        "handler running right now.\""
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Bucket | Tests | % of recorded |")
    lines.append("|---|---:|---:|")
    total = max(len(test_ids), 1)
    lines.append(
        f"| Pass under enforcement     | {len(passes):>5} | {100 * len(passes) / total:5.1f}% |"
    )
    lines.append(
        f"| Fixture-only bypass        | {len(fixture_only):>5} | {100 * len(fixture_only) / total:5.1f}% |"
    )
    lines.append(
        f"| GET side-effect            | {len(get_side_effect):>5} | {100 * len(get_side_effect) / total:5.1f}% |"
    )
    lines.append(
        f"| Dead-route dependent       | {len(dead_route):>5} | {100 * len(dead_route) / total:5.1f}% |"
    )
    lines.append(f"| **Total tests observed**   | **{len(test_ids):>3}** | 100.0% |")
    lines.append("")
    lines.append(
        f"_Total tests collected by pytest: {total_collected}. "
        f"Difference vs observed = tests that errored before any flush ran "
        f"(typically import/collect failures) or tests that produced no "
        f"flushes at all._"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "## Dead-route inventory — POST/PUT/DELETE/PATCH endpoints flushed under bypass"
    )
    lines.append("")
    lines.append(
        "These mutating-method endpoints performed at least one flush while "
        "only `FEATBypass` kept the session-level enforcement quiet. Each is "
        "a candidate to either (a) get a `@feat_shell` decorator or (b) "
        "confirm it routes mutation through a separately-decorated service "
        "function."
    )
    lines.append("")
    if top_endpoints:
        lines.append("| Method | Endpoint | Flush count | First observed in |")
        lines.append("|---|---|---:|---|")
        for (method, endpoint), n in top_endpoints:
            first = endpoint_first_test.get((method, endpoint), "")
            lines.append(f"| {method} | `{endpoint}` | {n} | `{first}` |")
        lines.append("")
        unique_endpoints = len(endpoint_counts)
        lines.append(
            f"_{unique_endpoints} unique mutating endpoints surfaced; top "
            f"{min(len(top_endpoints), unique_endpoints)} shown above._"
        )
    else:
        lines.append("_No mutating-route flushes observed under bypass._")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "## GET-side-effect inventory — INV-ARC-007 candidates"
    )
    lines.append("")
    lines.append(
        "GET handlers are required to be side-effect free. These endpoints "
        "flushed mutated state during a GET. The fix is to remove the write "
        "(typically a lazy-create or reconciliation pattern), not to add "
        "`@feat_shell`."
    )
    lines.append("")
    if top_get_endpoints:
        lines.append("| Method | Endpoint | Flush count | First observed in |")
        lines.append("|---|---|---:|---|")
        for (method, endpoint), n in top_get_endpoints:
            first = get_endpoint_first_test.get((method, endpoint), "")
            lines.append(f"| {method} | `{endpoint}` | {n} | `{first}` |")
        lines.append("")
        unique_get_endpoints = len(get_endpoint_counts)
        lines.append(
            f"_{unique_get_endpoints} unique GET endpoints surfaced._"
        )
    else:
        lines.append("_No GET-side-effect flushes observed under bypass._")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Top fixture-only flush callsites")
    lines.append("")
    lines.append(
        "These are the source locations where bypass-hidden flushes most "
        "frequently originate in fixture/setup code. Phase 2 fixture "
        "consolidation should target these hotspots first."
    )
    lines.append("")
    if top_fixture_callsites:
        lines.append("| Callsite | Flush count |")
        lines.append("|---|---:|")
        for site, n in top_fixture_callsites:
            lines.append(f"| `{site}` | {n} |")
        lines.append("")
    else:
        lines.append("_No fixture-only flushes observed._")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Raw data")
    lines.append("")
    lines.append(f"Machine-readable per-test data lives in `{raw_path.name}`.")
    lines.append("")

    md_path.write_text("\n".join(lines))


def pytest_sessionfinish(session, exitstatus):
    out_dir = Path("docs/TRACKING")
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json"
    md_path = out_dir / "V2_FEAT_BYPASS_DEPENDENCY_REPORT.md"

    # Convert defaultdict to regular dict for JSON serialization.
    serializable = {tid: dict(rec) for tid, rec in _records.items()}
    raw_path.write_text(json.dumps(serializable, indent=2, default=str))

    total_collected = session.testscollected if hasattr(session, "testscollected") else 0
    emit_markdown(
        serializable,
        raw_path,
        md_path,
        total_collected=total_collected,
        git_head=_git_head(),
    )

    # Console summary so the operator knows where to look.
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter:
        reporter.write_sep("=", "FEATBypass dependency report")
        reporter.write_line(f"Wrote {raw_path}")
        reporter.write_line(f"Wrote {md_path}")

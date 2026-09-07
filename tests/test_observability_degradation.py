"""Telemetry must not be able to take the application down.

`SPEC-OPS-003` §VII: telemetry failure "MUST NOT change the result, transaction
boundary, authorization, rollback behavior, or user-visible business outcome."

Two ways `app/observability.py` could violate that, neither of which any other
test can see on a complete install:

1. `prometheus_client` is imported at module scope, and `app/__init__.py`
   imports this module inside `create_app()`. An absent package therefore
   fails the *entire application* at construction, not the metrics surface.
   This is exactly how the dependency surfaced — as a pytest collection error
   with nothing to do with telemetry.
2. `record_request` runs in an `after_request` hook. An exception raised there
   is returned to the client, converting a successful response into a failure
   for a reason the caller has no stake in.

Both are latent whenever the install is correct, which is the ordinary case.
The tests below force the abnormal case rather than waiting for it.
"""

from __future__ import annotations

import builtins
import importlib

import pytest
from prometheus_client import REGISTRY

import app.observability as observability


def test_module_imports_without_prometheus_client(monkeypatch):
    """An absent telemetry package disables telemetry and nothing else."""
    real_import = builtins.__import__

    def refuse_prometheus(name, *args, **kwargs):
        if name == "prometheus_client" or name.startswith("prometheus_client."):
            raise ImportError("simulated: prometheus_client is not installed")
        return real_import(name, *args, **kwargs)

    # Metric objects self-register into the process-global default registry at
    # construction. Reloading would therefore register a second set under the
    # same names, so the originals are withdrawn first and the collectors this
    # test leaves behind are withdrawn again before the module is restored.
    original = [observability.HTTP_REQUESTS, observability.HTTP_DURATION]
    for collector in original:
        REGISTRY.unregister(collector)

    monkeypatch.setattr(builtins, "__import__", refuse_prometheus)

    # Reload under the refusal. If the guard regresses to a bare import, this
    # raises ImportError and the test fails here rather than in production.
    degraded = importlib.reload(observability)
    try:
        assert degraded.TELEMETRY_AVAILABLE is False
        # The public surface must remain callable, not merely importable.
        assert degraded.metrics_payload() == b""
        degraded.record_request(
            endpoint="main.health_check",
            method="GET",
            status_code=200,
            elapsed_seconds=0.01,
        )
    finally:
        monkeypatch.undo()
        restored = importlib.reload(observability)
        # Leave the registry as it was found, so later tests in the same
        # process see one set of series rather than none or two.
        for collector in (restored.HTTP_REQUESTS, restored.HTTP_DURATION):
            REGISTRY.unregister(collector)
        for collector in original:
            REGISTRY.register(collector)
        restored.HTTP_REQUESTS, restored.HTTP_DURATION = original


def test_recording_failure_is_swallowed(monkeypatch):
    """A broken metric must not propagate out of the after_request hook."""
    if not observability.TELEMETRY_AVAILABLE:
        pytest.skip("prometheus_client is not installed in this environment")

    class Exploding:
        def labels(self, *args, **kwargs):
            raise RuntimeError("simulated metrics backend failure")

    monkeypatch.setattr(observability, "HTTP_REQUESTS", Exploding())

    # An instrumented endpoint, so the call reaches the metric rather than
    # returning early on an unmapped capability — which would pass vacuously.
    assert "main.health_check" in observability.CAPABILITY_BY_ENDPOINT
    observability.record_request(
        endpoint="main.health_check",
        method="GET",
        status_code=200,
        elapsed_seconds=0.01,
    )


def test_unmapped_endpoint_records_nothing(monkeypatch):
    """Only endpoints in the closed registry may emit a series (§V)."""
    if not observability.TELEMETRY_AVAILABLE:
        pytest.skip("prometheus_client is not installed in this environment")

    class Exploding:
        def labels(self, *args, **kwargs):
            raise AssertionError("an unmapped endpoint must not emit a series")

    monkeypatch.setattr(observability, "HTTP_REQUESTS", Exploding())
    monkeypatch.setattr(observability, "HTTP_DURATION", Exploding())

    assert "admin.dashboard" not in observability.CAPABILITY_BY_ENDPOINT
    observability.record_request(
        endpoint="admin.dashboard",
        method="GET",
        status_code=200,
        elapsed_seconds=0.01,
    )

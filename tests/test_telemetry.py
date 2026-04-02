import sys
import types

from flask import Flask, g

from app.telemetry import annotate_request_context_span, tracing_enabled


class _SpanStub:
    def __init__(self):
        self.attributes = {}

    def is_recording(self):
        return True

    def set_attribute(self, key, value):
        self.attributes[key] = value


def test_tracing_disabled_by_default(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("OTEL_TRACES_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)

    assert tracing_enabled() is False


def test_tracing_enabled_with_traces_endpoint(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://tempo:4318/v1/traces")

    assert tracing_enabled() is True


def test_annotate_request_context_span_sets_request_attributes(monkeypatch):
    app = Flask(__name__)
    span = _SpanStub()
    fake_trace = types.SimpleNamespace(get_current_span=lambda: span)
    fake_otel = types.SimpleNamespace(trace=fake_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)

    with app.test_request_context("/example"):
        g.request_id = "req-123"
        g.correlation_context = {
            "actor_type": "student",
            "actor_opaque_id": "student-opaque",
            "join_code_id": 42,
        }

        annotate_request_context_span()

    assert span.attributes == {
        "app_request_id": "req-123",
        "app_actor_type": "student",
        "app_actor_opaque_id": "student-opaque",
        "app_join_code_id": 42,
    }

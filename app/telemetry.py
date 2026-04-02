"""
OpenTelemetry tracing bootstrap for the Flask application.

Tracing is opt-in. It activates only when explicitly enabled or when an OTLP
traces endpoint is configured in the environment.
"""

from __future__ import annotations

import os

from flask import g, has_request_context


DEFAULT_EXCLUDED_URLS = ",".join(
    (
        r"/static/.*",
        r"/health.*",
        r"/sysadmin/grafana/public/.*",
        r"/sysadmin/grafana/avatar/.*",
        r"/sysadmin/grafana/api/live/.*",
    )
)


def _is_truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def tracing_enabled() -> bool:
    if os.getenv("FLASK_ENV") == "testing":
        return False
    if _is_truthy(os.getenv("OTEL_SDK_DISABLED")):
        return False
    if _is_truthy(os.getenv("OTEL_TRACES_ENABLED")):
        return True
    return bool(
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )


def _service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME", "classroom-token-hub-web")


def _resource(environment: str) -> Resource:
    from opentelemetry.sdk.resources import Resource

    return Resource.create(
        {
            "service.name": _service_name(),
            "service.namespace": "classroom-token-hub",
            "deployment.environment": environment,
        }
    )


def _excluded_urls() -> str:
    return os.getenv("OTEL_PYTHON_FLASK_EXCLUDED_URLS", DEFAULT_EXCLUDED_URLS)


def init_tracing(app, engine) -> bool:
    """Initialize OpenTelemetry tracing for Flask, SQLAlchemy, and requests."""
    if not tracing_enabled():
        app.logger.info("OpenTelemetry tracing disabled")
        return False

    if app.extensions.get("otel_tracing"):
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        app.logger.warning("OpenTelemetry packages are not installed; tracing disabled")
        return False

    provider = TracerProvider(resource=_resource(app.config.get("ENV", "unknown")))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument_app(app, excluded_urls=_excluded_urls())

    requests_instrumentor = RequestsInstrumentor()
    if not requests_instrumentor.is_instrumented_by_opentelemetry:
        requests_instrumentor.instrument()

    sqlalchemy_instrumentor = SQLAlchemyInstrumentor()
    if not sqlalchemy_instrumentor.is_instrumented_by_opentelemetry:
        sqlalchemy_instrumentor.instrument(engine=engine)

    app.extensions["otel_tracing"] = {
        "enabled": True,
        "service_name": _service_name(),
    }
    app.logger.info("OpenTelemetry tracing enabled for service=%s", _service_name())
    return True


def annotate_current_span(**attributes) -> None:
    """Attach application-specific request metadata to the active span."""
    if not has_request_context():
        return

    try:
        from opentelemetry import trace
    except ImportError:
        return

    span = trace.get_current_span()
    if span is None or not span.is_recording():
        return

    for key, value in attributes.items():
        if value is None:
            continue
        span.set_attribute(key, value)


def annotate_request_context_span() -> None:
    """Attach the current request correlation data to the active server span."""
    if not has_request_context():
        return

    context = getattr(g, "correlation_context", None) or {}
    annotate_current_span(
        app_request_id=getattr(g, "request_id", None),
        app_actor_type=context.get("actor_type"),
        app_actor_opaque_id=context.get("actor_opaque_id"),
        app_join_code_id=context.get("join_code_id"),
    )

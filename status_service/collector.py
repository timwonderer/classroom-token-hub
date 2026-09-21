"""Collect bounded application health evidence outside the public GET path."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from status.contracts import ExternalObservationRecord
from status.projection import EpistemicState, EvidenceSource, ObservationClass, Outcome

from .store import FirestoreNoticeStore


APP_HEALTH_URL = "https://app.classroomtokenhub.com/health/status"
PROBE_VERSION = "app-health-v2"
SIGNALS = {
    "login": ("capability", ObservationClass.READINESS),
    "attendance": ("capability", ObservationClass.READINESS),
    "payroll": ("capability", ObservationClass.READINESS),
    "roster": ("capability", ObservationClass.READINESS),
    "classroom_economy": ("capability", ObservationClass.READINESS),
    "database": ("platform", ObservationClass.READINESS),
    "background_jobs": ("platform", ObservationClass.READINESS),
    "external_integrations": ("platform", ObservationClass.READINESS),
    "monitoring_freshness": ("platform", ObservationClass.READINESS),
    "invariant_verification": ("platform", ObservationClass.CORRECTNESS),
}
_DIAGNOSTIC_STATES = {
    "CHECK_NOT_REGISTERED": (Outcome.UNKNOWN, EpistemicState.UNAVAILABLE),
    "DATABASE_REACHABLE": (Outcome.PASS, EpistemicState.KNOWN),
    "DATABASE_UNAVAILABLE": (Outcome.FAIL, EpistemicState.UNAVAILABLE),
}


@dataclass(frozen=True)
class HealthResponse:
    body: bytes
    status: int


class _InvalidHealthResponse(ValueError):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch_app_health(client_id: str, client_secret: str) -> HealthResponse:
    if not client_id or not client_secret:
        raise ValueError("Both Cloudflare Access credentials are required")
    request = Request(APP_HEALTH_URL, headers={
        "CF-Access-Client-Id": client_id,
        "CF-Access-Client-Secret": client_secret,
        "Accept": "application/json",
    })
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200 or "application/json" not in response.headers.get("Content-Type", ""):
            raise _InvalidHealthResponse("Health response was not JSON 200", response.status)
        body = response.read(16_385)
    if len(body) > 16_384:
        raise _InvalidHealthResponse("Health response exceeded bound", 200)
    return HealthResponse(body, 200)


def _signal_map(body: bytes, now: datetime) -> dict[str, tuple[Outcome, EpistemicState, str, datetime | None]]:
    payload = json.loads(body)
    if not isinstance(payload, dict) or set(payload) != {"observed_at", "signals"}:
        raise ValueError("Unexpected health payload")
    observed_at = datetime.fromisoformat(payload["observed_at"])
    # The app and collector use separate clocks. Permit only a small positive
    # clock skew, while still rejecting stale or materially future payloads.
    if observed_at.tzinfo is None or not -timedelta(seconds=5) <= now - observed_at <= timedelta(minutes=2):
        raise ValueError("Stale or future health payload")
    if not isinstance(payload["signals"], list) or len(payload["signals"]) != len(SIGNALS):
        raise ValueError("Incomplete health signal set")
    mapped = {}
    for signal in payload["signals"]:
        if not isinstance(signal, dict) or set(signal) != {"key", "layer", "outcome", "epistemic_state", "diagnostic_code", "checked_at"}:
            raise ValueError("Unexpected health signal shape")
        key = signal["key"]
        if key not in SIGNALS or key in mapped or signal["layer"] != SIGNALS[key][0]:
            raise ValueError("Unknown, duplicate, or misclassified signal")
        outcome = Outcome(signal["outcome"])
        epistemic = EpistemicState(signal["epistemic_state"])
        diagnostic = signal["diagnostic_code"]
        if diagnostic not in _DIAGNOSTIC_STATES:
            raise ValueError("Unregistered diagnostic code")
        if (outcome, epistemic) != _DIAGNOSTIC_STATES[diagnostic]:
            raise ValueError("Invalid health signal state")
        if (key == "database") != diagnostic.startswith("DATABASE_"):
            raise ValueError("Diagnostic does not match health signal")
        checked_at_value = signal["checked_at"]
        if checked_at_value is None:
            if diagnostic != "CHECK_NOT_REGISTERED":
                raise ValueError("Registered check requires checked_at")
            checked_at = None
        else:
            if not isinstance(checked_at_value, str):
                raise ValueError("Invalid checked_at")
            if diagnostic == "CHECK_NOT_REGISTERED":
                raise ValueError("Unregistered check cannot claim a check time")
            checked_at = datetime.fromisoformat(checked_at_value)
            if checked_at.tzinfo is None or observed_at - checked_at < -timedelta(seconds=5):
                raise ValueError("Invalid or future checked_at")
            if observed_at - checked_at > timedelta(minutes=5):
                raise ValueError("Stale checked_at")
        mapped[key] = (outcome, epistemic, diagnostic, checked_at)
    return mapped


def collect(store: FirestoreNoticeStore, *, client_id: str, client_secret: str, now: datetime | None = None, fetch=fetch_app_health) -> list[ExternalObservationRecord]:
    observed_at = now or datetime.now(timezone.utc)
    correlation_id = f"corr-{uuid4().hex}"
    reachability = (Outcome.UNKNOWN, EpistemicState.UNAVAILABLE, "PROBE_UNAVAILABLE")
    signals = {key: (Outcome.UNKNOWN, EpistemicState.UNAVAILABLE, "PROBE_UNAVAILABLE", None) for key in SIGNALS}
    app_evidence_received = False
    transport_http_status = None
    started_ns = time.monotonic_ns()
    try:
        response = fetch(client_id, client_secret)
        transport_http_status = response.status
        observed_at = now if now is not None else datetime.now(timezone.utc)
        if response.status != 200:
            raise _InvalidHealthResponse("Health response was not JSON 200", response.status)
        reachability = (Outcome.PASS, EpistemicState.KNOWN, "HTTP_OK")
        # Use the same receipt time for validation and persisted freshness.
        signals = _signal_map(response.body, observed_at)
        app_evidence_received = True
    except HTTPError as exc:
        transport_http_status = exc.code
        # Access denial is a monitor-credential problem, not evidence of app failure.
        if exc.code not in (301, 302, 303, 307, 308, 401, 403):
            reachability = (Outcome.FAIL, EpistemicState.UNAVAILABLE, "HTTP_UNAVAILABLE")
    except (URLError, OSError, TimeoutError):
        reachability = (Outcome.FAIL, EpistemicState.UNAVAILABLE, "NETWORK_UNAVAILABLE")
    except _InvalidHealthResponse as exc:
        transport_http_status = exc.status
        if exc.status not in (301, 302, 303, 307, 308, 401, 403) and exc.status != 200:
            reachability = (Outcome.FAIL, EpistemicState.UNAVAILABLE, "HTTP_UNAVAILABLE")
    except (ValueError, TypeError, KeyError):
        # A reachable but unusable payload establishes liveness only.
        pass
    elapsed_ms = (time.monotonic_ns() - started_ns) / 1_000_000
    transport_latency_ms = int(elapsed_ms) if 0 <= elapsed_ms <= 600_000 else None
    records = []
    states = [("public_service_reachability", ObservationClass.LIVENESS, (*reachability, observed_at))]
    states.extend((key, kind, signals[key]) for key, (_, kind) in SIGNALS.items())
    for key, kind, (outcome, epistemic, diagnostic, checked_at) in states:
        record = ExternalObservationRecord(
            observation_id=f"obs-{uuid4().hex}", observed_at=observed_at,
            correlation_id=correlation_id,
            source=(EvidenceSource.APPLICATION_RUNTIME_EVIDENCE
                    if key != "public_service_reachability" and app_evidence_received
                    else EvidenceSource.EXTERNAL_PROBE),
            capability=key, observation_class=kind, outcome=outcome,
            epistemic_state=epistemic, diagnostic_code=diagnostic,
            transport_latency_ms=transport_latency_ms, probe_version=PROBE_VERSION,
            freshness_class="REALTIME",
            staleness_state_at_receipt=("UNKNOWN" if checked_at is None else "FRESH"),
            evaluator_version=None, checked_at=checked_at,
            transport_http_status=transport_http_status,
        )
        record.validate()
        records.append(record)
    store.append_observations(records)
    return records


def main() -> None:
    from google.cloud import firestore

    # Secret Manager values populated by a terminal pipeline may contain a final newline.
    client_id = os.environ.get("CF_ACCESS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("CF_ACCESS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Cloudflare Access credentials are required")
    store = FirestoreNoticeStore(firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "cth-status-prod")))
    records = collect(store, client_id=client_id, client_secret=client_secret)
    # No credentials, raw response, or tenant-linked data enter logs.
    print(f"Stored {len(records)} bounded status observations")


if __name__ == "__main__":
    main()

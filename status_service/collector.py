"""Transport closed numerical snapshots, never query or interpret domain state."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from status.measurements import parse_time, validate_fresh_snapshot, validate_snapshot
from status.platform import PLATFORM_SCHEMA, validate_platform
from .store import FirestoreNoticeStore

TELEMETRY_URL = "https://app.classroomtokenhub.com/health/telemetry"
PLATFORM_URL = "https://app.classroomtokenhub.com/health/status"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _fetch_json(url: str, client_id: str, client_secret: str) -> bytes:
    if not client_id or not client_secret:
        raise ValueError("Both Cloudflare Access credentials are required")
    request = Request(url, headers={"CF-Access-Client-Id": client_id,
                      "CF-Access-Client-Secret": client_secret, "Accept": "application/json"})
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200 or "application/json" not in response.headers.get("Content-Type", ""):
            raise ValueError("Snapshot response was not JSON 200")
        body = response.read(16_385)
    if len(body) > 16_384:
        raise ValueError("Snapshot exceeded response bound")
    return body


def fetch_telemetry(client_id: str, client_secret: str) -> bytes:
    return _fetch_json(TELEMETRY_URL, client_id, client_secret)


def fetch_platform(client_id: str, client_secret: str) -> bytes:
    return _fetch_json(PLATFORM_URL, client_id, client_secret)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def collect(store: FirestoreNoticeStore, *, client_id: str, client_secret: str, now: datetime | None = None, fetch=fetch_telemetry) -> dict | None:
    snapshot = None
    diagnostic = None
    body = None
    try:
        body = fetch(client_id, client_secret)
    except HTTPError as exc:
        diagnostic = "ACCESS_DENIED" if exc.code in (301, 302, 303, 307, 308, 401, 403) else "TRANSPORT_UNAVAILABLE"
    except (OSError, TimeoutError):
        diagnostic = "TRANSPORT_UNAVAILABLE"
    except (ValueError, TypeError, KeyError, OverflowError):
        diagnostic = "INVALID_SNAPSHOT"
    # One completion clock governs freshness validation and persisted receipt.
    received_at = now or datetime.now(timezone.utc)
    if diagnostic is None:
        try:
            if not isinstance(body, bytes) or len(body) > 16_384:
                raise ValueError("Invalid bounded body")
            candidate = validate_snapshot(json.loads(body, object_pairs_hook=_unique_object))
            try:
                snapshot = validate_fresh_snapshot(candidate, received_at)
            except ValueError:
                diagnostic = "STALE_SNAPSHOT"
        except (ValueError, TypeError, KeyError, OverflowError):
            diagnostic = "INVALID_SNAPSHOT"

    store.append_snapshot(snapshot, received_at, diagnostic=diagnostic)
    return snapshot


def collect_platform(store, *, client_id: str, client_secret: str,
                     now: datetime | None = None, fetch=fetch_platform) -> dict:
    """Keep the real SELECT1 result; discard every feature placeholder."""
    body = None
    transport = None
    http_failure = False
    try:
        body = fetch(client_id, client_secret)
    except HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308, 401, 403):
            transport = "ACCESS_DENIED"
        else:
            transport, http_failure = "TRANSPORT_UNAVAILABLE", True
    except (OSError, TimeoutError):
        transport = "TRANSPORT_UNAVAILABLE"
    except (ValueError, TypeError, KeyError, OverflowError):
        transport = "INVALID_RESPONSE"
    received = now or datetime.now(timezone.utc)
    stamp = received.isoformat()
    endpoint = {"key": "endpoint", "outcome": "UNKNOWN" if transport else "PASS",
                "checked_at": None if transport else stamp, "diagnostic": transport or "HTTP_OK"}
    if http_failure:
        endpoint.update(outcome="FAIL", checked_at=stamp, diagnostic="HTTP_UNAVAILABLE")
    database = {"key": "database", "outcome": "UNKNOWN", "checked_at": None,
                "diagnostic": transport or "INVALID_RESPONSE"}
    if transport is None:
        try:
            if not isinstance(body, bytes) or len(body) > 16_384:
                raise ValueError("Invalid bounded response")
            payload = json.loads(body, object_pairs_hook=_unique_object)
            if not isinstance(payload, dict) or set(payload) != {"observed_at", "signals"}:
                raise ValueError("Invalid source response")
            observed = parse_time(payload["observed_at"])
            signals = payload["signals"]
            if not isinstance(signals, list) or len(signals) > 64:
                raise ValueError("Invalid signal list")
            matches = [signal for signal in signals if isinstance(signal, dict) and signal.get("key") == "database"]
            if len(matches) != 1:
                raise ValueError("Database check missing or duplicated")
            signal = matches[0]
            if set(signal) != {"key", "layer", "outcome", "epistemic_state", "diagnostic_code", "checked_at"} or signal["layer"] != "platform":
                raise ValueError("Invalid database check")
            expected = {"DATABASE_REACHABLE": ("PASS", "KNOWN"), "DATABASE_UNAVAILABLE": ("FAIL", "UNAVAILABLE")}
            diagnostic = signal["diagnostic_code"]
            if not isinstance(diagnostic, str) or diagnostic not in expected or (signal["outcome"], signal["epistemic_state"]) != expected[diagnostic]:
                raise ValueError("Unrecognized database evidence")
            checked = parse_time(signal["checked_at"])
            if checked > observed or observed > received:
                raise ValueError("Future database evidence")
            if (received - observed).total_seconds() > 300 or (received - checked).total_seconds() > 300:
                database["diagnostic"] = "STALE_SOURCE"
            else:
                database.update(outcome=signal["outcome"], checked_at=signal["checked_at"], diagnostic=diagnostic)
        except (ValueError, TypeError, KeyError, OverflowError):
            database["diagnostic"] = "INVALID_RESPONSE"
    record = validate_platform({"schema_version": PLATFORM_SCHEMA, "received_at": stamp,
                                "checks": [endpoint, database]})
    store.append_platform(record)
    return record


def main() -> None:
    from google.cloud import firestore
    client_id = os.environ.get("CF_ACCESS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("CF_ACCESS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Cloudflare Access credentials are required")
    store = FirestoreNoticeStore(firestore.Client(database=os.environ.get("FIRESTORE_DATABASE", "cth-status-prod")))
    snapshot = collect(store, client_id=client_id, client_secret=client_secret)
    collect_platform(store, client_id=client_id, client_secret=client_secret)
    print("Stored request telemetry and platform checks" if snapshot is not None else "Stored unavailable request telemetry and platform checks")


if __name__ == "__main__":
    main()

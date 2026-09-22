"""Firestore persistence for bounded external status notices."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

class FirestoreNoticeStore:
    def __init__(self, client):
        self.client = client

    def list_notices(self, limit: int = 50) -> list[dict]:
        query = self.client.collection("external_status_notices").order_by("updated_at", direction="DESCENDING").limit(limit)
        return [{"id": snapshot.id, **snapshot.to_dict()} for snapshot in query.stream()]

    def list_active_notices(self) -> list[dict]:
        """Read every unresolved notice, independent of bounded history views."""
        collection = self.client.collection("external_status_notices")
        active = []
        for state in ("INVESTIGATING", "IDENTIFIED", "MONITORING"):
            for snapshot in collection.where("state", "==", state).stream():
                active.append({"id": snapshot.id, **snapshot.to_dict()})
        return sorted(active, key=lambda notice: notice["updated_at"], reverse=True)

    def current_snapshot(self) -> dict | None:
        """Read persisted current attempt; callers evaluate freshness at render time."""
        value = self.client.collection("telemetry_current").document("current").get()
        return value.to_dict() if value.exists else None

    def current_platform(self) -> dict | None:
        """Read the separate current endpoint/database check without mutations."""
        value = self.client.collection("platform_current").document("current").get()
        return value.to_dict() if value.exists else None

    def append_platform(self, record: dict) -> None:
        """Retain measured platform attempts independently of request snapshots."""
        from google.cloud import firestore
        from status.measurements import parse_time
        from status.platform import validate_platform

        record = validate_platform(record)
        received = parse_time(record["received_at"])
        current_ref = self.client.collection("platform_current").document("current")
        observation_ref = self.client.collection("platform_observations").document(uuid4().hex)

        @firestore.transactional
        def write(transaction):
            current_doc = current_ref.get(transaction=transaction)
            previous = current_doc.to_dict() if current_doc.exists else None
            # Append all attempts; a delayed delivery cannot rewind current state.
            transaction.create(observation_ref, {**record, "expires_at": received + timedelta(days=7)})
            if previous is None or received > parse_time(previous["received_at"]):
                transaction.set(current_ref, record)

        write(self.client.transaction())

    def measurement_history(self, days: int = 90) -> list[dict]:
        if not 1 <= days <= 90:
            raise ValueError("History is bounded to 90 days.")
        now = datetime.now(timezone.utc)
        dates = [now.date() - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        refs = [self.client.collection("telemetry_days").document(day.isoformat()) for day in dates]
        records = {doc.id: doc.to_dict() for doc in self.client.get_all(refs) if doc.exists}
        result = []
        for day in dates:
            item = records.get(day.isoformat(), {})
            elapsed = 1440 if day < now.date() else now.hour * 60 + now.minute + 1
            result.append({"date": day.isoformat(), "components": item.get("components", {}),
                           "scheduled_minutes": elapsed})
        return result

    def append_snapshot(self, snapshot: dict | None, received_at: datetime,
                        diagnostic: str | None = None) -> None:
        """Atomically retain source minutes, history counters and latest attempt."""
        from google.cloud import firestore
        from status.measurements import (DIAGNOSTICS, classify_component,
                                         parse_time, validate_fresh_snapshot)
        if received_at.utcoffset() is None:
            raise ValueError("Receipt time requires timezone.")
        received_at = received_at.astimezone(timezone.utc)
        if snapshot is None:
            if diagnostic not in DIAGNOSTICS:
                raise ValueError("A failed collection requires a closed diagnostic.")
        else:
            if diagnostic is not None:
                raise ValueError("Source snapshots cannot carry transport failure.")
            snapshot = validate_fresh_snapshot(snapshot, received_at)
        wrapper = {"snapshot": snapshot, "received_at": received_at, "diagnostic": diagnostic}
        current_ref = self.client.collection("telemetry_current").document("current")
        sampled = parse_time(snapshot["sampled_at"]) if snapshot else None
        minute_id = sampled.strftime("%Y%m%dT%H%MZ") if sampled else None
        source_ref = self.client.collection("telemetry_snapshots").document(minute_id) if snapshot else None
        day_ref = self.client.collection("telemetry_days").document(sampled.date().isoformat()) if snapshot else None
        failure_ref = self.client.collection("telemetry_attempts").document(uuid4().hex) if snapshot is None else None

        @firestore.transactional
        def write(transaction):
            previous_doc = current_ref.get(transaction=transaction)
            previous = previous_doc.to_dict() if previous_doc.exists else None
            source_doc = source_ref.get(transaction=transaction) if source_ref else None
            day_doc = day_ref.get(transaction=transaction) if day_ref else None
            # All reads precede writes, including duplicate-delivery reads.
            if source_ref and not source_doc.exists:
                day = day_doc.to_dict() if day_doc.exists else {"components": {}}
                components = day.setdefault("components", {})
                for component in snapshot["components"]:
                    counters = components.setdefault(component["key"], dict.fromkeys(
                        ("sampled", "measured", "normal", "elevated_errors", "high_latency", "other"), 0))
                    state = classify_component(component, snapshot, now=sampled)["state"]
                    counters["sampled"] += 1
                    eligible = state in {"NORMAL", "ELEVATED_ERRORS", "HIGH_LATENCY"}
                    counters["measured"] += int(eligible)
                    counters[state.lower() if eligible else "other"] += 1
                day["expires_at"] = datetime.combine(sampled.date() + timedelta(days=90),
                                                      datetime.min.time(), timezone.utc)
                transaction.create(source_ref, {**wrapper, "expires_at": sampled + timedelta(days=7)})
                transaction.set(day_ref, day)
            elif failure_ref:
                transaction.create(failure_ref, {**wrapper, "expires_at": received_at + timedelta(days=7)})
            # Do not let delayed or duplicate source evidence erase a newer failure,
            # nor allow older source samples to move the successful pointer backward.
            previous_received = previous.get("received_at") if previous else None
            previous_source = previous.get("snapshot") if previous else None
            advance = previous is None or received_at > previous_received
            if snapshot and previous_source:
                advance = advance and sampled > parse_time(previous_source["sampled_at"])
            if snapshot and source_doc.exists:
                advance = False
            if snapshot and previous and previous_source is None:
                advance = advance and sampled >= previous_received.replace(second=0, microsecond=0)
            if advance:
                transaction.set(current_ref, wrapper)
        write(self.client.transaction())

    def append_event(self, notice: dict, event_type: str, actor: str) -> str:
        now = datetime.now(timezone.utc)
        notice_id = notice.get("external_notice_id")
        if not notice_id:
            for snapshot in self.client.collection("external_status_notices").stream():
                if snapshot.to_dict().get("incident_ref") == notice["incident_ref"]:
                    notice_id = snapshot.id
                    break
        notice_id = notice_id or f"notice-{uuid4().hex}"
        event_id = f"event-{uuid4().hex}"
        event = {"external_notice_id": notice_id, "incident_ref": notice["incident_ref"], "event_id": event_id, "event_type": event_type, "published_at": now, "state": notice["state"], "capability": notice["capability"], "impact_statement": notice["impact_statement"], "recommended_user_action": notice["recommended_user_action"], "recovery_state": notice["recovery_state"], "recovery_expectation": notice.get("recovery_expectation"), "next_update_at": notice.get("next_update_at"), "next_update_unavailable": notice.get("next_update_unavailable", False), "source_observation_ids": notice["source_observation_ids"], "actor": actor}
        self.client.collection("external_status_notice_events").document(event_id).create(event)
        projection = {**notice, "external_notice_id": notice_id, "updated_at": now, "last_event_id": event_id}
        self.client.collection("external_status_notices").document(notice_id).set(projection)
        return event_id

    def resolve_notices(self, selections: dict[str, str], message: str, actor: str) -> None:
        """Resolve exact reviewed versions atomically, preserving publication history."""
        from google.cloud import firestore
        from .contracts import ExternalStatusNoticeEvent, NoticeState, RecoveryExpectationState

        if not selections or len(selections) > 100 or not message.strip() or len(message) > 500:
            raise ValueError("Select 1–100 issues and provide a resolution of at most 500 characters.")
        if any(not key or "/" in key or not version for key, version in selections.items()):
            raise ValueError("Invalid issue selection.")
        current = self.client.collection("external_status_notices")
        history = self.client.collection("external_status_notice_events")
        now = datetime.now(timezone.utc)

        @firestore.transactional
        def resolve(transaction):
            snapshots = {key: current.document(key).get(transaction=transaction) for key in selections}
            writes = []
            for key, snapshot in snapshots.items():
                notice = snapshot.to_dict() if snapshot.exists else None
                if (not notice or notice.get("state") not in {"INVESTIGATING", "IDENTIFIED", "MONITORING"}
                        or notice.get("last_event_id") != selections[key]
                        or notice.get("external_notice_id") != key
                        or not notice.get("incident_ref")):
                    raise ValueError("An issue changed or cannot be resolved. Refresh and review the selection.")
                event_id = f"event-{uuid4().hex}"
                updated = {**notice, "state": "RESOLVED", "impact_statement": message.strip(),
                           "recommended_user_action": "No action required.", "recovery_state": "UNAVAILABLE",
                           "recovery_expectation": None, "next_update_at": None, "next_update_unavailable": True,
                           "updated_at": now, "last_event_id": event_id}
                record = ExternalStatusNoticeEvent(
                    external_notice_id=key, incident_ref=notice["incident_ref"], event_id=event_id,
                    event_type="RESOLVED", published_at=now, state=NoticeState.RESOLVED,
                    capability=notice["capability"], impact_statement=updated["impact_statement"],
                    recommended_user_action=updated["recommended_user_action"],
                    recovery_state=RecoveryExpectationState.UNAVAILABLE, recovery_expectation=None,
                    next_update_at=None, next_update_unavailable=True,
                    source_observation_ids=tuple(notice.get("source_observation_ids", ())))
                record.validate()
                event = {field: updated[field] for field in (
                    "external_notice_id", "incident_ref", "state", "capability", "impact_statement",
                    "recommended_user_action", "recovery_state", "recovery_expectation", "next_update_at",
                    "next_update_unavailable", "source_observation_ids")}
                event.update(event_id=event_id, event_type="RESOLVED", published_at=now, actor=actor)
                writes.append((key, event_id, updated, event))
            for key, event_id, updated, event in writes:
                transaction.create(history.document(event_id), event)
                transaction.set(current.document(key), updated)

        resolve(self.client.transaction())

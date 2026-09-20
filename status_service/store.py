"""Firestore persistence for bounded external status notices."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from status.contracts import ExternalObservationRecord


def _observation_order(document: dict) -> tuple:
    """Prefer newer evidence; at equal time keep the least reassuring result."""
    severity = {
        ("PASS", "KNOWN"): 0,
        ("UNKNOWN", "UNAVAILABLE"): 1,
        ("FAIL", "UNAVAILABLE"): 2,
        ("FAIL", "KNOWN"): 3,
    }
    return (document["observed_at"], severity[(document["outcome"], document["epistemic_state"])], document["observation_id"])


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

    def list_current_observations(self) -> dict[str, dict]:
        """Read the replaceable bounded projection; never mutate during GET."""
        snapshots = self.client.collection("external_status_current").stream()
        return {snapshot.id: snapshot.to_dict() for snapshot in snapshots}

    def append_observations(self, records: list[ExternalObservationRecord]) -> None:
        """Append evidence and advance current pointers in one serializable transaction."""
        from google.cloud import firestore

        if not records:
            return
        documents = []
        for record in records:
            record.validate()
            document = {
                "observation_id": record.observation_id,
                "observed_at": record.observed_at,
                "checked_at": record.checked_at,
                "correlation_id": record.correlation_id,
                "source": record.source.value,
                "capability": record.capability,
                "observation_class": record.observation_class.value,
                "outcome": record.outcome.value,
                "epistemic_state": record.epistemic_state.value,
                "diagnostic_code": record.diagnostic_code,
                "latency_ms": record.latency_ms,
                "probe_version": record.probe_version,
            }
            documents.append(document)

        current_collection = self.client.collection("external_status_current")
        observation_collection = self.client.collection("external_status_observations")
        current_refs = {item["capability"]: current_collection.document(item["capability"]) for item in documents}

        @firestore.transactional
        def write(transaction):
            # Firestore requires all transactional reads before the first write.
            current = {key: snapshot.to_dict() if snapshot.exists else None
                       for key, ref in current_refs.items()
                       for snapshot in (ref.get(transaction=transaction),)}
            winners = {}
            for document in documents:
                key = document["capability"]
                previous = winners.get(key, current[key])
                if previous is None or _observation_order(document) > _observation_order(previous):
                    winners[key] = document
            for document in documents:
                transaction.create(observation_collection.document(document["observation_id"]), document)
            for key, document in winners.items():
                transaction.set(current_refs[key], document)

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

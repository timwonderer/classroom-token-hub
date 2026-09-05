"""Firestore persistence for bounded external status notices."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class FirestoreNoticeStore:
    def __init__(self, client):
        self.client = client

    def list_notices(self, limit: int = 50) -> list[dict]:
        query = self.client.collection("external_status_notices").order_by("updated_at", direction="DESCENDING").limit(limit)
        return [{"id": snapshot.id, **snapshot.to_dict()} for snapshot in query.stream()]

    def append_event(self, notice: dict, event_type: str, actor: str) -> str:
        now = datetime.now(timezone.utc)
        notice_id = notice.get("external_notice_id") or f"notice-{uuid4().hex}"
        event_id = f"event-{uuid4().hex}"
        event = {"external_notice_id": notice_id, "event_id": event_id, "event_type": event_type, "published_at": now, "state": notice["state"], "capability": notice["capability"], "impact_statement": notice["impact_statement"], "recommended_user_action": notice["recommended_user_action"], "recovery_state": notice["recovery_state"], "recovery_expectation": notice.get("recovery_expectation"), "next_update_at": notice.get("next_update_at"), "next_update_unavailable": notice.get("next_update_unavailable", False), "source_observation_ids": notice["source_observation_ids"], "actor": actor}
        self.client.collection("external_status_notice_events").document(event_id).create(event)
        projection = {**notice, "external_notice_id": notice_id, "updated_at": now, "last_event_id": event_id}
        self.client.collection("external_status_notices").document(notice_id).set(projection)
        return event_id

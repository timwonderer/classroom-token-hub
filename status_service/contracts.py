"""Bounded notice contract used by the standalone status service."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NoticeState(str, Enum):
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class RecoveryExpectationState(str, Enum):
    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ExternalStatusNoticeEvent:
    external_notice_id: str
    incident_ref: str
    event_id: str
    event_type: str
    published_at: datetime
    state: NoticeState
    capability: str
    impact_statement: str
    recommended_user_action: str
    recovery_state: RecoveryExpectationState
    recovery_expectation: datetime | None
    next_update_at: datetime | None
    next_update_unavailable: bool
    source_observation_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.external_notice_id or not self.incident_ref or not self.event_id or not self.event_type:
            raise ValueError("Notice identity and event type are required.")
        if not self.capability or not self.impact_statement or not self.recommended_user_action:
            raise ValueError("Notice communication fields are required.")
        if len(self.impact_statement) > 500 or len(self.recommended_user_action) > 240:
            raise ValueError("Notice communication fields exceed bounded limits.")
        if self.recovery_state == RecoveryExpectationState.UNAVAILABLE and self.recovery_expectation is not None:
            raise ValueError("Unavailable recovery expectation cannot carry a timestamp.")
        if self.recovery_state != RecoveryExpectationState.UNAVAILABLE and self.recovery_expectation is None:
            raise ValueError("Known or estimated recovery requires a timestamp.")
        if self.next_update_at is None and not self.next_update_unavailable:
            raise ValueError("Notice requires a next update timestamp or explicit unavailability.")
        if self.next_update_at is not None and self.next_update_unavailable:
            raise ValueError("Notice cannot provide and disclaim a next update simultaneously.")
        if len(self.incident_ref) > 160 or len(self.source_observation_ids) > 20:
            raise ValueError("Investigation reference or source links exceed limits.")
        if any(not isinstance(value, str) or len(value) > 160 for value in self.source_observation_ids):
            raise ValueError("Invalid source link.")
        for value in (self.published_at, self.recovery_expectation, self.next_update_at):
            if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
                raise ValueError("Notice timestamps require an explicit timezone.")

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
        if not self.external_notice_id or not self.event_id or not self.event_type:
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
        if not self.source_observation_ids:
            raise ValueError("Notice requires bounded source observation lineage.")

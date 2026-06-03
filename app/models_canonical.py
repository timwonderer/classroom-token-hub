"""Canonical V2 ORM models (DOM-CORE-002).

Wave 1 scope: define the 44 canonical table mappings as an authoritative
reference without changing runtime behavior.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True)


class Seat(Base, TimestampMixin):
    __tablename__ = "seats"
    id = sa.Column(sa.Integer, primary_key=True)
    public_id = sa.Column(
        sa.String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )


class Class_(Base, TimestampMixin):
    __tablename__ = "classes"
    id = sa.Column(sa.Integer, primary_key=True)
    class_id = sa.Column(sa.String(36), unique=True, nullable=False, index=True)


class IdentityProfile(Base, TimestampMixin):
    __tablename__ = "identity_profiles"
    id = sa.Column(sa.Integer, primary_key=True)


class UserInviteToken(Base, TimestampMixin):
    __tablename__ = "user_invite_tokens"
    id = sa.Column(sa.Integer, primary_key=True)


class UserRecoveryToken(Base, TimestampMixin):
    __tablename__ = "user_recovery_tokens"
    id = sa.Column(sa.Integer, primary_key=True)


class ClassFeature(Base, TimestampMixin):
    __tablename__ = "class_features"
    id = sa.Column(sa.Integer, primary_key=True)


class FeatureSetting(Base, TimestampMixin):
    __tablename__ = "feature_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class PolicyVersion(Base, TimestampMixin):
    __tablename__ = "policy_versions"
    id = sa.Column(sa.Integer, primary_key=True)


class PolicyTransition(Base, TimestampMixin):
    __tablename__ = "policy_transitions"
    id = sa.Column(sa.Integer, primary_key=True)


class HallPassSetting(Base, TimestampMixin):
    __tablename__ = "hall_pass_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class RentSetting(Base, TimestampMixin):
    __tablename__ = "rent_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class PayrollSetting(Base, TimestampMixin):
    __tablename__ = "payroll_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class PayrollReward(Base, TimestampMixin):
    __tablename__ = "payroll_rewards"
    id = sa.Column(sa.Integer, primary_key=True)


class PayrollFine(Base, TimestampMixin):
    __tablename__ = "payroll_fines"
    id = sa.Column(sa.Integer, primary_key=True)


class BankingSetting(Base, TimestampMixin):
    __tablename__ = "banking_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class AttendanceSession(Base, TimestampMixin):
    __tablename__ = "attendance_sessions"
    id = sa.Column(sa.Integer, primary_key=True)


class HallPassLog(Base, TimestampMixin):
    __tablename__ = "hall_pass_logs"
    id = sa.Column(sa.Integer, primary_key=True)


class SeatAttendanceState(Base, TimestampMixin):
    __tablename__ = "seat_attendance_state"
    id = sa.Column(sa.Integer, primary_key=True)


class AssessmentEvent(Base, TimestampMixin):
    __tablename__ = "assessment_events"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationLifecycle(Base, TimestampMixin):
    __tablename__ = "obligation_lifecycle"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationSatisfaction(Base, TimestampMixin):
    __tablename__ = "obligation_satisfaction"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationReversal(Base, TimestampMixin):
    __tablename__ = "obligation_reversal"
    id = sa.Column(sa.Integer, primary_key=True)


class EntitlementEvent(Base, TimestampMixin):
    __tablename__ = "entitlement_events"
    id = sa.Column(sa.Integer, primary_key=True)


class LedgerTransaction(Base, TimestampMixin):
    __tablename__ = "ledger_transaction"
    id = sa.Column(sa.Integer, primary_key=True)


class LedgerBalanceSnapshot(Base, TimestampMixin):
    __tablename__ = "ledger_balance_snapshot"
    id = sa.Column(sa.Integer, primary_key=True)


class StoreItem(Base, TimestampMixin):
    __tablename__ = "store_items"
    id = sa.Column(sa.Integer, primary_key=True)


class StoreItemVisibility(Base, TimestampMixin):
    __tablename__ = "store_item_visibility"
    id = sa.Column(sa.Integer, primary_key=True)


class StorePurchase(Base, TimestampMixin):
    __tablename__ = "store_purchases"
    id = sa.Column(sa.Integer, primary_key=True)


class RedemptionEvent(Base, TimestampMixin):
    __tablename__ = "redemption_events"
    id = sa.Column(sa.Integer, primary_key=True)


class OperationalEvent(Base, TimestampMixin):
    __tablename__ = "operational_events"
    id = sa.Column(sa.Integer, primary_key=True)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    id = sa.Column(sa.Integer, primary_key=True)


class IncidentEvent(Base, TimestampMixin):
    __tablename__ = "incident_events"
    id = sa.Column(sa.Integer, primary_key=True)


class IncidentSummary(Base, TimestampMixin):
    __tablename__ = "incident_summary"
    id = sa.Column(sa.Integer, primary_key=True)


class AlertEvent(Base, TimestampMixin):
    __tablename__ = "alert_events"
    id = sa.Column(sa.Integer, primary_key=True)


class InvariantRunEvent(Base, TimestampMixin):
    __tablename__ = "invariant_run_events"
    id = sa.Column(sa.Integer, primary_key=True)


class JobEvent(Base, TimestampMixin):
    __tablename__ = "job_events"
    id = sa.Column(sa.Integer, primary_key=True)


class HealthCheckEvent(Base, TimestampMixin):
    __tablename__ = "health_check_events"
    id = sa.Column(sa.Integer, primary_key=True)


class InterpretationSnapshot(Base, TimestampMixin):
    __tablename__ = "interpretation_snapshots"
    id = sa.Column(sa.Integer, primary_key=True)


class InterpretationAnnotation(Base, TimestampMixin):
    __tablename__ = "interpretation_annotations"
    id = sa.Column(sa.Integer, primary_key=True)


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueStatusHistory(Base, TimestampMixin):
    __tablename__ = "issue_status_history"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueResolutionAction(Base, TimestampMixin):
    __tablename__ = "issue_resolution_actions"
    id = sa.Column(sa.Integer, primary_key=True)


class TicketCorrelationPack(Base, TimestampMixin):
    __tablename__ = "ticket_correlation_packs"
    id = sa.Column(sa.Integer, primary_key=True)


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueCategory(Base, TimestampMixin):
    __tablename__ = "issue_categories"
    id = sa.Column(sa.Integer, primary_key=True)


__all__ = [
    "User",
    "Seat",
    "Class_",
    "IdentityProfile",
    "UserInviteToken",
    "UserRecoveryToken",
    "ClassFeature",
    "FeatureSetting",
    "PolicyVersion",
    "PolicyTransition",
    "HallPassSetting",
    "RentSetting",
    "PayrollSetting",
    "PayrollReward",
    "PayrollFine",
    "BankingSetting",
    "AttendanceSession",
    "HallPassLog",
    "SeatAttendanceState",
    "AssessmentEvent",
    "ObligationLifecycle",
    "ObligationSatisfaction",
    "ObligationReversal",
    "EntitlementEvent",
    "LedgerTransaction",
    "LedgerBalanceSnapshot",
    "StoreItem",
    "StoreItemVisibility",
    "StorePurchase",
    "RedemptionEvent",
    "OperationalEvent",
    "AuditLog",
    "IncidentEvent",
    "IncidentSummary",
    "AlertEvent",
    "InvariantRunEvent",
    "JobEvent",
    "HealthCheckEvent",
    "InterpretationSnapshot",
    "InterpretationAnnotation",
    "Issue",
    "IssueStatusHistory",
    "IssueResolutionAction",
    "TicketCorrelationPack",
    "Announcement",
    "IssueCategory",
]

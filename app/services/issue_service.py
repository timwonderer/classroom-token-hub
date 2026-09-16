from __future__ import annotations

from app.extensions import db
from app.models import ClassEconomy, Issue, Seat


def create_support_ticket(*, actor_public_id: str, class_public_id: str, category_id: int, title: str, scoped_description: str, expected_behavior: str | None, page_url: str | None, share_class_name: bool = False) -> Issue:
    """Create and flush a canonical support ticket row."""
    # Freeze the class display name at submission time (DOM-SUP-001 §VI). The
    # label is context, not a live pointer: renaming or destroying the class
    # afterwards must not rewrite captured context. Deleting its originating
    # seat destroys the ticket and attached pack through database cascades.
    class_row = ClassEconomy.query.filter_by(class_public_id=class_public_id).first()

    if not class_row or not Seat.query.filter_by(
        public_id=actor_public_id, class_id=class_row.class_id, role='teacher',
    ).first():
        raise ValueError('Teacher tickets require a seat in the specified class.')

    from flask import request
    from app.utils.ip_handler import get_real_ip
    from app.utils.canonical_temporal_resolver import utc_now

    report = Issue(
        actor_public_id=actor_public_id,
        class_public_id=class_public_id,
        class_label=class_row.display_name if class_row else None,
        category_id=category_id,
        issue_type='general',
        support_permissions={'student_report': True},
        share_class_name_with_sysadmin=share_class_name,
        context_snapshot={
            'timestamp': utc_now().isoformat(), 'page_url': page_url or request.url,
            'ip_address': get_real_ip(), 'user_agent': request.headers.get('User-Agent'),
        },
        title=title,
        student_explanation=scoped_description,
        student_expected_outcome=expected_behavior if expected_behavior else None,
        page_url=page_url if page_url else None,
        status=Issue.STATUS_OPEN,
    )
    db.session.add(report)
    db.session.flush()
    attach_correlation_pack(
        report, actor_type='teacher', actor_public_id=actor_public_id,
        class_id=class_row.class_id,
    )
    return report


def attach_correlation_pack(issue, *, actor_type, actor_public_id, class_id, include_recent_error=True):
    """Freeze the existing diagnostic pack inside the ticket's FEAT transaction."""
    from app.models import TicketCorrelationPack
    from app.services.tlcp import create_ticket_correlation_pack

    if issue.correlation_pack is not None:
        raise ValueError('A submitted correlation pack cannot be replaced.')
    data = create_ticket_correlation_pack(
        issue_id=issue.id, actor_type=actor_type, actor_public_id=actor_public_id,
        class_id=class_id, ticket_created_at=issue.submitted_at,
        include_recent_error=include_recent_error,
    )
    issue.correlation_pack = TicketCorrelationPack(
        issue_id=issue.id, correlation_version=data['correlation_version'],
        actor_type=data['actor_type'], actor_public_id=data['actor_public_id'],
        class_public_id=issue.class_public_id,
        request_trace_json=data['request_trace_json'], error_refs_json=data['error_refs_json'],
        created_at=data['created_at'],
    )
    db.session.flush()

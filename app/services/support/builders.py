"""Support domain view model builders (SPEC-UI-001 §VII, §IX).

Turn Issue rows into plain presentation dicts for the teacher's issue queue,
issue detail and support-ticket pages. Every timestamp leaves here as
presentation-ready text, localized through the canonical temporal resolver
(``app.utils.temporal_display``); templates only print it.
"""

from __future__ import annotations

from app.utils.temporal_display import format_timestamp


def build_teacher_issue_view(ctx, issue, student_display_name, class_label):
    """Plain-dict view of an Issue row plus its resolved identity fields.

    ``teacher_reviewed_at``, ``sysadmin_resolved_at`` and ``closed_at`` stay
    alongside their display text because the detail page shows those sections
    only when the event happened.
    """
    return {
        'id': issue.id,
        'status': issue.status,
        'student_display_name': student_display_name,
        'class_label': class_label,
        'category': {'name': issue.category.name if issue.category else 'Unknown'},
        'issue_type': issue.issue_type,
        'related_transaction_id': issue.related_transaction_id,
        'student_explanation': issue.student_explanation or '',
        'student_expected_outcome': issue.student_expected_outcome,
        'submitted_at_display': format_timestamp(ctx, issue.submitted_at),
        'updated_at_display': format_timestamp(ctx, issue.updated_at),
        'escalated_at_display': format_timestamp(ctx, issue.escalated_at),
        'escalation_reason': issue.escalation_reason,
        'teacher_resolution': issue.teacher_resolution,
        'teacher_reviewed_at': issue.teacher_reviewed_at,
        'teacher_reviewed_at_display': format_timestamp(ctx, issue.teacher_reviewed_at),
        'teacher_notes': issue.teacher_notes,
        'teacher_diagnostic_note': issue.teacher_diagnostic_note,
        'sysadmin_notes': issue.sysadmin_notes,
        'sysadmin_resolved_at': issue.sysadmin_resolved_at,
        'sysadmin_resolved_at_display': format_timestamp(ctx, issue.sysadmin_resolved_at),
        'closed_at': issue.closed_at,
        'closed_at_display': format_timestamp(ctx, issue.closed_at),
        'closed_by_type': issue.closed_by_type,
        'context_snapshot': issue.context_snapshot,
        'page_url': issue.page_url,
        'system_metadata': issue.system_metadata,
        'eligible_for_reward': issue.eligible_for_reward,
        'share_class_name_with_sysadmin': issue.share_class_name_with_sysadmin,
        # Relationships resolved to plain lists by the caller when needed.
        'resolution_actions': [],
        'status_history': [],
    }


def build_resolution_action_view(ctx, action):
    """Plain-dict view of an IssueResolutionAction row."""
    return {
        'action_type': action.action_type,
        'action_description': action.action_description,
        'performed_by_type': action.performed_by_type,
        'performed_by_public_id': action.performed_by_public_id,
        'related_transaction_id': action.related_transaction_id,
        'amount_changed': action.amount_changed,
        'before_value': action.before_value,
        'after_value': action.after_value,
        'created_at_display': format_timestamp(ctx, action.created_at),
    }


def build_status_history_view(ctx, history):
    """Plain-dict view of an IssueStatusHistory row."""
    return {
        'previous_status': history.previous_status,
        'new_status': history.new_status,
        'changed_at_display': format_timestamp(ctx, history.changed_at),
        'changed_by_type': history.changed_by_type,
        'changed_by_public_id': history.changed_by_public_id,
        'notes': history.notes,
    }


def build_teacher_support_report_views(ctx, issues):
    """The teacher's own tickets, with captured class context (never refreshed)."""
    return [{
        'report': {
            'title': issue.title or 'Support Ticket',
            'status': issue.status,
            'submitted_at_display': format_timestamp(ctx, issue.submitted_at),
            'report_type': issue.issue_type,
        },
        'class_label': issue.class_label,
        'scope_class_id': issue.class_public_id,
        'issue_category': issue.category.name if issue.category else 'Unknown',
        'clean_description': issue.student_explanation or '',
    } for issue in issues]

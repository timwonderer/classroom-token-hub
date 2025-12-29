"""
Helper functions for the Issue Resolution System.

Provides utilities for creating issues, managing status changes, and ensuring
proper data minimization for sysadmin review.
"""

from datetime import datetime, timezone
from flask import request
import hashlib
import secrets

from app.extensions import db
from app.models import Issue, IssueStatusHistory, IssueResolutionAction, Transaction, Student, StudentBlock
from app.utils.helpers import generate_anonymous_code
from app.utils.ip_handler import get_real_ip


def generate_opaque_student_reference(student_id):
    """
    Generate a non-reversible, opaque reference for a student.
    Used for sysadmin investigations without revealing student identity.

    Args:
        student_id: The student's database ID

    Returns:
        str: Opaque hash that cannot be reversed to identify the student
    """
    return generate_anonymous_code(f"student_issue:{student_id}")


def create_context_snapshot(student, join_code, related_transaction_id=None, related_record_type=None, related_record_id=None):
    """
    Create an immutable snapshot of system context for an issue.

    Args:
        student: Student model instance
        join_code: Current class join code
        related_transaction_id: Optional transaction ID for transaction-specific issues
        related_record_type: Optional record type ('transaction', 'tap_event', etc.)
        related_record_id: Optional record ID

    Returns:
        dict: Context snapshot with ledger state, amounts, timestamps, etc.
    """
    snapshot = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'page_url': request.url if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None,
        'ip_address': get_real_ip() if request else None,
    }

    # Get current balances from StudentBlock
    student_block = StudentBlock.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).first()

    if student_block:
        snapshot['balances'] = {
            'checking': student_block.checking_balance or 0,
            'savings': student_block.savings_balance or 0,
            'total': (student_block.checking_balance or 0) + (student_block.savings_balance or 0)
        }
    else:
        snapshot['balances'] = {
            'checking': 0,
            'savings': 0,
            'total': 0
        }

    # If transaction-specific, include transaction details
    if related_transaction_id:
        transaction = Transaction.query.get(related_transaction_id)
        if transaction:
            snapshot['transaction'] = {
                'id': transaction.id,
                'amount': transaction.amount,
                'account_type': transaction.account_type,
                'description': transaction.description,
                'type': transaction.type,
                'timestamp': transaction.timestamp.isoformat() if transaction.timestamp else None,
                'is_void': transaction.is_void
            }

    # Get recent transaction history (last 10 transactions for context)
    recent_transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).limit(10).all()

    snapshot['recent_transactions'] = [
        {
            'id': t.id,
            'amount': t.amount,
            'description': t.description,
            'timestamp': t.timestamp.isoformat() if t.timestamp else None
        }
        for t in recent_transactions
    ]

    return snapshot


def create_issue(student, teacher_id, join_code, category_id, explanation, expected_outcome=None,
                 related_transaction_id=None, related_record_type=None, related_record_id=None):
    """
    Create a new issue submission.

    Args:
        student: Student model instance
        teacher_id: Teacher's admin ID
        join_code: Current class join code
        category_id: IssueCategory ID
        explanation: Student's explanation of the issue
        expected_outcome: Optional - what student expected to happen
        related_transaction_id: Optional - for transaction-specific issues
        related_record_type: Optional - type of related record
        related_record_id: Optional - ID of related record

    Returns:
        Issue: Created issue instance
    """
    from app.models import IssueCategory, TeacherBlock

    # Get category to determine issue_type
    category = IssueCategory.query.get(category_id)
    if not category:
        raise ValueError("Invalid category")

    # Get class label
    seat = TeacherBlock.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).first()

    class_label = seat.get_class_label() if seat else None

    # Generate opaque reference
    opaque_ref = generate_opaque_student_reference(student.id)

    # Create context snapshot
    context_snapshot = create_context_snapshot(
        student, join_code, related_transaction_id, related_record_type, related_record_id
    )

    # Create the issue
    issue = Issue(
        student_id=student.id,
        student_first_name=student.first_name,
        student_last_initial=student.last_initial,
        opaque_student_reference=opaque_ref,
        teacher_id=teacher_id,
        join_code=join_code,
        class_label=class_label,
        category_id=category_id,
        issue_type=category.category_type,
        student_explanation=explanation,
        student_expected_outcome=expected_outcome,
        related_transaction_id=related_transaction_id,
        related_record_type=related_record_type,
        related_record_id=related_record_id,
        context_snapshot=context_snapshot,
        page_url=request.url if request else None,
        status='submitted'
    )

    db.session.add(issue)
    db.session.flush()  # Get the issue ID

    # Record status history
    record_status_change(issue, None, 'submitted', 'student', student.id)

    db.session.commit()

    return issue


def record_status_change(issue, previous_status, new_status, changed_by_type, changed_by_id, notes=None):
    """
    Record a status change in the issue history.

    Args:
        issue: Issue model instance
        previous_status: Previous status (or None for initial submission)
        new_status: New status
        changed_by_type: Type of user making change ('student', 'teacher', 'sysadmin', 'system')
        changed_by_id: ID of user making change
        notes: Optional notes about the change
    """
    history = IssueStatusHistory(
        issue_id=issue.id,
        previous_status=previous_status,
        new_status=new_status,
        changed_by_type=changed_by_type,
        changed_by_id=changed_by_id,
        notes=notes
    )

    db.session.add(history)


def record_resolution_action(issue, action_type, performed_by_type, performed_by_id,
                             action_description=None, related_transaction_id=None,
                             amount_changed=None, before_value=None, after_value=None):
    """
    Record a resolution action taken on an issue.

    Args:
        issue: Issue model instance
        action_type: Type of action ('reverse_transaction', 'correct_amount', etc.)
        performed_by_type: Type of user ('teacher', 'sysadmin')
        performed_by_id: ID of user performing action
        action_description: Optional description of the action
        related_transaction_id: Optional transaction ID if action affects a transaction
        amount_changed: Optional amount that was changed
        before_value: Optional before state
        after_value: Optional after state
    """
    action = IssueResolutionAction(
        issue_id=issue.id,
        action_type=action_type,
        action_description=action_description,
        performed_by_type=performed_by_type,
        performed_by_id=performed_by_id,
        related_transaction_id=related_transaction_id,
        amount_changed=amount_changed,
        before_value=before_value,
        after_value=after_value
    )

    db.session.add(action)


def update_issue_status(issue, new_status, changed_by_type, changed_by_id, notes=None):
    """
    Update issue status and record the change in history.

    Args:
        issue: Issue model instance
        new_status: New status value
        changed_by_type: Type of user making change
        changed_by_id: ID of user making change
        notes: Optional notes about the change
    """
    previous_status = issue.status
    issue.status = new_status
    issue.updated_at = datetime.now(timezone.utc)

    record_status_change(issue, previous_status, new_status, changed_by_type, changed_by_id, notes)

"""Reusable helpers for hard-deleting student records and dependent data."""

import sqlalchemy as sa

from app.extensions import db
from app.models import (
    BalanceCache,
    HallPassLog,
    InsuranceClaim,
    Issue,
    IssueResolutionAction,
    IssueStatusHistory,
    RedemptionAuditLog,
    RentPayment,
    RentWaiver,
    Student,
    StudentBlock,
    StudentInsurance,
    StudentItem,
    StudentTeacher,
    TapEvent,
    TeacherBlock,
    Transaction,
    UserReport,
    Seat,
)
from app.services.recovery_bridge_service import delete_recovery_codes_for_student


def _collect_related_ids(student_id):
    """Materialize dependent record IDs once for downstream delete/update queries."""
    student_item_ids = [
        row[0]
        for row in db.session.query(StudentItem.id).filter(StudentItem.student_id == student_id).all()
    ]
    issue_ids = [
        row[0]
        for row in db.session.query(Issue.id).filter(Issue.student_id == student_id).all()
    ]
    insurance_ids = [
        row[0]
        for row in db.session.query(StudentInsurance.id).filter(StudentInsurance.student_id == student_id).all()
    ]
    tx_ids = [
        row[0]
        for row in db.session.query(Transaction.id)
        .join(Seat, Transaction.seat_id == Seat.id)
        .filter(Seat.student_id == student_id)
        .all()
    ]
    seat_ids = [
        row[0]
        for row in db.session.query(Seat.id).filter(Seat.student_id == student_id).all()
    ]
    return student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids


def _unclaim_all_teacher_blocks_for_student(student_id):
    """Convert all claimed roster seats for this student back to unclaimed seats."""
    TeacherBlock.query.filter(
        TeacherBlock.student_id == student_id
    ).update(
        {
            TeacherBlock.student_id: None,
            TeacherBlock.is_claimed: False,
            TeacherBlock.claimed_at: None,
        },
        synchronize_session=False,
    )


def _clear_cross_transaction_refs(tx_ids):
    """Clear references to transactions that are about to be deleted."""
    if not tx_ids:
        return

    Issue.query.filter(
        Issue.related_transaction_id.in_(tx_ids)
    ).update(
        {Issue.related_transaction_id: None},
        synchronize_session=False,
    )
    IssueResolutionAction.query.filter(
        IssueResolutionAction.related_transaction_id.in_(tx_ids)
    ).update(
        {IssueResolutionAction.related_transaction_id: None},
        synchronize_session=False,
    )
    Transaction.query.filter(
        Transaction.original_transaction_id.in_(tx_ids)
    ).update(
        {Transaction.original_transaction_id: None},
        synchronize_session=False,
    )
    Transaction.query.filter(
        Transaction.reversal_transaction_id.in_(tx_ids)
    ).update(
        {Transaction.reversal_transaction_id: None},
        synchronize_session=False,
    )


def _delete_student_scoped_rows(student_id, student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids):
    """Delete records that are scoped directly to the student being removed."""
    if student_item_ids:
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(student_item_ids)
        ).delete(synchronize_session=False)
    if issue_ids:
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)
        IssueStatusHistory.query.filter(
            IssueStatusHistory.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)

    insurance_claim_filters = [InsuranceClaim.student_id == student_id]
    if insurance_ids:
        insurance_claim_filters.append(InsuranceClaim.student_insurance_id.in_(insurance_ids))
    if tx_ids:
        insurance_claim_filters.append(InsuranceClaim.transaction_id.in_(tx_ids))
    InsuranceClaim.query.filter(sa.or_(*insurance_claim_filters)).delete(synchronize_session=False)

    Issue.query.filter(Issue.student_id == student_id).delete(synchronize_session=False)
    StudentInsurance.query.filter(StudentInsurance.student_id == student_id).delete(synchronize_session=False)
    UserReport.query.filter(UserReport._student_id == student_id).delete(synchronize_session=False)
    delete_recovery_codes_for_student(student_id)
    if tx_ids:
        Transaction.query.filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
    TapEvent.query.filter(TapEvent.student_id == student_id).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.student_id == student_id).delete(synchronize_session=False)
    StudentItem.query.filter(StudentItem.student_id == student_id).delete(synchronize_session=False)
    RentPayment.query.filter(RentPayment.student_id == student_id).delete(synchronize_session=False)
    RentWaiver.query.filter(RentWaiver.student_id == student_id).delete(synchronize_session=False)
    StudentBlock.query.filter(StudentBlock.student_id == student_id).delete(synchronize_session=False)
    if seat_ids:
        BalanceCache.query.filter(BalanceCache.seat_id.in_(seat_ids)).delete(synchronize_session=False)


def hard_delete_student_if_orphaned(student_id):
    """Hard-delete a student and dependent rows only when no teacher links remain."""
    has_links = (
        db.session.query(StudentTeacher.id)
        .filter(StudentTeacher.student_id == student_id)
        .all()
    )
    print(f"DEBUG: hard_delete_student_if_orphaned for student_id={student_id}. has_links={has_links}")
    if has_links:
        return False

    student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids = _collect_related_ids(student_id)
    _unclaim_all_teacher_blocks_for_student(student_id)
    _clear_cross_transaction_refs(tx_ids)
    _delete_student_scoped_rows(student_id, student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids)
    Student.query.filter(Student.id == student_id).delete(synchronize_session=False)
    return True


def remove_student_from_teacher_scope(student_id, teacher_id):
    """
    Remove a student from a specific teacher's roster and hard-delete if orphaned.
    """
    StudentTeacher.query.filter(
        StudentTeacher.student_id == student_id,
        StudentTeacher.teacher_id == teacher_id,
    ).delete(synchronize_session=False)
    TeacherBlock.query.filter(
        TeacherBlock.student_id == student_id,
        TeacherBlock.teacher_id == teacher_id,
    ).update(
        {
            TeacherBlock.student_id: None,
            TeacherBlock.is_claimed: False,
            TeacherBlock.claimed_at: None,
        },
        synchronize_session=False,
    )
    return hard_delete_student_if_orphaned(student_id)

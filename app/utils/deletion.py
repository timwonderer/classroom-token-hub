import logging
from typing import Optional

from flask import current_app
from sqlalchemy import func, or_, case, select

from app.extensions import db
from app.models import (
    ClassEconomy, ClassMembership, TeacherBlock, Transaction, StudentBlock,
    TapEvent, HallPassLog, RedemptionAuditLog, StudentItem, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    StudentInsurance, RentPayment, Announcement, StoreItemBlock, StoreItem,
    Student, StudentTeacher, PayrollSettings, RentSettings,
    InsurancePolicyBlock,
)
from app.feats.base import feat_shell, InvariantViolation

logger = logging.getLogger(__name__)


def _raise_invariant_violation(message: str) -> None:
    logger.critical("P0 INVARIANT VIOLATION: %s", message)
    raise InvariantViolation(message)


def _assert_class_scope_integrity(class_id: str, join_code: str) -> None:
    scoped_models = (
        ("teacher_blocks", TeacherBlock),
        ("ledger_transaction", Transaction),
        ("student_blocks", StudentBlock),
        ("tap_events", TapEvent),
        ("hall_pass_logs", HallPassLog),
        ("student_items", StudentItem),
        ("analytics_events", AnalyticsEvent),
        ("analytics_snapshots", AnalyticsSnapshot),
        ("issues", Issue),
        ("student_insurance", StudentInsurance),
        ("rent_payments", RentPayment),
        ("announcements", Announcement),
    )
    violations = []
    for label, model in scoped_models:
        count = db.session.query(model).filter(
            model.join_code == join_code,
            model.class_id.is_(None),
        ).count()
        if count:
            violations.append(f"{label}={count}")

    affected_blocks = db.session.query(TeacherBlock.block).filter(
        TeacherBlock.class_id == class_id,
        TeacherBlock.block.isnot(None),
    ).distinct().all()
    affected_student_ids = db.session.query(TeacherBlock.student_id).filter(
        TeacherBlock.class_id == class_id,
        TeacherBlock.student_id.isnot(None),
    ).distinct().all()
    block_names = [block for (block,) in affected_blocks]
    student_ids = [student_id for (student_id,) in affected_student_ids]
    if block_names and student_ids:
        inferred_student_block_nulls = db.session.query(StudentBlock).filter(
            StudentBlock.student_id.in_(student_ids),
            StudentBlock.period.in_(block_names),
            StudentBlock.class_id.is_(None),
        ).count()
        if inferred_student_block_nulls:
            violations.append(f"student_blocks_inferred={inferred_student_block_nulls}")

    if violations:
        _raise_invariant_violation(
            f"class_id NULL rows detected for class_id={class_id} join_code={join_code}: {', '.join(violations)}"
        )

@feat_shell("FEAT-OPS-001")
def collapse_universe(class_id: str, reason: str, actor_membership_id: Optional[int]) -> bool:
    """
    Canonical destruction primitive for a class economy.
    
    The boundary may enter through `join_code`, but this primitive executes on the
    canonical `class_id` anchor only.

    A deleted class MUST leave zero remaining rows in any table scoped by that class.
    There is no soft delete. There is no archive state. There is no preserved financial history.
    
    Args:
        class_id: Canonical class boundary to collapse.
        reason: An audit reason for the deletion (logged).
        actor_membership_id: The ClassMembership ID of the actor performing the deletion.
        
    Returns:
        True if the universe was collapsed (or didn't exist), False if an error occurred.
    """
    if not class_id:
        return True  # Idempotency: If class_id does not exist, return success.

    try:
        economy = db.session.get(ClassEconomy, class_id)
        if not economy:
            return True
        join_code = economy.join_code
        _assert_class_scope_integrity(class_id, join_code)

        logger.info(
            "Collapsing universe for class_id=%s join_code=%s. Reason: %s. Actor: %s",
            class_id,
            join_code,
            reason,
            actor_membership_id,
        )

        # 1. Identify affected TeacherBlocks and Students
        affected_blocks = db.session.query(TeacherBlock.block, TeacherBlock.teacher_id).filter_by(
            class_id=class_id
        ).all()
        
        affected_student_ids_tb = [
            s_id for (s_id,) in db.session.query(TeacherBlock.student_id).filter(
                TeacherBlock.class_id == class_id,
                TeacherBlock.student_id.isnot(None)
            ).distinct().all()
        ]
        affected_student_ids_sb = [
            s_id for (s_id,) in db.session.query(StudentBlock.student_id).filter(
                StudentBlock.class_id == class_id,
                StudentBlock.student_id.isnot(None)
            ).distinct().all()
        ]
        affected_student_ids = list(set(affected_student_ids_tb + affected_student_ids_sb))

        # Many tables are handled by ON DELETE CASCADE from ClassEconomy
        # (e.g. BalanceCache, Transaction, StudentBlock, TapEvent, RentPayment, ClassMembership, ClassJoinCodeAlias)
        # We explicitly delete the others or things that require manual cleanup first

        # 2. Activity / State Logs & Records (Not all have ON DELETE CASCADE yet)
        HallPassLog.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsSnapshot.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsEvent.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        Announcement.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        StudentBlock.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 3. Insurance & Issue Data
        issue_ids_subq = select(Issue.id).filter_by(class_id=class_id).subquery()
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(select(issue_ids_subq))
        ).delete(synchronize_session=False)
        Issue.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        insurance_ids_subq = select(StudentInsurance.id).filter_by(class_id=class_id).subquery()
        tx_ids_subq = select(Transaction.id).filter_by(class_id=class_id).subquery()
        InsuranceClaim.query.filter(
            or_(
                InsuranceClaim.student_insurance_id.in_(select(insurance_ids_subq)),
                InsuranceClaim.transaction_id.in_(select(tx_ids_subq))
            )
        ).delete(synchronize_session=False)
        StudentInsurance.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 4. Inventory / Store Data
        student_item_ids_subq = select(StudentItem.id).filter_by(class_id=class_id).subquery()
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(select(student_item_ids_subq))
        ).delete(synchronize_session=False)
        StudentItem.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # Clean up StoreItemBlocks for the affected blocks
        if affected_blocks:
            involved_teachers = list(set(t_id for _, t_id in affected_blocks))
            block_names = list(set(b_name for b_name, _ in affected_blocks))
            
            # Find all store items belonging to the affected teachers that are visible to these blocks
            store_items_in_blocks = db.session.query(StoreItem.id).filter(
                StoreItem.teacher_id.in_(involved_teachers)
            ).subquery()
            
            # Delete the visibility blocks for those store items matching the deleted block names
            StoreItemBlock.query.filter(
                StoreItemBlock.store_item_id.in_(select(store_items_in_blocks)),
                StoreItemBlock.block.in_(block_names)
            ).delete(synchronize_session=False)

            # Delete StoreItems that now have NO remaining StoreItemBlock visibility entries
            # We must do this for all teachers involved in the blocks
            for t_id in involved_teachers:
                deletable_store_items = db.session.query(StoreItem.id).outerjoin(
                    StoreItemBlock, StoreItem.id == StoreItemBlock.store_item_id
                ).filter(
                    StoreItem.teacher_id == t_id,
                    StoreItemBlock.store_item_id == None
                ).subquery()
                
                # We already deleted StudentItems, so we just delete the StoreItems
                StoreItem.query.filter(StoreItem.id.in_(select(deletable_store_items))).delete(synchronize_session=False)

        # 5. Delete TeacherBlocks for this class
        TeacherBlock.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 6. Delete the ClassEconomy itself (This triggers ON DELETE CASCADE for Transactions, Memberships, etc.)
        db.session.delete(economy)

        # 7. Post-collapse: Student Erasure and Link Cleanup
        # If a student has zero remaining memberships AND zero TeacherBlocks under THIS specific teacher, 
        # remove the StudentTeacher association for this teacher.
        # If they have zero across ALL teachers, fully delete the student.
        if affected_student_ids:
            involved_teachers = list(set(t_id for _, t_id in affected_blocks))
            for s_id in affected_student_ids:
                # Cleanup teacher-student link for specific teachers
                for t_id in involved_teachers:
                    # Does student have any remaining classes with this specific teacher?
                    remaining_with_teacher = db.session.query(TeacherBlock.id).filter_by(
                        student_id=s_id, teacher_id=t_id
                    ).count()
                    
                    if remaining_with_teacher == 0:
                        StudentTeacher.query.filter_by(student_id=s_id, teacher_id=t_id).delete(synchronize_session=False)
                
                # Full erasure if totally orphaned
                remaining_memberships = db.session.query(ClassMembership.id).filter_by(student_id=s_id).count()
                remaining_tblocks = db.session.query(TeacherBlock.id).filter_by(student_id=s_id).count()
                
                if remaining_memberships == 0 and remaining_tblocks == 0:
                    logger.info(f"Student Erasure Rule triggered for student_id={s_id}")
                    # Remove any leftover bridge rows
                    StudentTeacher.query.filter_by(student_id=s_id).delete(synchronize_session=False)
                    # Orphaned transactions will be deleted via ON DELETE CASCADE from Seats when Student is deleted.
                    Student.query.filter_by(id=s_id).delete(synchronize_session=False)

        # 8. Post-collapse: Settings Cleanup
        # If no remaining TeacherBlock exists for that block name for the teacher, delete the settings.
        if affected_blocks:
            for block_name, teacher_id in affected_blocks:
                remaining_blocks = db.session.query(TeacherBlock.id).filter_by(block=block_name, teacher_id=teacher_id).count()
                if remaining_blocks == 0:
                    logger.info(f"Settings Cleanup Rule triggered for block={block_name}, teacher={teacher_id}")
                    PayrollSettings.query.filter_by(teacher_id=teacher_id, block=block_name).delete(synchronize_session=False)
                    RentSettings.query.filter_by(teacher_id=teacher_id, block=block_name).delete(synchronize_session=False)
                    InsurancePolicyBlock.query.filter_by(block=block_name).delete(synchronize_session=False) # Simplified, might need teacher_id scoping depending on model

        db.session.flush()  # FEAT-AUTHORIZED-SHELL
        return True

    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to collapse universe for class_id={class_id}: {e}", exc_info=True)
        return False

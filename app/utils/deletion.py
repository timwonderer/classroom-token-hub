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

logger = logging.getLogger(__name__)

def collapse_universe(join_code: str, reason: str, actor_membership_id: Optional[int]) -> bool:
    """
    Canonical Destruction Primitive for a Class Economy (join_code).
    
    A deleted join_code MUST leave zero remaining rows in any table scoped by that join_code.
    There is no soft delete. There is no archive state. There is no preserved financial history.
    
    Args:
        join_code: The join_code of the class economy to collapse.
        reason: An audit reason for the deletion (logged).
        actor_membership_id: The ClassMembership ID of the actor performing the deletion.
        
    Returns:
        True if the universe was collapsed (or didn't exist), False if an error occurred.
    """
    if not join_code:
        return True # Idempotency: If join_code does not exist, return success.

    try:
        # Check if the economy actually exists to avoid unnecessary work if called idempotently
        economy = db.session.get(ClassEconomy, join_code)
        if not economy:
            return True

        logger.info(f"Collapsing universe for join_code={join_code}. Reason: {reason}. Actor: {actor_membership_id}")

        # 1. Identify affected TeacherBlocks and Students
        affected_blocks = db.session.query(TeacherBlock.block, TeacherBlock.teacher_id).filter_by(
            join_code=join_code
        ).all()
        
        affected_student_ids_tb = [
            s_id for (s_id,) in db.session.query(TeacherBlock.student_id).filter(
                TeacherBlock.join_code == join_code,
                TeacherBlock.student_id.isnot(None)
            ).distinct().all()
        ]
        affected_student_ids_sb = [
            s_id for (s_id,) in db.session.query(StudentBlock.student_id).filter(
                StudentBlock.join_code == join_code,
                StudentBlock.student_id.isnot(None)
            ).distinct().all()
        ]
        affected_student_ids = list(set(affected_student_ids_tb + affected_student_ids_sb))

        # Many tables are handled by ON DELETE CASCADE from ClassEconomy
        # (e.g. BalanceCache, Transaction, StudentBlock, TapEvent, RentPayment, ClassMembership, ClassJoinCodeAlias)
        # We explicitly delete the others or things that require manual cleanup first

        # 2. Activity / State Logs & Records (Not all have ON DELETE CASCADE yet)
        HallPassLog.query.filter_by(join_code=join_code).delete(synchronize_session=False)
        AnalyticsSnapshot.query.filter_by(join_code=join_code).delete(synchronize_session=False)
        AnalyticsEvent.query.filter_by(join_code=join_code).delete(synchronize_session=False)
        Announcement.query.filter_by(join_code=join_code).delete(synchronize_session=False)
        StudentBlock.query.filter_by(join_code=join_code).delete(synchronize_session=False)

        # 3. Insurance & Issue Data
        issue_ids_subq = select(Issue.id).filter_by(join_code=join_code).subquery()
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(select(issue_ids_subq))
        ).delete(synchronize_session=False)
        Issue.query.filter_by(join_code=join_code).delete(synchronize_session=False)

        insurance_ids_subq = select(StudentInsurance.id).filter_by(join_code=join_code).subquery()
        tx_ids_subq = select(Transaction.id).filter_by(join_code=join_code).subquery()
        InsuranceClaim.query.filter(
            or_(
                InsuranceClaim.student_insurance_id.in_(select(insurance_ids_subq)),
                InsuranceClaim.transaction_id.in_(select(tx_ids_subq))
            )
        ).delete(synchronize_session=False)
        StudentInsurance.query.filter_by(join_code=join_code).delete(synchronize_session=False)

        # 4. Inventory / Store Data
        student_item_ids_subq = select(StudentItem.id).filter_by(join_code=join_code).subquery()
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(select(student_item_ids_subq))
        ).delete(synchronize_session=False)
        StudentItem.query.filter_by(join_code=join_code).delete(synchronize_session=False)

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

        # 5. Delete TeacherBlocks for this join_code
        TeacherBlock.query.filter_by(join_code=join_code).delete(synchronize_session=False)
        
        # 5b. Remove legacy StudentBlock entries (that rely on period name instead of join_code)
        if affected_blocks and affected_student_ids:
            block_names = list(set(b_name for b_name, _ in affected_blocks))
            StudentBlock.query.filter(
                StudentBlock.student_id.in_(affected_student_ids),
                StudentBlock.period.in_(block_names),
                StudentBlock.join_code.is_(None)
            ).delete(synchronize_session=False)

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
                    # Clean up all remaining orphaned transactions for this student
                    Transaction.query.filter_by(student_id=s_id).delete(synchronize_session=False)
                    # The delete will cascade to other student-specific data
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

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to collapse universe for join_code={join_code}: {e}", exc_info=True)
        return False

#!/usr/bin/env python3
"""
One-time cleanup script to remove orphaned StoreItemBlock entries.

This script identifies and removes StoreItemBlock entries where the corresponding
TeacherBlock no longer exists (i.e., the class has been deleted).

Usage:
    flask shell < scripts/cleanup_orphaned_store_blocks.py
"""

from app.extensions import db
from app.models import StoreItemBlock, TeacherBlock, StoreItem
from sqlalchemy import and_, or_, tuple_

def cleanup_orphaned_store_blocks():
    """Remove StoreItemBlock entries for non-existent classes."""

    orphaned_entries_subq = (
        db.session.query(
            StoreItemBlock.store_item_id.label("store_item_id"),
            StoreItemBlock.block.label("block"),
        )
        .outerjoin(StoreItem, StoreItem.id == StoreItemBlock.store_item_id)
        .outerjoin(
            TeacherBlock,
            and_(
                TeacherBlock.teacher_id == StoreItem.teacher_id,
                TeacherBlock.block == StoreItemBlock.block,
            ),
        )
        .filter(
            or_(
                StoreItem.id.is_(None),
                TeacherBlock.id.is_(None),
            )
        )
        .distinct()
        .subquery()
    )

    orphaned_entries = db.session.query(
        orphaned_entries_subq.c.store_item_id,
        orphaned_entries_subq.c.block,
    ).all()

    if not orphaned_entries:
        print("No orphaned StoreItemBlock entries found.")
        return 0

    print(f"Found {len(orphaned_entries)} orphaned StoreItemBlock entries:")
    for store_item_id, block in orphaned_entries:
        print(f"  - StoreItem ID {store_item_id}, Block '{block}'")

    try:
        deleted_count = (
            StoreItemBlock.query
            .filter(
                tuple_(StoreItemBlock.store_item_id, StoreItemBlock.block).in_(
                    db.session.query(
                        orphaned_entries_subq.c.store_item_id,
                        orphaned_entries_subq.c.block,
                    )
                )
            )
            .delete(synchronize_session=False)
        )
        db.session.commit()
        print(f"\nSuccessfully deleted {deleted_count} orphaned StoreItemBlock entries.")
        return deleted_count
    except Exception as exc:
        db.session.rollback()
        print(f"Cleanup failed: {exc}")
        raise

if __name__ == "__main__":
    cleanup_orphaned_store_blocks()

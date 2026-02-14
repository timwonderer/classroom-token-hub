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

def cleanup_orphaned_store_blocks():
    """Remove StoreItemBlock entries for non-existent classes."""
    
    # Get all unique blocks from StoreItemBlock
    all_store_blocks = db.session.query(
        StoreItemBlock.store_item_id,
        StoreItemBlock.block
    ).distinct().all()
    
    orphaned_entries = []
    
    for store_item_id, block in all_store_blocks:
        # Get the teacher_id for this store item
        store_item = db.session.get(StoreItem, store_item_id)
        if not store_item:
            # Store item doesn't exist, this is orphaned
            orphaned_entries.append((store_item_id, block))
            continue
        
        # Check if a TeacherBlock exists for this teacher and block
        teacher_block_exists = TeacherBlock.query.filter_by(
            teacher_id=store_item.teacher_id,
            block=block
        ).first() is not None
        
        if not teacher_block_exists:
            orphaned_entries.append((store_item_id, block))
    
    if not orphaned_entries:
        print("No orphaned StoreItemBlock entries found.")
        return 0
    
    print(f"Found {len(orphaned_entries)} orphaned StoreItemBlock entries:")
    for store_item_id, block in orphaned_entries:
        print(f"  - StoreItem ID {store_item_id}, Block '{block}'")
    
    # Delete orphaned entries
    deleted_count = 0
    for store_item_id, block in orphaned_entries:
        result = StoreItemBlock.query.filter_by(
            store_item_id=store_item_id,
            block=block
        ).delete()
        deleted_count += result
    
    db.session.commit()
    print(f"\nSuccessfully deleted {deleted_count} orphaned StoreItemBlock entries.")
    return deleted_count

if __name__ == "__main__":
    cleanup_orphaned_store_blocks()

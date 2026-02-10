#!/usr/bin/env python3
"""
Cleanup script for duplicate auto-tap-out events.

This script identifies and soft-deletes duplicate "Daily limit reached" tap-out events
that were created due to the race condition bug. It keeps the FIRST tap-out event
and marks all subsequent duplicates as deleted.

Usage:
    python cleanup_duplicate_tapouts.py --student-id 357
    python cleanup_duplicate_tapouts.py --all --dry-run
"""

import argparse
from datetime import datetime
from app import create_app, db
from app.models import TapEvent


def find_duplicate_tapouts(student_id=None):
    """
    Find duplicate daily limit tap-out events.

    Returns a dict mapping (student_id, period, date) -> list of duplicate TapEvent objects
    """
    query = TapEvent.query.filter(
        TapEvent.status == "inactive",
        TapEvent.reason.like("Daily limit%"),
        TapEvent.is_deleted == False
    )

    if student_id:
        query = query.filter(TapEvent.student_id == student_id)

    # Get all daily limit tap-outs
    tapouts = query.order_by(TapEvent.student_id, TapEvent.period, TapEvent.timestamp).all()

    # Group by (student_id, period, date)
    grouped = {}
    for tapout in tapouts:
        # Get the date in UTC
        date = tapout.timestamp.date() if hasattr(tapout.timestamp, 'date') else datetime.fromisoformat(str(tapout.timestamp)).date()
        key = (tapout.student_id, tapout.period, date)

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(tapout)

    # Filter to only groups with duplicates
    duplicates = {k: v for k, v in grouped.items() if len(v) > 1}

    return duplicates


def cleanup_duplicates(duplicates, dry_run=True):
    """
    Clean up duplicate tap-out events.
    Keeps the first one (by timestamp) and soft-deletes the rest.
    """
    stats = {
        'total_groups': len(duplicates),
        'total_duplicates': 0,
        'deleted': 0
    }

    for (student_id, period, date), events in duplicates.items():
        # Sort by timestamp to keep the earliest
        events_sorted = sorted(events, key=lambda e: e.timestamp)
        keep = events_sorted[0]
        delete = events_sorted[1:]

        stats['total_duplicates'] += len(delete)

        print(f"\n{'='*80}")
        print(f"Student ID: {student_id}, Period: {period}, Date: {date}")
        print(f"Found {len(events)} tap-out events with same reason:")
        print(f"  KEEPING: ID={keep.id}, Timestamp={keep.timestamp}, Reason={keep.reason}")

        for dup in delete:
            print(f"  DELETE:  ID={dup.id}, Timestamp={dup.timestamp}, Reason={dup.reason}")

            if not dry_run:
                dup.is_deleted = True
                stats['deleted'] += 1

    if not dry_run:
        try:
            db.session.commit()
            print(f"\n✅ Successfully marked {stats['deleted']} duplicate events as deleted")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing changes: {e}")
            stats['deleted'] = 0

    return stats


def main():
    parser = argparse.ArgumentParser(description='Clean up duplicate auto-tap-out events')
    parser.add_argument('--student-id', type=int, help='Clean up duplicates for specific student')
    parser.add_argument('--all', action='store_true', help='Clean up duplicates for all students')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview changes without modifying database (default)')
    parser.add_argument('--execute', action='store_true', help='Actually modify the database')

    args = parser.parse_args()

    if not args.student_id and not args.all:
        parser.error("Must specify either --student-id or --all")

    dry_run = not args.execute

    app = create_app()
    with app.app_context():
        print("🔍 Searching for duplicate daily limit tap-out events...")

        duplicates = find_duplicate_tapouts(student_id=args.student_id)

        if not duplicates:
            print("\n✅ No duplicates found!")
            return

        print(f"\n⚠️  Found {len(duplicates)} groups with duplicate tap-outs")

        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
            print("   Run with --execute to actually modify the database\n")
        else:
            print("\n⚠️  EXECUTE MODE - Changes will be committed to database!\n")
            confirm = input("Are you sure you want to proceed? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled.")
                return

        stats = cleanup_duplicates(duplicates, dry_run=dry_run)

        print(f"\n{'='*80}")
        print("Summary:")
        print(f"  Total groups with duplicates: {stats['total_groups']}")
        print(f"  Total duplicate events found: {stats['total_duplicates']}")
        print(f"  Events marked as deleted: {stats['deleted']}")

        if dry_run:
            print("\n💡 Run with --execute to apply these changes")


if __name__ == '__main__':
    main()

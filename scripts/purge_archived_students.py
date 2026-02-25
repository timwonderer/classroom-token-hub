#!/usr/bin/env python3
"""
One-time cleanup for legacy archived students.

This removes Student rows where is_active is False and deletes dependent records.
It also removes any StudentTeacher links first so the student can be hard-deleted.

Default mode is dry-run. Use --apply to persist changes.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Student, StudentTeacher
from app.utils.student_deletion import hard_delete_student_if_orphaned


def purge_archived_students(apply: bool, limit: int | None = None) -> int:
    with create_app().app_context():
        query = Student.query.filter(Student.is_active.is_(False)).order_by(Student.id.asc())
        if limit is not None:
            query = query.limit(limit)
        archived_students = query.all()

        if not archived_students:
            print("No legacy archived students found (is_active=false).")
            return 0

        print(f"Found {len(archived_students)} archived student(s).")
        if not apply:
            print("Dry-run only. No data will be modified.")

        deleted_count = 0
        for student in archived_students:
            link_count = StudentTeacher.query.filter_by(student_id=student.id).count()
            print(
                f"- student_id={student.id} name={student.full_name} links={link_count}"
            )
            if not apply:
                continue

            StudentTeacher.query.filter_by(student_id=student.id).delete(synchronize_session=False)
            deleted = hard_delete_student_if_orphaned(student.id)
            if deleted:
                deleted_count += 1
            else:
                print(f"  ! skipped student_id={student.id} (still linked unexpectedly)")

        if apply:
            db.session.commit()
            print(f"Deleted {deleted_count} archived student(s).")
        return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Purge legacy archived students (is_active=false).")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. If omitted, runs in dry-run mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of archived students to process.",
    )
    args = parser.parse_args()

    purge_archived_students(apply=args.apply, limit=args.limit)


if __name__ == "__main__":
    main()

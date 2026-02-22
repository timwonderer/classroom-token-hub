"""
Regression tests for the class deletion audit fixes (2026-02-21).

Covers:
  - P1: BalanceCache rows are deleted when a join code is hard-deleted
  - P2: Sysadmin period deletion uses join_code scope, not legacy Student.block
  - P3: PayrollSettings / RentSettings are cleaned up when the last join code
        for a block name is deleted

See docs/security/CLASS_DELETION_AUDIT.md for the full audit report.
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import (
    Admin,
    Student,
    StudentTeacher,
    TeacherBlock,
    BalanceCache,
    PayrollSettings,
    RentSettings,
    SystemAdmin,
    StudentBlock,
)
from app.hash_utils import get_random_salt, hash_hmac


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _create_teacher(username: str) -> tuple[Admin, str]:
    secret = pyotp.random_base32()
    teacher = Admin(username=username, totp_secret=secret)
    db.session.add(teacher)
    db.session.commit()
    return teacher, secret


def _create_sysadmin(username: str = "sysadmin-audit") -> tuple[SystemAdmin, str]:
    secret = pyotp.random_base32()
    sa = SystemAdmin(username=username, totp_secret=secret)
    db.session.add(sa)
    db.session.commit()
    return sa, secret


def _create_student(teacher: Admin, first_name: str, block: str, join_code: str) -> Student:
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)

    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        dob_sum=2025,
    )
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=first_name[0].upper(),
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=join_code,
        is_claimed=True,
        student_id=student.id,
    ))
    db.session.commit()
    return student


def _login_teacher(client, teacher: Admin, secret: str):
    client.post(
        "/admin/login",
        data={"username": teacher.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str):
    client.post(
        "/sysadmin/login",
        data={"username": sysadmin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# P1: BalanceCache is deleted on join-code hard-delete
# ---------------------------------------------------------------------------

def test_balance_cache_deleted_when_join_code_deleted(client):
    """BalanceCache rows for a deleted join code must not survive."""
    teacher, secret = _create_teacher("teacher-bc-del")
    student = _create_student(teacher, "Alice", "A", "BCDEL1")

    cache = BalanceCache(
        student_id=student.id,
        join_code="BCDEL1",
        posted_checking_balance_cents=5000,
        posted_savings_balance_cents=1000,
    )
    db.session.add(cache)
    db.session.commit()
    cache_id = cache.id

    _login_teacher(client, teacher, secret)
    resp = client.post(
        "/admin/join-code/delete",
        json={"join_code": "BCDEL1"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"

    # BalanceCache row must be gone
    assert db.session.get(BalanceCache, cache_id) is None


def test_balance_cache_for_other_join_code_not_deleted(client):
    """BalanceCache for a different join code must survive when only one class is deleted."""
    teacher, secret = _create_teacher("teacher-bc-keep")
    student_a = _create_student(teacher, "Alice", "A", "BCDEL2")
    student_b = _create_student(teacher, "Bob", "B", "BCKEEP2")

    cache_del = BalanceCache(
        student_id=student_a.id,
        join_code="BCDEL2",
        posted_checking_balance_cents=1000,
        posted_savings_balance_cents=0,
    )
    cache_keep = BalanceCache(
        student_id=student_b.id,
        join_code="BCKEEP2",
        posted_checking_balance_cents=2000,
        posted_savings_balance_cents=500,
    )
    db.session.add_all([cache_del, cache_keep])
    db.session.commit()
    keep_id = cache_keep.id

    _login_teacher(client, teacher, secret)
    resp = client.post("/admin/join-code/delete", json={"join_code": "BCDEL2"})
    assert resp.get_json()["status"] == "success"

    # BCKEEP2 cache row must still be present
    assert db.session.get(BalanceCache, keep_id) is not None


# ---------------------------------------------------------------------------
# P2: Sysadmin period deletion uses join_code scope
# ---------------------------------------------------------------------------

def test_sysadmin_period_deletion_finds_students_via_join_code(client):
    """
    Sysadmin period deletion must use TeacherBlock.join_code to find enrolled
    students, not the deprecated Student.block field.

    Setup: student enrolled in block "Z" with join_code "SZJC1", but
    Student.block intentionally left as "" (empty) to prove the fix doesn't
    rely on it.
    """
    teacher, _ = _create_teacher("teacher-sz-jc")
    sysadmin, sys_secret = _create_sysadmin("sysadmin-sz")

    # Create student whose Student.block does NOT match the period name
    salt = get_random_salt()
    fhh = hash_hmac(b"A2025", salt)
    student = Student(
        first_name="Zara",
        last_initial="Z",
        block="",          # deliberately does NOT equal "Z"
        salt=salt,
        first_half_hash=fhh,
        dob_sum=2025,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="Z",
        first_name="Zara",
        last_initial="Z",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=fhh,
        join_code="SZJC1",
        is_claimed=True,
        student_id=student.id,
    ))
    db.session.commit()
    teacher.last_login = None
    db.session.commit()

    st_link_id = StudentTeacher.query.filter_by(
        student_id=student.id, admin_id=teacher.id
    ).first().id

    _login_sysadmin(client, sysadmin, sys_secret)
    resp = client.post(
        f"/sysadmin/delete-period/{teacher.id}/Z",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # TeacherBlock must be gone
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="Z").count() == 0

    # StudentTeacher link must also be gone (student has no other classes with this teacher)
    assert db.session.get(StudentTeacher, st_link_id) is None


def test_sysadmin_period_deletion_preserves_link_for_multi_period_student(client):
    """
    When a student is enrolled in two periods (A and B) with the same teacher
    and sysadmin deletes period A, the StudentTeacher link must be preserved
    because the student is still in period B.
    """
    teacher, _ = _create_teacher("teacher-mp-del")
    sysadmin, sys_secret = _create_sysadmin("sysadmin-mp")

    student = _create_student(teacher, "Sam", "A", "MPJC1A")

    # Add a second TeacherBlock seat for the same student in period B
    salt2 = get_random_salt()
    fhh2 = hash_hmac(b"S2025", salt2)
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name="Sam",
        last_initial="S",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt2,
        first_half_hash=fhh2,
        join_code="MPJC1B",
        is_claimed=True,
        student_id=student.id,
    ))
    db.session.commit()
    teacher.last_login = None
    db.session.commit()

    st = StudentTeacher.query.filter_by(
        student_id=student.id, admin_id=teacher.id
    ).first()
    st_id = st.id

    _login_sysadmin(client, sysadmin, sys_secret)
    resp = client.post(
        f"/sysadmin/delete-period/{teacher.id}/A",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Period A TeacherBlock gone
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").count() == 0

    # Period B TeacherBlock still present
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="B").count() == 1

    # StudentTeacher link preserved (student still has period B)
    assert db.session.get(StudentTeacher, st_id) is not None


# ---------------------------------------------------------------------------
# P3: Settings orphan cleanup on join-code deletion
# ---------------------------------------------------------------------------

def test_payroll_settings_deleted_when_last_join_code_for_block_removed(client):
    """PayrollSettings for block 'A' must be removed when no TeacherBlock remains for it."""
    teacher, secret = _create_teacher("teacher-ps-del")
    _create_student(teacher, "Pam", "A", "PSDEL1")

    ps = PayrollSettings(teacher_id=teacher.id, block="A", pay_rate=0.25)
    db.session.add(ps)
    db.session.commit()
    ps_id = ps.id

    _login_teacher(client, teacher, secret)
    resp = client.post("/admin/join-code/delete", json={"join_code": "PSDEL1"})
    assert resp.get_json()["status"] == "success"

    # PayrollSettings for block A should be gone (no more TeacherBlock for it)
    assert db.session.get(PayrollSettings, ps_id) is None


def test_rent_settings_deleted_when_last_join_code_for_block_removed(client):
    """RentSettings for block 'A' must be removed when no TeacherBlock remains for it."""
    teacher, secret = _create_teacher("teacher-rs-del")
    _create_student(teacher, "Raj", "A", "RSDEL1")

    rs = RentSettings(teacher_id=teacher.id, block="A", rent_amount=50)
    db.session.add(rs)
    db.session.commit()
    rs_id = rs.id

    _login_teacher(client, teacher, secret)
    resp = client.post("/admin/join-code/delete", json={"join_code": "RSDEL1"})
    assert resp.get_json()["status"] == "success"

    assert db.session.get(RentSettings, rs_id) is None


def test_payroll_settings_preserved_when_other_join_code_for_block_exists(client):
    """
    PayrollSettings for block 'A' must NOT be deleted if the teacher still has
    another join code under that same block name.
    """
    teacher, secret = _create_teacher("teacher-ps-keep")
    _create_student(teacher, "Pat", "A", "PSKP1")  # will be deleted

    # Add a second seat in the same block A but different join code
    salt2 = get_random_salt()
    fhh2 = hash_hmac(b"P2025", salt2)
    student2 = Student(
        first_name="Paula",
        last_initial="P",
        block="A",
        salt=salt2,
        first_half_hash=fhh2,
        dob_sum=2025,
    )
    db.session.add(student2)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student2.id, admin_id=teacher.id))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Paula",
        last_initial="P",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt2,
        first_half_hash=fhh2,
        join_code="PSKP2",  # different join code, same block
        is_claimed=True,
        student_id=student2.id,
    ))
    db.session.commit()

    ps = PayrollSettings(teacher_id=teacher.id, block="A", pay_rate=0.50)
    db.session.add(ps)
    db.session.commit()
    ps_id = ps.id

    _login_teacher(client, teacher, secret)
    # Delete only PSKP1 — PSKP2 still exists for block A
    resp = client.post("/admin/join-code/delete", json={"join_code": "PSKP1"})
    assert resp.get_json()["status"] == "success"

    # PayrollSettings must still be there (block A still has PSKP2)
    assert db.session.get(PayrollSettings, ps_id) is not None

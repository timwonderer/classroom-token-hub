"""Tests verifying settings helpers refuse to fall back to missing scoped rows.

After the settings fallback hardening, all settings helpers must:
- Return None (banking, rent) or system defaults (features) when no
  join-code-scoped settings exist for the student's class context.
"""
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import (
    Admin,
    BankingSettings,
    ClassEconomy,
    ClassMembership,
    FeatureSettings,
    RentSettings,
    Student,
    StudentTeacher,
    TeacherBlock,
)
from app.routes.student import (
    get_banking_settings_for_context,
    get_feature_settings_for_student,
    get_rent_settings_for_context,
)


@pytest.fixture
def teacher_with_legacy_and_scoped_settings(client):
    """Create a teacher with no scoped settings rows for the active class."""
    teacher = Admin(username="fallback_test_teacher", totp_secret="secret")
    db.session.add(teacher)
    db.session.flush()

    student = Student(
        first_name="Fallback",
        last_initial="T",
        block="A",
        salt=b"salt",
    )
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))

    join_code = "FALL01"
    economy = ClassEconomy(join_code=join_code, teacher_id=teacher.id, status="active", created_by_admin_id=teacher.id)
    db.session.add(economy)
    db.session.add(ClassMembership(join_code=join_code, admin_id=teacher.id, role="admin", status="active"))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        is_claimed=True,
        student_id=student.id,
        first_name="Fallback",
        last_initial="T",
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b"salt",
        first_half_hash="hash",
    ))

    # Legacy teacher-global rows are still allowed on banking/rent in the current schema.
    db.session.add(BankingSettings(
        teacher_id=teacher.id,
        join_code=None,
        overdraft_protection_enabled=True,
        savings_apy=5.0,
    ))
    db.session.add(RentSettings(
        teacher_id=teacher.id,
        join_code=None,
        block=None,
        is_enabled=True,
        rent_amount=100.0,
    ))

    db.session.commit()
    return {
        "teacher": teacher,
        "student": student,
        "join_code": join_code,
        "class_id": economy.class_id,
    }


# ---- Banking Settings ----

def test_banking_settings_ignores_legacy_global_row(client, teacher_with_legacy_and_scoped_settings):
    """When no join-code-scoped BankingSettings exist, helper returns None — not the legacy row."""
    data = teacher_with_legacy_and_scoped_settings
    context = {"join_code": data["join_code"], "teacher_id": data["teacher"].id}

    result = get_banking_settings_for_context(context)
    # Only legacy row exists (join_code=None) — helper must NOT return it
    assert result is None


def test_banking_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When a join-code-scoped BankingSettings exists, helper returns it."""
    data = teacher_with_legacy_and_scoped_settings
    db.session.add(BankingSettings(
        teacher_id=data["teacher"].id,
        join_code=data["join_code"],
        overdraft_protection_enabled=False,
        savings_apy=0,
    ))
    db.session.commit()

    context = {"join_code": data["join_code"], "teacher_id": data["teacher"].id}
    result = get_banking_settings_for_context(context)
    assert result is not None
    assert result.join_code == data["join_code"]
    assert result.overdraft_protection_enabled is False


def test_banking_settings_returns_none_for_missing_context(client):
    """Helper returns None when context is None or missing join_code."""
    assert get_banking_settings_for_context(None) is None
    assert get_banking_settings_for_context({}) is None
    assert get_banking_settings_for_context({"teacher_id": 999}) is None


# ---- Rent Settings ----

def test_rent_settings_ignores_legacy_global_row(client, teacher_with_legacy_and_scoped_settings):
    """When no join-code-scoped RentSettings exist, helper returns None — not the legacy row."""
    data = teacher_with_legacy_and_scoped_settings
    context = {"join_code": data["join_code"], "teacher_id": data["teacher"].id}

    result = get_rent_settings_for_context(context)
    assert result is None


def test_rent_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When a join-code-scoped RentSettings exists, helper returns it."""
    data = teacher_with_legacy_and_scoped_settings
    db.session.add(RentSettings(
        teacher_id=data["teacher"].id,
        join_code=data["join_code"],
        block="A",
        is_enabled=True,
        rent_amount=50.0,
    ))
    db.session.commit()

    context = {"join_code": data["join_code"], "teacher_id": data["teacher"].id}
    result = get_rent_settings_for_context(context)
    assert result is not None
    assert result.join_code == data["join_code"]
    assert float(result.rent_amount) == 50.0


# ---- Feature Settings ----

def test_feature_settings_returns_defaults_without_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When no join-code-scoped FeatureSettings exist, helper returns defaults."""
    data = teacher_with_legacy_and_scoped_settings

    with client.application.test_request_context():
        from flask import session as flask_session
        flask_session["student_id"] = data["student"].id
        flask_session["current_join_code"] = data["join_code"]

        result = get_feature_settings_for_student()

    # Should return system defaults, NOT the legacy teacher-global row
    defaults = FeatureSettings.get_defaults()
    assert result == defaults


def test_feature_settings_returns_scoped_row(client, teacher_with_legacy_and_scoped_settings):
    """When a join-code-scoped FeatureSettings exists, helper returns it."""
    data = teacher_with_legacy_and_scoped_settings
    db.session.add(FeatureSettings(
        teacher_id=data["teacher"].id,
        join_code=data["join_code"],
        class_id=data["class_id"],
        block="A",
        banking_enabled=False,
        store_enabled=False,
        insurance_enabled=False,
        rent_enabled=False,
        hall_pass_enabled=False,
        payroll_enabled=False,
    ))
    db.session.commit()

    with client.application.test_request_context():
        from flask import session as flask_session
        flask_session["student_id"] = data["student"].id
        flask_session["current_join_code"] = data["join_code"]

        result = get_feature_settings_for_student()

    # Should return the scoped row with all features disabled
    assert result["banking_enabled"] is False
    assert result["store_enabled"] is False

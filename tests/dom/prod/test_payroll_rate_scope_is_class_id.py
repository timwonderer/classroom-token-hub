"""Payroll rate and daily-limit resolution is scoped by `class_id` alone.

INV-ARC-014 §V forbids execution depending on "labels, sections, periods"; only
canonical identifiers may carry runtime authority. The payroll readers violated
this: they filtered `PayrollSettings` on `(class_id, block)`, matching `block`
against `ClassEconomy.section`.

That is not a cross-tenant leak — `class_id` was on every query — and it is not
what the readiness tracker anticipated when it asked whether the code "can select
the wrong rate." The defect runs the other way, and it is worse for being quiet:

`uq_payroll_settings_active_scope` is UNIQUE on `class_id` alone WHERE
`availability_state = 'IN_USE'`, so a class has *exactly one* selectable policy
row. The reader then asked for `block = <section>`, and on a miss fell back to
`block IS NULL`. Whenever the single row's `block` was a non-null string that did
not equal the class's section, **both queries missed the only row that existed**
and every seat in the class was paid the hardcoded `DEFAULT_PAY_RATE_PER_SECOND`
instead of the configured rate. No error, no log — just wrong money.

Three routes into that state, none of them exotic:

1. `ClassEconomy.section` is mutable. Configure payroll, then rename the section.
2. `block` is in `PayrollSettings._FROZEN_POLICY_FIELDS`, so it is submittable and
   carried forward from the predecessor on every subsequent submission — a stale
   value propagates forward untouched and is never revalidated.
3. Rows predating the class_id-only scope.

The writer was already canonical: `upsert_payroll_settings` scopes by `class_id`
alone, and the model's own `__table_args__` comment states that `block` "is
display metadata and is never a scoping key." Only the readers were stale, so the
writer and the reader disagreed about what identified a policy.

These tests fail against the pre-fix commit, where a mismatched `block` label
silently substitutes the default rate for the configured one.
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, PayrollSettings
from app.payroll import (
    DEFAULT_PAY_RATE_PER_SECOND_DECIMAL,
    _get_batch_pay_rates,
    get_daily_limit_seconds,
    get_pay_rate_for_class,
)
from app.services.payroll_settings_service import upsert_payroll_settings
from tests.helpers.classroom_initializer import initialize

CONFIGURED_RATE_PER_MINUTE = Decimal("2.00")
CONFIGURED_RATE_PER_SECOND = CONFIGURED_RATE_PER_MINUTE / Decimal("60")


def _submit(class_id, **settings_data) -> PayrollSettings:
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"payroll:scope:{class_id}:{sorted(settings_data.items())}",
    ):
        setting = upsert_payroll_settings(class_id=class_id, settings_data=settings_data)
        db.session.flush()
    return setting


def _set_section(class_id, section):
    """Set the class's display section label."""
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"class:section:{class_id}:{section}",
    ):
        row = ClassEconomy.query.filter_by(class_id=class_id).one()
        row.section = section
        db.session.flush()


def _retire_all_payroll_policies(class_id):
    """Leave the class with no selectable payroll policy.

    The classroom initializer provisions one, so "unconfigured" has to be
    arranged rather than assumed.
    """
    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"payroll:retire-all:{class_id}",
    ):
        for row in PayrollSettings.query.filter_by(
            class_id=class_id, availability_state="IN_USE"
        ).all():
            row.availability_state = "RETIRED"
        db.session.flush()


def test_the_configured_rate_survives_a_block_label_that_matches_no_section(app):
    """The regression. A stale label must not cost the class its pay rate.

    The row is IN_USE, class-scoped, and carries a real rate. Under the old
    reader, `block='A'` against `section='B'` missed the block-specific query,
    then missed the `block IS NULL` fallback, and returned the hardcoded default.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _set_section(classroom.class_id, "B")
        _submit(classroom.class_id, pay_rate=CONFIGURED_RATE_PER_MINUTE, block="A")

        resolved = get_pay_rate_for_class(class_id=classroom.class_id)

        assert resolved == CONFIGURED_RATE_PER_SECOND
        assert resolved != DEFAULT_PAY_RATE_PER_SECOND_DECIMAL, (
            "a mismatched display label silently substituted the default rate"
        )


def test_renaming_the_section_after_configuring_payroll_does_not_change_pay(app):
    """The most reachable route into the bug: an ordinary rename.

    Nothing about renaming a section is a payroll operation, so nothing warns the
    teacher that it just repriced every student in the class.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _set_section(classroom.class_id, "A")
        _submit(classroom.class_id, pay_rate=CONFIGURED_RATE_PER_MINUTE, block="A")
        before = get_pay_rate_for_class(class_id=classroom.class_id)

        _set_section(classroom.class_id, "RENAMED")
        after = get_pay_rate_for_class(class_id=classroom.class_id)

        assert before == CONFIGURED_RATE_PER_SECOND
        assert after == before, "a display-only rename repriced the class"


def test_the_daily_limit_survives_the_same_mismatch(app):
    """`get_daily_limit_seconds` shared the reader and so shared the defect.

    Its failure mode is the more permissive one: a missed row reads as "no limit
    configured," so the cap silently stops being enforced.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _set_section(classroom.class_id, "B")
        _submit(
            classroom.class_id,
            pay_rate=CONFIGURED_RATE_PER_MINUTE,
            block="A",
            settings_mode="simple",
            daily_limit_hours=Decimal("2"),
        )

        assert get_daily_limit_seconds(class_id=classroom.class_id) == 2 * 3600


def test_a_class_with_no_section_label_still_resolves_its_configured_rate(app):
    """A class need not carry a section label to have a pay rate."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _set_section(classroom.class_id, None)
        _submit(classroom.class_id, pay_rate=CONFIGURED_RATE_PER_MINUTE)

        assert get_pay_rate_for_class(class_id=classroom.class_id) == CONFIGURED_RATE_PER_SECOND


def test_the_batch_reader_agrees_with_the_single_class_reader(app):
    """`calculate_payroll_breakdown` prices via the batch map, not the scalar read.

    Two readers of the same policy that disagree would pay a student one amount
    and show them another, so the agreement is the property worth pinning — not
    either value on its own.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _set_section(classroom.class_id, "B")
        _submit(classroom.class_id, pay_rate=CONFIGURED_RATE_PER_MINUTE, block="A")

        batch = _get_batch_pay_rates([classroom.class_id])
        scalar = get_pay_rate_for_class(class_id=classroom.class_id)

        assert batch[classroom.class_id] == scalar == CONFIGURED_RATE_PER_SECOND


def test_an_unconfigured_class_still_falls_back_to_the_default(app):
    """The fallback is still reachable — it just is not reachable by accident."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _retire_all_payroll_policies(classroom.class_id)
        assert PayrollSettings.query.filter_by(
            class_id=classroom.class_id, availability_state="IN_USE"
        ).count() == 0

        assert (
            get_pay_rate_for_class(class_id=classroom.class_id)
            == DEFAULT_PAY_RATE_PER_SECOND_DECIMAL
        )
        assert get_daily_limit_seconds(class_id=classroom.class_id) is None

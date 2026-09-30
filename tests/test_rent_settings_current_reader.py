"""The current rent policy is the newest recorded version.

``get_rent_settings`` resolves the policy for new work, and operational paths
(the overdue purchase gate, cycle creation, legacy payment) read it. Ordering it
by a forward-dated ``rent_effective_at`` let an older row outrank the newest one.

A rent policy binds when a period is issued (DOM-OBL-001 §V.7), so the newest row
governs the first period issued after it is recorded, and every period already
issued keeps the ``policy_uuid`` it froze. ``rent_effective_at`` records the start
of that first period: a change saved mid-period is dated to the next boundary
(DOM-CLASS-003 §VII, operator ruling 2026-09-30) and is still the row new work
takes — it is never outranked by the date on it.
"""

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.services.admin_settings_service import supersede_rent_settings
from app.services.class_configuration_query_service import get_rent_settings
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import customize_rent_settings


def test_newest_recorded_rent_policy_is_current(app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        first = customize_rent_settings(classroom.class_id, rent_amount=Decimal("40.00"))
        second = customize_rent_settings(classroom.class_id, rent_amount=Decimal("45.00"))
        db.session.commit()

        current = get_rent_settings(classroom.class_id)
        assert current.policy_uuid == second.policy_uuid
        assert current.policy_uuid != first.policy_uuid
        assert current.rent_amount == Decimal("45.00")
        assert current.rent_effective_at == current.rent_configured_at


def test_a_row_dated_to_the_next_boundary_is_the_row_for_new_work(app):
    """The date records when the row first governs; it never demotes the row."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        customize_rent_settings(classroom.class_id, rent_amount=Decimal("40.00"))
        boundary = utc_now() + timedelta(days=5)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"rent-dated:{classroom.class_id}"):
            dated = supersede_rent_settings(
                class_id=classroom.class_id,
                updates={"rent_amount": Decimal("45.00")},
                effective_at=boundary,
            )
        db.session.commit()

        current = get_rent_settings(classroom.class_id)
        assert current.policy_uuid == dated.policy_uuid
        assert current.rent_effective_at == boundary

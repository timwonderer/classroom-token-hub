"""The current rent policy is the newest recorded version, in force at once.

``get_rent_settings`` resolves the policy for new work, and operational paths
(the overdue purchase gate, cycle creation, legacy payment) read it. Ordering it
by a forward-dated ``rent_effective_at`` let a row describing future terms be
read as current. A deferred economic change is a PolicyTransition activated at
an operational boundary (FEAT-ECON-001 §VII-VIII), never a row dated forward,
so a superseding version is in force from the moment it is recorded.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.services.admin_settings_service import supersede_rent_settings
from app.services.class_configuration_query_service import get_rent_settings
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


def test_rent_supersession_cannot_be_dated_forward():
    with pytest.raises(TypeError):
        supersede_rent_settings(class_id="any", updates={}, effective_at=None)

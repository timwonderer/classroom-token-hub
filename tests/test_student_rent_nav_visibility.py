"""The rent nav must survive another obligation family sharing bill_cycles.

``bill_cycles`` carries every recurring obligation, discriminated by
``internal_ref``. The rent policy lookup selected the class's newest cycle row
regardless of family, so once a student bought insurance the insurance cycle
won the ordering and its ``policy_uuid`` -- an ``InsurancePolicy`` -- resolved
to no ``RentSettings``. Rent then read as unconfigured and the nav link
disappeared from a class that had rent fully set up.

Both families mint ``cycle_number = 1`` at genesis, so the old
``ORDER BY cycle_number DESC, id DESC`` decided the winner on insert order --
whichever obligation the class adopted second silently took over rent's lookup.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.extensions import db
from app.feats.establish_bill_cycle_feat import execute_establish_bill_cycle
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.canonical_classroom import login_student, provision_classroom
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature

pytestmark = [pytest.mark.regression]


def test_rent_nav_survives_an_insurance_bill_cycle(client, app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        class_id = classroom.class_id
        enable_class_feature(class_id=class_id, feature="rent")
        enable_class_feature(class_id=class_id, feature="insurance")
        rent_policy = customize_rent_settings(class_id, rent_amount=50)
        rent_policy_uuid = rent_policy.policy_uuid
        db.session.commit()

        now = utc_now()

        execute_establish_bill_cycle(
            class_id=class_id,
            internal_ref=f"rent:{class_id}",
            cycle_boundary_at=now,
            next_assessment_at=now + timedelta(days=7),
            policy_uuid=rent_policy_uuid,
        )
        db.session.commit()

        # The insurance lineage lands second, so its row wins any ordering that
        # is not discriminated by internal_ref.
        insurance_policy_uuid = str(uuid.uuid4())
        execute_establish_bill_cycle(
            class_id=class_id,
            internal_ref=(
                f"insurance:{student.seat_id}:{insurance_policy_uuid}"
                f":ins:{uuid.uuid4().hex}"
            ),
            cycle_boundary_at=now,
            next_assessment_at=now + timedelta(days=30),
            policy_uuid=insurance_policy_uuid,
        )
        db.session.commit()

        login_student(client, student)

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    assert "/student/rent" in response.get_data(as_text=True)

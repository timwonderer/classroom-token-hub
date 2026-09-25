"""A student can pay an overdue insurance premium — FEAT-STOR-007 §V.

A premium whose automatic payment failed stays outstanding, and the student may
pay it at any later time (FEAT-STOR-007 §V). The route is passphrase-confirmed
(FEAT-IDEN-002 credential boundary) and stays reachable after insurance is
disabled while a premium survives (DOM-OBL-001 §IX.16).

The premium lineage is built on the renewal tests' controlled 2027 clock; the
HTTP requests run on the real clock, which payment does not depend on.
"""

from __future__ import annotations

from datetime import timedelta

from tests.helpers.canonical_classroom import login_student
from tests.helpers.class_domain import disable_class_feature
from tests.test_insurance_coverage_renewal_feat import PREVIEW_2, PURCHASE, local, world  # noqa: F401


def _overdue(world):
    """Purchase paid; the advance premium for period 2 failed autopay."""
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))  # exactly the first premium
    w.buy()
    w.renew(PREVIEW_2)
    assert w.premium_state(2).is_outstanding
    return w


def _pay(client, w, passphrase):
    return client.post(
        f"/student/insurance/policy/{w.policy_uuid}/pay-premium",
        data={"passphrase": passphrase},
    )


def test_student_pays_an_overdue_premium_with_their_passphrase(client, world):
    w = _overdue(world)
    w.fund(local(1, 15))
    login_student(client, w.student)

    response = _pay(client, w, w.student.passphrase)

    assert response.status_code == 302
    assert w.premium_state(2).is_satisfied


def test_premium_payment_refuses_a_wrong_passphrase(client, world):
    w = _overdue(world)
    w.fund(local(1, 15))
    login_student(client, w.student)

    _pay(client, w, "not-the-passphrase")

    assert w.premium_state(2).is_outstanding


def test_overdue_premium_stays_payable_after_insurance_is_disabled(client, world):
    w = _overdue(world)
    w.fund(local(1, 15))
    disable_class_feature(class_id=w.class_id, feature="insurance")
    login_student(client, w.student)

    response = _pay(client, w, w.student.passphrase)

    assert response.status_code == 302
    assert w.premium_state(2).is_satisfied

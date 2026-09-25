"""Policies reads that other domains consume by ``policy_uuid`` (DOM-POL-001 §VII).

A downstream fact frozen by reference resolves its terms from the exact
immutable policy version it carries. These reads take that ``policy_uuid`` and
answer one question each, so a consumer never opens a policy-family table or
branches on the family (DOM-POL-001A §V.E).
"""

from __future__ import annotations

from app.extensions import db
from app.models import InsurancePolicy, RentSettings


class PolicyReferenceNotFound(LookupError):
    """No policy version with this ``policy_uuid`` exists in the class."""


def get_bill_preview_days(policy_uuid: str, *, class_id: str) -> int:
    """The bill preview interval, in class-local calendar days, of one policy version.

    It is the interval before a period's coverage boundary at which that
    period's obligation is assessed and becomes payable (DOM-OBL-001 §V.7).
    ``0`` means the obligation is assessed at the boundary itself.

    Resolves the exact version identified by ``policy_uuid``, never a newer or
    active row of the same family. Raises ``PolicyReferenceNotFound`` when no
    version with that ``policy_uuid`` exists in the class.
    """
    rent = (
        db.session.query(RentSettings)
        .filter_by(policy_uuid=policy_uuid, class_id=class_id)
        .one_or_none()
    )
    if rent is not None:
        if not rent.bill_preview_enabled:
            return 0
        return max(0, int(rent.bill_preview_days or 0))

    insurance = (
        db.session.query(InsurancePolicy)
        .filter_by(policy_uuid=policy_uuid, class_id=class_id)
        .one_or_none()
    )
    if insurance is not None:
        return max(0, int(getattr(insurance, "bill_preview_days", None) or 0))

    raise PolicyReferenceNotFound(
        f"no policy version {policy_uuid!r} in class {class_id!r}"
    )

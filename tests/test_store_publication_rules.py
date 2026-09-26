"""Store publication rules follow SPEC-STORE-001, and the form offers the same.

``store_service._validate_definition`` is the one seam that writes a product, so
a rule it gets wrong is wrong everywhere. Two had drifted from the schema: a
privilege's expiry check read the raw ``direct_purchase_allowed`` key rather
than its resolved default, and redemption prompts were accepted on collective
goals and refused on hall passes, the opposite of §IV.C.
"""

import pytest

from app.services import store_service
from app.services.store.form_contract import resolve_store_form_contract

pytestmark = [pytest.mark.regression]


def _definition(**overrides):
    definition = {
        "name": "Rule Probe",
        "item_type": "delayed",
        "economic_role": "necessity",
        "price": "5.00",
    }
    definition.update(overrides)
    return definition


def test_privilege_expiry_uses_the_resolved_purchase_mode():
    """An omitted direct_purchase_allowed means directly purchasable."""
    with pytest.raises(store_service.InvalidDefinition, match="expiration duration"):
        store_service._validate_definition(_definition(item_type="privilege"))


@pytest.mark.parametrize("item_type", ["delayed", "hall_pass"])
def test_redemption_prompt_is_accepted_on_delayed_use_and_hall_pass(item_type):
    store_service._validate_definition(
        _definition(item_type=item_type, redemption_prompt="Which class period?")
    )


@pytest.mark.parametrize("item_type", ["collective", "immediate", "privilege"])
def test_redemption_prompt_is_refused_on_other_types(item_type):
    with pytest.raises(store_service.InvalidDefinition, match="redemption prompt"):
        store_service._validate_definition(
            _definition(item_type=item_type, redemption_prompt="Tell us more", auto_expiry_days=7)
        )


def test_form_contract_offers_the_prompt_on_exactly_those_types():
    expected = {"delayed": True, "hall_pass": True, "collective": False, "immediate": False, "privilege": False}
    for item_type, promptable in expected.items():
        legal = resolve_store_form_contract(
            item_type=item_type, rent_linked=False, direct_purchase=True,
            rent_prevents_purchase_when_late=False,
        ).legal_fields
        assert ("redemption_prompt" in legal) is promptable, item_type
        assert store_service.item_type_field_rules()[item_type]["promptable"] is promptable, item_type

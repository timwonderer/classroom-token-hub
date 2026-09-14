"""The Store item form's gating script, exercised in a real browser.

``tests/test_store_item_type_field_gating.py`` proves the server ships the right
contracts and renders a wrapper for every legal field. Neither proves that
``static/js/store_item_type_gating.js`` applies them: a script that never ran, or
that hid a control without disabling it, would leave both green. This drives the
real script in Chromium against the form the app actually renders, and checks
what a teacher sees and what the browser would submit.

Only the rendered form, its contract catalogue and the gating script are loaded,
so the page needs no network; the script depends on nothing else. Playwright and
Chromium are environment-dependent, so their absence skips rather than fails.
"""

import re
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None

from app.extensions import db
from app.feats.base import FEATContext
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")

GATING_SCRIPT = (
    Path(__file__).resolve().parent.parent / "static" / "js" / "store_item_type_gating.js"
).read_text(encoding="utf-8")

_READ_STATE = """() => {
  const form = document.querySelector('form[data-store-item-form]');
  const wrappers = [...form.querySelectorAll('[data-contract-field]')];
  const controls = wrapper => [...wrapper.querySelectorAll('input, select, textarea')]
    .filter(control => control.type !== 'hidden');
  return {
    shown: wrappers.filter(w => !w.hidden).map(w => w.dataset.contractField).sort(),
    enabledWhileHidden: wrappers.filter(w => w.hidden)
      .flatMap(w => controls(w).filter(c => !c.disabled).map(c => c.name)),
    disabledWhileShown: wrappers.filter(w => !w.hidden)
      .flatMap(w => controls(w).filter(c => c.disabled).map(c => c.name)),
    submitted: [...new FormData(form).keys()],
  };
}"""


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")
        with browser:
            yield browser.new_page()


def _load_form(page, body):
    form = re.search(r"<form[^>]*data-store-item-form.*?</form>", body, re.DOTALL)
    contracts = re.search(
        r'<script id="storeFormContracts" type="application/json">.*?</script>', body, re.DOTALL
    )
    assert form and contracts, "page does not render the Store item form and its contracts"
    page.set_content(
        "<!doctype html><html><body>"
        f"{form.group(0)}{contracts.group(0)}<script>{GATING_SCRIPT}</script>"
        "</body></html>"
    )
    return page.evaluate(
        "() => JSON.parse(document.getElementById('storeFormContracts').textContent)"
    )


def _unconditional_legal_fields(contract):
    """Legal fields not waiting on a dependency; every toggle starts unset on create."""
    return sorted(
        field["name"]
        for section in contract["sections"]
        for field in section["fields"]
        if not field.get("depends_on")
    )


def _store_teacher(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()
    return classroom


def test_create_form_shows_enables_and_submits_exactly_each_contract(client, page):
    """Every reachable contract state: what is shown is what is legal, and only it is sent."""
    _store_teacher(client)
    contracts = _load_form(page, client.get("/admin/store").get_data(as_text=True))

    checked_states = 0
    for key, contract in contracts.items():
        item_type, linked, direct = key.split("|")
        if linked == "1" and "is_rent_linked" not in contracts[f"{item_type}|0|1"]["legal_fields"]:
            continue  # no teacher can reach a rent-linked state for this type
        page.select_option('[name="item_type"]', item_type)
        if "is_rent_linked" in contracts[f"{item_type}|0|1"]["legal_fields"]:
            page.set_checked('[name="is_rent_linked"]', linked == "1")
        if linked == "1":
            page.set_checked('[name="direct_purchase_allowed"]', direct == "1")

        state = page.evaluate(_READ_STATE)
        expected = _unconditional_legal_fields(contract)
        assert state["shown"] == expected, key
        assert state["enabledWhileHidden"] == [], key
        assert state["disabledWhileShown"] == [], key
        illegal = {
            name for name in state["submitted"]
            if name not in contract["legal_fields"] and name != "csrf_token"
        }
        assert not illegal, (key, illegal)
        checked_states += 1

    assert checked_states >= len(contracts) - 2  # only collective's rent-linked keys are unreachable


def test_a_value_made_illegal_by_a_type_change_is_cleared_and_not_submitted(client, page):
    _store_teacher(client)
    _load_form(page, client.get("/admin/store").get_data(as_text=True))

    page.select_option('[name="item_type"]', "delayed")
    page.check('[name="is_bundle"]')
    page.fill('[name="bundle_quantity"]', "3")
    page.select_option('[name="item_type"]', "immediate")

    assert page.is_disabled('[name="is_bundle"]')
    assert not page.is_checked('[name="is_bundle"]')
    assert page.input_value('[name="bundle_quantity"]') == ""
    submitted = page.evaluate(_READ_STATE)["submitted"]
    assert "is_bundle" not in submitted and "bundle_quantity" not in submitted


def test_a_dependency_toggle_hides_without_discarding_the_value(client, page):
    """Unchecking a feature hides its settings; it is not an illegal item configuration."""
    _store_teacher(client)
    _load_form(page, client.get("/admin/store").get_data(as_text=True))

    page.select_option('[name="item_type"]', "delayed")
    page.check('[name="is_bundle"]')
    page.fill('[name="bundle_quantity"]', "3")
    page.uncheck('[name="is_bundle"]')

    assert page.is_disabled('[name="bundle_quantity"]')
    assert page.input_value('[name="bundle_quantity"]') == "3"
    page.check('[name="is_bundle"]')
    assert page.is_enabled('[name="bundle_quantity"]')
    assert page.input_value('[name="bundle_quantity"]') == "3"


def test_edit_form_applies_the_contract_and_keeps_persisted_values(client, page):
    classroom = _store_teacher(client)
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"gating-browser:edit:{classroom.class_id}"):
        item = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            user_id=classroom.teacher_user.id,
            name="Snack Pack",
            price="25.00",
            is_bundle=True,
            bundle_quantity=3,
        )

    contracts = _load_form(
        page, client.get(f"/admin/store/edit/{item.product_lineage_uuid}").get_data(as_text=True)
    )
    state = page.evaluate(_READ_STATE)

    expected = sorted(set(_unconditional_legal_fields(contracts["delayed|0|1"])) | {"bundle_quantity"})
    assert state["shown"] == expected
    assert state["enabledWhileHidden"] == []
    assert state["disabledWhileShown"] == []
    assert page.input_value('[name="name"]') == "Snack Pack"
    assert float(page.input_value('[name="price"]')) == 25.0
    assert page.is_checked('[name="is_bundle"]')
    assert page.input_value('[name="bundle_quantity"]') == "3"

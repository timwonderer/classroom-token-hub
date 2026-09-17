"""Regression: the Store admin surface must not mount the rent recommendation panel.

The Store "Add New Item" (and "Edit Item") forms previously mounted the generic
economy-balance ``displayCWIInfo()`` renderer on an ``#cwi-info`` container. That
renderer is rent-specific: it hardcodes the word "rent", a "per month" cadence,
and the rent CWI band. Rendering it on the Store form produced a nonsensical rent
pricing recommendation on a store item. The fix REMOVED the rent panel from the
composition source rather than repurposing it.

Store guidance has its own lawful shape, and it must survive that removal:

* SPEC-ECON-003 §4.9 maps the Store surface to the unified CWI Helper
  (``INCOME_SHARE`` and ``PURCHASE_SCENARIO``). On the form that is live price
  feedback: the price input carries ``data-economy-validate="store_item"`` and
  the checker renders into ``#economy-warnings``.
* SPEC-ECON-003 §4.7 gives each economic role an advisory reference band. The
  ``data-economic-role-select`` control drives ``#role-recommendation``.

The Basic/Standard/Premium/Luxury pricing tier and its ``#tier-recommendation``
container were retired for the economic role (SPEC-STORE-001 v1.1), so the tier
container is asserted absent rather than preserved.

This test asserts:
  * neither Store surface mounts the ``#cwi-info`` rent panel container,
  * the store item form script does not invoke ``displayCWIInfo`` (composition source),
  * while both surfaces mount the Store Helper and economic-role guidance, with the
    scripts that bind them.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.extensions import db
from app.feats.base import FEATContext
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.store_products import publish_store_product


REPO_ROOT = Path(__file__).resolve().parents[3]


def _assert_store_guidance_mounted(body: str, path: str) -> None:
    # The rent recommendation container must NOT be mounted on the Store form.
    assert 'id="cwi-info"' not in body, path
    # The retired pricing-tier guidance must not come back either.
    assert 'id="tier-recommendation"' not in body, path

    # Unified CWI Helper, live price feedback (SPEC-ECON-003 §4.9).
    assert 'data-economy-validate="store_item"' in body, path
    assert 'id="economy-warnings"' in body, path
    # Economic-role reference band (SPEC-ECON-003 §4.7).
    assert 'data-economic-role-select="true"' in body, path
    assert 'id="role-recommendation"' in body, path

    # Markup alone binds nothing. item-form-economy.js returns early without
    # #economy-data or without EconomyBalanceChecker from economy-balance.js.
    assert 'id="economy-data"' in body, path
    assert "js/economy-balance.js" in body, path
    assert "js/item-form-economy.js" in body, path


def test_DOM_CLASS_001__store_surface_does_not_mount_rent_cwi_panel(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")

    response = client.get("/admin/store")
    assert response.status_code == 200

    _assert_store_guidance_mounted(response.get_data(as_text=True), "/admin/store")


def test_DOM_CLASS_001__store_item_form_script_does_not_invoke_rent_renderer():
    """Composition-source guard: the store item form script must not call the
    rent-specific ``displayCWIInfo()`` renderer. Removing the mount only from the
    template would let the defect return via any future container named #cwi-info."""
    script = (REPO_ROOT / "static" / "js" / "item-form-economy.js").read_text()

    assert "displayCWIInfo" not in script, (
        "item-form-economy.js must not invoke the rent-specific displayCWIInfo() "
        "renderer on the Store surface"
    )
    assert "tier-recommendation" not in script

    # The Store guidance wiring must remain: the Helper renders into
    # #economy-warnings, and the economic role select drives the reference band
    # from the engine's store_roles recommendations.
    assert re.search(r"warningsContainer:\s*['\"]#economy-warnings['\"]", script)
    assert "[data-economic-role-select]" in script
    assert "role-recommendation" in script
    assert "store_roles" in script


def test_DOM_CLASS_001__store_edit_surface_does_not_mount_rent_cwi_panel(client):
    """The Edit Item surface shares the same form partial and must also be clean.

    Checked on the rendered page, not the template source: admin_edit_item.html
    holds only the ``render_store_item_contract`` call, so its source can show
    neither the guidance containers nor their absence.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    db.session.commit()
    with FEATContext(
        "FEAT-SETTINGS-001",
        idempotency_key=f"store_surface_no_rent_panel:item:{classroom.class_id}",
    ):
        item = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="IMMEDIATE_USE",
            created_by_seat_id=classroom.teacher_seat.id,
            name="Homework Pass",
            description="Skip one homework assignment",
            price="25.00",
        )

    path = f"/admin/store/edit/{item.product_lineage_uuid}"
    response = client.get(path)
    assert response.status_code == 200

    _assert_store_guidance_mounted(response.get_data(as_text=True), path)

    edit_template = (REPO_ROOT / "templates" / "admin_edit_item.html").read_text()
    assert 'id="cwi-info"' not in edit_template
    assert "render_store_item_contract" in edit_template

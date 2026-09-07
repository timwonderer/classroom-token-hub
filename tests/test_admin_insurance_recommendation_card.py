"""The insurance policy form surfaces Economic Engine recommendations as a card.

The engine's advisory values (SPEC-ECON-003 §4.5) are precomputed at GET time and
embedded so the form can reactively show suggested starting values per insurance
type and tier. This exercises the real admin ingress end to end.
"""
from __future__ import annotations

import json
import re

from tests.helpers.canonical_classroom import provision_classroom, login_teacher
from tests.helpers.class_domain import enable_class_feature


def _get_new_form(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        login_teacher(client, classroom)
    return client.get("/admin/insurance/new")


def _rec_blob(html):
    m = re.search(
        r'<script type="application/json" id="insurance-rec-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert m, "recommendation JSON blob missing from form"
    return json.loads(m.group(1))


def test_form_renders_recommendation_card(app, client):
    resp = _get_new_form(app, client)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Economic Engine recommendation" in html
    assert 'id="rec-card"' in html


def test_recommendation_blob_carries_all_products_and_tiers(app, client):
    resp = _get_new_form(app, client)
    rec = _rec_blob(resp.get_data(as_text=True))

    assert set(rec.keys()) >= {"ready", "mode", "products"}
    products = rec["products"]
    assert set(products.keys()) == {"TRANSACTION", "PRODUCTIVITY", "NON_MONETARY"}
    for tiers in products.values():
        assert set(tiers.keys()) == {"single", "basic", "mid", "premium"}


def test_recommendation_reimbursement_is_percent_units(app, client):
    """Engine fractions (0.60) are surfaced as form-facing percent (60), and the
    per-type field shape matches the form (NON_MONETARY carries no reimbursement)."""
    resp = _get_new_form(app, client)
    rec = _rec_blob(resp.get_data(as_text=True))
    if not rec["ready"]:
        # Without a CWI the engine degrades gracefully; nothing to assert on units.
        return

    txn_premium = rec["products"]["TRANSACTION"]["premium"]
    assert txn_premium["reimbursement_percentage"] == 80.0
    assert txn_premium["payout_multiple"] == 5.0
    assert txn_premium["max_payout"] is not None

    non_monetary = rec["products"]["NON_MONETARY"]["mid"]
    assert non_monetary["reimbursement_percentage"] is None
    assert non_monetary["waiting_period_days"] is not None

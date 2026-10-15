"""Economic Engine Helper for insurance authoring (SPEC-ECON-003 §4.4.8, §4.9)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import economic_engine as ee
from app.services import insurance_premium_helper as helper_mod
from app.services.insurance_premium_helper import build_insurance_premium_helper
from tests.helpers.canonical_classroom import provision_classroom

CWI = Decimal("200.00")


@pytest.fixture
def class_id(app, monkeypatch):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        base = ee.resolve_base(classroom.class_id)
        monkeypatch.setattr(ee, "resolve_base", lambda cid: replace(base, cwi=CWI, economy_policy_mode="default"))
        yield classroom.class_id


def test_weekly_recommendation_follows_tier_band_position(class_id):
    weekly = build_insurance_premium_helper(class_id)["frequencies"]["WEEKLY"]
    # default band 5%–12% CWI; §4.4.8: Basic = bottom, Mid/Single = midpoint, Premium = top.
    assert weekly["recommended"] == {"single": 17.0, "basic": 10.0, "mid": 17.0, "premium": 24.0}
    assert (weekly["band_min"], weekly["band_max"], weekly["income"]) == (10.0, 24.0, 200.0)


def test_monthly_uses_30_day_authoring_normalization(class_id):
    monthly = build_insurance_premium_helper(class_id)["frequencies"]["MONTHLY"]
    # 17.00 × 30/7 = 72.857… → 72.86
    assert monthly["recommended"]["mid"] == 72.86
    assert monthly["income"] == 857.14


def _weekly_rent_row(monkeypatch, *, enabled):
    monkeypatch.setattr(helper_mod, "is_feature_enabled", lambda cid, feature: enabled and feature == "rent")
    monkeypatch.setattr(helper_mod, "get_rent_settings", lambda cid: SimpleNamespace(
        rent_amount=Decimal("70.00"), frequency_type="weekly",
        custom_frequency_value=None, custom_frequency_unit=None))


def test_rent_is_scaled_to_each_billing_frequency(class_id, monkeypatch):
    _weekly_rent_row(monkeypatch, enabled=True)
    assert build_insurance_premium_helper(class_id)["rent"] == {"WEEKLY": 70.0, "MONTHLY": 300.0}


def test_retained_rent_row_ignored_while_rent_is_off(class_id, monkeypatch):
    _weekly_rent_row(monkeypatch, enabled=False)
    assert build_insurance_premium_helper(class_id)["rent"] is None


def test_no_rent_settings_means_no_remaining_after(class_id, monkeypatch):
    monkeypatch.setattr(helper_mod, "get_rent_settings", lambda cid: None)
    assert build_insurance_premium_helper(class_id)["rent"] is None


@pytest.mark.parametrize("cwi", [None, Decimal("0.00"), Decimal("-5.00")])
def test_helper_absent_without_positive_cwi(app, monkeypatch, cwi):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        base = ee.resolve_base(classroom.class_id)
        monkeypatch.setattr(ee, "resolve_base", lambda cid: replace(base, cwi=cwi))
        assert build_insurance_premium_helper(classroom.class_id) is None


def test_policy_form_embeds_helper(app, client, monkeypatch):
    from tests.helpers.canonical_classroom import login_teacher
    from tests.helpers.class_domain import enable_class_feature

    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        base = ee.resolve_base(classroom.class_id)
        login_teacher(client, classroom)

    # No CWI yet: the box explains what to set up instead of guessing.
    html = client.get("/admin/insurance/new").get_data(as_text=True)
    assert 'id="insurance-premium-helper"' in html
    assert "insurance-premium-helper-data" not in html

    monkeypatch.setattr(ee, "resolve_base", lambda cid: replace(base, cwi=CWI, economy_policy_mode="default"))
    html = client.get("/admin/insurance/new").get_data(as_text=True)
    assert 'id="insurance-premium-helper-data"' in html
    # Deferred, so it reads the tier controls rendered later in the form.
    assert '<script defer src="/static/js/insurance-premium-helper.js">' in html

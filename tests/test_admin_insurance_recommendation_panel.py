"""The teacher insurance policy form shows the Economic Engine's advisory recommendation.

The panel consumes FEAT-CLASS-003 ``recommend_insurance_terms`` (which wraps
``economic_engine.resolve_insurance``, SPEC-ECON-003 §4.4). Every assertion here
compares the rendered page against that producer for the same class rather than
against hardcoded numbers, so a spec amendment to the presets moves both sides.

Advisory only: nothing in the panel constrains a submission (FEAT-CLASS-003
enforces hard bounds only), and the GET that renders it performs no writes
(INV-ARC-007).
"""
from __future__ import annotations

import json
from decimal import Decimal

from bs4 import BeautifulSoup
from sqlalchemy import event

from app.extensions import db
from app.feats.class_configuration.feat_class_003_insurance_policy_management import (
    recommend_insurance_terms,
)
from app.models import EconomicEngine, InsurancePolicy
from tests.helpers.canonical_classroom import login_teacher, provision_classroom
from tests.helpers.class_domain import enable_class_feature, update_expected_weekly_hours
from tests.helpers.classroom_initializer import initialize_as_teacher

PRODUCTS = ("TRANSACTION", "PRODUCTIVITY", "NON_MONETARY")
TIERS = ("single", "basic", "mid", "premium")


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

def _teacher_with_insurance(client, app, *, key="chemistry_p1", weekly_hours="5"):
    """Provision a class, enable insurance, and (optionally) make its CWI resolvable.

    Provisioned classes carry a payroll pay rate but no expected weekly hours, so
    the CWI is undefined until the teacher sets hours through the real route.
    """
    classroom = initialize_as_teacher(key, client, app)
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    if weekly_hours is not None:
        resp = update_expected_weekly_hours(client, weekly_hours)
        assert resp.status_code == 302
    return classroom


def _soup(resp):
    assert resp.status_code == 200, resp.status_code
    return BeautifulSoup(resp.get_data(as_text=True), "html.parser")


def _panel(soup):
    panel = soup.find(id="insurance-reco")
    assert panel is not None, "recommendation panel missing from the insurance form"
    return panel


def _blob(soup):
    node = soup.find("script", id="insurance-reco-data")
    assert node is not None, "recommendation JSON blob missing from the insurance form"
    assert node.get("type") == "application/json"
    return json.loads(node.string)


def _dec(value):
    return None if value is None else Decimal(str(value))


def _table(panel, product, layout):
    table = panel.find("table", attrs={"data-reco-product": product, "data-reco-layout": layout})
    assert table is not None, f"no {layout} table for {product}"
    return table


def _producer(class_id, product, tier):
    return recommend_insurance_terms(class_id=class_id, insurance_type=product, tier=tier)


# --------------------------------------------------------------------------- #
# new form                                                                    #
# --------------------------------------------------------------------------- #

def test_new_form_renders_panel_with_producer_values(client, app):
    classroom = _teacher_with_insurance(client, app)
    soup = _soup(client.get("/admin/insurance/new"))

    panel = _panel(soup)
    heading_id = panel.get("aria-labelledby")
    assert heading_id, "panel must be labelled by its heading"
    heading = soup.find(id=heading_id)
    assert heading is not None and heading.name in {"h3", "h4"}
    assert "Economic Engine recommendation" in heading.get_text(" ", strip=True)
    assert "Advisory" in panel.get_text(" ", strip=True)

    blob = _blob(soup)
    assert blob["ready"] is True
    single = _producer(classroom.class_id, "TRANSACTION", "single")
    assert _dec(blob["cwi"]) == single.cwi
    assert blob["mode"] == single.mode

    # The default type is TRANSACTION, ungrouped: that table is the one on show,
    # currency first, carrying the producer's weekly premium and payout ceiling.
    shown = _table(panel, "TRANSACTION", "single")
    assert not shown.has_attr("hidden")
    text = shown.get_text(" ", strip=True)
    assert f"${single.weekly_premium:.2f}" in text
    assert f"${single.maximum_policy_payout:.2f}" in text
    for product in PRODUCTS:
        for layout in ("single", "tiered"):
            if (product, layout) != ("TRANSACTION", "single"):
                assert _table(panel, product, layout).has_attr("hidden")


def test_blob_matches_producer_for_every_selectable_product_and_tier(client, app):
    classroom = _teacher_with_insurance(client, app)
    blob = _blob(_soup(client.get("/admin/insurance/new")))

    assert set(blob["products"]) == set(PRODUCTS)
    for product in PRODUCTS:
        assert set(blob["products"][product]["tiers"]) == set(TIERS)
        for tier in TIERS:
            res = _producer(classroom.class_id, product, tier)
            got = blob["products"][product]["tiers"][tier]
            assert _dec(got["weekly_premium"]) == res.weekly_premium
            assert _dec(got["premium_rate_percent"]) == res.recommended_premium_rate * 100
            assert _dec(got["maximum_policy_payout"]) == res.maximum_policy_payout
            assert _dec(got["payout_multiple"]) == res.payout_multiple
            assert got["claims_per_week_equivalent"] == res.claims_allowance_period
            assert got["claimable_dates_per_week_equivalent"] == res.claimable_days_period
            assert got["claim_window_days"] == res.claim_window_days
            assert got["waiting_period_days"] == res.waiting_period_days


def test_blob_units_match_the_form_fields(client, app):
    """Reimbursement is a percent (the form's field), not the engine's fraction."""
    classroom = _teacher_with_insurance(client, app)
    blob = _blob(_soup(client.get("/admin/insurance/new")))

    for product in ("TRANSACTION", "PRODUCTIVITY"):
        for tier in TIERS:
            res = _producer(classroom.class_id, product, tier)
            got = blob["products"][product]["tiers"][tier]
            assert res.reimbursement_percentage < 1  # engine fraction, e.g. 0.60
            assert _dec(got["reimbursement_percent"]) == res.reimbursement_percentage * 100
        low, high = _producer(classroom.class_id, product, "single").recommended_ranges["reimbursement_pct"]
        ranges = blob["products"][product]["ranges"]
        assert [_dec(v) for v in ranges["reimbursement_percent"]] == [low * 100, high * 100]

    # NON_MONETARY has no monetary coverage parameters at all (SPEC-ECON-003 §4.4.5).
    for tier in TIERS:
        got = blob["products"]["NON_MONETARY"]["tiers"][tier]
        assert got["reimbursement_percent"] is None
        assert got["payout_multiple"] is None
        assert got["maximum_policy_payout"] is None
        assert got["waiting_period_days"] is not None

    # The premium envelope is reported as a fraction of CWI in percent.
    rate_lo, rate_hi = _producer(classroom.class_id, "TRANSACTION", "single").recommended_ranges["premium_rate"]
    band = blob["products"]["TRANSACTION"]["ranges"]["premium_rate_percent"]
    assert [_dec(v) for v in band] == [rate_lo * 100, rate_hi * 100]


# --------------------------------------------------------------------------- #
# edit form + re-render                                                       #
# --------------------------------------------------------------------------- #

def test_edit_form_shows_the_existing_policys_type_and_tier(client, app):
    classroom = _teacher_with_insurance(client, app)
    created = client.post("/admin/insurance/new", data={
        "insurance_type": "PRODUCTIVITY", "premium": "5.00", "charge_frequency": "WEEKLY",
        "reimbursement_percentage": "60", "payout_multiple": "4",
        "claimable_dates_per_week_equivalent": "2",
        "title": "Lost wages", "tier_group": "__new__", "tier_group_new": "Paycheck", "tier_level": "2",
    }, follow_redirects=False)
    assert created.status_code == 302
    policy = InsurancePolicy.query.filter_by(class_id=classroom.class_id).one()

    soup = _soup(client.get(f"/admin/insurance/edit/{policy.policy_uuid}"))
    panel = _panel(soup)

    shown = _table(panel, "PRODUCTIVITY", "tiered")
    assert not shown.has_attr("hidden")
    assert _table(panel, "PRODUCTIVITY", "single").has_attr("hidden")
    assert _table(panel, "TRANSACTION", "single").has_attr("hidden")

    mid = _producer(classroom.class_id, "PRODUCTIVITY", "mid")
    assert f"${mid.weekly_premium:.2f}" in shown.get_text(" ", strip=True)

    # The tier being edited is marked in text, not by colour alone.
    markers = {
        m["data-reco-selected-marker"]: m.has_attr("hidden")
        for m in shown.find_all(attrs={"data-reco-selected-marker": True})
    }
    assert markers == {"basic": True, "mid": False, "premium": True}

    summary = panel.find(attrs={"aria-live": "polite"})
    assert summary is not None
    summary_text = summary.get_text(" ", strip=True)
    assert "Productivity" in summary_text and "Mid" in summary_text
    assert f"${mid.weekly_premium:.2f}" in summary_text


def test_rejected_submission_rerender_still_shows_panel(client, app):
    _teacher_with_insurance(client, app)
    resp = client.post("/admin/insurance/new", data={
        "insurance_type": "NON_MONETARY", "premium": "-1", "charge_frequency": "WEEKLY",
        "claims_per_week_equivalent": "1", "waiting_period_days": "3", "title": "Bad",
    }, follow_redirects=False)
    soup = _soup(resp)
    panel = _panel(soup)
    assert _blob(soup)["ready"] is True
    # The sticky resubmission keeps its type, so the panel follows it.
    assert not _table(panel, "NON_MONETARY", "single").has_attr("hidden")
    assert InsurancePolicy.query.count() == 0


def test_monthly_frequency_states_figures_are_week_equivalents(client, app):
    """A monthly premium depends on the covered month's length, which the form lacks."""
    _teacher_with_insurance(client, app)
    resp = client.post("/admin/insurance/new", data={
        "insurance_type": "TRANSACTION", "premium": "-1", "charge_frequency": "MONTHLY",
        "reimbursement_percentage": "60", "payout_multiple": "4",
        "claims_per_week_equivalent": "2", "claim_window_days": "7", "title": "Bad",
    }, follow_redirects=False)
    panel = _panel(_soup(resp))
    note = panel.find(attrs={"data-reco-monthly-note": True})
    assert note is not None and not note.has_attr("hidden")
    assert "week-equivalent" in note.get_text(" ", strip=True)


# --------------------------------------------------------------------------- #
# degradation, purity, isolation                                              #
# --------------------------------------------------------------------------- #

def test_class_without_cwi_degrades_to_a_setup_note(client, app):
    classroom = _teacher_with_insurance(client, app, weekly_hours=None)
    assert _producer(classroom.class_id, "TRANSACTION", "single").cwi is None

    soup = _soup(client.get("/admin/insurance/new"))
    panel = _panel(soup)
    blob = _blob(soup)
    assert blob["ready"] is False
    assert blob["cwi"] is None

    note = panel.find(attrs={"data-reco-not-ready": True})
    assert note is not None
    hrefs = {a.get("href") for a in note.find_all("a")}
    assert "/admin/economic-engine" in hrefs
    assert "/admin/payroll" in hrefs
    # WCAG 1.4.1 (axe link-in-text-block): links inside a sentence need a cue
    # besides colour, so they carry an underline.
    for link in note.find_all("a"):
        assert "text-decoration-underline" in (link.get("class") or []), link

    # No invented currency, but the CWI-independent coverage terms still show.
    shown = _table(panel, "TRANSACTION", "single")
    text = shown.get_text(" ", strip=True)
    assert "$" not in text
    res = _producer(classroom.class_id, "TRANSACTION", "single")
    assert f"{res.reimbursement_percentage * 100:.0f}%" in text


def test_get_performs_no_writes(client, app):
    classroom = _teacher_with_insurance(client, app)
    engines_before = EconomicEngine.query.filter_by(class_id=classroom.class_id).count()
    mutations = []

    def _record(session, _flush_context, _instances):
        if session.new or session.dirty or session.deleted:
            mutations.append((list(session.new), list(session.dirty), list(session.deleted)))

    # insert=True: observe the flush before the app's own FEAT flush guard can
    # raise on it, so a regression fails here naming the write, not as a bare 500.
    event.listen(db.session, "before_flush", _record, insert=True)
    try:
        resp = client.get("/admin/insurance/new")
    finally:
        event.remove(db.session, "before_flush", _record)

    assert mutations == []
    assert resp.status_code == 200
    assert EconomicEngine.query.filter_by(class_id=classroom.class_id).count() == engines_before
    assert InsurancePolicy.query.count() == 0


def test_panel_accessibility_structure(client, app):
    """INV-ARC-020: one polite live summary, captioned tables, marked scope, audited page."""
    from tests.test_accessibility import _audit_html_accessibility

    _teacher_with_insurance(client, app)
    resp = client.get("/admin/insurance/new")
    soup = _soup(resp)
    panel = _panel(soup)

    live = panel.find_all(attrs={"aria-live": True})
    assert len(live) == 1, "exactly one live region, so a change is announced once"
    assert live[0].get("aria-live") == "polite"
    assert live[0].find("table") is None, "tables must not sit inside the live region"

    tables = panel.find_all("table")
    assert len(tables) == len(PRODUCTS) * 2
    for table in tables:
        assert table.find("caption") is not None and table.caption.get_text(strip=True)
        for th in table.find_all("th"):
            assert th.get("scope") in {"row", "col"}

    assert 'style="' not in str(panel), "SPEC-DES-001: no inline style in the panel"
    _audit_html_accessibility(resp.get_data(as_text=True))


def test_panel_reflects_the_active_class_not_a_sibling_class(client, app):
    """Two periods of one teacher with different economic bases never cross."""
    first = _teacher_with_insurance(client, app, key="chemistry_p1", weekly_hours="5")

    second = provision_classroom("ap_csp_p3")
    assert second.teacher_user_id == first.teacher_user_id
    enable_class_feature(class_id=second.class_id, feature="insurance")
    login_teacher(client, second)
    assert update_expected_weekly_hours(client, "10").status_code == 302

    first_cwi = _producer(first.class_id, "TRANSACTION", "single").cwi
    second_cwi = _producer(second.class_id, "TRANSACTION", "single").cwi
    assert first_cwi is not None and second_cwi is not None and first_cwi != second_cwi

    blob = _blob(_soup(client.get("/admin/insurance/new")))
    assert _dec(blob["cwi"]) == second_cwi
    second_mid = _producer(second.class_id, "PRODUCTIVITY", "mid")
    assert _dec(blob["products"]["PRODUCTIVITY"]["tiers"]["mid"]["weekly_premium"]) == second_mid.weekly_premium

    login_teacher(client, first)
    blob = _blob(_soup(client.get("/admin/insurance/new")))
    assert _dec(blob["cwi"]) == first_cwi

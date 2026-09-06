"""The cross-domain gate must fail on real INV-ARC-021 defects and only on those.

`scripts/validate-cross-domain.py` is the sole evidence for the CI-XDOMAIN
family, which selects on `app/feats/**`, `app/services/**`, `app/models.py`, and
`migrations/**`. A false positive blocks most application PRs; a false negative
lets domain coupling reach the trunk under a green required check. Both
directions are covered here, as is the baseline's own decay.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_cross_domain", ROOT / "scripts" / "validate-cross-domain.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _tree(tmp_path, files):
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return validator.coordination_findings(tmp_path)


def _models(tmp_path, source):
    path = tmp_path / "models.py"
    path.write_text(source, encoding="utf-8")
    return validator.foreign_key_findings(path)


# --- §V.2 / §V.6 coordination direction -------------------------------------


def test_service_importing_a_coordination_feat_is_an_error(tmp_path):
    """§V.6: a domain service must not perform capability composition."""
    findings = _tree(tmp_path, {
        "app/services/rent_service.py": "from app.feats.obligations import assess\n",
    })
    assert findings == ["app/services/rent_service.py imports app.feats.obligations"]


def test_service_importing_the_feat_harness_is_allowed(tmp_path):
    """`app.feats.base` is the execution harness, not a coordination unit."""
    assert _tree(tmp_path, {
        "app/services/rent_service.py": "from app.feats.base import get_correlation_id\n",
    }) == []


def test_relative_feat_import_from_a_nested_service_is_resolved(tmp_path):
    """`from ..feats.prod import x` must resolve to the same absolute module."""
    findings = _tree(tmp_path, {
        "app/services/payroll/settlement.py": "from ...feats.prod import record\n",
    })
    assert findings == ["app/services/payroll/settlement.py imports app.feats.prod"]


def test_relative_harness_import_is_still_allowed(tmp_path):
    assert _tree(tmp_path, {
        "app/services/payroll/settlement.py": "from ...feats.base import get_correlation_id\n",
    }) == []


@pytest.mark.parametrize("layer", ["services", "feats"])
def test_importing_a_route_inverts_the_layering(tmp_path, layer):
    findings = _tree(tmp_path, {
        f"app/{layer}/thing.py": "from app.routes.admin import bp\n",
    })
    assert findings == [f"app/{layer}/thing.py imports app.routes.admin"]


def test_feat_importing_a_feat_and_service_importing_a_service_are_allowed(tmp_path):
    """Coordination inside the FEAT layer, and intra-layer service reuse, are legal."""
    assert _tree(tmp_path, {
        "app/feats/store.py": "from app.feats.obligations import assess\n",
        "app/services/a.py": "from app.services.b import helper\n",
        "app/feats/ledger.py": "from app.services.ledger_service import balance\n",
    }) == []


def test_a_route_importing_a_feat_is_not_this_gates_question(tmp_path):
    """Route composition is CI-ARC-EXEC's surface; judging it here would duplicate."""
    assert _tree(tmp_path, {
        "app/routes/admin.py": "from app.feats.store import purchase\n",
    }) == []


def test_plain_import_statement_form_is_detected(tmp_path):
    findings = _tree(tmp_path, {
        "app/services/rent_service.py": "import app.feats.obligations\n",
    })
    assert findings == ["app/services/rent_service.py imports app.feats.obligations"]


# --- §V.7 cross-domain foreign keys -----------------------------------------


SHARED_ANCHOR_MODEL = """
class Thing(db.Model):
    __tablename__ = 'assessment_events'
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'))
    class_id = db.Column(UUID, db.ForeignKey('classes.class_id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
"""


def test_shared_anchor_targets_are_the_legal_cross_domain_edges(tmp_path):
    """§V.7 names class_id, seat_id, and user_id as the only legal targets."""
    assert _models(tmp_path, SHARED_ANCHOR_MODEL) == []


def test_foreign_key_across_a_domain_boundary_is_an_error(tmp_path):
    findings = _models(tmp_path, """
class Assessment(db.Model):
    __tablename__ = 'assessment_events'
    ledger_transaction_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id'))
""")
    assert findings == [
        "assessment_events.ledger_transaction_id -> ledger_transaction.id (DOM-OBL -> DOM-LED)"
    ]


def test_foreign_key_within_one_domain_is_allowed(tmp_path):
    """Both tables are DOM-OPS, so the edge crosses no boundary."""
    assert _models(tmp_path, """
class Incident(db.Model):
    __tablename__ = 'incident_events'
    audit_id = db.Column(db.Integer, db.ForeignKey('audit_events.id'))
""") == []


def test_self_referential_foreign_key_is_allowed(tmp_path):
    assert _models(tmp_path, """
class Issue(db.Model):
    __tablename__ = 'issues'
    parent_id = db.Column(db.Integer, db.ForeignKey('issues.id'))
""") == []


def test_a_table_missing_from_the_schema_definition_is_reported_not_assumed(tmp_path):
    """Unattributed ownership is a finding, never a silent pass."""
    findings = _models(tmp_path, """
class Mystery(db.Model):
    __tablename__ = 'not_in_dom_core_002'
    txn_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id'))
""")
    assert findings == [
        "not_in_dom_core_002.txn_id -> ledger_transaction.id: "
        "not_in_dom_core_002 has no domain attribution in DOM-CORE-002 §V"
    ]


def test_composite_foreign_key_constraint_form_is_extracted(tmp_path):
    """`__table_args__` constraints declare edges the inline form does not."""
    findings = _models(tmp_path, """
class Assessment(db.Model):
    __tablename__ = 'assessment_events'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['policy_version_id'], ['policy_versions.id']
        ),
    )
""")
    assert findings == [
        "assessment_events.policy_version_id -> policy_versions.id (DOM-OBL -> DOM-CLASS)"
    ]


# --- baseline behavior -------------------------------------------------------


def test_the_repository_currently_matches_its_declared_baseline():
    result = validator.evaluate()
    assert result["introduced"] == []
    assert result["resolved"] == []
    assert validator.main() == 0


def test_the_baseline_is_not_empty():
    """An empty baseline here would mean the check had nothing to compare against."""
    assert validator.BASELINE_COORDINATION
    assert validator.BASELINE_FOREIGN_KEYS


def test_every_baseline_entry_still_reproduces():
    """A baseline is an exemption list, and an exemption for a fixed defect is a
    filter that matches nothing — the failure class this CI system exists to catch."""
    observed = set(validator.coordination_findings()) | set(validator.foreign_key_findings())
    stale = (validator.BASELINE_COORDINATION | validator.BASELINE_FOREIGN_KEYS) - observed
    assert stale == set()


def test_a_new_violation_is_reported_as_introduced(monkeypatch, tmp_path):
    (tmp_path / "app" / "services").mkdir(parents=True)
    (tmp_path / "app" / "services" / "new.py").write_text(
        "from app.feats.store import purchase\n", encoding="utf-8"
    )
    (tmp_path / "app" / "models.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(validator, "BASELINE_COORDINATION", set())
    monkeypatch.setattr(validator, "BASELINE_FOREIGN_KEYS", set())
    result = validator.evaluate(tmp_path)
    assert result["introduced"] == ["app/services/new.py imports app.feats.store"]
    assert result["resolved"] == []


def test_a_baseline_entry_that_no_longer_reproduces_fails_the_gate(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    (tmp_path / "app" / "models.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(validator, "BASELINE_COORDINATION", {"app/services/gone.py imports app.feats.x"})
    monkeypatch.setattr(validator, "BASELINE_FOREIGN_KEYS", set())
    result = validator.evaluate(tmp_path)
    assert result["introduced"] == []
    assert result["resolved"] == ["app/services/gone.py imports app.feats.x"]

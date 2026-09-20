"""An assessment is recorded as an assessment, not as a rent payment.

`FEAT-OBLI-001` ("Assess Obligation") and `FEAT-OBL-001` ("Rent Payment") are
different workflows in the same domain whose ids differ by one letter. The
assessment entry point carried `@requires_feat_context("FEAT-OBL-001")`, so
everything it did was attributed to the payment workflow.

`INV-ARC-000` §VIII.2 takes a request's recorded domain, capability and action
from the FEAT it executes under, and `feat_code` on audit and ledger rows is
written from the active context (`app/models.py`, the `before_flush` hook). A
workflow executing under another workflow's id therefore produces lineage that
names the wrong action — an audit statement that is false, not untidy.

Scope: `execute_assess_obligation` has no production caller today. Rent and
insurance assessment reach `assess_obligation` directly from inside
`FEAT-OBL-002` and `FEAT-OBL-004`, which attribute correctly. The defect was
latent; these tests are what stop it becoming live the first time a route calls
the public entry point.
"""

import inspect

from app.extensions import db
from app.feats import assess_obligation_feat
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.base import FEAT_REGISTRY, get_active_feat_name
from app.models import ObligationAssessment
from tests.helpers.classroom_initializer import initialize


def test_the_registry_holds_both_workflows_separately():
    """Collapsing either id into the other would make the collision permanent."""
    assert FEAT_REGISTRY["FEAT-OBLI-001"]["desc"] == "Assess Obligation"
    assert FEAT_REGISTRY["FEAT-OBL-001"]["desc"] == "Rent Payment"
    assert FEAT_REGISTRY["FEAT-OBLI-001"]["domain"] == "Obligations"


def test_assessment_executes_under_its_own_feat(app, monkeypatch):
    """The regression: this read FEAT-OBL-001 before the fix."""
    classroom = initialize("chemistry_p1", app)

    with app.app_context():
        student = classroom.students[0]
        seen = {}
        original = assess_obligation_feat.assess_obligation

        def capture(request, *, context):
            seen["feat"] = get_active_feat_name()
            return original(request, context=context)

        monkeypatch.setattr(assess_obligation_feat, "assess_obligation", capture)

        execute_assess_obligation(
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            internal_ref="rent:monthly",
            correlation_id="attribution-assessment",
            obligation_type="RENT",
        )
        db.session.commit()

        assert seen["feat"] == "FEAT-OBLI-001"


def test_the_assessment_row_is_still_written(app):
    """FEAT-OBLI-001 §I: create the immutable ASSESSMENT event row.

    Re-attribution must move the label and nothing else.
    """
    classroom = initialize("chemistry_p1", app)

    with app.app_context():
        student = classroom.students[0]
        assessment = execute_assess_obligation(
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            internal_ref="rent:monthly",
            correlation_id="attribution-row",
            obligation_type="RENT",
        )
        db.session.commit()

        row = db.session.get(ObligationAssessment, assessment.id)
        assert row.event_type == "ASSESSMENT"
        assert row.class_id == classroom.class_id
        assert row.seat_id == student.seat.id
        assert row.ledger_transaction_id is None


def test_rent_payment_keeps_the_payment_feat():
    """The adjacent surface: the fix must not move rent payment's attribution."""
    from app.feats import rent_payment_feat

    source = inspect.getsource(rent_payment_feat)
    assert source.count('@requires_feat_context("FEAT-OBL-001")') == 2
    assert "FEAT-OBLI-001" not in source


def test_the_scheduled_cycles_keep_their_own_feats():
    """Rent and insurance assessment run inside their own workflows, unchanged.

    These are the production paths that actually write assessments, so a change
    to the assessment entry point must leave their attribution alone.
    """
    from app.feats import purchase_insurance_feat, reconcile_rent_feat

    assert '@requires_feat_context("FEAT-OBL-002")' in inspect.getsource(reconcile_rent_feat)
    assert '@requires_feat_context("FEAT-OBL-004")' in inspect.getsource(purchase_insurance_feat)

"""Forward-only insurance migration preserves payloads and explicit coverage continuity."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.extensions import db
from app.models import InsurancePolicy, InsuranceTierGroup
from app.feats.base import FEATContext
from app.services import insurance_definition_service as definitions
from app.services.insurance_configuration import _validate_and_build_definition
from tests.test_insurance_tier_purchase_exclusion import _setup, _buy
from tests.test_insurance_purchase_feat import _submission, _student_ctx
from app.feats.purchase_insurance_feat import execute_purchase_insurance


def migration(connection):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/c8f1a2b3d490_configuration_portability.py"
    spec = spec_from_file_location("configuration_migration", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


def test_successors_preserve_terms_and_exclude_held_predecessor(app):
    classroom = _setup(app)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="migration:seed"):
        old = definitions.create_insurance_definition(class_id=classroom.class_id,
            definition=_validate_and_build_definition(_submission(tier_group="Coverage", tier_level=1)),
            actor_seat_id=classroom.teacher_seat.id)
    old_id = old.policy_uuid
    assert _buy(classroom, old_id, "migration:purchase").success
    before = {column.name: getattr(old, column.name) for column in InsurancePolicy.__table__.columns}
    class_id = classroom.class_id
    student_context = _student_ctx(classroom)
    db.session.remove()
    with db.engine.begin() as connection:
        module = migration(connection)
        module.upgrade()
        module.upgrade()
    original = InsurancePolicy.query.filter_by(class_id=class_id, policy_uuid=old_id).one()
    successor = InsurancePolicy.query.filter_by(class_id=class_id, supersedes_policy_uuid=old_id).one()
    for field, value in before.items():
        if field not in {"availability_state", "retired_at"}:
            assert getattr(original, field) == value
        if field not in {"policy_uuid", "tier_group_id", "supersedes_policy_uuid", "created_at", "retired_at", "availability_state"}:
            assert getattr(successor, field) == value
    assert original.availability_state == "RETIRED"
    assert successor.tier_group_id
    assert InsuranceTierGroup.query.filter_by(class_id=class_id).count() == 1
    assert execute_purchase_insurance(canonical_context=student_context, policy_uuid=successor.policy_uuid, idempotency_key="migration:successor-purchase").error_code == "POLICY_ALREADY_HELD_IN_GROUP"


def test_migration_refuses_live_grouped_coverage_without_successor(app):
    import pytest
    classroom = _setup(app)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="migration:ambiguous-seed"):
        old = definitions.create_insurance_definition(class_id=classroom.class_id,
            definition=_validate_and_build_definition(_submission(tier_group="Coverage", tier_level=1)),
            actor_seat_id=classroom.teacher_seat.id)
    old_id = old.policy_uuid
    assert _buy(classroom, old_id, "migration:ambiguous-purchase").success
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="migration:retire"):
        definitions.retire_insurance_definition(class_id=classroom.class_id, policy_uuid=old_id)
    class_id = classroom.class_id
    db.session.remove()
    with pytest.raises(RuntimeError, match="explicit successor path"):
        with db.engine.begin() as connection:
            migration(connection).upgrade()
    assert InsuranceTierGroup.query.filter_by(class_id=class_id).count() == 0
    assert InsurancePolicy.query.filter_by(class_id=class_id).count() == 1

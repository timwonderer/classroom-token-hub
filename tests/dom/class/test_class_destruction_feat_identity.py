"""Class destruction has its own execution identity: FEAT-CLASS-006.

Destroying a class boundary used to execute under ``FEAT-CLASS-001``, whose
contract is class-boundary *creation*: its §III forbids executing within a
CanonicalContext because the target class does not yet exist, and its §X
guarantees only that a boundary is **established**. ``FEAT-IDEN-007``
§Composition designated it for destruction anyway, so two Normative documents
disagreed about what that FEAT was, and the runtime followed the wrong one.

Every request executes a single command path whose domain, capability and action
are recorded as part of its observability (INV-ARC-000 §VIII.2), and a FEAT names
a user-facing action rather than a bucket of vaguely related operations on one
table (INV-CORE-001). Destruction also carries semantics creation has no
analogue for: class-scoped data must not survive deletion of its ``class_id``
(INV-CORE-000 §26, §33), and a principal left holding no Seat anywhere cannot
exist (DOM-IDEN-005 §V.6, §VI). So the audit statement "this class was destroyed
by the create-a-class command" was not untidy — it was false.

``FEAT-CLASS-006`` now owns it, on both surfaces that reach it, and it is bounded
the same way teacher destruction is: the pre-FEAT read only selects the
executor, and the FEAT re-evaluates the authoritative state under its own locks,
failing closed without mutation when class destruction is no longer the lawful
result.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.extensions import db
from app.feats.base import FEAT_REGISTRY, FEATContext, get_active_feat_name
from app.models import ClassEconomy, Seat, StoreProduct, User
from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.store_products import publish_store_product

ADMIN_SOURCE = pathlib.Path(__file__).resolve().parents[3] / "app" / "routes" / "admin.py"

DESTRUCTION_ENTRY_POINTS = {
    # function name -> the FEAT that must own it
    "_hard_delete_class_scope": "FEAT-CLASS-006",
    "_execute_class_scope_deletion": "FEAT-CLASS-006",
    "_execute_account_scope_deletion": "FEAT-IDEN-007",
    "_execute_seat_deletion": "FEAT-IDEN-006",
}


def _class_delete_phrase(class_id: str) -> str:
    class_row = db.session.get(ClassEconomy, class_id)
    label = (class_row.display_name or "").strip() or class_row.join_code
    return f"DELETE {label}".upper()


def _add_store_item(class_id: str, name: str) -> str:
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"store-item:{class_id}:{name}"):
        product = publish_store_product(
            class_id=class_id, entitlement_type="IMMEDIATE_USE", name=name, price="5.00",
        )
    return product.policy_uuid


def _product_exists(policy_uuid: str) -> bool:
    return db.session.query(StoreProduct).filter_by(policy_uuid=policy_uuid).first() is not None


@pytest.fixture
def captured_class_destruction(monkeypatch):
    """Record the FEAT active while the class-scope teardown command runs.

    Both bindings of the command are wrapped. ``FEAT-CLASS-006`` reaches it
    through the admin module's reference, while ``FEAT-IDEN-007`` composes it
    through ``teacher_destruction``'s own module global — which is the point of
    its §Composition rule, so a fixture that watched only one binding would
    silently record nothing for the other path.
    """
    import app.routes.admin as admin_module
    import app.services.teacher_destruction as destruction_module

    seen: list[str | None] = []
    real = destruction_module._destroy_class_scope_rows

    def wrapper(*args, **kwargs):
        seen.append(get_active_feat_name())
        return real(*args, **kwargs)

    monkeypatch.setattr(admin_module, "_destroy_class_scope_rows", wrapper)
    monkeypatch.setattr(destruction_module, "_destroy_class_scope_rows", wrapper)
    return seen


# --------------------------------------------------------------------------
# Execution identity
# --------------------------------------------------------------------------

def test_the_feat_registry_separates_creating_a_class_from_destroying_one():
    """Two commands, two entries — and destruction is HIGH blast radius."""
    assert FEAT_REGISTRY["FEAT-CLASS-006"]["blast_radius"] == "HIGH"
    assert FEAT_REGISTRY["FEAT-CLASS-006"]["domain"] == "Class Configuration"
    create_desc = FEAT_REGISTRY["FEAT-CLASS-001"]["desc"].lower()
    destroy_desc = FEAT_REGISTRY["FEAT-CLASS-006"]["desc"].lower()
    assert "creat" in create_desc and "destroy" not in create_desc
    assert "destroy" in destroy_desc


def test_no_destruction_entry_point_is_declared_under_the_creation_feat():
    """Structural guard: the decorator on each destructive entry point.

    Runtime capture proves what happened on one path; this proves no destruction
    entry point is *declared* under FEAT-CLASS-001, including paths a given test
    run never reaches.
    """
    tree = ast.parse(ADMIN_SOURCE.read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in DESTRUCTION_ENTRY_POINTS:
            continue
        feats = [
            decorator.args[0].value
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and getattr(decorator.func, "id", None) == "requires_feat_context"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
        ]
        assert len(feats) == 1, f"{node.name} must declare exactly one FEAT, got {feats}"
        found[node.name] = feats[0]

    assert found == DESTRUCTION_ENTRY_POINTS, found
    assert "FEAT-CLASS-001" not in found.values()


def test_deleting_a_class_executes_under_feat_class_006(client, app, captured_class_destruction):
    """The join-code surface, with a sibling class so the principal survives."""
    sibling = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id
    assert sibling.teacher_user.id == teacher_user_id

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    assert captured_class_destruction == ["FEAT-CLASS-006"]
    assert "FEAT-CLASS-001" not in captured_class_destruction

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(User, teacher_user_id) is not None


def test_deleting_the_last_class_still_executes_under_teacher_destruction(client, app, captured_class_destruction):
    """FEAT-CLASS-006 must not absorb the case that destroys the principal."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json().get("account_deleted") is True

    # The class teardown ran as a composed domain command under FEAT-IDEN-007,
    # never under FEAT-CLASS-006 and never under FEAT-CLASS-001.
    assert captured_class_destruction == ["FEAT-IDEN-007"]

    db.session.expire_all()
    assert db.session.get(User, teacher_user_id) is None


def test_audit_lineage_names_the_destruction_feat_not_the_creation_feat(client, app, captured_class_destruction):
    """What `feat_code` and FEAT-ENTRY would record for a destroyed class."""
    initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    recorded = captured_class_destruction[0]
    assert recorded == "FEAT-CLASS-006"
    assert recorded != "FEAT-CLASS-001"
    assert FEAT_REGISTRY[recorded]["blast_radius"] == "HIGH"


# --------------------------------------------------------------------------
# Locked re-evaluation (FEAT-CLASS-006 §IV.2)
# --------------------------------------------------------------------------

def test_a_class_that_became_the_last_one_is_refused_not_destroyed(
    client, app, captured_class_destruction, monkeypatch
):
    """Dispatch selects the executor; the locked re-read decides.

    If the class becomes the principal's last between the pre-FEAT read and the
    locks, destroying it would leave a principal holding no Seat anywhere —
    DOM-IDEN-005 §V.6 and §VI, which grant teachers no exception. That command is
    FEAT-IDEN-007. FEAT-CLASS-006 must refuse without mutating anything rather
    than perform a destruction its own contract does not cover.
    """
    import app.routes.admin as admin_module

    sibling = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id

    real = admin_module._class_deletion_destroys_principal
    calls = {"n": 0}

    def survives_then_does_not(user_id, class_id):
        calls["n"] += 1
        # First call is the route's pre-FEAT read, which picks FEAT-CLASS-006.
        # By the time the FEAT holds its locks, this is the last class.
        return False if calls["n"] == 1 else True

    monkeypatch.setattr(admin_module, "_class_deletion_destroys_principal", survives_then_does_not)

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 409, response.get_data(as_text=True)
    assert "nothing was deleted" in response.get_json()["message"].lower()

    # It was re-evaluated inside the FEAT, and the teardown never began.
    assert calls["n"] >= 2
    assert captured_class_destruction == []

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is not None
    assert db.session.get(ClassEconomy, sibling.class_id) is not None
    assert db.session.get(User, teacher_user_id) is not None
    assert Seat.query.filter_by(class_id=classroom.class_id).count() > 0

    assert real is not None  # the real predicate is what production uses


# --------------------------------------------------------------------------
# Atomicity and hard-deletion semantics
# --------------------------------------------------------------------------

def test_a_failure_during_teardown_leaves_the_class_whole(client, app, monkeypatch):
    """FEAT-CLASS-006 is the transaction boundary: no half-destroyed class.

    The teardown runs to completion and then fails, so every delete it issued is
    pending in the FEAT's transaction when the error propagates. None of it may
    persist (FEAT-CLASS-006 §VII).
    """
    import app.routes.admin as admin_module

    initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    item = _add_store_item(classroom.class_id, "Widget A")
    seat_count = Seat.query.filter_by(class_id=classroom.class_id).count()
    assert seat_count > 0

    original = admin_module._destroy_class_scope_rows

    def destroy_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after the teardown completed")

    monkeypatch.setattr(admin_module, "_destroy_class_scope_rows", destroy_then_fail)
    # A sibling class exists, so this is the FEAT-CLASS-006 path; the account
    # path is covered separately and reaches the command by another binding.

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 500

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is not None
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == seat_count
    assert _product_exists(item)


def test_destruction_leaves_no_row_scoped_to_the_destroyed_class(client, app):
    """Hard deletion, not a soft flag: `class_id` is the existential root.

    INV-CORE-000 §26 and §33 — scoped data must not survive deletion of its
    `class_id` unless explicitly re-scoped. The sibling class proves the sweep
    is bounded by `class_id` rather than by teacher ownership.
    """
    sibling = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    doomed_item = _add_store_item(classroom.class_id, "Widget A")
    sibling_item = _add_store_item(sibling.class_id, "Widget B")

    response = admin_delete_class(
        client, **valid_destruction_gate(_class_delete_phrase(classroom.class_id))
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == 0
    assert not _product_exists(doomed_item)

    # Bounded by class_id: the same teacher's other class is untouched.
    assert db.session.get(ClassEconomy, sibling.class_id) is not None
    assert Seat.query.filter_by(class_id=sibling.class_id).count() > 0
    assert _product_exists(sibling_item)

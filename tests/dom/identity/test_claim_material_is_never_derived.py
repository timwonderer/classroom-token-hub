"""Claim material is entered, never derived from the display layer.

`identity_profiles` is display-only identity (INV-ARC-019 §"`identity_profiles`
= display-only identity"). The claim hashes and `roster_fingerprint` on a Seat
are the authoritative key that decides who may claim it.

Those profile values are decryptable, so regenerating the hashes from the stored
profile is technically available — and that is exactly the hazard. It would let
display-layer metadata backfill an authoritative key, reversing the direction
authority is allowed to flow. It would also infer intent: deriving the name
assumes the teacher wants it unchanged, when a teacher who wanted that would have
typed it, and a teacher who did not has already decided otherwise.

So this is a structural guard rather than a behavioural one. After an Unclaim the
profile and the claim material agree, so no black-box test can tell a derived
value from an entered one — by then they are the same string. The distinction
only exists in where the value came from, which is a property of the source.
"""

from __future__ import annotations

import ast
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Every module that writes claim material.
SOURCES = (
    "app/feats/identity_feat.py",
    "app/services/classroom_setup.py",
    "app/routes/admin.py",
)

# The functions that mint claim material, and which of their arguments carry the
# name. `class_id` and `field` are scope, not identity, and may be read off a row.
CLAIM_MATERIAL_FUNCTIONS = {
    "hash_claim_name": {"positional": (0,), "keyword": {"first_name", "last_name"}},
    "hash_roster_fingerprint": {"positional": (), "keyword": {"first_name", "last_name"}},
}


def _name_arguments(node: ast.Call, spec: dict) -> list[ast.AST]:
    arguments = [node.args[i] for i in spec["positional"] if i < len(node.args)]
    arguments += [kw.value for kw in node.keywords if kw.arg in spec["keyword"]]
    return arguments


def _describe(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - older ast
        return type(node).__name__


def test_no_claim_hash_is_computed_from_a_stored_row():
    """The name argument must be a plain value, never read off an object.

    Checked by shape rather than by variable name. An earlier version of this
    test matched a list of likely names (`profile`, `identity_profile`, …) and
    let a deliberately injected `_probe_profile.first_name` straight through —
    a guard keyed on naming only catches violations that are already obvious.

    Any attribute read here (`x.first_name`) means the name came out of a
    persisted row rather than from this operation's input, which is the
    direction DOM-IDEN-005 forbids. `class_id` and `field` are exempt: they are
    scope, not identity.
    """
    offenders = []
    for relative in SOURCES:
        path = REPO_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            spec = CLAIM_MATERIAL_FUNCTIONS.get(callee)
            if spec is None:
                continue
            for argument in _name_arguments(node, spec):
                if isinstance(argument, ast.Attribute):
                    offenders.append(f"{relative}:{node.lineno} {callee}(… {_describe(argument)} …)")
    assert offenders == [], (
        "Claim material must be minted from names entered at the time of the "
        "operation, never read back off a stored row — the IdentityProfile is "
        "display-only identity (INV-ARC-019) and must not backfill the key that "
        "governs who may claim a Seat (DOM-IDEN-005 §Why the names must be "
        f"entered, never derived): {offenders}"
    )


def test_the_unclaim_form_does_not_prefill_the_name_fields(client, app):
    """A prefilled field is derivation wearing a different hat.

    If the form arrives carrying the current name, the default outcome is
    "unchanged" and the teacher's intent stops being observable — the same
    inference, moved from the backend into the markup.
    """
    from bs4 import BeautifulSoup
    from tests.helpers.classroom_initializer import initialize_as_teacher

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student_name = classroom.students[0].first_name

    soup = BeautifulSoup(client.get("/admin/students").get_data(as_text=True), "html.parser")
    for field_id in ("unclaimFirstName", "unclaimLastName"):
        field = soup.find(id=field_id)
        assert field is not None, field_id
        assert not field.get("value"), f"{field_id} must arrive blank"
        assert field.get("placeholder") in (None, ""), f"{field_id} must not suggest a name"

    # The roster does pass the current name to the modal, and should: the
    # confirmation reads "Unclaim <name>?" so the teacher can see which seat
    # they are acting on. What must not happen is that name reaching the input
    # fields, which would make "unchanged" the default and hide the decision.
    unclaim_triggers = soup.select('[data-bs-target="#unclaimStudentModal"]')
    assert unclaim_triggers, "the roster should still offer Unclaim"
    assert any(student_name in str(t.attrs.get("data-student-name", "")) for t in unclaim_triggers), (
        "the confirmation should still name the seat being unclaimed"
    )

    script = "\n".join(tag.get_text() for tag in soup.find_all("script"))
    for field_id in ("unclaimFirstName", "unclaimLastName"):
        assigns_value = re.search(
            rf"""getElementById\(\s*['"]{field_id}['"]\s*\)\s*\.value\s*=""", script
        )
        assert not assigns_value, f"{field_id} must never be seeded by script"

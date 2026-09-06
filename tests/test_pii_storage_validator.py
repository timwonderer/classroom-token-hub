"""The PII storage gate must fail on real defects and only on those.

`scripts/validate-pii-storage.py` is auxiliary evidence for the CI-PII invariant
family, so a false positive blocks every `app/models.py` change and a false
negative lets an unamended PII column reach the schema. Both directions are
covered here.

A third direction matters as much as the other two: this validator selects the
classes and columns it audits by name. A rename would leave it auditing nothing
and reporting success, which is indistinguishable from auditing everything and
finding it clean. The coverage assertions below pin that failure mode shut.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_pii_storage", ROOT / "scripts" / "validate-pii-storage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()

# A minimal but complete stand-in for the governed surface of app/models.py.
# Every field INV-ARC-018 declares is present in its declared storage form, so
# this source must produce no findings. Each defect test mutates one line of it.
COMPLIANT_MODELS = """
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username_hash = db.Column(db.String(64), unique=True, nullable=False)
    username_lookup_hash = db.Column(db.String(64), nullable=True)
    pin_hash = db.Column(db.Text, nullable=True)
    passphrase_hash = db.Column(db.Text, nullable=True)


class IdentityProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    notes = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)


class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    claim_first_name_hash = db.Column(db.String(128), nullable=True)
    claim_last_name_hash = db.Column(db.String(128), nullable=True)
"""


def _check(tmp_path, source):
    path = tmp_path / "models.py"
    path.write_text(source, encoding="utf-8")
    return validator.validate(path)


# --------------------------------------------------------------------------
# Direction 1: valid forms are not flagged.
# --------------------------------------------------------------------------


def test_the_compliant_surface_produces_no_findings(tmp_path):
    assert _check(tmp_path, COMPLIANT_MODELS) == []


def test_the_live_models_module_is_compliant():
    """The gate is only wired into CI-PII because the tree currently passes it."""
    assert validator.validate() == []


def test_credential_hashes_are_not_treated_as_identity_pii(tmp_path):
    """`pin_hash` and friends are security material, not §VI display/claim PII."""
    source = COMPLIANT_MODELS.replace(
        "    pin_hash = db.Column(db.Text, nullable=True)\n", ""
    )
    assert _check(tmp_path, source) == []
    assert _check(tmp_path, COMPLIANT_MODELS) == []


def test_ungoverned_classes_are_ignored(tmp_path):
    """A free-text column outside the identity classes is another domain's concern."""
    source = COMPLIANT_MODELS + """

class Transaction(db.Model):
    notes = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
"""
    assert _check(tmp_path, source) == []


def test_opaque_teacher_text_is_not_an_identity_pii_field(tmp_path):
    """`IdentityProfile.notes` holds author-supplied text the application never
    inspects. It is not one of the identity fields enumerated by §VI, so the
    enforceable contract is its storage form, not its membership in that table.
    """
    assert ("IdentityProfile", "notes") not in validator.ALLOWED
    assert validator.OPAQUE_ENCRYPTED[("IdentityProfile", "notes")] == "encrypted"
    assert _check(tmp_path, COMPLIANT_MODELS) == []


# --------------------------------------------------------------------------
# Direction 2: real defects are caught.
# --------------------------------------------------------------------------


def test_plaintext_display_name_is_a_defect(tmp_path):
    """§V.2 — a display-purpose name must not reach the database as plaintext."""
    source = COMPLIANT_MODELS.replace(
        "first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)",
        "first_name = db.Column(db.String(64), nullable=False)",
    )
    assert _check(tmp_path, source) == [
        "IdentityProfile.first_name: expected encrypted storage, found plain"
    ]


def test_an_unamended_pii_column_is_a_defect(tmp_path):
    """§VI — a new identity PII field requires an amendment before it may exist."""
    source = COMPLIANT_MODELS.replace(
        "    claim_first_name_hash = db.Column(db.String(128), nullable=True)",
        "    claim_first_name_hash = db.Column(db.String(128), nullable=True)\n"
        "    guardian_email_hash = db.Column(db.String(128), nullable=True)",
    )
    assert _check(tmp_path, source) == [
        "Seat.guardian_email_hash: PII field is not permitted by INV-ARC-018 §VI"
    ]


def test_a_plaintext_free_text_column_is_a_defect(tmp_path):
    """Author-supplied text is opaque, so §V.2 encryption is the enforceable rule."""
    source = COMPLIANT_MODELS.replace(
        "notes = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)",
        "notes = db.Column(db.Text, nullable=True)",
    )
    assert _check(tmp_path, source) == [
        "IdentityProfile.notes: expected encrypted storage, found plain"
    ]


def test_an_undeclared_free_text_column_is_a_defect(tmp_path):
    """§VII.2 — a new free-text vessel on an identity class must be reviewed first."""
    source = COMPLIANT_MODELS.replace(
        "    notes = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)",
        "    notes = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)\n"
        "    description = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)",
    )
    assert _check(tmp_path, source) == [
        "IdentityProfile.description: undeclared free-text column on a governed "
        "identity class (INV-ARC-018 §VII.2)"
    ]


# --------------------------------------------------------------------------
# Direction 3: the gate cannot pass by auditing nothing.
# --------------------------------------------------------------------------


def test_a_renamed_governed_class_is_reported_rather_than_skipped(tmp_path):
    """Selection is by class name, so a rename must fail loudly, not silently."""
    source = COMPLIANT_MODELS.replace(
        "class IdentityProfile(db.Model):", "class Profile(db.Model):"
    )
    assert _check(tmp_path, source) == [
        "IdentityProfile: governed class is absent from models.py; "
        "INV-ARC-018 §VI coverage cannot be established"
    ]


def test_an_empty_module_fails_instead_of_passing_vacuously(tmp_path):
    """The degenerate case: nothing to audit is a failure, not a pass."""
    findings = _check(tmp_path, "")
    assert len(findings) == len(validator.GOVERNED_CLASSES)
    assert all("coverage cannot be established" in finding for finding in findings)


def test_a_dropped_allowlisted_column_is_reported(tmp_path):
    """An allowlist entry matching no column no longer describes the schema."""
    source = COMPLIANT_MODELS.replace(
        "    claim_last_name_hash = db.Column(db.String(128), nullable=True)\n", ""
    )
    assert _check(tmp_path, source) == [
        "Seat.claim_last_name_hash: declared by INV-ARC-018 but absent from models.py; "
        "the allowlist no longer describes the schema"
    ]


def test_every_declared_field_is_exercised_against_the_live_schema():
    """Guards the allowlist itself against drifting into unreachable entries.

    `test_the_live_models_module_is_compliant` would also pass with an empty
    allowlist. This asserts the allowlist is non-empty and that every field it
    declares really is matched in `app/models.py`.
    """
    declared = set(validator.ALLOWED) | set(validator.OPAQUE_ENCRYPTED)
    assert declared, "the allowlist must not be empty or the gate audits nothing"

    tree = ast.parse(validator.MODEL_PATH.read_text(encoding="utf-8"))
    present = {
        (node.name, field)
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in validator.GOVERNED_CLASSES
        for field, _ in validator._column_fields(node)
    }
    assert declared <= present

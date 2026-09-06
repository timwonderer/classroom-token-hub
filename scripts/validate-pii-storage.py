#!/usr/bin/env python3
"""Validate the explicitly permitted PII storage forms in app/models.py."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "app" / "models.py"

GOVERNED_CLASSES = {"User", "Seat", "IdentityProfile"}

# Authority: INV-ARC-018 §VI. Keep this finite and explicit. A new field must
# amend the invariant before this allowlist changes.
ALLOWED = {
    ("User", "username_hash"): "hmac",
    ("IdentityProfile", "first_name"): "encrypted",
    ("IdentityProfile", "last_name"): "encrypted",
    ("Seat", "claim_first_name_hash"): "hmac",
    ("Seat", "claim_last_name_hash"): "hmac",
}

# Opaque author-supplied text. The application neither inspects nor interprets
# what a teacher types here, so it is not one of the identity PII fields
# enumerated by INV-ARC-018 §VI and the §VI allowlist does not govern it. What
# is enforceable is the storage form: it holds arbitrary author text and so must
# be encrypted at rest under §V.2 regardless of content.
OPAQUE_ENCRYPTED = {
    ("IdentityProfile", "notes"): "encrypted",
}

# Credential hashes are security material, but are not the PII fields governed
# by the finite identity-display/claim allowlist in INV-ARC-018 §VI.
NON_PII_HASH_FIELDS = {"username_lookup_hash", "pin_hash", "passphrase_hash"}

# Names that denote identity PII wherever they appear. A column matching one of
# these, or any ``*_hash`` column, must be justified by ALLOWED or by
# NON_PII_HASH_FIELDS; otherwise it is an unamended §VI addition.
PII_FIELD_NAMES = {"first_name", "last_name"}

# INV-ARC-018 §VII.2 names these as vessels that PII leaks into. Their contents
# are not inspectable, so the enforceable rule is that a free-text column on a
# governed identity class must be explicitly declared in OPAQUE_ENCRYPTED and
# must be encrypted at rest. An undeclared one is an unreviewed leak surface.
FREE_TEXT_NAMES = {"notes", "description", "metadata", "comment"}


def _column_fields(cls: ast.ClassDef) -> list[tuple[str, str]]:
    fields = []
    for node in cls.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "Column":
            continue
        storage = "plain"
        if call.args and isinstance(call.args[0], ast.Call):
            inner = call.args[0]
            if isinstance(inner.func, ast.Name) and inner.func.id == "PIIEncryptedType":
                storage = "encrypted"
        if target.id.endswith("_hash"):
            storage = "hmac"
        fields.append((target.id, storage))
    return fields


def validate(path: Path = MODEL_PATH) -> list[str]:
    """Return every INV-ARC-018 storage-form finding in ``path``.

    Absence is a finding too. A silent rename of a governed class or of an
    allowlisted column would otherwise leave this check auditing nothing, which
    is indistinguishable from auditing everything and finding it clean.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    seen_classes: set[str] = set()
    seen_fields: set[tuple[str, str]] = set()

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in GOVERNED_CLASSES:
            continue
        seen_classes.add(node.name)
        for field, storage in _column_fields(node):
            key = (node.name, field)
            seen_fields.add(key)
            if field in NON_PII_HASH_FIELDS:
                continue
            expected = ALLOWED.get(key) or OPAQUE_ENCRYPTED.get(key)
            if expected is None:
                if field in PII_FIELD_NAMES or field.endswith("_hash"):
                    findings.append(
                        f"{node.name}.{field}: PII field is not permitted by INV-ARC-018 §VI"
                    )
                elif field in FREE_TEXT_NAMES:
                    findings.append(
                        f"{node.name}.{field}: undeclared free-text column on a governed "
                        "identity class (INV-ARC-018 §VII.2)"
                    )
            elif storage != expected:
                findings.append(
                    f"{node.name}.{field}: expected {expected} storage, found {storage}"
                )

    for missing in sorted(GOVERNED_CLASSES - seen_classes):
        findings.append(
            f"{missing}: governed class is absent from {path.name}; "
            "INV-ARC-018 §VI coverage cannot be established"
        )
    for cls, field in sorted(set(ALLOWED) | set(OPAQUE_ENCRYPTED)):
        if cls in seen_classes and (cls, field) not in seen_fields:
            findings.append(
                f"{cls}.{field}: declared by INV-ARC-018 but absent from {path.name}; "
                "the allowlist no longer describes the schema"
            )
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print("PII storage violations:")
        print("\n".join(f"  - {finding}" for finding in findings))
        return 1
    print(
        f"PII storage allowlist passed "
        f"({len(ALLOWED)} governed fields, {len(OPAQUE_ENCRYPTED)} opaque encrypted)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

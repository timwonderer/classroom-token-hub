"""Release bundles derive from the lineage, and an unbundled checkout refuses to install.

The CI job runs ``scripts/verify_fresh_bundles.py`` against a real PostgreSQL 14
cluster. These tests hold its comparison and the installer's refusal without one:
each detector is fed the change it exists to catch (SOP-TEST-003 §IX.A).
"""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fresh_database import install  # noqa: E402
from verify_fresh_bundles import compare, source_of  # noqa: E402

BUNDLE = ROOT / "migrations" / "fresh" / "a0faf8b2a35d"


def _copy(tmp_path, name):
    target = tmp_path / name
    shutil.copytree(BUNDLE, target)
    return target


def test_identical_bundles_compare_clean(tmp_path):
    assert compare(BUNDLE, _copy(tmp_path, "derived")) == []


def test_mutation_hand_edited_schema_is_reported(tmp_path):
    derived = _copy(tmp_path, "derived")
    (derived / "schema.sql").write_bytes((BUNDLE / "schema.sql").read_bytes() + b"\n-- edited\n")
    assert compare(BUNDLE, derived) == ["schema.sql differs from the lineage's derivation"]


@pytest.mark.parametrize("field", ["schema_sha256", "ddl_sha256", "empty_schema_sha256", "categories", "sequences", "revision"])
def test_mutation_changed_manifest_field_is_reported(tmp_path, field):
    derived = _copy(tmp_path, "derived")
    manifest = json.loads((derived / "manifest.json").read_text())
    manifest[field] = "tampered"
    (derived / "manifest.json").write_text(json.dumps(manifest))
    assert compare(BUNDLE, derived) == [f"manifest {field} differs"]


def test_provenance_fields_are_not_derivation():
    """Where and when a bundle was generated may differ; what it contains may not."""
    manifest = json.loads((BUNDLE / "manifest.json").read_text())
    assert source_of(manifest) == manifest["release_sha"]  # generated before the rename
    assert source_of({"source_sha": "a" * 40, "release_sha": "b" * 40}) == "a" * 40


def _checkout(tmp_path, head, bundles=()):
    """A minimal release tree whose sole Alembic head is ``head``."""
    root = tmp_path / "release"
    versions = root / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / f"{head}_only.py").write_text(f"revision = '{head}'\ndown_revision = None\n")
    for name in bundles:
        shutil.copytree(BUNDLE, root / "migrations" / "fresh" / name)
    return root


def _never_connect(*_args, **_kwargs):
    pytest.fail("the installer reached the database before refusing")


def test_checkout_without_a_matching_bundle_refuses_before_connecting(tmp_path, monkeypatch):
    """F4: a checkout whose head has no validated bundle installs nothing."""
    monkeypatch.setattr("fresh_database.target", _never_connect)
    with pytest.raises(OSError):
        install(SimpleNamespace(), release_root=_checkout(tmp_path, "ffffffffffff"))


def test_bundle_for_another_revision_refuses_before_connecting(tmp_path, monkeypatch):
    monkeypatch.setattr("fresh_database.target", _never_connect)
    root = _checkout(tmp_path, "ffffffffffff")
    shutil.copytree(BUNDLE, root / "migrations" / "fresh" / "ffffffffffff")
    with pytest.raises(ValueError, match="does not match this checkout's sole head"):
        install(SimpleNamespace(), release_root=root)

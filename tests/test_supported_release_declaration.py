"""The supported fresh-install release is declared once and ships a valid bundle.

``scripts/check_supported_release.py`` runs against the real tags in CI
(``check-migrations.yml``). These tests feed its pure ``check()`` each violation
it exists to catch (SOP-TEST-003 §IX.A), plus the real declaration and documents.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_supported_release import DECLARATION, DOCUMENTS, check, declared_tags, sole_head  # noqa: E402

TAG, COMMIT, REVISION = "v9.9.9", "c" * 40, "bbbbbbbbbbbb"
SCHEMA = b"CREATE TABLE t (id int);\n"
MANIFEST = json.dumps({"revision": REVISION, "ddl_sha256": hashlib.sha256(SCHEMA).hexdigest()}).encode()
FILES = ["revision = 'aaaaaaaaaaaa'\ndown_revision = None\n",
         f"revision = '{REVISION}'\ndown_revision = 'aaaaaaaaaaaa'\n"]
LINE = f"**Supported fresh-install release:** [{TAG}](https://example.invalid)"


def _check(**overrides):
    args = dict(declaration={"tag": TAG, "commit": COMMIT, "revision": REVISION}, ref_commit=COMMIT,
                release_files=FILES, release_bundle=(SCHEMA, MANIFEST), checkout_bundle=(SCHEMA, MANIFEST),
                documents={"README.md": LINE, "handbook.md": f"x\n{LINE}\n"})
    args.update(overrides)
    return check(**args)


def test_consistent_declaration_passes():
    assert _check() == []


def test_mutation_tag_moved_to_another_commit():
    assert _check(ref_commit="d" * 40) == [f"tag {TAG} resolves to {'d' * 40}, not the declared commit {COMMIT}"]


def test_mutation_missing_tag():
    assert "resolves to None" in _check(ref_commit=None)[0]


def test_mutation_release_head_is_not_the_declared_revision():
    later = FILES + [f"revision = 'eeeeeeeeeeee'\ndown_revision = '{REVISION}'\n"]
    assert _check(release_files=later) == [f"{TAG}'s sole migration head is eeeeeeeeeeee, not the declared revision {REVISION}"]


def test_mutation_release_without_its_bundle():
    assert _check(release_bundle=(None, None)) == [f"{TAG} does not contain migrations/fresh/{REVISION}/"]


def test_mutation_release_bundle_tampered():
    problems = _check(release_bundle=(SCHEMA + b"-- edit\n", MANIFEST))
    assert f"{TAG}'s bundle schema.sql does not match its manifest ddl_sha256" in problems


def test_mutation_checkout_bundle_differs_from_release():
    assert _check(checkout_bundle=(SCHEMA, MANIFEST + b" ")) == [
        f"this checkout's migrations/fresh/{REVISION}/ differs from the one {TAG} ships"]


@pytest.mark.parametrize("text, named", [
    ("**Supported fresh-install release:** v2.4.5", ["v2.4.5"]),
    ("no declaration here", []),
    (f"{LINE}\n{LINE}", [TAG, TAG]),
])
def test_mutation_document_drift(text, named):
    problems = _check(documents={"README.md": text})
    assert problems == [f"README.md names {named or 'no'} supported fresh-install release; expected exactly [{TAG!r}]"]


def test_sole_head_of_a_branched_history_is_none():
    assert sole_head(FILES + ["revision = 'ffffffffffff'\ndown_revision = 'aaaaaaaaaaaa'\n"]) is None


def test_real_declaration_names_the_tag_each_document_declares():
    declaration = json.loads((ROOT / DECLARATION).read_text())
    for name in DOCUMENTS:
        assert declared_tags((ROOT / name).read_text(encoding="utf-8")) == [declaration["tag"]], name
    assert (ROOT / "migrations" / "fresh" / declaration["revision"] / "manifest.json").is_file()

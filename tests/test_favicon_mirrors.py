"""Every surface's tab icon is a byte-identical copy of static/images/icon-192.png.

The public site and status service each publish their own directory, so they cannot
link the application's file and carry a copy instead. A copy nobody checks drifts on
the next icon change. (The Hugo docs site copies the source at build time and checks it
in docs-generator-proof/test_proof.py.)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static/images/icon-192.png"
MIRRORS = (
    "github-pages/assets/icon-192.png",
    "status_service/static/icon-192.png",
)


def drifted_mirrors(source: Path, root: Path, mirrors) -> list[str]:
    expected = source.read_bytes()
    return [m for m in mirrors if not (root / m).is_file() or (root / m).read_bytes() != expected]


def test_favicon_mirrors_match_source():
    assert drifted_mirrors(SOURCE, ROOT, MIRRORS) == []


def test_favicon_mirror_check_catches_a_stale_copy(tmp_path):
    """Mutation proof: a copy one byte off, and a missing copy, are both reported."""
    source = tmp_path / "icon.png"
    source.write_bytes(SOURCE.read_bytes())
    (tmp_path / "stale.png").write_bytes(SOURCE.read_bytes()[:-1])
    (tmp_path / "same.png").write_bytes(SOURCE.read_bytes())
    assert drifted_mirrors(source, tmp_path, ("stale.png", "same.png", "missing.png")) == [
        "stale.png",
        "missing.png",
    ]

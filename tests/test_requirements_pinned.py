from pathlib import Path

import pytest


pytestmark = pytest.mark.regression


def _is_pinned_requirement(line: str) -> bool:
    # Keep direct URL/path-style requirements as-is; enforce pins for package specs.
    if " @ " in line:
        return True
    return "==" in line


def test_requirements_are_pinned():
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    unpinned: list[str] = []

    for raw_line in requirements_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            continue
        if not _is_pinned_requirement(line):
            unpinned.append(line)

    assert not unpinned, "Unpinned dependencies found in requirements.txt:\n" + "\n".join(unpinned)

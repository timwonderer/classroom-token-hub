"""scripts/release_notes.py refuses a CHANGELOG section that is not in the standard shape (SOP-DEP-002 §VII.A)."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "release_notes", Path(__file__).resolve().parents[1] / "scripts" / "release_notes.py"
)
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

RUN = "https://github.com/timwonderer/classroom-token-hub/actions/runs/123"
GOOD = f"""## [Unreleased]

## [9.9.9] - 2026-10-12 — A title

Released as `abc1234` on 2026-10-12 at 05:27 UTC by release run [123]({RUN}). No migration. Record: [DEPLOY_2026-10-12_abc1234.md](docs/ops/audits/DEPLOY_2026-10-12_abc1234.md).

### Fixed

- A fix, see [the SOP](docs/SOP.md) and [upstream](https://example.com).

### Security

- A security fix.

## [9.9.8] - 2026-10-11 — Older
"""


def test_release_notes_extracts_title_body_and_sha():
    title, body, sha = release_notes.extract(GOOD, "9.9.9")
    assert title == "v9.9.9 — A title"
    assert sha == "abc1234"
    assert "Older" not in body
    assert "](https://github.com/timwonderer/classroom-token-hub/blob/main/docs/SOP.md)" in body
    assert "](https://example.com)" in body


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda s: s.replace("### Fixed\n\n- A fix", "### Fixes\n\n- A fix"), "unknown subsections"),
        (lambda s: s.replace("### Fixed", "### TMP").replace("### Security", "### Fixed").replace("### TMP", "### Security"),
         "not in the order"),
        (lambda s: s.replace("Released as `abc1234` on", "Deployed as `abc1234` on"), "Released as"),
        (lambda s: s.replace(" No migration.", ""), "Released as"),
        (lambda s: s.replace("— A title", "A title"), "heading"),
    ],
)
def test_release_notes_refuses_a_section_out_of_shape(mutate, reason):
    with pytest.raises(ValueError, match=reason):
        release_notes.extract(mutate(GOOD), "9.9.9")

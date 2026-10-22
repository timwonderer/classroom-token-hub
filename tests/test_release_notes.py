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


TAGGED = f"""## [9.9.9] - 2026-10-22 — A title

Released as `abc1234` on 2026-10-22 at 04:38 UTC by release run [123]({RUN}). Migration `a1b2c3d4`. Record: [DEPLOY_2026-10-22_abc1234.md](docs/ops/audits/DEPLOY_2026-10-22_abc1234.md). Includes `def5678`.

### Changed

- <!-- notes: internal --> **Dependencies.** gunicorn 26.2.0 (#1380), mentioned for context only.
- <!-- notes: security-reliability --> **Ledger type vocabulary is closed** (`DOM-LED-001`). Follows #1599.

### Fixed

- <!-- notes: fixed, highlight --> **Delete Class works again** (#1624). A long paragraph of detail.
  - a sub-bullet that stays with its entry
- <!-- notes: accessibility --> **Buttons keep contrast under keyboard focus** (#1626, #1630).

### Security

- <!-- notes: security-reliability, highlight --> **Operator console verifies the signed assertion** (#1618).
"""


def _rendered(text=TAGGED):
    _, body, _ = release_notes.extract(text, "9.9.9")
    return release_notes.render(body)


def test_render_orders_the_owner_sections_with_highlights_first():
    notes = _rendered()
    headings = [line for line in notes.splitlines() if line.startswith("## ")]
    assert headings == ["## Highlights", "## Fixed", "## Security & Reliability", "## Accessibility", "## Internal Changes"]


def test_render_lists_one_headline_per_entry_and_collapses_the_full_text():
    notes = _rendered()
    highlights = notes.split("## Highlights")[1].split("## Fixed")[0]
    assert "- Delete Class works again (#1624)" in highlights
    assert "- Operator console verifies the signed assertion (#1618)" in highlights
    assert "A long paragraph of detail" not in highlights
    fixed = notes.split("## Fixed")[1].split("## Security")[0]
    assert "<details><summary>Full details</summary>" in fixed
    assert "A long paragraph of detail" in fixed and "a sub-bullet that stays with its entry" in fixed


def test_render_shows_only_the_prs_an_entry_cites_as_its_own():
    notes = _rendered()
    assert "- Dependencies\n" in notes            # #1380 is in the prose, not the headline's citation
    assert "- Ledger type vocabulary is closed\n" in notes   # "Follows #1599" is context
    assert "- Buttons keep contrast under keyboard focus (#1626, #1630)" in notes


def test_render_hides_the_tags_and_links_the_deployment_record_last():
    notes = _rendered()
    assert "<!-- notes:" not in notes
    assert notes.startswith("Released 2026-10-22 at 04:38 UTC. Migration `a1b2c3d4`.")
    tail = notes.split("\n---\n")[1]
    assert "Deployment record: [DEPLOY_2026-10-22_abc1234.md](https://github.com/" in tail
    assert "Release run: [123](" in tail and "Includes `def5678`." in tail


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda s: s.replace("- <!-- notes: accessibility --> ", "- "), "no '<!-- notes"),
        (lambda s: s.replace("notes: accessibility", "notes: a11y"), "unknown notes section"),
    ],
)
def test_render_refuses_an_entry_without_a_known_section(mutate, reason):
    with pytest.raises(ValueError, match=reason):
        _rendered(mutate(TAGGED))

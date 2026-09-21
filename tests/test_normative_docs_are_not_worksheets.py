"""A normative document is a procedure, never somebody's filled-in worksheet.

The failure this guards against has already happened once. `SOP-DEP-001` is a
prose runbook with no checkboxes, so an operator who wanted something tickable
made one: a copy of its sections under `docs/TRACKING/`, which was then filled
in during a real deployment and committed. The result was a parallel copy of a
governing procedure, carrying one run's host state, held at a tier that
`CLAUDE.md` marks descriptive — and drifting from the SOP from the moment it
was written.

Untracking that file removed the instance. This removes the class: a ticked box
in a normative document means the master was used as the worksheet.

Per `SOP-TEST-003` §IX.A the detection is a pure function over source text, and
the companion test feeds it a synthetic violation spelled the way a real one
would be, so the gate cannot go green because the scanner stopped seeing.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The normative roots named by CLAUDE.md. docs/TRACKING/, docs/MAP/ and
# docs/ops/ are deliberately absent: a tracking doc or a deployment record is
# *supposed* to carry ticked boxes. That is what those tiers are for.
NORMATIVE_ROOTS = (
    "docs/INVARIANT",
    "docs/DOMAIN",
    "docs/FEATURE-EXECUTION",
    "docs/SPEC",
    "docs/STANDARD_OPERATING_PROCEDURES",
)

FENCE = re.compile(r"^\s*(?:```|~~~)")
TICKED = re.compile(r"^\s*[-*+]\s+\[[xX]\]")


def ticked_checkboxes(text: str) -> list[tuple[int, str]]:
    """Ticked task-list items outside fenced code.

    A fenced block is skipped: a document may legitimately *show* a ticked box
    as an example of the markup, and flagging that would train readers to
    silence the rule.
    """
    found: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and TICKED.match(line):
            found.append((number, line.strip()))
    return found


def _normative_documents() -> list[Path]:
    paths: list[Path] = []
    for root in NORMATIVE_ROOTS:
        base = REPO_ROOT / root
        if base.exists():
            paths += [p for p in base.rglob("*.md") if "archive" not in p.parts]
    return sorted(paths)


@pytest.mark.parametrize(
    "path", _normative_documents(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_normative_document_carries_no_ticked_checkbox(path):
    """A ticked box here means the master was used as the worksheet."""
    violations = ticked_checkboxes(path.read_text(encoding="utf-8"))
    assert not violations, (
        f"{path.relative_to(REPO_ROOT)} carries a completed checklist item, so the "
        f"governing document has been filled in as a worksheet. Copy it to an "
        f"untracked path and tick the copy.\n"
        + "\n".join(f"  line {n}: {t}" for n, t in violations)
    )


@pytest.mark.parametrize(
    "markup",
    [
        "- [x] Confirm the exact 40-character v2 commit SHA to test.",
        "- [X] Confirm migration head count is exactly one.",
        "  - [x] Nested under a step.",
        "* [x] A star-bulleted list item.",
        "+ [x] A plus-bulleted list item.",
    ],
)
def test_detector_reports_a_filled_box(markup):
    """Guard against the gate going green because the scanner went blind."""
    assert ticked_checkboxes(f"## VI. Release gate\n\n{markup}\n")


@pytest.mark.parametrize(
    "markup",
    [
        # an empty box is the correct state of a procedure
        "- [ ] Confirm the exact 40-character v2 commit SHA to test.",
        # prose that merely mentions the markup
        "Mark each item `- [x]` in your copy, never in this document.",
        # a fenced example may show the filled form
        "```markdown\n- [x] Confirm the release SHA\n```",
        "~~~\n- [x] Confirm the release SHA\n~~~",
        # not a task list
        "- [a] An ordinary bracketed list item.",
        "-[x] No space after the bullet, so not a task item.",
    ],
)
def test_detector_admits_empty_boxes_prose_and_fenced_examples(markup):
    assert ticked_checkboxes(markup) == []


def test_detector_resumes_after_a_closed_fence():
    """A filled box after an example block must still be reported."""
    text = "```\n- [x] shown as an example\n```\n\n- [x] actually ticked\n"
    found = ticked_checkboxes(text)
    assert [n for n, _ in found] == [5]

"""Links point at the repository's current name.

`classroom-economy` was the repository's old name; `classroom-token-hub` is
current. GitHub redirects a renamed repository, so a stale link still resolves
and nothing appears broken — which is why thirty of them survived across the
public marketing pages, the in-app docs, the user guides, the documentation
site's edit links, and a setup script. The redirect is not a guarantee: it
lapses if the old name is ever taken by another repository.

Scope is deliberately narrow. `classroom-economy` is *also* the live systemd
unit and the deployment directory on the production host, and it appears in a
TOTP issuer label where changing it would invalidate enrolled authenticators.
This checks the repository-URL form only, so those are untouched by
construction.

`docs/archive/` is exempt: a link that was correct when archived is history,
and the archive is not published.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

RETIRED_OWNER_REPO = "timwonderer/classroom-economy"
CURRENT_OWNER_REPO = "timwonderer/classroom-token-hub"

# The URL form only. A bare "classroom-economy" is a host path, a service unit,
# or the English phrase "classroom economy", and none of those are this rule's
# business.
RETIRED_URL = re.compile(r"github\.com/" + re.escape(RETIRED_OWNER_REPO) + r"(?![\w-])")

EXEMPT_PREFIXES = ("docs/archive/",)

# Built at runtime, never written as one literal. This module is itself tracked
# and scanned, so a fixture spelling the retired URL out would make the guard
# report its own test data and fail on every checkout. It did: the test passed
# while the file was still untracked and began failing the moment it was
# committed, because committing changed the scanner's input.
RETIRED_BASE_URL = "https://github.com/" + RETIRED_OWNER_REPO
CURRENT_BASE_URL = "https://github.com/" + CURRENT_OWNER_REPO


def retired_repository_links(text: str) -> list[tuple[int, str]]:
    """Lines carrying a link to the repository's retired name."""
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if RETIRED_URL.search(line)
    ]


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [
        p
        for p in out
        if not p.startswith(EXEMPT_PREFIXES)
        and "node_modules/" not in p
        and Path(p).suffix
        in {".md", ".html", ".js", ".jsx", ".ts", ".tsx", ".py", ".sh", ".yml", ".yaml", ".json", ".css", ".txt"}
    ]


def test_no_tracked_file_links_to_the_retired_repository_name():
    offenders: list[str] = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        offenders += [f"  {rel}:{n}: {t}" for n, t in retired_repository_links(text)]
    assert not offenders, (
        f"These link to the retired repository name. GitHub's rename redirect hides "
        f"the breakage until the old name is reused.\n"
        f"Use {CURRENT_OWNER_REPO}.\n" + "\n".join(offenders)
    )


# ─── Mutation proofs ───


@pytest.mark.parametrize(
    "line",
    [
        f'const repoUrl = "{RETIRED_BASE_URL}";',
        f'<a href="{RETIRED_BASE_URL}">Repository</a>',
        f"See {RETIRED_BASE_URL}/blob/main/CHANGELOG.md",
        f"  --url {RETIRED_BASE_URL} \\",
        f"[docs]({RETIRED_BASE_URL}/tree/main/docs)",
    ],
)
def test_detector_reports_a_retired_link(line):
    """Guard against the gate going green because the scanner went blind."""
    assert retired_repository_links(line)


@pytest.mark.parametrize(
    "line",
    [
        # the current name, including the prefix-collision case
        f'const repoUrl = "{CURRENT_BASE_URL}";',
        f"{RETIRED_BASE_URL}-archive",
        # the live production host path and service unit
        "            cd ~/classroom-economy",
        "            sudo systemctl restart classroom-economy",
        "test -d ~/classroom-economy",
        # a TOTP issuer label; changing it would invalidate enrolled authenticators
        "Encodes: `otpauth://totp/classroom-economy:{user_id}@{class_id}`",
        # the English phrase
        "The isolated classroom-economy boundary represented canonically by `class_id`.",
        # a different owner entirely
        "https://github.com/someone-else/" + RETIRED_OWNER_REPO.split("/")[1],
    ],
)
def test_detector_admits_infrastructure_names_and_the_current_url(line):
    assert retired_repository_links(line) == []


def test_this_module_is_scanned_and_does_not_report_itself():
    """The guard must cover its own file — exempting it would leave the one
    place most likely to spell the retired URL unchecked — and must not trip
    over its own fixtures."""
    rel = str(Path(__file__).resolve().relative_to(REPO_ROOT))
    assert rel in _tracked_files(), "this module must be in scope"
    assert retired_repository_links(Path(__file__).read_text(encoding="utf-8")) == []


def test_the_file_list_is_not_silently_empty():
    """Guards against the glob matching nothing, which would pass vacuously."""
    files = _tracked_files()
    assert len(files) > 100
    assert any(f.startswith("github-pages/") for f in files)
    assert not any(f.startswith("docs/archive/") for f in files)

#!/usr/bin/env python3
"""Build a GitHub release from one CHANGELOG section (SOP-DEP-002 §VII.A step 11).

The CHANGELOG section is the only source of release notes. This refuses a section that is not in the standard
shape, so the notes cannot drift from release to release:

    ## [X.Y.Z] - YYYY-MM-DD — Title

    Released as `<sha>` on YYYY-MM-DD at HH:MM UTC by release run [<id>](<run url>). No migration. | Migration `<rev>`.
    Record: [DEPLOY_<date>_<sha>.md](docs/ops/audits/DEPLOY_<date>_<sha>.md). (Further sentences may follow.)

    ### Added / Changed / Deprecated / Removed / Fixed / Security / Investigated, no code change
    (each optional, in that order)

Usage:
    python3 scripts/release_notes.py 2.2.3 --title        # prints "v2.2.3 — Title"
    python3 scripts/release_notes.py 2.2.3 > notes.md     # prints the body, links made absolute
"""
import argparse
import re
import subprocess
import sys

REPO_URL = "https://github.com/timwonderer/classroom-token-hub"
SUBSECTION_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security", "Investigated, no code change"]
RELEASED_AS = re.compile(
    r"^Released as `(?P<sha>[0-9a-f]{7,40})` on \d{4}-\d{2}-\d{2} at \d{2}:\d{2} UTC by release run "
    r"\[(?P<run>\d+)\]\(" + re.escape(REPO_URL) + r"/actions/runs/(?P=run)\)\. "
    r"(No migration|Migrations? `[0-9a-f]+`(, `[0-9a-f]+`)*)\. "
    r"Record: \[(?P<rec>DEPLOY_\d{4}-\d{2}-\d{2}_[0-9a-f]+\.md)\]\(docs/ops/audits/(?P=rec)\)\."
)


def extract(changelog: str, version: str):
    """Return (title, body) for one version, or raise ValueError naming what is out of shape."""
    head = re.compile(r"^## \[" + re.escape(version) + r"\] - (\d{4}-\d{2}-\d{2}) — (.+)$", re.M)
    m = head.search(changelog)
    if not m:
        raise ValueError(f"no '## [{version}] - YYYY-MM-DD — Title' heading")
    nxt = re.compile(r"^## \[", re.M).search(changelog, m.end())
    body = changelog[m.end(): nxt.start() if nxt else len(changelog)].strip("\n")

    first = body.split("\n", 1)[0]
    released = RELEASED_AS.match(first)
    if not released:
        raise ValueError("first line is not the standard 'Released as ...' line")

    found = re.findall(r"^### (.+)$", body, re.M)
    unknown = [h for h in found if h not in SUBSECTION_ORDER]
    if unknown:
        raise ValueError(f"unknown subsections {unknown}; allowed: {SUBSECTION_ORDER}")
    if found != sorted(found, key=SUBSECTION_ORDER.index) or len(set(found)) != len(found):
        raise ValueError(f"subsections {found} are not in the order {SUBSECTION_ORDER}, once each")

    # Relative links resolve against the repository on GitHub, not the release page.
    body = re.sub(r"\]\((?!https?://|#|mailto:)([^)]+)\)", lambda l: f"]({REPO_URL}/blob/main/{l.group(1)})", body)
    return f"v{version} — {m.group(2)}", body, released.group("sha")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="X.Y.Z, without the v")
    ap.add_argument("--title", action="store_true", help="print the release title instead of the body")
    ap.add_argument("--changelog", default="CHANGELOG.md")
    args = ap.parse_args()
    try:
        title, body, sha = extract(open(args.changelog, encoding="utf-8").read(), args.version)
    except ValueError as exc:
        sys.exit(f"CHANGELOG [{args.version}]: {exc}")
    tag = subprocess.run(["git", "rev-parse", f"v{args.version}^{{commit}}"], capture_output=True, text=True)
    if tag.returncode or not tag.stdout.startswith(sha):
        sys.exit(f"tag v{args.version} does not point at `{sha}` from the Released-as line")
    print(title if args.title else body)


if __name__ == "__main__":
    main()

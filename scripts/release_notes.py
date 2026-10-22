#!/usr/bin/env python3
"""Build a GitHub release from one CHANGELOG section (SOP-DEP-002 §VII.A step 11).

The CHANGELOG section is the only source of release notes. This refuses a section that is not in the standard
shape, so the notes cannot drift from release to release:

    ## [X.Y.Z] - YYYY-MM-DD — Title

    Released as `<sha>` on YYYY-MM-DD at HH:MM UTC by release run [<id>](<run url>). No migration. | Migration `<rev>`.
    Record: [DEPLOY_<date>_<sha>.md](docs/ops/audits/DEPLOY_<date>_<sha>.md). (Further sentences may follow.)

    ### Added / Changed / Deprecated / Removed / Fixed / Security / Investigated, no code change
    (each optional, in that order)

The notes are rendered for readers, not copied: Highlights, then Fixed, Security & Reliability, Accessibility and
Internal Changes, each a one-line-per-entry list with the full entries collapsed beneath, and the deployment record
linked at the end. Each entry names its section in an invisible tag after its bullet:
`- <!-- notes: fixed|security-reliability|accessibility|internal[, highlight] --> **Headline** ...`. A CHANGELOG entry is written for developers and runs to a paragraph; v2.3.0's verbatim notes were
about 20,000 characters, with single bullets past 2,000 (owner, 2026-10-22: "almost unreadable").

Usage:
    python3 scripts/release_notes.py 2.2.3 --title        # prints "v2.2.3 — Title"
    python3 scripts/release_notes.py 2.2.3 > notes.md     # prints the rendered notes, links made absolute
    python3 scripts/release_notes.py 2.2.3 --raw          # prints the section verbatim (links made absolute)
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


NOTES_SECTIONS = {  # tag -> heading, in the order the notes show them (owner, 2026-10-22)
    "fixed": "Fixed",
    "security-reliability": "Security & Reliability",
    "accessibility": "Accessibility",
    "internal": "Internal Changes",
}
TAG = re.compile(r"^- <!-- notes: ([a-z0-9-]+)(, highlight)? --> ")


def _entries(text: str) -> list[str]:
    """Top-level bullets of one subsection; indented lines and sub-bullets stay with their entry."""
    entries: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            entries.append(line)
        elif entries and line.strip():
            entries[-1] += "\n" + line
    return entries


def _headline(entry: str) -> str:
    """The entry's bold lead, or its first sentence when it has none."""
    entry = TAG.sub("- ", entry)
    bold = re.match(r"- \*\*(.+?)\*\*", entry)
    if bold:
        return bold.group(1).rstrip(".")
    return re.split(r"(?<=\.)\s", entry[2:].split("\n", 1)[0], maxsplit=1)[0].rstrip(".")


def _prs(entry: str) -> list[str]:
    """PRs the entry cites as its own: those in the parenthesis right after the bold headline. A PR mentioned
    later in the prose is context, not the entry's source, and is not shown."""
    own = re.match(r"- (?:<!-- [^>]* --> )?\*\*.+?\*\* \(([^)]*)\)", entry)
    seen: list[str] = []
    for number in re.findall(r"#(\d{3,5})\b", own.group(1) if own else ""):
        if f"#{number}" not in seen:
            seen.append(f"#{number}")
    return seen


def _line(entry: str) -> str:
    prs = _prs(entry)
    return f"- {_headline(entry)}" + (f" ({', '.join(prs)})" if prs else "")


def render(body: str) -> str:
    """Reader-facing notes: Highlights, then Fixed, Security & Reliability, Accessibility and Internal Changes.

    Every entry carries `<!-- notes: <section>[, highlight] -->` after its bullet; the CHANGELOG renders it
    invisibly. A section lists one line per entry (its bold headline and cited PRs), then the entries in full,
    collapsed. Highlights repeat their entries' headlines. The release run and deployment record close the notes.
    Raises ValueError for an untagged entry or an unknown section.
    """
    first, _, rest = body.partition("\n")
    # `extract` has already made the links absolute, so read the fields rather than re-match RELEASED_AS.
    when = re.search(r"on (\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2}) UTC", first)
    migrations = re.search(r"(No migration|Migrations? `[^.]+`)\.", first).group(1)
    record_match = re.search(r"Record: (\[[^\]]+\]\([^)]+\))\.", first)
    record = record_match.group(1)
    run = re.search(r"release run (\[\d+\]\([^)]+\))", first).group(1)
    extra = first[record_match.end():].strip()

    grouped: dict[str, list[str]] = {tag: [] for tag in NOTES_SECTIONS}
    highlights: list[str] = []
    for entry in _entries(re.sub(r"^### .+$", "", rest, flags=re.M)):
        tag = TAG.match(entry)
        if not tag:
            raise ValueError(f"entry has no '<!-- notes: <section> -->' tag: {entry[:80]!r}")
        if tag.group(1) not in NOTES_SECTIONS:
            raise ValueError(f"unknown notes section {tag.group(1)!r}; allowed: {list(NOTES_SECTIONS)}")
        grouped[tag.group(1)].append(entry)
        if tag.group(2):
            highlights.append(entry)

    out = [f"Released {when.group(1)} at {when.group(2)} UTC. {migrations}."]
    if highlights:
        out += ["", "## Highlights", "", *(_line(e) for e in highlights)]
    for tag, heading in NOTES_SECTIONS.items():
        entries = grouped[tag]
        if not entries:
            continue
        full = [TAG.sub("- ", e) for e in entries]
        out += ["", f"## {heading}", "", *(_line(e) for e in entries), "",
                "<details><summary>Full details</summary>", "", *full, "", "</details>"]
    out += ["", "---", "", f"Deployment record: {record} · Release run: {run}"]
    if extra:
        out += ["", extra]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="X.Y.Z, without the v")
    ap.add_argument("--title", action="store_true", help="print the release title instead of the body")
    ap.add_argument("--raw", action="store_true", help="print the section verbatim instead of rendering it")
    ap.add_argument("--changelog", default="CHANGELOG.md")
    args = ap.parse_args()
    try:
        title, body, sha = extract(open(args.changelog, encoding="utf-8").read(), args.version)
    except ValueError as exc:
        sys.exit(f"CHANGELOG [{args.version}]: {exc}")
    tag = subprocess.run(["git", "rev-parse", f"v{args.version}^{{commit}}"], capture_output=True, text=True)
    if tag.returncode or not tag.stdout.startswith(sha):
        sys.exit(f"tag v{args.version} does not point at `{sha}` from the Released-as line")
    if args.title:  # the title needs no rendering, so releases from before the notes tags still have one
        print(title)
        return
    try:
        print(body if args.raw else render(body))
    except ValueError as exc:
        sys.exit(f"CHANGELOG [{args.version}]: {exc}")


if __name__ == "__main__":
    main()

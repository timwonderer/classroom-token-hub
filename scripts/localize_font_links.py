#!/usr/bin/env python3
"""Replace Google-CDN font <link> tags in templates with the self-hosted CSS.

For every template that references fonts.googleapis.com / fonts.gstatic.com,
this removes those <link> tags (stylesheet, preconnect, and preload) and drops
in a single local stylesheet link:

    <link rel="stylesheet" href="{{ url_for('static', filename='css/fonts.css') }}">

The local link is placed where the first removed font tag was, preserving that
line's indentation. One-off run; kept in-repo for reference/auditability.
"""
from __future__ import annotations

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(REPO_ROOT, "templates")

LOCAL_LINK = (
    "<link rel=\"stylesheet\" "
    "href=\"{{ url_for('static', filename='css/fonts.css') }}\">"
)

# Any <link ...> tag (self-closing or not). <link> has no closing tag, and font
# URLs never contain '>', so matching up to the first '>' is safe. DOTALL lets a
# single tag span multiple lines (as the preload tags do).
LINK_TAG_RE = re.compile(r"<link\b[^>]*?>", re.DOTALL | re.IGNORECASE)

GOOGLE_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")

# Comments that only made sense while the CDN links existed.
STALE_COMMENT_KEYWORDS = (
    "preconnect",
    "preload material symbols",
    "for faster loading",
    "for faster icon rendering",
)


def strip_stale_comments(text: str) -> str:
    """Remove single-line ``<!-- ... -->`` comments mentioning a stale keyword.

    Previously one regex, ``^[ \\t]*<!--[^\\n]*(keyword1|...)[^\\n]*-->[ \\t]*\\n``
    (CodeQL py/polynomial-redos alert #276): the ``[^\\n]*`` on both sides of the
    alternation match the same overlapping set of characters, so a comment line
    containing many near-misses of a keyword gives the engine multiple ways to
    split the same text between the two groups. Checking "starts with <!--",
    "ends with -->", and "contains a keyword" as three independent string
    operations on each line is equivalent here (there is never more than one
    comment per line) and has no adjacent quantifiers to backtrack across.
    """
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip(" \t")
        lowered = stripped.lower()
        if (
            stripped.startswith("<!--")
            and stripped.endswith("-->")
            and any(keyword in lowered for keyword in STALE_COMMENT_KEYWORDS)
        ):
            continue
        out.append(line)
    return "\n".join(out)


def is_google_font_tag(tag: str) -> bool:
    return any(host in tag for host in GOOGLE_HOSTS)


def leading_ws(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    ws = []
    for ch in text[line_start:start]:
        if ch in " \t":
            ws.append(ch)
        else:
            break
    return "".join(ws)


def process(text: str) -> tuple[str, int]:
    matches = [m for m in LINK_TAG_RE.finditer(text) if is_google_font_tag(m.group(0))]
    if not matches:
        return text, 0

    indent = leading_ws(text, matches[0].start())
    replacement_done = False
    # Rebuild the string, splicing out google tags. Replace first with local link.
    out = []
    cursor = 0
    for m in matches:
        out.append(text[cursor:m.start()])
        if not replacement_done:
            out.append(LOCAL_LINK)
            replacement_done = True
        else:
            # Drop the tag entirely; also swallow the trailing newline + indent so
            # we don't leave a blank line behind.
            end = m.end()
            if text[end:end + 1] == "\n":
                # remove following newline and any pure-whitespace indent that led
                # up to this tag on its own line
                pass
        cursor = m.end()
    out.append(text[cursor:])
    result = "".join(out)

    # Remove comments that only made sense alongside the removed CDN links.
    result = strip_stale_comments(result)
    # Strip trailing whitespace left on otherwise-blank lines.
    result = re.sub(r"[ \t]+\n", "\n", result)
    # Collapse runs of 2+ blank lines (created by removals) into one.
    result = re.sub(r"\n{3,}", "\n\n", result)
    _ = indent  # indentation preserved implicitly by slicing before the tag
    return result, len(matches)


def main() -> int:
    changed = 0
    for root, _dirs, files in os.walk(TEMPLATES):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as fh:
                original = fh.read()
            if not any(host in original for host in GOOGLE_HOSTS):
                continue
            updated, n = process(original)
            if updated != original:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(updated)
                rel = os.path.relpath(path, REPO_ROOT)
                print(f"  {rel}: replaced {n} google font tag(s)")
                changed += 1
    print(f"Updated {changed} template(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

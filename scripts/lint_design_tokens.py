#!/usr/bin/env python3
"""Mechanical gate for the SPEC-DES-001 template contract (§IX, §XIV).

Scans ``templates/`` and reports, per file and line:

  R1  a hardcoded colour — hex, ``rgb()``/``hsl()``, or a named colour — in a CSS
      value (``<style>`` block or ``style`` attribute), in a colour-bearing SVG
      attribute, or as a string in template-embedded script
  R5  an inline ``style`` attribute whose value is static on every render
  R6  a literal design value (type, spacing, radius, elevation, motion, opacity)
      in a ``<style>`` block, or in the static part of a computed ``style``
      attribute; structural geometry (§IX) is not a design value and is ignored
  R7  a selector defined in a template ``<style>`` block that ``style.css`` also
      defines — a page copy that either duplicates the shared rule or silently
      loses to it

Usage:
    python scripts/lint_design_tokens.py            # scan templates/
    python scripts/lint_design_tokens.py FILE...    # scan named templates
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "templates"
SHARED_CSS = REPO_ROOT / "static" / "css" / "style.css"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule} {self.message}"


# ─── Lexical helpers ───

HEX = re.compile(r"(?<![\w&#/])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w-])")
COLOR_FUNC = re.compile(r"\b(?:rgba?|hsla?)\s*\(")
NAMED_COLORS = (
    "white black red green blue gray grey silver orange yellow purple pink gold "
    "navy teal maroon brown cyan magenta lime olive aqua fuchsia indigo violet "
    "crimson coral salmon tomato lightgray lightgrey darkgray darkgrey whitesmoke "
    "gainsboro"
).split()
NAMED = re.compile(r"(?<![\w-])(?:" + "|".join(NAMED_COLORS) + r")(?![\w-])", re.I)

STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)</style>", re.S | re.I)
SCRIPT_BLOCK = re.compile(r"(<script\b[^>]*>)(.*?)</script>", re.S | re.I)
STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*(["'])(.*?)\1""", re.S | re.I)
SVG_COLOR_ATTR = re.compile(r"""\s(?:fill|stroke|stop-color|color|bgcolor)\s*=\s*(["'])(.*?)\1""", re.I)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DECL = re.compile(r"(-{0,2}[a-zA-Z][\w-]*)\s*:\s*([^;]+)")

JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
# JS-built markup (`'...' + value + '...'`, `${value}`) is computed per render too.
JS_DYNAMIC = re.compile(r"""['"]\s*\+|\+\s*['"]|\$\{""")

LENGTH = re.compile(r"(?<![\w.#-])-?(?:\d+\.?\d*|\.\d+)(?:px|rem|em|pt|ms|s)\b")
ZERO_LENGTH = re.compile(r"^-?0*\.?0+(?:px|rem|em|pt|ms|s)$")


def _blank(match: re.Match) -> str:
    """Replace a comment with spaces, keeping newlines so offsets and lines hold."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _strip_comments(text: str) -> str:
    text = re.sub(r"\{#.*?#\}", _blank, text, flags=re.S)
    return re.sub(r"<!--.*?-->", _blank, text, flags=re.S)


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", _blank, css, flags=re.S)


def _strip_var(value: str) -> str:
    """Remove every var(...) including nested fallbacks."""
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"var\([^()]*\)", " ", value)
    return value


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# ─── Value classification ───

SPACING = re.compile(r"^(?:padding|margin)(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?$|^(?:row-|column-)?gap$")
RADIUS = re.compile(r"^border(?:-(?:top|bottom)-(?:left|right))?-radius$")
MOTION = re.compile(r"^(?:transition|animation)(?:-duration|-delay)?$")
COLOR_PROPS = re.compile(r"color$|^background|^border|^outline|^box-shadow$|^text-shadow$|^fill$|^stroke$|^--|^text-decoration|^caret-color$|^column-rule")


def color_literals(value: str) -> list[str]:
    """Colour literals left in a CSS value once var() references are removed."""
    bare = _strip_var(value)
    found = [m.group(0) for m in HEX.finditer(bare)]
    found += [m.group(0).rstrip("(") + ")" for m in COLOR_FUNC.finditer(bare)]
    found += [m.group(0) for m in NAMED.finditer(bare)]
    # Fallbacks inside var(--x, #fff) are still hardcoded colours.
    for fallback in re.findall(r"var\(\s*--[\w-]+\s*,([^()]*(?:\([^()]*\))?[^()]*)\)", value):
        found += [m.group(0) for m in HEX.finditer(fallback)]
        found += [m.group(0) for m in NAMED.finditer(fallback)]
    return found


def design_literal(prop: str, value: str) -> str | None:
    """Return why a declaration carries a literal design value, or None."""
    prop = prop.lower()
    value = value.replace("!important", "").strip()
    bare = _strip_var(value).strip()
    if not bare or bare.lower() in {"inherit", "initial", "unset", "revert", "none", "auto", "normal"}:
        return None

    def nonzero_lengths(units: tuple[str, ...]) -> list[str]:
        return [
            m.group(0) for m in LENGTH.finditer(bare)
            if m.group(0).endswith(units) and not ZERO_LENGTH.match(m.group(0))
        ]

    if prop == "font-size":
        if nonzero_lengths(("px", "rem", "em", "pt")) or re.search(r"\b(?:x*-?small|medium|x*-?large|larger|smaller)\b", bare):
            return "literal font-size; use a --text-* token or .type-* / .icon-* utility"
    elif prop == "font-weight":
        if re.search(r"\b[1-9]00\b|\b(?:bold|bolder|lighter)\b", bare):
            return "literal font-weight; use a --weight-* token"
    elif prop == "line-height":
        if nonzero_lengths(("px", "rem", "em", "pt")) or re.fullmatch(r"\d*\.\d+|[2-9]\d*", bare):
            return "literal line-height; use a --leading-* token"
    elif prop == "letter-spacing":
        if nonzero_lengths(("px", "rem", "em", "pt")):
            return "literal letter-spacing; use a --tracking-* token"
    elif SPACING.match(prop):
        if nonzero_lengths(("px", "rem", "em", "pt")):
            return f"literal {prop}; use a --space-* token"
    elif RADIUS.match(prop):
        if nonzero_lengths(("px", "rem", "em", "pt")):
            return f"literal {prop}; use a --radius-* token"
    elif prop in {"box-shadow", "text-shadow"}:
        if nonzero_lengths(("px", "rem", "em", "pt")):
            return f"literal {prop}; use a --shadow-* token"
    elif MOTION.match(prop):
        if nonzero_lengths(("ms", "s")):
            return f"literal {prop} duration; use a --duration-* token"
    elif prop == "opacity":
        if re.fullmatch(r"0*\.\d+|0\.\d+", bare):
            return "literal opacity; use an --alpha-* token or .alpha-* utility"
    return None


def check_declarations(block: str, base: int, text: str, rel: str, context: str) -> list[Finding]:
    findings: list[Finding] = []
    for decl in DECL.finditer(block):
        prop, value = decl.group(1), decl.group(2)
        line = _line_of(text, base + decl.start())
        if COLOR_PROPS.search(prop.lower()) or prop.startswith("--"):
            for literal in color_literals(value):
                findings.append(Finding(rel, line, "R1", f"hardcoded colour {literal!r} in {context} ({prop})"))
        reason = design_literal(prop, value)
        if reason:
            findings.append(Finding(rel, line, "R6", f"{reason} in {context}: {prop}: {value.strip()}"))
    return findings


# ─── Shared selector index (R7) ───

def _selectors(css: str) -> list[tuple[str, int]]:
    css = _strip_css_comments(css)
    out = []
    for rule in RULE.finditer(css):
        prelude = rule.group(1)
        # The prelude of the first rule inside @media carries the at-rule text.
        if "@" in prelude:
            prelude = prelude.split(";")[-1]
            if prelude.strip().startswith("@"):
                continue
        for selector in prelude.split(","):
            normalized = " ".join(selector.split())
            if not normalized or normalized in {"from", "to"} or re.fullmatch(r"[\d.]+%", normalized):
                continue
            out.append((normalized, rule.start(1)))
    return out


_SHARED_SELECTORS: set[str] | None = None


def shared_selectors() -> set[str]:
    global _SHARED_SELECTORS
    if _SHARED_SELECTORS is None:
        _SHARED_SELECTORS = {s for s, _ in _selectors(SHARED_CSS.read_text(encoding="utf-8"))}
    return _SHARED_SELECTORS


# ─── Scanning ───

SELECTOR_CONTEXT = re.compile(
    r"""(?:href|data-bs-target|data-bs-parent|data-target|aria-controls|xlink:href|action)\s*=\s*["'][^"']*$"""
    r"""|(?:querySelector(?:All)?|closest|matches|getElementById|\$)\s*\(\s*[`"'][^`"']*$"""
)


def scan_file(path: Path) -> list[Finding]:
    rel = str(path.relative_to(REPO_ROOT))
    raw = path.read_text(encoding="utf-8")
    text = _strip_comments(raw)
    findings: list[Finding] = []

    style_spans = []
    for block in STYLE_BLOCK.finditer(text):
        body_start = block.start(2)
        css = JINJA.sub(_blank, _strip_css_comments(block.group(2)))
        style_spans.append((block.start(), block.end()))
        for rule in RULE.finditer(css):
            findings += check_declarations(rule.group(2), body_start + rule.start(2), text, rel, "<style>")
        shared = shared_selectors()
        for selector, offset in _selectors(css):
            if selector in shared:
                findings.append(Finding(rel, _line_of(text, body_start + offset), "R7",
                                        f"selector {selector!r} is also defined in static/css/style.css"))

    def in_style_block(offset: int) -> bool:
        return any(start <= offset < end for start, end in style_spans)

    for attr in STYLE_ATTR.finditer(text):
        if in_style_block(attr.start()):
            continue
        value = attr.group(2)
        line = _line_of(text, attr.start())
        dynamic = bool(JINJA.search(value) or JS_DYNAMIC.search(value))
        if not dynamic and value.strip():
            findings.append(Finding(rel, line, "R5", f'static inline style="{value.strip()}"'))
            continue
        static_part = JS_DYNAMIC.sub(" ", JINJA.sub(" ", value))
        findings += check_declarations(static_part, attr.start(2), text, rel, "style attribute")

    for attr in SVG_COLOR_ATTR.finditer(text):
        if JINJA.search(attr.group(2)):
            continue
        for literal in color_literals(attr.group(2)):
            findings.append(Finding(rel, _line_of(text, attr.start()), "R1",
                                    f"hardcoded colour {literal!r} in attribute"))

    for script in SCRIPT_BLOCK.finditer(text):
        body = script.group(2)
        base = script.start(2)
        for match in re.finditer(r"""(["'`])((?:(?!\1).)*)\1""", body):
            literal = match.group(2)
            preceding = body[max(0, match.start() - 80):match.start() + 1]
            if SELECTOR_CONTEXT.search(preceding):
                continue
            if re.fullmatch(r"\s*#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\s*", literal) \
                    or COLOR_FUNC.match(literal.strip()) \
                    or re.fullmatch(r"\s*(?:" + "|".join(NAMED_COLORS) + r")\s*", literal, re.I):
                findings.append(Finding(rel, _line_of(text, base + match.start()), "R1",
                                        f"hardcoded colour {literal.strip()!r} in script"))

    return findings


def scan(paths: list[Path] | None = None) -> list[Finding]:
    targets = paths or sorted(TEMPLATES.rglob("*.html"))
    findings: list[Finding] = []
    for path in targets:
        findings += scan_file(path.resolve())
    return sorted(set(findings), key=lambda f: (f.path, f.line, f.rule, f.message))


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv] or None
    findings = scan(paths)
    for finding in findings:
        print(finding)
    if findings:
        by_rule: dict[str, int] = {}
        for finding in findings:
            by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
        summary = ", ".join(f"{rule}={count}" for rule, count in sorted(by_rule.items()))
        print(f"\n{len(findings)} finding(s) in {len({f.path for f in findings})} template(s): {summary}")
        return 1
    print("SPEC-DES-001 template contract: no findings")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""The docs site is a brand surface and must carry the canonical brand values.

SPEC-DES-001 §XIII: ``docs-site/`` maintains its own stylesheet and is outside
the runtime token layer, but it MUST NOT contradict the canonical values in
§VI.4. The same section records a live brand split on ``github-pages/`` as the
shape this failure takes when nothing checks it — a published surface rendering
a colour the design system retired, with no symptom anywhere.

The check is over token *values*, not over whether a file mentions a colour: the
docs site is free to consume a subset of the tokens, but any token it does
define must agree with ``static/css/tokens.css``.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_TOKENS = REPO_ROOT / "static" / "css" / "tokens.css"
SITE_TOKENS = REPO_ROOT / "docs-site" / "src" / "css" / "tokens.css"

# The values SPEC-DES-001 §VI.4 names as canonical, plus the pinned text token
# §VI.6 exists to protect. A surface that gets these right is on-brand; one that
# gets any of them wrong is the github-pages failure repeating.
BRAND_TOKENS = (
    "--primary",
    "--primary-hover",
    "--primary-subtle",
    "--secondary",
    "--secondary-hover",
    "--secondary-subtle",
    "--accent-text-on-light",
    "--background",
    "--surface",
    "--text-inverse",
)

_DECLARATION = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)


def declared_tokens(css_source):
    """Custom properties declared on the default (teacher) role, last wins.

    Role-dependent tokens are declared three times in the application's token
    layer — once on ``:root`` for the teacher default and once under each of the
    student and sysadmin body classes. A docs reader holds no role, so the site
    carries the default identity, and only the ``:root`` blocks are comparable.
    Reading the file as one flat namespace would compare the docs site against
    whichever theme happens to be written last, which is Guardian Gray.

    Pure over the source text so the detector can be run against a synthetic
    off-brand stylesheet rather than only against a compliant repository.
    """
    tokens = {}
    # Comments sit between rules and would otherwise be read as part of the
    # next selector, which silently skips the block they document.
    source = re.sub(r"/\*.*?\*/", "", css_source, flags=re.DOTALL)
    for selector, body in _RULE.findall(source):
        if not selector.strip().startswith(":root"):
            continue
        for name, value in _DECLARATION.findall(body):
            tokens[name] = value.strip()
    return tokens


def test_declared_tokens_reports_an_off_brand_value():
    """Mutation proof: the detector must see a retired brand colour.

    #d3af37 is the v1 gold that github-pages still carries — the near miss a
    future edit would really produce, not an obviously wrong value.
    """
    mutated = ":root { --primary: #236960; --secondary: #d3af37; }"

    assert declared_tokens(mutated)["--secondary"] == "#d3af37"
    assert declared_tokens(mutated)["--primary"] != "#1a4d47"


@pytest.mark.parametrize("token", BRAND_TOKENS)
def test_docs_site_token_matches_the_application(token):
    app_tokens = declared_tokens(APP_TOKENS.read_text(encoding="utf-8"))
    site_tokens = declared_tokens(SITE_TOKENS.read_text(encoding="utf-8"))

    assert token in site_tokens, f"{token} is not defined by the docs site"
    assert site_tokens[token] == app_tokens[token], (
        f"{token} is {site_tokens[token]} on the docs site and "
        f"{app_tokens[token]} in static/css/tokens.css"
    )


def test_the_docs_site_stylesheet_states_no_colour_of_its_own():
    """Design values live in the token layer; custom.css only maps them.

    SPEC-DES-001 §XII: the token layer conforms when the component layer
    contains no raw colour outside a token definition.
    """
    custom = (REPO_ROOT / "docs-site" / "src" / "css" / "custom.css").read_text(
        encoding="utf-8"
    )
    without_comments = re.sub(r"/\*.*?\*/", "", custom, flags=re.DOTALL)

    literals = re.findall(
        r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)", without_comments
    )
    # The specificity escape hatch :not(#\#) is a selector, not a colour.
    literals = [value for value in literals if not value.startswith("#\\")]

    assert literals == [], f"raw colour in custom.css: {literals}"


def test_the_brand_mark_is_text_not_an_image():
    """SPEC-DES-001 §IX: the brand is the three-row wordmark, never a logo file.

    An image cannot take the role theme, cannot be recoloured by a token, and
    needs a redundant alt string to be read aloud.
    """
    home = (REPO_ROOT / "docs-site" / "src" / "pages" / "index.js").read_text(
        encoding="utf-8"
    )

    for word in ("CLASSROOM", "TOKEN", "HUB"):
        assert f'"{word}"' in home
    for icon in ("local_atm", "store", "finance_mode"):
        assert f'"{icon}"' in home

    assets = REPO_ROOT / "docs-site" / "static"
    logos = [
        path
        for path in assets.rglob("*")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    ]
    assert logos == [], f"image assets that could stand in for the brand: {logos}"


def referenced_tokens(css_source):
    """Project custom properties a stylesheet consumes via var().

    Infima's own namespaces are excluded: --ifm-* and --docusaurus-* are
    defined by the theme, not by this workspace.

    Pure over the source text, so the detector can be run against a synthetic
    stylesheet that references a token nobody defines.
    """
    names = set(re.findall(r"var\(\s*(--[a-z0-9-]+)", css_source))
    return {
        name
        for name in names
        if not name.startswith(("--ifm-", "--docusaurus-"))
    }


def test_referenced_tokens_reports_a_token_nobody_defines():
    """Mutation proof: an undefined token must be visible to the detector.

    This is not hypothetical. `border: var(--space-hairline) solid
    var(--border-color)` was written against a token the site's own token layer
    did not define. CSS drops the whole declaration when a var() in a shorthand
    is empty, so the borders on cards, the navbar, the footer and the code
    blocks silently did not render — and border-color fell back to currentColor,
    which on a card that is a link is the link colour.
    """
    mutated = ".card { border: var(--space-hairline) solid var(--border-color); }"

    assert referenced_tokens(mutated) == {"--space-hairline", "--border-color"}


def test_every_token_the_stylesheet_uses_is_defined():
    site_css_dir = REPO_ROOT / "docs-site" / "src" / "css"
    all_css = "".join(
        stylesheet.read_text(encoding="utf-8")
        for stylesheet in site_css_dir.glob("*.css")
    )
    defined = {name for name, _ in _DECLARATION.findall(all_css)}

    used = referenced_tokens(
        (site_css_dir / "custom.css").read_text(encoding="utf-8")
    ) | referenced_tokens(
        (site_css_dir / "tokens.css").read_text(encoding="utf-8")
    )

    assert used <= defined, f"undefined token(s): {sorted(used - defined)}"

"""No Jinja filter wraps unescaped text in Markup(), no template bare-|safes.

Required follow-up to ``docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md``
§5: two independent XSS sinks (S1, S4; see ``GHSA-7fxj-gpw3-23g3``) shipped and
sat in production for up to ~11 months because neither CodeQL's default suite
nor ``security-extended`` has a query for this taint shape — a custom filter
that calls ``Markup()`` without escaping first, or ``|safe``-filtered template
output built from request- or database-sourced text. The incident record marks
a guard for this pattern "required, not optional".

Two layers, per SOP-TEST-003 §IX.A: a structural guard over the real sources
(expect zero violations today — both sinks are already fixed), and mutation
proofs that reproduce the exact shipped bug shapes against the detector
directly, so a passing guard is evidence, not a coincidence of nothing being
broken right now.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guards.unsafe_jinja_filter_markup import (
    find_filter_registrations,
    find_unsafe_markup_in_filters,
    find_autoescape_false_blocks,
    find_unsafe_safe_filters,
    find_template_violations,
    load_baseline,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
TEMPLATES_ROOT = REPO_ROOT / "templates"
BASELINE_PATH = Path(__file__).resolve().parent / "guards" / "unsafe_safe_filter_baseline.txt"


def _app_sources() -> list[Path]:
    return sorted(APP_ROOT.rglob("*.py"))


def _template_sources() -> list[Path]:
    return sorted(TEMPLATES_ROOT.rglob("*.html"))


# --------------------------------------------------------------------------
# Structural guard — Part A, Python filter functions
# --------------------------------------------------------------------------

def test_no_registered_filter_wraps_unescaped_text_in_markup():
    sources = _app_sources()
    filter_names: set[str] = set()
    for path in sources:
        filter_names |= find_filter_registrations(path.read_text(encoding="utf-8"))

    assert filter_names >= {"nl2br_filter", "render_markdown", "url_encode_filter"}, (
        "guard did not find the filters registered in app/__init__.py — "
        "has the registration pattern changed?"
    )

    violations = []
    for path in sources:
        violations += find_unsafe_markup_in_filters(
            path.read_text(encoding="utf-8"),
            filter_names,
            str(path.relative_to(REPO_ROOT)),
        )

    assert not violations, (
        "a Jinja filter calls Markup() on text that is not provably escaped "
        "first (the S4 taint shape, GHSA-7fxj-gpw3-23g3):\n  "
        + "\n  ".join(str(v) for v in violations)
    )


# --------------------------------------------------------------------------
# Structural guard — Part B, templates
# --------------------------------------------------------------------------

def test_no_template_has_an_unrouted_unsafe_safe_filter_or_autoescape_false():
    baseline = load_baseline(BASELINE_PATH.read_text(encoding="utf-8"))

    violations = []
    for path in _template_sources():
        violations += find_template_violations(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))
        )

    unrouted = [v for v in violations if v.key is None or v.key not in baseline]

    assert not unrouted, (
        "a template marks output |safe without a proven-safe filter ahead of "
        "it, or disables autoescaping (the S1 dashboard-sink taint shape, "
        "GHSA-7fxj-gpw3-23g3). If this is genuinely safe (pre-sanitized before "
        "reaching the template, or author-controlled, not request/DB data), "
        "add a justified entry to tests/guards/unsafe_safe_filter_baseline.txt "
        "— that file only shrinks, it is not a place to silence a new finding "
        "without review:\n  " + "\n  ".join(str(v) for v in unrouted)
    )


def test_baseline_has_no_stale_entries():
    """The baseline only shrinks (same discipline as migrations/lint_baseline.txt):
    an entry that no longer matches a real violation must be deleted."""
    baseline = load_baseline(BASELINE_PATH.read_text(encoding="utf-8"))

    live_keys = set()
    for path in _template_sources():
        for v in find_unsafe_safe_filters(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))
        ):
            live_keys.add(v.key)

    stale = baseline - live_keys
    assert not stale, f"stale baseline entries, delete them: {sorted(stale)}"


def test_guard_still_recognises_the_real_safe_usages():
    """SOP-TEST-003 §IX.A(4): the allowlisted ``|nl2br|safe`` usages this repo
    actually ships must still parse as filter usages, not silently skip."""
    total_safe_exprs = 0
    for path in _template_sources():
        source = path.read_text(encoding="utf-8")
        total_safe_exprs += source.count("|safe")
    assert total_safe_exprs >= 2, "guard's test fixture is stale: expected the two known |nl2br|safe usages"


# --------------------------------------------------------------------------
# Mutation proofs — SOP-TEST-003 §IX.A
# --------------------------------------------------------------------------

def test_detector_reports_the_shipped_s4_filter_verbatim():
    """The exact shape ``nl2br_filter`` shipped with before the fix."""
    shipped = """
def nl2br_filter(s):
    if s is None:
        return ''
    return Markup(s.replace('\\n', '<br>\\n'))
"""
    violations = find_unsafe_markup_in_filters(shipped, {"nl2br_filter"})
    assert len(violations) == 1
    assert violations[0].filter_name == "nl2br_filter"


def test_detector_is_quiet_on_the_real_fixed_nl2br_filter():
    """The real, currently-shipped fix must not itself be a false positive."""
    init_source = (APP_ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "def nl2br_filter(s):" in init_source
    violations = find_unsafe_markup_in_filters(init_source, {"nl2br_filter"})
    assert violations == [], violations


def test_detector_reports_a_bare_name_passed_straight_to_markup():
    source = """
def render_whatever(raw_text):
    return Markup(raw_text)
"""
    violations = find_unsafe_markup_in_filters(source, {"render_whatever"})
    assert len(violations) == 1


def test_detector_is_quiet_on_a_literal_markup_call():
    source = """
def spacer():
    return Markup('&mdash;')
"""
    assert find_unsafe_markup_in_filters(source, {"spacer"}) == []


def test_detector_is_quiet_on_escape_then_markup():
    source = """
def render_whatever(raw_text):
    from markupsafe import escape, Markup
    safe = escape(raw_text)
    return Markup(safe)
"""
    assert find_unsafe_markup_in_filters(source, {"render_whatever"}) == []


def test_detector_is_quiet_on_bleach_clean_then_markup():
    source = """
def render_whatever(raw_html):
    cleaned = bleach.Cleaner(tags=['p']).clean(raw_html)
    return Markup(cleaned)
"""
    assert find_unsafe_markup_in_filters(source, {"render_whatever"}) == []


def test_detector_ignores_markup_in_an_unregistered_function():
    """Shape alone isn't enough — it must actually be a registered filter."""
    source = """
def not_a_filter(raw_text):
    return Markup(raw_text)
"""
    assert find_unsafe_markup_in_filters(source, {"some_other_filter"}) == []


def test_registration_finder_matches_the_real_registration_pattern():
    init_source = (APP_ROOT / "__init__.py").read_text(encoding="utf-8")
    names = find_filter_registrations(init_source)
    assert {"url_encode_filter", "render_markdown", "nl2br_filter"} <= names


def test_registration_finder_reports_a_synthetic_registration():
    source = "app.jinja_env.filters['greeting'] = render_greeting\n"
    assert find_filter_registrations(source) == {"render_greeting"}


def test_detector_reports_a_bare_safe_filter_template():
    """The exact shape S1's dashboard sink shipped before the fix."""
    source = '<div id="serverState" hidden>{{ attendance_state_json|safe }}</div>\n'
    violations = find_unsafe_safe_filters(source)
    assert len(violations) == 1
    assert violations[0].kind == "unsafe_safe_filter"


def test_detector_reports_autoescape_false_unconditionally():
    source = "{% autoescape false %}\n{{ announcement.message }}\n{% endautoescape %}\n"
    violations = find_autoescape_false_blocks(source)
    assert len(violations) == 1


def test_detector_is_quiet_on_the_allowlisted_nl2br_safe_usage():
    source = "<p>{{ announcement.message|nl2br|safe }}</p>\n"
    assert find_unsafe_safe_filters(source) == []


def test_detector_is_quiet_on_plain_autoescaped_output():
    source = '<div id="serverState" hidden>{{ attendance_state_json }}</div>\n'
    assert find_template_violations(source) == []


def test_detector_distinguishes_allowlisted_from_non_allowlisted_filter_before_safe():
    """A filter not yet proven safe must still be caught even chained with one that is."""
    source = "<p>{{ message|nl2br|striptags|safe }}</p>\n"
    violations = find_unsafe_safe_filters(source)
    assert len(violations) == 1


# Review near misses: sanitization must cover every emitted part, at the sink.


@pytest.mark.parametrize('expression', [
    'raw + escape("constant")',
    'escape("constant") + raw',
    "f'{raw}{escape(\"constant\")}'",
    'escaped.replace("x", raw)',
    'escaped.format(raw)',
])
def test_detector_reports_partially_escaped_markup(expression):
    source = f'def render(raw):\n    escaped = escape(raw)\n    return Markup({expression})\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


@pytest.mark.parametrize('body', [
    'value = escape(raw)\n    value = raw\n    return Markup(value)',
    'return Markup(value)\n    value = escape(raw)',
    'value = escape(raw)\n    if flag:\n        value = raw\n    return Markup(value)',
    'if flag:\n        value = escape(raw)\n    return Markup(value)',
    'value = escape(raw)\n    value += raw\n    return Markup(value)',
    'value = escape(raw)\n    for value in rows:\n        return Markup(value)',
    'value = escape(raw)\n    while flag:\n        value = raw\n    return Markup(value)',
    'value = escape(raw)\n    value, other = raw, ""\n    return Markup(value)',
    'value = escape(raw)\n    return Markup((value := raw))',
    'value = escape(raw)\n    try:\n        value = raw\n    finally:\n        return Markup(value)',
])
def test_detector_reports_unsafe_reaching_assignment(body):
    source = f'def render(raw, flag, rows):\n    {body}\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


@pytest.mark.parametrize('body', [
    'value = raw\n    value = escape(value)\n    return Markup(value)',
    'if flag:\n        value = escape(raw)\n    else:\n        value = bleach.clean(raw)\n    return Markup(value)',
    'value = escape(raw)\n    result = Markup(value)\n    value = raw\n    return result',
    'return Markup(escape(raw) + "<br>" + bleach.clean(raw))',
    'value = escape(raw)\n    value = value + "<br>"\n    return Markup(value)',
])
def test_detector_accepts_safe_reaching_assignments(body):
    source = f'def render(raw, flag):\n    {body}\n'
    assert find_unsafe_markup_in_filters(source, {'render'}) == []


@pytest.mark.parametrize('expression', [
    '{{ raw|safe() }}',
    '{{- raw|safe -}}',
    '{{ raw|safe|upper }}',
    '{{ raw|safe()|upper }}',
    '{{ "<b>" ~ (raw|safe) }}',
])
def test_detector_reports_alternative_safe_filter_syntax(expression):
    violations = find_unsafe_safe_filters('\n' + expression)
    assert len(violations) == 1
    assert violations[0].line == 2


@pytest.mark.parametrize('expression', [
    '{{ raw|nl2br|safe() }}',
    '{{- raw|nl2br|safe -}}',
    '{{ raw|nl2br|safe|upper }}',
    '{{ "literal|safe" }}',
])
def test_detector_accepts_safe_jinja_syntax(expression):
    assert find_unsafe_safe_filters(expression) == []


def test_nonterminal_safe_does_not_reuse_a_trailing_safe_baseline_key():
    trailing = find_unsafe_safe_filters('{{ raw|safe }}')[0]
    nonterminal = find_unsafe_safe_filters('{{ raw|safe|replace("x", untrusted) }}')[0]
    assert trailing.key != nonterminal.key

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

from collections import Counter
from pathlib import Path

import pytest

from tests.guards.unsafe_jinja_filter_markup import (
    CARD_RAW_ARGUMENTS,
    find_unsafe_card_macro_arguments,
    find_filter_registrations,
    find_unsafe_markup_in_filters,
    find_autoescape_false_blocks,
    find_unsafe_safe_filters,
    find_template_violations,
    load_baseline,
    unbaselined_violations,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"
STATUS_ROOT = REPO_ROOT / "status_service"
TEMPLATES_ROOT = REPO_ROOT / "templates"
BASELINE_PATH = Path(__file__).resolve().parent / "guards" / "unsafe_safe_filter_baseline.txt"


def _app_sources() -> list[Path]:
    return sorted([*APP_ROOT.rglob("*.py"), *STATUS_ROOT.rglob("*.py")])


def _template_sources() -> list[Path]:
    return sorted([*TEMPLATES_ROOT.rglob("*.html"), *(STATUS_ROOT / "templates").rglob("*.html")])


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

    unrouted = unbaselined_violations(violations, baseline)

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

    live_keys = Counter()
    for path in _template_sources():
        for v in find_unsafe_safe_filters(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))
        ):
            live_keys[v.key] += 1

    stale = baseline - live_keys
    assert not stale, f"stale baseline entries, delete them: {sorted(stale)}"


def test_guard_still_recognises_the_real_safe_usages():
    """SOP-TEST-003 §IX.A(4): the allowlisted ``|nl2br|safe`` usages this repo
    actually ships must still parse as filter usages, not silently skip."""
    found = []
    for path in _template_sources():
        found.extend(find_unsafe_safe_filters(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT)), allowlist=frozenset()
        ))
    expected = {
        "templates/admin_announcements.html::announcement.message|nl2br|safe",
        "templates/student_dashboard.html::announcement.message|nl2br|safe",
    }
    assert Counter(v.key for v in found if v.key in expected) == Counter({key: 1 for key in expected})


def test_card_macro_baseline_premises_hold_for_every_caller():
    violations = []
    for path in _template_sources():
        violations.extend(find_unsafe_card_macro_arguments(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))
        ))
    assert not violations, "\n".join(str(v) for v in violations)


def test_card_macro_guard_positions_match_the_real_definitions():
    from jinja2 import Environment, nodes

    tree = Environment(autoescape=True).parse((TEMPLATES_ROOT / 'macros/cards.html').read_text())
    definitions = {macro.name: macro for macro in tree.find_all(nodes.Macro)}
    for name, arguments in CARD_RAW_ARGUMENTS.items():
        assert {arg: definitions[name].args[index].name for arg, index in arguments.items()} == {arg: arg for arg in arguments}


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
import bleach
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
    source = f'from markupsafe import escape\nimport bleach\ndef render(raw):\n    escaped = escape(raw)\n    return Markup({expression})\n'
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
    source = f'from markupsafe import escape\nimport bleach\ndef render(raw, flag, rows):\n    {body}\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


@pytest.mark.parametrize('body', [
    'value = raw\n    value = escape(value)\n    return Markup(value)',
    'if flag:\n        value = escape(raw)\n    else:\n        value = bleach.clean(raw)\n    return Markup(value)',
    'value = escape(raw)\n    result = Markup(value)\n    value = raw\n    return result',
    'return Markup(escape(raw) + "<br>" + bleach.clean(raw))',
    'value = escape(raw)\n    value = value + "<br>"\n    return Markup(value)',
])
def test_detector_accepts_safe_reaching_assignments(body):
    source = f'from markupsafe import escape\nimport bleach\ndef render(raw, flag):\n    {body}\n'
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


@pytest.mark.parametrize('setup, expression', [
    ('def escape(value):\n    return value', 'escape(raw)'),
    ('', 'passthrough.clean(raw)'),
    ('from helpers import escape', 'escape(raw)'),
    ('import helpers as bleach', 'bleach.clean(raw)'),
    ('import markupsafe\nmarkupsafe.escape = passthrough', 'markupsafe.escape(raw)'),
])
def test_detector_rejects_same_named_non_sanitizers(setup, expression):
    source = f'{setup}\ndef render(raw):\n    return Markup({expression})\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


@pytest.mark.parametrize('body', [
    'from markupsafe import escape\n    escape = passthrough\n    return Markup(escape(raw))',
    'from markupsafe import escape\n    from .helpers import escape\n    return Markup(escape(raw))',
    'import bleach\n    cleaner = bleach.Cleaner()\n    cleaner = passthrough\n    return Markup(cleaner.clean(raw))',
    'from markupsafe import escape\n    if flag:\n        escape = passthrough\n    return Markup(escape(raw))',
    'from markupsafe import escape\n    def escape(value):\n        return value\n    return Markup(escape(raw))',
])
def test_detector_invalidates_reassigned_sanitizer_provenance(body):
    source = f'def render(raw, flag):\n    {body}\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


@pytest.mark.parametrize('setup, expression', [
    ('from markupsafe import escape as esc', 'esc(raw)'),
    ('import markupsafe as ms', 'ms.escape(raw)'),
    ('from bleach import clean as sanitize', 'sanitize(raw)'),
    ('import bleach as sanitizer', 'sanitizer.clean(raw)'),
    ('from bleach import Cleaner', 'Cleaner().clean(raw)'),
    ('import bleach\n    cleaner = bleach.Cleaner()', 'cleaner.clean(raw)'),
])
def test_detector_accepts_imported_sanitizer_provenance(setup, expression):
    source = f'def render(raw):\n    {setup}\n    return Markup({expression})\n'
    assert find_unsafe_markup_in_filters(source, {'render'}) == []


@pytest.mark.parametrize('expression', ['Markup(object=raw)', 'Markup(**kwargs)', 'Markup(*args)'])
def test_detector_reports_keyword_or_unknown_markup_input(expression):
    source = f'def render(raw, args, kwargs):\n    return {expression}\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


def test_detector_accepts_sanitized_keyword_markup_input():
    source = 'from markupsafe import escape\ndef render(raw):\n    return Markup(object=escape(raw))\n'
    assert find_unsafe_markup_in_filters(source, {'render'}) == []


@pytest.mark.parametrize('registration', [
    "app.jinja_env.filters['x'] = filters.render_x",
    "app.jinja_env.filters.update({'x': render_x})",
    "app.jinja_env.filters.update(x=render_x)",
    "app.add_template_filter(render_x, 'x')",
    "app.add_template_filter(f=render_x, name='x')",
    "@app.template_filter('x')\ndef render_x(raw):\n    return Markup(raw)",
])
def test_detector_discovers_and_scans_other_registration_forms(registration):
    source = registration
    if not registration.startswith('@'):
        source += '\ndef render_x(raw):\n    return Markup(raw)\n'
    names = find_filter_registrations(source)
    assert names == {'render_x'}
    assert len(find_unsafe_markup_in_filters(source, names)) == 1


@pytest.mark.parametrize('registration', [
    "app.jinja_env.filters['x'] = lambda raw: Markup(raw)",
    "app.jinja_env.filters.update(dynamic_filters)",
    "app.jinja_env.filters.update(**dynamic_filters)",
])
def test_detector_fails_closed_on_unknown_registration_forms(registration):
    with pytest.raises(ValueError, match='unsupported Jinja'):
        find_filter_registrations(registration)


@pytest.mark.parametrize('value', ['false', 'False'])
def test_detector_reports_jinja_false_constant_spellings(value):
    source = f'{{%- autoescape {value} -%}}\n{{{{ raw }}}}\n{{% endautoescape %}}'
    assert len(find_autoescape_false_blocks(source)) == 1


@pytest.mark.parametrize('value', ['true', 'True'])
def test_detector_accepts_enabled_autoescape(value):
    source = f'{{% autoescape {value} %}}{{{{ raw }}}}{{% endautoescape %}}'
    assert find_autoescape_false_blocks(source) == []


def test_repository_guard_scans_status_service_sources_and_templates(tmp_path, monkeypatch):
    status_root = tmp_path / 'status_service'
    template_root = status_root / 'templates'
    template_root.mkdir(parents=True)
    app_path = status_root / 'app.py'
    app_path.write_text("app.jinja_env.filters['x'] = render_x\ndef render_x(raw):\n    return Markup(raw)\n")
    template_path = template_root / 'public_status.html'
    template_path.write_text('{{ raw|safe }}')
    monkeypatch.setattr(f'{__name__}.STATUS_ROOT', status_root)
    assert app_path in _app_sources()
    assert template_path in _template_sources()
    names = find_filter_registrations(app_path.read_text())
    assert len(find_unsafe_markup_in_filters(app_path.read_text(), names)) == 1
    assert len(find_template_violations(template_path.read_text())) == 1


def test_repository_guard_finds_real_status_filters():
    assert STATUS_ROOT / 'app.py' in _app_sources()
    names = find_filter_registrations((STATUS_ROOT / 'app.py').read_text())
    assert {'format_status_time', 'iso_utc'} <= names
    assert STATUS_ROOT / 'templates/public_status.html' in _template_sources()


def test_baseline_counts_reviewed_occurrences_and_routes_duplicates():
    key = 'templates/example.html::toc|safe'
    baseline = load_baseline(f'# Two reviewed sinks\n{key}\n{key}\n')
    assert baseline == Counter({key: 2})
    reviewed = find_template_violations('{{ toc|safe }}\n{{ toc|safe }}', 'templates/example.html')
    assert unbaselined_violations(reviewed, baseline) == []
    added = find_template_violations('{{ toc|safe }}\n' * 3, 'templates/example.html')
    assert len(unbaselined_violations(added, baseline)) == 1
    assert unbaselined_violations(added, baseline)[0].line == 3
    assert baseline == Counter({key: 2})
    assert baseline - Counter(v.key for v in reviewed[:1]) == Counter({key: 1})


@pytest.mark.parametrize('setup, constructor', [
    ('from markupsafe import Markup as M', 'M'),
    ('import markupsafe as ms\n    M = ms.Markup', 'M'),
    ('from markupsafe import Markup\n    constructor = Markup', 'constructor'),
])
def test_detector_reports_aliased_markup_constructors(setup, constructor):
    source = f'def render(raw):\n    {setup}\n    return {constructor}(raw)\n'
    assert len(find_unsafe_markup_in_filters(source, {'render'})) == 1


def test_detector_accepts_sanitized_aliased_markup():
    source = 'from markupsafe import Markup as M, escape as e\ndef render(raw):\n    return M(e(raw))\n'
    assert find_unsafe_markup_in_filters(source, {'render'}) == []


@pytest.mark.parametrize('expression', [
    "cards.alert_card('info', 'title', attrs=raw)",
    "cards.alert_card('info', 'title', body_attrs=request_text)",
    "cards.top_card('title', header_actions=db_text)",
    "cards.nested_card('title', header_actions='<b>' ~ raw ~ '</b>')",
    "cards.alert_card('info', 'title', None, '', None, None, 'h3', False, raw)",
    "cards.alert_card('info', 'title', **kwargs)",
    "cards.alert_card(*args)",
    "cards['alert_card']('info', 'title', attrs=raw)",
    "cards[macro_name]('info', 'title', attrs=raw)",
    "(cards|attr('alert_card'))('info', 'title', attrs=raw)",
    "cards.alert_card('info', 'title', attrs=raw|int(default=unsafe_text))",
])
def test_card_macro_guard_reports_unconstrained_markup(expression):
    source = "{% import 'macros/cards.html' as cards %}{{ " + expression + " }}"
    assert find_unsafe_card_macro_arguments(source)


@pytest.mark.parametrize('expression', [
    "cards.alert_card('info', 'title', attrs='hidden')",
    "cards.alert_card('info', 'title', attrs='data-id=\"' ~ (announcement.id|int) ~ '\"')",
    "cards.top_card('title', header_actions='<b>static</b>')",
    "cards['alert_card']('info', 'title', body_attrs='tabindex=\"-1\"')",
])
def test_card_macro_guard_accepts_literal_and_integer_markup(expression):
    source = "{% import 'macros/cards.html' as cards %}{{ " + expression + " }}"
    assert find_unsafe_card_macro_arguments(source) == []


def test_card_macro_guard_catches_imported_alias_and_forwarding():
    imported = "{% from 'macros/cards.html' import alert_card as notice %}{{ notice('info', 'title', attrs=raw) }}"
    assert len(find_unsafe_card_macro_arguments(imported)) == 1
    forwarded = "{% import 'macros/cards.html' as cards %}{% set notice = cards.alert_card %}{{ notice('info', 'title', attrs=raw) }}"
    assert find_unsafe_card_macro_arguments(forwarded)


def test_card_macro_guard_catches_an_unsafe_default():
    assert find_unsafe_card_macro_arguments("{% macro alert_card(level, title, attrs=raw) %}{{ attrs|safe }}{% endmacro %}")


@pytest.mark.parametrize('identifier, expected', [(123, '123'), ('\" onmouseover=alert(1)', '0')])
def test_real_announcement_macro_constrains_raw_attribute_identifier(identifier, expected):
    from types import SimpleNamespace
    from jinja2 import Environment, FileSystemLoader

    source = (TEMPLATES_ROOT / 'student_dashboard.html').read_text()
    opening = next(line for line in source.splitlines() if "attrs='data-announcement-id=" in line)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_ROOT)), autoescape=True)
    snippet = env.from_string("{% import 'macros/cards.html' as cards %}" + opening + "message{% endcall %}")
    announcement = SimpleNamespace(id=identifier, title='title', get_priority_level=lambda: 'info', get_priority_icon=lambda: 'info')
    rendered = snippet.render(announcement=announcement)
    if isinstance(identifier, int):
        prior_opening = opening.replace('(announcement.id | int)', 'announcement.id')
        prior = env.from_string("{% import 'macros/cards.html' as cards %}" + prior_opening + "message{% endcall %}")
        assert rendered == prior.render(announcement=announcement)
    assert f'data-announcement-id="{expected}"' in rendered
    from html.parser import HTMLParser

    class AttributeNames(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert 'onmouseover' not in dict(attrs)

    AttributeNames().feed(rendered)

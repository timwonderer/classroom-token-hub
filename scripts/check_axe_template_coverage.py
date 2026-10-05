#!/usr/bin/env python3
"""Fail a PR that changes a template no axe scenario ever rendered.

A changed template is *covered* when at least one canonical accessibility
render path put it in front of axe-core:

* a real-route scenario (``tests/test_axe_app_pages.py``), recorded to
  ``AXE_RENDERED_TEMPLATES_FILE``; or
* a registered fixture state (``tests/a11y_fixtures``, audited by
  ``tests/test_axe_fixture_pages.py``), recorded to ``AXE_FIXTURE_TEMPLATES_FILE``.

Either way the template counts when it was rendered directly, or when a rendered
template reaches it through ``extends``, ``include``, ``import`` or
``from ... import`` -- so a change to a layout or macro is covered by every page
that uses it. A template with a real-route scenario needs no duplicate fixture.

A changed template with neither path, and no individually justified entry in the
exemptions file, fails the gate. "No convenient route" is not a justification:
register a fixture state instead.

Usage:
    check_axe_template_coverage.py --changed changed.txt --rendered routes.json \
        [--fixture-rendered fixtures.json] \
        [--exemptions tests/axe_coverage_exemptions.json] [--templates-dir templates]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, meta

TEMPLATES_PREFIX = "templates/"


def referenced(env: Environment, name: str) -> set[str]:
    """Templates ``name`` extends, includes or imports (one level)."""
    try:
        source, _, _ = env.loader.get_source(env, name)
        ast = env.parse(source)
    except Exception:  # missing or unparsable template: nothing reachable from it
        return set()
    return {ref for ref in meta.find_referenced_templates(ast) if ref}


def closure(env: Environment, roots: set[str]) -> set[str]:
    """Every template reachable from ``roots`` through extends/include/import."""
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(referenced(env, name) - seen)
    return seen


def uncovered(changed: set[str], covered: set[str], exemptions: dict[str, str]) -> list[str]:
    return sorted(name for name in changed if name not in covered and name not in exemptions)


def stale_exemptions(exemptions: dict[str, str], templates_dir: Path) -> list[str]:
    return sorted(name for name in exemptions if not (templates_dir / name).exists())


def load_changed(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(TEMPLATES_PREFIX) and line.endswith(".html"):
            names.add(line[len(TEMPLATES_PREFIX):])
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--changed", type=Path, required=True)
    parser.add_argument("--rendered", type=Path, required=True, help="templates rendered by the real-route sweep")
    parser.add_argument("--fixture-rendered", type=Path, default=None,
                        help="templates rendered by registered fixture states")
    parser.add_argument("--exemptions", type=Path, default=Path("tests/axe_coverage_exemptions.json"))
    parser.add_argument("--templates-dir", type=Path, default=Path("templates"))
    args = parser.parse_args(argv)

    changed = load_changed(args.changed)
    if not changed:
        print("No changed templates; nothing to cover.")
        return 0

    rendered: set[str] = set()
    for label, path, required in (("real-route sweep", args.rendered, True),
                                  ("fixture render", args.fixture_rendered, False)):
        if path is None:
            continue
        if not path.exists():
            print(f"ACCESSIBILITY COVERAGE FAIL\nreason: {path} does not exist -- the {label} recorded nothing, "
                  "so no changed template can be shown to have been audited by it.")
            return 1
        names = set(json.loads(path.read_text(encoding="utf-8")))
        if not names and required:
            print(f"ACCESSIBILITY COVERAGE FAIL\nreason: the {label} rendered no templates.")
            return 1
        rendered |= names

    exemptions = json.loads(args.exemptions.read_text(encoding="utf-8")) if args.exemptions.exists() else {}
    env = Environment(loader=FileSystemLoader(str(args.templates_dir)))
    covered = closure(env, rendered)

    problems = False
    missing = uncovered(changed, covered, exemptions)
    if missing:
        problems = True
        for name in missing:
            print(f"ACCESSIBILITY COVERAGE FAIL\ntemplate: templates/{name}\n"
                  "reason: no route scenario or registered render fixture")
        print("Register a fixture state in tests/a11y_fixtures, or add a route scenario to "
              "tests/test_axe_app_pages.py. A route is not required just to make a template testable.")
    stale = stale_exemptions(exemptions, args.templates_dir)
    if stale:
        problems = True
        print("FAIL: exemptions naming templates that no longer exist: " + ", ".join(stale))

    redundant = sorted(name for name in exemptions if name in covered)
    if redundant:
        problems = True
        print("FAIL: these templates are covered now; remove their exemptions: " + ", ".join(redundant))

    exempt_hit = sorted(changed & set(exemptions) - covered)
    for name in exempt_hit:
        print(f"WARN: templates/{name} is exempt from the CI sweep: {exemptions[name]}")
    if not problems:
        print(f"OK: {len(changed)} changed template(s) covered by the axe sweep or explicitly exempt.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

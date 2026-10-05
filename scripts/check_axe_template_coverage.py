#!/usr/bin/env python3
"""Fail a PR that changes a template no axe sweep ever rendered.

The Accessibility Gate runs the authenticated axe-core sweep
(``tests/test_axe_app_pages.py``), which records every template it renders to
``AXE_RENDERED_TEMPLATES_FILE``. A changed template is *covered* when it was
rendered directly, or when a rendered template reaches it through ``extends``,
``include``, ``import`` or ``from ... import`` -- so a change to a layout or macro
is covered by every page that uses it.

A changed template that is neither covered nor listed in the exemptions file
fails the gate: the sweep has no page for it, so a defect in it would merge
unaudited. Fix that by adding the page to the sweep, or -- only where a page
cannot be built in CI -- by adding a dated exemption with the reason.

Usage:
    check_axe_template_coverage.py --changed changed.txt --rendered rendered.json \
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
    parser.add_argument("--rendered", type=Path, required=True)
    parser.add_argument("--exemptions", type=Path, default=Path("tests/axe_coverage_exemptions.json"))
    parser.add_argument("--templates-dir", type=Path, default=Path("templates"))
    args = parser.parse_args(argv)

    changed = load_changed(args.changed)
    if not changed:
        print("No changed templates; nothing to cover.")
        return 0

    if not args.rendered.exists():
        print(f"FAIL: {args.rendered} does not exist -- the axe sweep recorded nothing, "
              "so no changed template can be shown to have been audited.")
        return 1
    rendered = set(json.loads(args.rendered.read_text(encoding="utf-8")))
    if not rendered:
        print("FAIL: the axe sweep rendered no templates.")
        return 1

    exemptions = json.loads(args.exemptions.read_text(encoding="utf-8")) if args.exemptions.exists() else {}
    env = Environment(loader=FileSystemLoader(str(args.templates_dir)))
    covered = closure(env, rendered)

    problems = False
    missing = uncovered(changed, covered, exemptions)
    if missing:
        problems = True
        print("FAIL: changed templates that no axe sweep page renders or reaches:")
        for name in missing:
            print(f"  - templates/{name}")
        print("Add a page that renders it to tests/test_axe_app_pages.py, or add a justified "
              "entry to tests/axe_coverage_exemptions.json.")
    stale = stale_exemptions(exemptions, args.templates_dir)
    if stale:
        problems = True
        print("FAIL: exemptions naming templates that no longer exist: " + ", ".join(stale))

    exempt_hit = sorted(changed & set(exemptions) - covered)
    for name in exempt_hit:
        print(f"WARN: templates/{name} is exempt from the CI sweep: {exemptions[name]}")
    if not problems:
        print(f"OK: {len(changed)} changed template(s) covered by the axe sweep or explicitly exempt.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

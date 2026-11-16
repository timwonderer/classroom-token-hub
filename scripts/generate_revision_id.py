#!/usr/bin/env python3
"""Select an unused Alembic revision ID from the current migration repository."""

import ast
from pathlib import Path
from uuid import uuid4


def declared_value(tree, name):
    """Read a literal top-level migration declaration without executing its module."""
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
        elif isinstance(statement, ast.Assign):
            targets = statement.targets
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(statement.value)
    raise ValueError(f"Missing migration declaration: {name}")


def generate_revision_id(existing=None, *, requested=None):
    """Preserve an explicit unused ID, or generate an unused 12-character hex ID."""
    if existing is None:
        versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
        existing = {
            declared_value(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)), "revision")
            for path in versions.glob("*.py") if not path.name.startswith("__")
        }

    if requested is not None:
        if requested in existing:
            raise ValueError(f"Revision ID {requested!r} already exists.")
        return requested

    while True:
        candidate = uuid4().hex[:12]
        if candidate not in existing:
            return candidate


if __name__ == '__main__':
    print(generate_revision_id())

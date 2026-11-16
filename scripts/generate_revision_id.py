#!/usr/bin/env python3
"""Select an unused Alembic revision ID from the current migration repository."""

import ast
from pathlib import Path
from uuid import uuid4


def declared_value(tree, name):
    """Require one unconditional, single-target literal declaration at module scope."""
    declarations = []
    pending = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                raise ValueError(f"Unexpected binding of {name} on line {node.lineno}")
            continue  # Assignments inside a function or class have separate scope.
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)):
            declarations.append(node)
        if isinstance(node, ast.alias) and (node.asname or node.name.split('.')[0]) in (name, '*'):
            raise ValueError(f"Unexpected import binding of {name} on line {node.lineno}")
        if ((isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name == name)
                or (isinstance(node, ast.MatchMapping) and node.rest == name)):
            raise ValueError(f"Unexpected conditional binding of {name} on line {node.lineno}")
        if isinstance(node, ast.comprehension):
            pending.extend([node.iter, *node.ifs])
            continue  # Comprehension iteration targets also have separate scope.
        pending.extend(ast.iter_child_nodes(node))

    if len(declarations) != 1:
        raise ValueError(f"Expected exactly one declaration of {name}, found {len(declarations)}")
    target, = declarations
    for statement in tree.body:
        if ((isinstance(statement, ast.Assign) and statement.targets == [target])
                or (isinstance(statement, ast.AnnAssign) and statement.target is target)):
            try:
                value = ast.literal_eval(statement.value)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Expected literal {name} on line {statement.lineno}") from error
            if isinstance(value, str) and value.strip():
                return value
            if name == 'down_revision' and (value is None or (
                isinstance(value, tuple) and value and all(isinstance(item, str) and item.strip() for item in value)
            )):
                return value
            raise ValueError(f"Invalid {name} value on line {statement.lineno}")
    raise ValueError(f"Expected a single-target top-level assignment of {name} on line {target.lineno}")


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

import ast
import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.regression


ROUTE_DECORATORS = {"route", "get", "post", "put", "delete", "patch"}
ROUTE_PARAM_RE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def _iter_route_files(project_root: Path) -> list[Path]:
    files = sorted((project_root / "app" / "routes").glob("*.py"))
    files.extend([project_root / "app" / "auth.py", project_root / "app" / "__init__.py"])
    return [path for path in files if path.exists()]


def _extract_route_path(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return None
    first_arg = decorator.args[0]
    if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
        return None
    return first_arg.value


def _is_route_decorator(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    if isinstance(func, ast.Attribute):
        return func.attr in ROUTE_DECORATORS
    if isinstance(func, ast.Name):
        return func.id in ROUTE_DECORATORS
    return False


def test_dynamic_route_params_match_handler_signature():
    project_root = Path(__file__).resolve().parents[1]
    mismatches: list[str] = []

    for route_file in _iter_route_files(project_root):
        tree = ast.parse(route_file.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            accepted = {arg.arg for arg in node.args.args}
            accepted.update(arg.arg for arg in node.args.kwonlyargs)
            has_kwargs = node.args.kwarg is not None

            for decorator in node.decorator_list:
                if not _is_route_decorator(decorator):
                    continue
                route_path = _extract_route_path(decorator)
                if not route_path:
                    continue
                route_params = ROUTE_PARAM_RE.findall(route_path)
                missing = [param for param in route_params if param not in accepted and not has_kwargs]
                if missing:
                    relative = route_file.relative_to(project_root)
                    mismatches.append(
                        f"{relative}:{node.lineno} route '{route_path}' missing args {missing} in '{node.name}'"
                    )

    assert not mismatches, "Route/signature mismatches found:\n" + "\n".join(mismatches)

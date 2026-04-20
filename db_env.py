"""Branch-aware database URL resolution for local development and tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

V1_DEV_KEY = "V1_DEV_DATABASE_URL"
V2_DEV_KEY = "V2_DEV_DATABASE_URL"
V1_TEST_KEY = "V1_TEST_DATABASE_URL"
V2_TEST_KEY = "V2_TEST_DATABASE_URL"


def _project_root(explicit_root: str | Path | None = None) -> Path:
    if explicit_root:
        return Path(explicit_root)
    return Path(__file__).resolve().parent


def detect_branch_name(environ: dict[str, str] | None = None, project_root: str | Path | None = None) -> str | None:
    env = environ or os.environ
    for key in ("CTH_BRANCH", "GIT_BRANCH", "BRANCH_NAME"):
        branch = env.get(key)
        if branch:
            return branch

    repo_root = _project_root(project_root)
    if not (repo_root / ".git").exists():
        return None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    branch = result.stdout.strip()
    return branch or None


def branch_db_version(branch_name: str | None) -> str:
    return "v2" if branch_name and branch_name.startswith("V2_") else "v1"


def resolve_dev_database_url(environ: dict[str, str] | None = None, project_root: str | Path | None = None) -> str | None:
    env = environ or os.environ
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]

    branch_name = detect_branch_name(env, project_root=project_root)
    key = V2_DEV_KEY if branch_db_version(branch_name) == "v2" else V1_DEV_KEY
    return env.get(key)


def resolve_test_database_url(environ: dict[str, str] | None = None, project_root: str | Path | None = None) -> str | None:
    env = environ or os.environ
    if env.get("TEST_DATABASE_URL"):
        return env["TEST_DATABASE_URL"]

    branch_name = detect_branch_name(env, project_root=project_root)
    key = V2_TEST_KEY if branch_db_version(branch_name) == "v2" else V1_TEST_KEY
    return env.get(key)

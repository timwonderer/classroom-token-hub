#!/usr/bin/env python3
"""Publish a user-guide documentation artifact on the droplet (SOP-DEP-003).

Installed BY HAND at /root/release-gate/docs_publish.py, root-owned 0700, next to guarded-docs.sh,
which is the forced command for DOCS_DEPLOY_KEY and the only caller. This repository copy is the
reviewable source, not the live file, for the same reason as guarded-deploy.sh: anything inside the
application checkout is something a pull request can edit.

It publishes ``docs/user-guides/`` from one commit on main as an immutable artifact under
/srv/cth-docs/releases/<sha>/ and switches /srv/cth-docs/current to it atomically. The application
(CTH_USER_GUIDES_DIR=/srv/cth-docs/current/docs) serves guides from there, so publishing needs no
restart and never touches the application checkout, its code, templates or database.

Checks, all before the switch:
  1. the revision is 40 hex characters and an ancestor of origin/main;
  2. the artifact holds only regular files under docs/user-guides/ with allowed suffixes: no
     symlinks, submodules or other file types;
  3. screening: every commit since the deployed application release that touched docs/user-guides/
     touched nothing else (CHANGELOG.md and github-pages/ excepted). A merge is judged by its diff
     against its first parent, so a pull request that changed code and guides in separate commits
     is still caught when it lands. A guide written together with code most likely
     describes code that is not deployed yet. This screens; it does not prove compatibility, which
     the publisher attests to under SOP-DEP-003.
After extraction, and again after the switch, every published file's git blob hash must equal the
commit's, with nothing extra; then the running application's environment must point at
/srv/cth-docs/current/docs, so what is verified is what is served.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys

APP_DIR = Path("/root/classroom-economy")
DOCS_HOME = Path("/srv/cth-docs")
SCOPE = "docs/user-guides/"
SCREEN_EXEMPT = {"CHANGELOG.md"}
SCREEN_EXEMPT_PREFIXES = ("github-pages/",)  # deployed by GitHub Pages, never served by the app
ALLOWED_SUFFIXES = {".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
REGULAR_MODES = {"100644", "100755"}
SERVICE = "classroom-economy"
ENV_NAME = "CTH_USER_GUIDES_DIR"
SHA = re.compile(r"[0-9a-f]{40}")


class Refused(Exception):
    pass


# ---- pure checks (tested in tests/test_docs_publish.py) ---------------------------------------

def tree_problems(entries):
    """Problems with an artifact listing: [(mode, type, path)] from ``git ls-tree -r``."""
    problems = []
    if not entries:
        problems.append(f"no files under {SCOPE}")
    for mode, kind, path in entries:
        if not path.startswith(SCOPE) or "/../" in f"/{path}/" or path.startswith("/"):
            problems.append(f"outside {SCOPE}: {path}")
        elif kind != "blob" or mode not in REGULAR_MODES:
            problems.append(f"not a regular file (mode {mode}, {kind}): {path}")
        elif Path(path).suffix.lower() not in ALLOWED_SUFFIXES:
            problems.append(f"file type not allowed: {path}")
    return problems


def screening_problems(commits):
    """Commits [(sha, [paths])] that touched user guides together with anything else."""
    problems = []
    for sha, paths in commits:
        if not any(p.startswith(SCOPE) for p in paths):
            continue
        others = sorted(p for p in paths if not p.startswith(SCOPE) and p not in SCREEN_EXEMPT
                        and not p.startswith(SCREEN_EXEMPT_PREFIXES))
        if others:
            problems.append(f"{sha[:12]} changes user guides together with {', '.join(others[:5])}"
                            + (" …" if len(others) > 5 else ""))
    return problems


def blob_hash(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def extraction_problems(root, entries, provenance=False):
    """Differences between an extracted tree under ``root`` and the commit's listing.

    ``provenance`` allows the one file publishing adds at the artifact's top level, ``SOURCE``.
    """
    problems, expected = [], {}
    for mode, _kind, path, blob in entries:
        expected[path] = blob
    found = set()
    for item in sorted(Path(root).rglob("*")):
        rel = item.relative_to(root).as_posix()
        if provenance and rel == "SOURCE" and item.is_file() and not item.is_symlink():
            continue
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            problems.append(f"unexpected file type: {rel}")
        elif item.is_file():
            found.add(rel)
            if rel not in expected:
                problems.append(f"not in the commit: {rel}")
            elif blob_hash(item.read_bytes()) != expected[rel]:
                problems.append(f"content differs from the commit: {rel}")
    problems += [f"missing: {p}" for p in sorted(set(expected) - found)]
    return problems


# ---- droplet operations -----------------------------------------------------------------------

def git(*args):
    return subprocess.run(["git", "-C", str(APP_DIR), *args], check=True,
                          capture_output=True, text=True).stdout


def listing(sha, with_blob=False):
    out = git("ls-tree", "-r", "--full-tree", sha, "--", SCOPE)
    rows = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, blob = meta.split()
        rows.append((mode, kind, path, blob) if with_blob else (mode, kind, path))
    return rows


def screened_commits(app_sha, sha):
    # No path limiting and no --no-merges: history simplification can hide a merge, and a merge's
    # own changes (its diff against the first parent) are what landed on main.
    commits = []
    for c in git("rev-list", f"{app_sha}..{sha}").split():
        paths = git("diff", "--name-only", f"{c}^1", c).split()
        if any(p.startswith(SCOPE) for p in paths):
            commits.append((c, paths))
    return commits


def served_root():
    pid = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", SERVICE],
                         check=True, capture_output=True, text=True).stdout.strip()
    if not pid or pid == "0":
        raise Refused(f"{SERVICE} is not running")
    env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    values = [e.split(b"=", 1)[1].decode() for e in env if e.startswith(ENV_NAME.encode() + b"=")]
    return values[0] if values else None


def verify_current(sha, entries):
    current = DOCS_HOME / "current"
    target = os.readlink(current)
    if Path(target).name != sha:
        raise Refused(f"current points at {target}, not {sha}")
    source = json.loads((current / "SOURCE").read_text())
    if source.get("docs_sha") != sha:
        raise Refused("SOURCE does not name the published revision")
    problems = extraction_problems(current, entries, provenance=True)
    if problems:
        raise Refused("published tree differs from the commit: " + "; ".join(problems[:5]))
    served = served_root()
    if served != str(current / "docs"):
        raise Refused(f"{SERVICE} serves guides from {served!r}, not {current / 'docs'}. On the first "
                      f"publication this is expected: set {ENV_NAME}, restart, and publish again "
                      "(infra/release-gate/README.md)")


def deploy(sha, run_id):
    if not SHA.fullmatch(sha):
        raise Refused("revision must be exactly 40 lowercase hex characters")
    if run_id and not run_id.isdigit():
        raise Refused("run id must be digits")
    git("fetch", "--no-tags", "--quiet", "origin", "main")
    git("cat-file", "-e", f"{sha}^{{commit}}")
    if subprocess.run(["git", "-C", str(APP_DIR), "merge-base", "--is-ancestor", sha, "origin/main"]).returncode:
        raise Refused(f"{sha} is not on main")
    app_sha = git("rev-parse", "HEAD").strip()
    problems = tree_problems(listing(sha)) + screening_problems(screened_commits(app_sha, sha))
    if problems:
        raise Refused("; ".join(problems))
    entries = listing(sha, with_blob=True)
    releases = DOCS_HOME / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    final = releases / sha
    if not final.exists():
        staging = releases / f".{sha}.staging"
        if staging.exists():
            shutil.rmtree(staging)
        # Owner-writable, readable by the service user: the guides are public pages.
        staging.mkdir(mode=0o755)
        archive = subprocess.run(["git", "-C", str(APP_DIR), "archive", "--format=tar", sha, "--", SCOPE],
                                 check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "--no-same-owner", "-C", str(staging)], input=archive, check=True)
        problems = extraction_problems(staging, entries)
        if problems:
            raise Refused("extracted tree differs from the commit: " + "; ".join(problems[:5]))
        (staging / "SOURCE").write_text(json.dumps({"docs_sha": sha, "app_sha_at_publish": app_sha,
                                                    "run_id": run_id or None}, sort_keys=True) + "\n")
        os.rename(staging, final)
    elif extraction_problems(final, entries, provenance=True):
        raise Refused(f"existing artifact for {sha} differs from the commit; remove it by hand and retry")
    link = DOCS_HOME / "current.next"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path("releases") / sha)
    os.replace(link, DOCS_HOME / "current")  # atomic: readers see the old or the new tree, never a mix
    verify_current(sha, entries)
    files = [p for _m, _k, p, _b in entries]
    print(json.dumps({"published": sha, "app_sha": app_sha, "files": len(files)}, sort_keys=True))


def status():
    current = DOCS_HOME / "current"
    source = json.loads((current / "SOURCE").read_text()) if current.exists() else None
    print(json.dumps({"current": source, "app_sha": git("rev-parse", "HEAD").strip(),
                      "served_from": served_root()}, sort_keys=True))


def main(argv):
    try:
        if argv[:1] == ["status"] and len(argv) == 1:
            status()
        elif argv[:1] == ["deploy"] and len(argv) in (2, 3):
            deploy(argv[1], argv[2] if len(argv) == 3 else "")
        else:
            raise Refused("usage: deploy <sha> [run_id] | status")
    except Refused as error:
        sys.exit(f"docs-publish refused: {error}")


if __name__ == "__main__":
    main(sys.argv[1:])

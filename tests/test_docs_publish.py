"""The droplet-side documentation publisher refuses what SOP-DEP-003 excludes (SOP-TEST-003 §IX.A).

The pure checks get one deliberate violation each. An end-to-end run publishes from throwaway git
repositories into a temporary /srv/cth-docs stand-in, exercising fetch, lineage, screening,
extraction, the atomic switch and post-switch verification; only systemd is stubbed.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("docs_publish", ROOT / "infra/release-gate/docs_publish.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)

GOOD = ("100644", "blob", "docs/user-guides/teacher_manual.md")


# ---- tree ----

def test_regular_guides_pass():
    assert dp.tree_problems([GOOD, ("100644", "blob", "docs/user-guides/img/a.png")]) == []


@pytest.mark.parametrize("entry, fragment", [
    (("120000", "blob", "docs/user-guides/link.md"), "not a regular file"),
    (("160000", "commit", "docs/user-guides/sub"), "not a regular file"),
    (("100644", "blob", "docs/user-guides/page.html"), "file type not allowed"),
    (("100755", "blob", "docs/user-guides/run.py"), "file type not allowed"),
    (("100644", "blob", "docs/SPEC/x.md"), "outside docs/user-guides/"),
    (("100644", "blob", "templates/docs/index.html"), "outside docs/user-guides/"),
])
def test_mutation_disallowed_entry_is_reported(entry, fragment):
    assert any(fragment in p for p in dp.tree_problems([GOOD, entry]))


def test_empty_artifact_is_refused():
    assert dp.tree_problems([]) == ["no files under docs/user-guides/"]


# ---- screening ----

def test_guide_only_and_unrelated_commits_pass():
    commits = [("a" * 40, ["docs/user-guides/x.md", "CHANGELOG.md", "github-pages/timeline.html"]),
               ("b" * 40, ["app/models.py"])]
    assert dp.screening_problems(commits) == []


@pytest.mark.parametrize("other", ["templates/docs/index.html", "app/routes/docs.py", "docs/SPEC/x.md"])
def test_mutation_guide_changed_with_anything_else_is_reported(other):
    problems = dp.screening_problems([("c" * 40, ["docs/user-guides/x.md", other])])
    assert len(problems) == 1 and other in problems[0]


# ---- extraction ----

def _entries(root):
    return [("100644", "blob", p.relative_to(root).as_posix(), dp.blob_hash(p.read_bytes()))
            for p in sorted(root.rglob("*")) if p.is_file()]


def test_extraction_matches(tmp_path):
    (tmp_path / "docs/user-guides").mkdir(parents=True)
    (tmp_path / "docs/user-guides/a.md").write_text("# A\n")
    assert dp.extraction_problems(tmp_path, _entries(tmp_path)) == []


def test_mutation_extraction_differences_are_reported(tmp_path):
    guides = tmp_path / "docs/user-guides"
    guides.mkdir(parents=True)
    (guides / "a.md").write_text("# A\n")
    (guides / "b.md").write_text("# B\n")
    entries = _entries(tmp_path)
    (guides / "a.md").write_text("# tampered\n")
    (guides / "b.md").unlink()
    (guides / "extra.md").write_text("# extra\n")
    (guides / "link.md").symlink_to(tmp_path / "docs/user-guides/a.md")
    problems = dp.extraction_problems(tmp_path, entries)
    for fragment in ("content differs", "missing: docs/user-guides/b.md", "not in the commit",
                     "unexpected file type"):
        assert any(fragment in p for p in problems), fragment
    (tmp_path / "SOURCE").write_text("{}")
    assert any("SOURCE" in p for p in dp.extraction_problems(tmp_path, entries))
    assert not any("SOURCE" in p for p in dp.extraction_problems(tmp_path, entries, provenance=True))


# ---- end to end ----

def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo, files, message, push=True):
    for path, text in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", message)
    if push:
        _git(repo, "push", "-q", "origin", "HEAD:main")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def droplet(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    release = _commit(work, {"app/x.py": "x = 1\n", "docs/user-guides/a.md": "# A v1\n"}, "release")
    app = tmp_path / "classroom-economy"
    subprocess.run(["git", "clone", "-q", str(origin), str(app)], check=True, capture_output=True)
    _git(app, "checkout", "-q", "--detach", release)
    home = tmp_path / "srv-cth-docs"
    monkeypatch.setattr(dp, "APP_DIR", app)
    monkeypatch.setattr(dp, "DOCS_HOME", home)
    monkeypatch.setattr(dp, "served_root", lambda: str(home / "current" / "docs"))
    return work, app, home, release


def test_publish_switches_current_and_leaves_the_app_checkout_untouched(droplet, capsys):
    work, app, home, release = droplet
    docs = _commit(work, {"docs/user-guides/a.md": "# A v2\n"}, "guide fix")
    dp.deploy(docs, "42")
    assert os.readlink(home / "current") == f"releases/{docs}"
    assert (home / "current/docs/user-guides/a.md").read_text() == "# A v2\n"
    assert json.loads((home / "current/SOURCE").read_text())["docs_sha"] == docs
    assert _git(app, "rev-parse", "HEAD") == release and _git(app, "status", "--porcelain") == ""
    dp.deploy(release, "43")  # rollback is publishing the earlier revision
    assert (home / "current/docs/user-guides/a.md").read_text() == "# A v1\n"


def test_guide_written_with_code_is_refused(droplet):
    work, _app, home, _release = droplet
    mixed = _commit(work, {"docs/user-guides/a.md": "# A new feature\n", "app/x.py": "x = 2\n"}, "feature")
    with pytest.raises(dp.Refused, match="together with app/x.py"):
        dp.deploy(mixed, "")
    assert not (home / "current").exists()


def test_merge_landing_code_and_guides_in_separate_commits_is_refused(droplet):
    work, _app, home, _release = droplet
    _git(work, "checkout", "-q", "-b", "feature")
    _commit(work, {"app/x.py": "x = 2\n"}, "code", push=False)
    _commit(work, {"docs/user-guides/a.md": "# A new feature\n"}, "guide", push=False)
    _git(work, "checkout", "-q", "main")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "merge", "-q", "--no-ff",
         "-m", "merge feature", "feature")
    _git(work, "push", "-q", "origin", "HEAD:main")
    with pytest.raises(dp.Refused, match="together with app/x.py"):
        dp.deploy(_git(work, "rev-parse", "HEAD"), "")
    assert not (home / "current").exists()


def test_revision_off_main_is_refused(droplet):
    work, _app, _home, _release = droplet
    _git(work, "checkout", "-q", "-b", "side")
    (work / "docs/user-guides/a.md").write_text("# side\n")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qam", "side")
    _git(work, "push", "-q", "origin", "side")
    _git(droplet[1], "fetch", "-q", "origin", "side")
    with pytest.raises(dp.Refused, match="not on main"):
        dp.deploy(_git(work, "rev-parse", "HEAD"), "")


def test_wrong_served_root_fails_verification(droplet, monkeypatch):
    work, _app, _home, _release = droplet
    docs = _commit(work, {"docs/user-guides/a.md": "# A v3\n"}, "guide")
    monkeypatch.setattr(dp, "served_root", lambda: "/root/classroom-economy/docs")
    with pytest.raises(dp.Refused, match="serves guides from"):
        dp.deploy(docs, "")

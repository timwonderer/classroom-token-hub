"""Keep the public operator instructions aligned with the reference installer."""
import ast
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "docs" / "self-hosting"
ENTRY = Path("infra/self-hosting/install.py")


def test_reference_installation_uses_every_installer_stage_in_order():
    tree = ast.parse((ROOT / ENTRY).read_text())
    stages = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "STAGES")
    handbook = (HANDBOOK / "reference-installation.md").read_text()
    commands = re.findall(r"`(python3 infra/self-hosting/install\.py apply [^`]+)`", handbook)
    assert [shlex.split(command) for command in commands] == [
        ["python3", str(ENTRY), "apply", stage, "--config", "$manifest"] for stage in stages
    ]
    assert 'python3 infra/self-hosting/install.py check STAGE --config "$manifest"' in handbook
    result = subprocess.run([sys.executable, str(ENTRY), "--help"], check=True, cwd=ROOT,
                            capture_output=True, text=True)
    assert ",".join(stages) in result.stdout
    assert "--config" in result.stdout


def test_handbook_chapters_are_navigable_and_local_links_resolve():
    contents = (HANDBOOK / "README.md").read_text()
    for page in HANDBOOK.glob("*.md"):
        if page.name != "README.md":
            assert f"]({page.name})" in contents
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", page.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            assert (page.parent / target.split("#")[0]).is_file(), (page.name, target)

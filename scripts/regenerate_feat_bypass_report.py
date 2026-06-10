#!/usr/bin/env python3
"""
Regenerate V2_FEAT_BYPASS_DEPENDENCY_REPORT.md from the existing
V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json, without re-running the test suite.

Use this when the markdown layout changes but the underlying flush data is
still current. Re-running the full audit takes ~11 minutes; regenerating
takes <1 second.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests._feat_bypass_audit import emit_markdown  # noqa: E402


def git_head() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=ROOT,
        )
        return out.decode().strip()
    except Exception:
        return None


def main() -> int:
    tracking = ROOT / "docs" / "development" / "tracking"
    raw_path = tracking / "V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json"
    md_path = tracking / "V2_FEAT_BYPASS_DEPENDENCY_REPORT.md"

    if not raw_path.exists():
        print(f"error: {raw_path} not found. Run the audited suite first:")
        print("  FEAT_BYPASS_AUDIT=1 pytest tests/")
        return 1

    records = json.loads(raw_path.read_text())
    total = len(records)  # Best-effort; we lose the original collected count.

    # Try to recover the original "tests collected" count from the previous
    # markdown if it's there; otherwise fall back to the observed cohort size.
    total_collected = total
    if md_path.exists():
        for line in md_path.read_text().splitlines():
            if "Total tests collected by pytest" in line:
                # Format: "_Total tests collected by pytest: 816. Diff..._"
                try:
                    chunk = line.split("pytest:", 1)[1].split(".", 1)[0]
                    total_collected = int(chunk.strip())
                    break
                except (IndexError, ValueError):
                    pass

    emit_markdown(
        records,
        raw_path,
        md_path,
        total_collected=total_collected,
        git_head=git_head(),
    )
    print(f"regenerated {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave3_identity_drop_surface_does_not_expand():
    result = subprocess.run(
        [sys.executable, "scripts/wave3_identity_drop_surface_guardrail.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    assert result.returncode == 0, output

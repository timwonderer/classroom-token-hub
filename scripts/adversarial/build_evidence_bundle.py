#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


FILES = [
    "violations.jsonl",
    "cross_class_report.json",
    "lineage_report.json",
    "runtime_attacks_report.json",
    "scorecard.md",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build immutable evidence bundle (Phase 1)")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-dir", default=os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial"))
    args = parser.parse_args()

    root = Path(args.artifact_dir)
    run_dir = root / args.run_id
    bundle_dir = root / "bundles" / args.run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": args.run_id,
        "created_at": now_iso(),
        "code_sha": os.getenv("GIT_COMMIT_SHA", "unknown"),
        "migration_head": os.getenv("ALEMBIC_HEAD", "unknown"),
        "seed_id": os.getenv("ADVERSARIAL_SEED_ID", "unknown"),
        "source_run_dir": str(run_dir),
        "copied_files": [],
    }

    for name in FILES:
        src = run_dir / name
        if src.exists():
            dst = bundle_dir / name
            shutil.copy2(src, dst)
            manifest["copied_files"].append(name)

    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "bundle_dir": str(bundle_dir), "copied": manifest["copied_files"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

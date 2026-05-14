#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import hashlib
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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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

    # Build sanitized, commit-safe record set.
    sanitized_dir = root / "sanitized" / args.run_id
    sanitized_dir.mkdir(parents=True, exist_ok=True)
    cross = load_json(run_dir / "cross_class_report.json") or {}
    lineage = load_json(run_dir / "lineage_report.json") or {}
    runtime = load_json(run_dir / "runtime_attacks_report.json") or {}
    injection = load_json(run_dir / "injection_report.json") or {}

    summary = {
        "run_id": args.run_id,
        "generated_at": now_iso(),
        "code_sha": os.getenv("GIT_COMMIT_SHA", "unknown"),
        "checks": {
            "cross_class": {
                "status": cross.get("status", "MISSING"),
                "violation_count": cross.get("violation_count", 0),
            },
            "lineage": {
                "status": lineage.get("status", "MISSING"),
                "violation_count": lineage.get("violation_count", 0),
            },
            "runtime_attacks": {
                "status": runtime.get("status", "MISSING"),
                "violation_count": runtime.get("violation_count", 0),
            },
            "injection_step": {
                "status": "PASS" if injection else "MISSING",
                "violation_count": 0,
            },
        },
    }
    (sanitized_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    scorecard_lines = [
        f"# Adversarial Sanitized Summary ({args.run_id})",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Code SHA: `{summary['code_sha']}`",
        "",
        "| Check | Status | Violations |",
        "|---|---|---:|",
        f"| Cross-Class Isolation | {summary['checks']['cross_class']['status']} | {summary['checks']['cross_class']['violation_count']} |",
        f"| Lineage Verifier | {summary['checks']['lineage']['status']} | {summary['checks']['lineage']['violation_count']} |",
        f"| Runtime Session Attacks | {summary['checks']['runtime_attacks']['status']} | {summary['checks']['runtime_attacks']['violation_count']} |",
        f"| Synthetic Injection Step | {summary['checks']['injection_step']['status']} | 0 |",
        "",
        "> This summary intentionally excludes raw payloads, repro traces, session-level fields, and actor identifiers.",
    ]
    (sanitized_dir / "scorecard_sanitized.md").write_text("\n".join(scorecard_lines) + "\n", encoding="utf-8")

    manifest_sanitized = {
        "run_id": args.run_id,
        "created_at": now_iso(),
        "source_run_dir": str(run_dir),
        "generated_files": [],
    }
    for name in ("summary.json", "scorecard_sanitized.md"):
        path = sanitized_dir / name
        manifest_sanitized["generated_files"].append(
            {"name": name, "sha256": file_sha256(path)}
        )
    (sanitized_dir / "manifest.json").write_text(json.dumps(manifest_sanitized, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "bundle_dir": str(bundle_dir),
                "copied": manifest["copied_files"],
                "sanitized_dir": str(sanitized_dir),
                "sanitized_files": [f["name"] for f in manifest_sanitized["generated_files"]],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

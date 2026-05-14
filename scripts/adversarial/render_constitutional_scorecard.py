#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    run_id = os.getenv("ADVERSARIAL_RUN_ID", "current")
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / run_id
    root.mkdir(parents=True, exist_ok=True)

    get_violations = read_jsonl(root / "violations.jsonl")
    cross_class = read_json(root / "cross_class_report.json")
    lineage = read_json(root / "lineage_report.json")
    runtime = read_json(root / "runtime_attacks_report.json")
    injection = read_json(root / "injection_report.json")

    checks = [
        ("GET Mutation Detector", "FAIL" if get_violations else "PASS", len(get_violations)),
        (
            "Cross-Class Isolation Verifier",
            (cross_class or {}).get("status", "MISSING"),
            (cross_class or {}).get("violation_count", 0),
        ),
        (
            "Lineage Verifier (Skeleton)",
            (lineage or {}).get("status", "MISSING"),
            (lineage or {}).get("violation_count", 0),
        ),
        (
            "Runtime Session Attack Battery",
            (runtime or {}).get("status", "MISSING"),
            (runtime or {}).get("violation_count", 0),
        ),
        (
            "Synthetic Impossible-State Injection",
            "PASS" if injection else "MISSING",
            0,
        ),
    ]

    overall = "PASS"
    for _, status, _count in checks:
        if status in {"FAIL", "MISSING"}:
            overall = "FAIL"
            break

    lines = [
        "# Constitutional Scorecard (Phase 1)",
        "",
        f"- Run ID: `{run_id}`",
        f"- Overall: **{overall}**",
        "",
        "| Check | Status | Violations |",
        "|---|---|---:|",
    ]
    for name, status, count in checks:
        lines.append(f"| {name} | {status} | {count} |")

    (root / "scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "overall": overall, "scorecard": str(root / "scorecard.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase 1 lineage verifier skeleton.

Current scope:
- checks for missing lineage_event_id on Transaction rows created in the last N days
- marks as FAIL if any are found

This is intentionally minimal for Phase 1.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import create_app
from app.models import ClassEconomy, Transaction


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(filename: str) -> Path:
    run_id = os.getenv("ADVERSARIAL_RUN_ID", "current")
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root / filename


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument(
        "--require-lineage",
        action="store_true",
        help="Fail when lineage_event_id is missing (strict mode).",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        topology = json.loads(artifact_path("topology.json").read_text(encoding="utf-8"))
        phase1_class_ids = [topology[key] for key in ("ADVA1", "ADVA2", "ADVB1")]
        if not all(ClassEconomy.query.filter_by(class_id=cid).first() for cid in phase1_class_ids):
            raise SystemExit("Seeded classes are missing")
        query = Transaction.query.filter(
            Transaction.timestamp >= cutoff, Transaction.class_id.in_(phase1_class_ids)
        )
        rows = query.with_entities(
            Transaction.id,
            Transaction.class_id,
            Transaction.seat_id,
            Transaction.lineage_event_id,
        ).all()

        missing = []
        for tx_id, class_id, seat_id, lineage_event_id in rows:
            if lineage_event_id is None:
                missing.append(
                    {
                        "table": Transaction.__tablename__,
                        "row_id": tx_id,
                        "class_id": str(class_id) if class_id else None,
                        "seat_id": seat_id,
                        "reason": "missing_lineage_event_id",
                    }
                )

        strict = bool(args.require_lineage)
        status = "FAIL" if (strict and missing) else "BLOCKED" if missing or not rows else "PASS"
        report = {
            "generated_at": now_iso(),
            "check": "lineage_lawfulness_skeleton",
            "scope": f"phase1_classes_transactions_since_{cutoff.isoformat()}",
            "status": status,
            "checked_count": len(rows),
            "violation_count": len(missing) if strict else 0,
            "violations": missing if strict else [],
            "unverified_count": len(missing),
            "unverified_rows": missing if not strict else [],
            "note": (
                "Phase 1 skeleton only; missing lineage_event_id is treated as UNVERIFIED by default. "
                "Use --require-lineage for strict failure."
            ),
        }
        artifact_path("lineage_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"status": report["status"], "violation_count": report["violation_count"], "unverified_count": len(missing)}))
        return 1 if strict and missing else 2 if missing or not rows else 0


if __name__ == "__main__":
    raise SystemExit(main())

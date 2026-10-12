#!/usr/bin/env python3
"""Inject one synthetic impossible state for Phase 1 validation.

Injection implemented:
- LedgerBalanceSnapshot.class_id mismatched from its Seat.class_id (cross-class isolation violation)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

from app import create_app
from app.extensions import db
from app.models import LedgerBalanceSnapshot, ClassEconomy, Seat


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(filename: str) -> Path:
    run_id = os.getenv("ADVERSARIAL_RUN_ID", "current")
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root / filename


def main() -> int:
    app = create_app()
    with app.app_context():
        topology = json.loads(artifact_path("topology.json").read_text(encoding="utf-8"))
        class_ids = [topology[key] for key in ("ADVA1", "ADVA2", "ADVB1")]
        if not all(db.session.get(ClassEconomy, class_id) for class_id in class_ids):
            raise SystemExit("Seeded classes are missing")
        if len(class_ids) < 2:
            raise SystemExit("Need at least two classes to inject cross-class impossible state")

        row = (
            LedgerBalanceSnapshot.query.join(Seat, Seat.id == LedgerBalanceSnapshot.seat_id)
            .filter(LedgerBalanceSnapshot.class_id == Seat.class_id,
                    LedgerBalanceSnapshot.class_id.in_(class_ids))
            .with_entities(
                LedgerBalanceSnapshot.id,
                LedgerBalanceSnapshot.class_id,
                LedgerBalanceSnapshot.seat_id,
                Seat.class_id,
                LedgerBalanceSnapshot.account_type,
            )
            .first()
        )
        if not row:
            raise SystemExit("Seeded ledger snapshot is required; run seed_phase1_minimal.py first")
        alt_class_id = None

        bc_id, bc_class_id, seat_id, seat_class_id, bc_account_type = row
        for cid in class_ids:
            if str(cid) == str(seat_class_id):
                continue
            # uq_balance_snapshot_scope is (class_id, seat_id, account_type), so the
            # collision check must carry the account too.
            collision = LedgerBalanceSnapshot.query.filter_by(
                seat_id=seat_id, class_id=cid, account_type=bc_account_type
            ).first()
            if collision is None:
                alt_class_id = cid
                break
        if alt_class_id is None:
            raise SystemExit(
                "Unable to inject mismatch: every alternate class_id already has a balance_cache row for this seat_id"
            )

        # Deliberate corruption via raw SQL in controlled adversarial harness.
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(f"UPDATE {LedgerBalanceSnapshot.__tablename__} SET class_id = :new_class WHERE id = :row_id"),
                {"new_class": str(alt_class_id), "row_id": int(bc_id)},
            )

        payload = {
            "generated_at": now_iso(),
            "injection": "balance_cache_class_mismatch",
            "row_id": int(bc_id),
            "seat_id": int(seat_id),
            "old_class_id": str(bc_class_id),
            "seat_class_id": str(seat_class_id),
            "new_class_id": str(alt_class_id),
            "bootstrap_balance_cache_created": False,
        }
        artifact_path("injection_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, **payload}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

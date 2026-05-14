#!/usr/bin/env python3
"""Inject one synthetic impossible state for Phase 1 validation.

Injection implemented:
- BalanceCache.class_id mismatched from its Seat.class_id (cross-class isolation violation)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

from app import create_app
from app.extensions import db
from app.feats.base import FEATContext
from app.models import BalanceCache, ClassEconomy, Seat


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
        class_ids = [c.class_id for c in ClassEconomy.query.limit(10).all() if c.class_id]
        if len(class_ids) < 2:
            raise SystemExit("Need at least two classes to inject cross-class impossible state")

        row = (
            BalanceCache.query.join(Seat, Seat.id == BalanceCache.seat_id)
            .filter(BalanceCache.class_id == Seat.class_id)
            .with_entities(BalanceCache.id, BalanceCache.class_id, BalanceCache.seat_id, Seat.class_id)
            .first()
        )
        bootstrap_created = False
        if not row:
            # Seed topology may not include a balance cache row yet; bootstrap one safely.
            candidate_seat = Seat.query.filter(Seat.claimed_at.isnot(None)).first()
            if not candidate_seat:
                raise SystemExit("No eligible Seat row found for BalanceCache bootstrap")
            cache = BalanceCache.query.filter_by(seat_id=candidate_seat.id, class_id=candidate_seat.class_id).first()
            if not cache:
                with FEATContext("FEAT-ADMN-001", idempotency_key="feat:adv:inject:bootstrap-balance-cache"):
                    cache = BalanceCache(
                        seat_id=candidate_seat.id,
                        class_id=candidate_seat.class_id,
                        student_id=candidate_seat.student_id,
                        join_code=candidate_seat.join_code,
                        posted_checking_balance_cents=0,
                        posted_savings_balance_cents=0,
                    )
                    db.session.add(cache)
                    db.session.flush()
            row = (cache.id, cache.class_id, cache.seat_id, candidate_seat.class_id)
            bootstrap_created = True

        bc_id, bc_class_id, seat_id, seat_class_id = row
        alt_class_id = next(cid for cid in class_ids if str(cid) != str(seat_class_id))

        # Deliberate corruption via raw SQL in controlled adversarial harness.
        db.session.execute(
            sa.text("UPDATE balance_cache SET class_id = :new_class WHERE id = :row_id"),
            {"new_class": str(alt_class_id), "row_id": int(bc_id)},
        )
        db.session.commit()

        payload = {
            "generated_at": now_iso(),
            "injection": "balance_cache_class_mismatch",
            "row_id": int(bc_id),
            "seat_id": int(seat_id),
            "old_class_id": str(bc_class_id),
            "seat_class_id": str(seat_class_id),
            "new_class_id": str(alt_class_id),
            "bootstrap_balance_cache_created": bootstrap_created,
        }
        artifact_path("injection_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, **payload}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

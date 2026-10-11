#!/usr/bin/env python3
"""Seed an empty isolated database using SPEC-TEST-001's classroom initializer."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def seed(app):
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.feats.identity_feat import import_student_seats
    from app.models import ClassEconomy, Seat, User
    from app.services.context_resolver import CanonicalContext
    from app.services.ledger_command_service import create_idempotent_transaction
    from app.services.ledger_settlement_service import settle_balances
    from tests.helpers.canonical_identities import CLASSROOMS
    from tests.helpers.classroom_initializer import initialize

    if User.query.first() or ClassEconomy.query.first() or Seat.query.first():
        raise ValueError("Phase 1 seed requires an empty isolated database; restore golden_base first")
    classrooms = {
        name: initialize(key, app)
        for name, key in (("ADVA1", "chemistry_p1"), ("ADVA2", "ap_csp_p3"), ("ADVB1", "duplicate_names"))
    }
    a2 = classrooms["ADVA2"]
    ctx = CanonicalContext(a2.teacher_user_id, a2.class_id, a2.teacher_seat_id, "teacher")
    row = CLASSROOMS["ap_csp_p3"]["roster"][0]
    import_student_seats(
        canonical_context=ctx,
        rows=[{"first_name": row["first_name"], "last_name": row["last_name"]}],
        correlation_id="corr_adversarial_roster",
        idempotency_key=f"feat:adv:roster:{a2.class_id}",
    )
    a1 = classrooms["ADVA1"]
    seat = a1.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key=f"feat:adv:credit:{a1.class_id}"):
        create_idempotent_transaction(
            class_id=a1.class_id, seat_id=seat.id, target_seat_id=seat.id,
            actor_seat_id=a1.teacher_seat_id, mechanism="teacher", amount="1.00",
            account_type="checking", type="manual_payment", description="Synthetic adversarial seed",
            idempotency_key=f"feat:adv:credit:{a1.class_id}",
        )
    with FEATContext("FEAT-LED-003", idempotency_key=f"feat:adv:settle:{a1.class_id}"):
        settle_balances(seat.id, a1.class_id)
    return {name: classroom.class_id for name, classroom in classrooms.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values, load_dotenv

    if not dotenv_values(args.env_file).get("DATABASE_URL"):
        parser.error("The isolated env file must explicitly set DATABASE_URL")
    load_dotenv(args.env_file, override=True)
    from app import create_app
    app = create_app()
    with app.app_context():
        topology = seed(app)
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / os.getenv("ADVERSARIAL_RUN_ID", "current")
    root.mkdir(parents=True, exist_ok=True)
    (root / "topology.json").write_text(json.dumps(topology, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "classes_seeded": len(topology)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

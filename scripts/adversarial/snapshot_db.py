#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a DB snapshot for adversarial replay/reset")
    parser.add_argument("--name", required=True, help="Snapshot name")
    parser.add_argument("--out-dir", default=os.getenv("ADVERSARIAL_SNAPSHOT_DIR", "artifacts/adversarial/snapshots"))
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required")

    out_dir = Path(args.out_dir) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    dump_file = out_dir / "db.dump"
    manifest_file = out_dir / "manifest.json"

    cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(dump_file), db_url]
    subprocess.run(cmd, check=True)

    manifest = {
        "snapshot_name": args.name,
        "created_at": now_iso(),
        "database_url_redacted": db_url.split("@")[-1],
        "dump_file": str(dump_file),
        "env_name": os.getenv("ADVERSARIAL_ENV_NAME", "cth_adversarial"),
    }
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "snapshot": args.name, "manifest": str(manifest_file)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

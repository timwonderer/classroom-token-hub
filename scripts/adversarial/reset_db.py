#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset adversarial DB from snapshot")
    parser.add_argument("--snapshot-dir", required=True, help="Path to snapshot directory containing db.dump")
    parser.add_argument("--database-url", required=True, help="Target database URL")
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    dump_file = snapshot_dir / "db.dump"
    if not dump_file.exists():
        raise SystemExit(f"Missing dump file: {dump_file}")

    # --clean/--if-exists ensures objects are replaced from snapshot
    cmd = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        args.database_url,
        str(dump_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr or ""
        tolerated = (
            'unrecognized configuration parameter "transaction_timeout"' in stderr
            and "errors ignored on restore: 1" in stderr
        )
        if not tolerated:
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=stderr)
    print(json.dumps({"ok": True, "restored_from": str(dump_file)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

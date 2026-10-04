"""The backup tool refuses PostgreSQL clients whose major differs from the server's.

On 2026-10-04 the first v2.1.1 pre-release backup failed verification: pg_dump 17
wrote `SET transaction_timeout`, which the PostgreSQL 14 verify database rejects.
`require_matching_clients` now refuses before any dump or restore runs.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

TOOL_PATH = Path(__file__).resolve().parent.parent / "infra" / "db-backup" / "cth_db_backup.py"


@pytest.fixture(scope="module")
def backup_tool():
    spec = importlib.util.spec_from_file_location("cth_db_backup", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "output, major",
    [
        ("pg_dump (PostgreSQL) 14.24 (Ubuntu 14.24-0ubuntu0.22.04.1)\n", 14),
        ("pg_restore (PostgreSQL) 17.5\n", 17),
        ("pg_dump (PostgreSQL) 9.6.24\n", 9),
    ],
)
def test_db_backup_parse_pg_major_reads_the_major(backup_tool, output, major):
    assert backup_tool.parse_pg_major(output) == major


def test_db_backup_parse_pg_major_rejects_unrecognised_output(backup_tool):
    with pytest.raises(ValueError):
        backup_tool.parse_pg_major("command not found")


def test_db_backup_newer_client_than_server_is_a_mismatch(backup_tool):
    problems = backup_tool.client_version_mismatches(
        {"pg_dump": 17, "pg_restore": 14}, {"source database": 14, "verify database": 14}
    )
    assert problems == [
        "pg_dump is PostgreSQL 17, source database is 14",
        "pg_dump is PostgreSQL 17, verify database is 14",
    ]


def test_db_backup_older_client_than_server_is_a_mismatch(backup_tool):
    assert backup_tool.client_version_mismatches({"pg_restore": 14}, {"target database": 16}) == [
        "pg_restore is PostgreSQL 14, target database is 16"
    ]


def test_db_backup_matching_majors_pass(backup_tool):
    assert backup_tool.client_version_mismatches(
        {"pg_dump": 14, "pg_restore": 14}, {"source database": 14, "verify database": 14}
    ) == []


def _fake_clients(majors):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{cmd[0]} (PostgreSQL) {majors[cmd[0]]}.1\n", stderr="")

    return run


def test_db_backup_require_matching_clients_refuses_pg_dump_17_against_14(backup_tool, monkeypatch):
    monkeypatch.setattr(backup_tool.subprocess, "run", _fake_clients({"pg_dump": 17, "pg_restore": 17}))
    monkeypatch.setattr(backup_tool, "server_major", lambda url: 14)
    with pytest.raises(RuntimeError, match="pg_dump is PostgreSQL 17, source database is 14"):
        backup_tool.require_matching_clients({"source database": "src", "verify database": "verify"})


def test_db_backup_require_matching_clients_accepts_matching_14(backup_tool, monkeypatch):
    monkeypatch.setattr(backup_tool.subprocess, "run", _fake_clients({"pg_dump": 14, "pg_restore": 14}))
    monkeypatch.setattr(backup_tool, "server_major", lambda url: 14)
    backup_tool.require_matching_clients({"source database": "src", "verify database": "verify"})

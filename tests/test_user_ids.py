"""users.id parsing at the edges (app/utils/user_ids.py) and the tenant audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.utils.user_ids import (
    parse_passkey_external_id,
    parse_user_id,
    passkey_external_id,
)

UID = "7a1c2e4b-9d3f-4c8a-b6e2-1f0d9c8b7a65"


@pytest.mark.parametrize("value", [3, "3", "user_3", "", None, "not-a-uuid", True, 3.0])
def test_values_that_are_not_uuids_name_no_principal(value):
    assert parse_user_id(value) is None


def test_a_uuid_is_returned_in_canonical_form():
    assert parse_user_id(UID.upper()) == UID


@pytest.mark.parametrize("external", ["user_3", "admin_3", "sysadmin_" + UID, UID, None, 3])
def test_external_ids_other_than_user_uuid_name_no_principal(external):
    assert parse_passkey_external_id(external) is None


def test_external_id_round_trips():
    assert parse_passkey_external_id(passkey_external_id(UID)) == UID


def _audit_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "passkey_tenant_audit.py"
    spec = importlib.util.spec_from_file_location("passkey_tenant_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tenant_audit_flags_only_entries_naming_no_current_principal():
    summaries = [
        SimpleNamespace(user_id=f"user_{UID}"),
        SimpleNamespace(user_id="user_3"),
        SimpleNamespace(user_id="user_3e5f7a9b-1c2d-4e6f-8a0b-2c4d6e8f0a1b"),
    ]
    orphans = _audit_module().find_orphans(summaries, {UID})
    assert [s.user_id for s in orphans] == ["user_3", "user_3e5f7a9b-1c2d-4e6f-8a0b-2c4d6e8f0a1b"]

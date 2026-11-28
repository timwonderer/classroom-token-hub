"""SPEC-IDEN-002 §V: a ``credential_operations`` row is deleted only by the sweep or principal destruction.

A spent step-up row is the receipt that refuses a replayed provider token until its retention time
has passed. The detector is ``tests/guards/credential_operation_deletes.py``; the mutation proofs
below feed it the spellings a future change would really use (SOP-TEST-003 §IX.A).
"""

from pathlib import Path

import pytest

from tests.guards.credential_operation_deletes import ALLOWED, find_deletes, scan_repository

REPO = Path(__file__).resolve().parent.parent


def test_every_credential_operation_delete_is_the_sweep_or_principal_destruction():
    hits, parsed = scan_repository(REPO)
    assert parsed >= 150, f"scanned only {parsed} files: the guard is not looking at app/"
    assert not hits, "Only expire_stale_operations may delete credential_operations rows:\n" + "\n".join(
        f"{h.path}:{h.line} in {h.function}: {h.rule}" for h in hits)


def test_the_detector_sees_the_one_lawful_deleter():
    """If this stops finding the sweep's delete, the detector has stopped detecting."""
    (path, function), = ALLOWED
    found = find_deletes((REPO / path).read_text(encoding="utf-8"), path)
    assert [h.function for h in found] == [function]


def test_principal_destruction_is_the_cascade_not_an_application_delete():
    from app.models import CredentialOperation
    (fk,) = CredentialOperation.__table__.c.user_id.foreign_keys
    assert fk.ondelete == "CASCADE"


@pytest.mark.parametrize("source", [
    "def purge():\n    db.session.query(CredentialOperation).delete()\n",
    "def purge():\n    CredentialOperation.query.filter(CredentialOperation.user_id == 1).delete(synchronize_session=False)\n",
    "def purge():\n    db.session.query(models.CredentialOperation).filter_by(user_id=1).delete()\n",
    "def purge(op):\n    op = db.session.get(CredentialOperation, 1)\n    db.session.delete(op)\n",
    "def purge():\n    op: CredentialOperation = db.session.get(CredentialOperation, 1)\n    db.session.delete(op)\n",
    "def purge(user_id):\n    ops = CredentialOperation.query.filter_by(user_id=user_id).all()\n    for op in ops:\n        db.session.delete(op)\n",
    "def purge():\n    ops = db.metadata.tables['credential_operations']\n    db.session.execute(sa.delete(ops))\n",
    "def purge():\n    table = db.metadata.tables['credential_operations']\n    db.session.execute(table.delete())\n",
    "def purge():\n    db.session.execute(sa.text('DELETE FROM credential_operations WHERE true'))\n",
    "def purge():\n    db.session.execute(text('truncate table credential_operations'))\n",
])
def test_mutation_proof_reports_each_way_to_delete_operation_rows(source):
    assert find_deletes(source), source


@pytest.mark.parametrize("source", [
    "def read():\n    return db.session.query(CredentialOperation).filter_by(user_id=1).all()\n",
    "def drop_user(user):\n    db.session.delete(user)\n",
    "def drop_user_typed(user_id):\n    user: User = db.session.get(User, user_id)\n    db.session.delete(user)\n",
    "def drop_passkeys(user_id):\n    PasskeyCredential.query.filter_by(user_id=user_id).delete()\n",
    "def text():\n    return 'delete from classes'\n",
])
def test_unrelated_deletes_are_not_reported(source):
    assert find_deletes(source) == [], source

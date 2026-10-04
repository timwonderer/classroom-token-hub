"""Build disposable predecessor schemas with their genuine canonical writers.

Historical migration fixtures must run forward from the frozen baseline instead
of undoing immutable current-head evidence. Pinned source is never a runtime
compatibility path and produces no new historical attestations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from app.extensions import db

BEFORE_UUID_SOURCE = "7f2bb2562ff4f083785af67259be960c7d01db1a"
BEFORE_PAYROLL_SOURCE = "ae72c625733d2caeab51895b1c39bf3ad888c1b9"
PAYROLL_AUTHORITY_SOURCE = "46af1c8739f9e89e35c4b362ae06c0f8aaed6263"


def predecessor_classrooms(source_revision, schema_revision, keys, *, with_passkey=False, anchored_payroll=False):
    """Rebuild only the active disposable test DB and return scalar source IDs."""
    url = db.engine.url
    assert url.drivername.startswith("postgresql") and "test" in (url.database or "")
    db.session.remove()
    db.engine.dispose()
    repository = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="cth-migration-source-") as directory:
        source = Path(directory)
        archive = source / "source.tar"
        with archive.open("wb") as stream:
            subprocess.run(["git", "archive", source_revision], cwd=repository,
                           stdout=stream, check=True)
        subprocess.run(["tar", "-xf", str(archive), "-C", str(source)], check=True)
        if anchored_payroll:
            # Supply explicit scheduling inputs to the old test initializer's
            # constructor before INSERT. Runtime code and migrations stay exact;
            # this is hypothetical migration input, not reconstructed production.
            initializer = source / "tests/helpers/canonical_classroom.py"
            contents = initializer.read_text()
            constructor_input = "            payroll_frequency_days=14,"
            assert contents.count(constructor_input) == 1
            contents = contents.replace("from dataclasses import", "from datetime import datetime, timezone\nfrom dataclasses import", 1)
            contents = contents.replace(constructor_input, constructor_input + "\n"
                "            first_pay_date=datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc),\n"
                "            pay_schedule_type='biweekly',")
            initializer.write_text(contents)
        environment = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False),
                           PYTHONPATH=str(source), MIGRATION_FIXTURE_REVISION=schema_revision,
                           MIGRATION_FIXTURE_KEYS=json.dumps(list(keys)),
                           MIGRATION_FIXTURE_PASSKEY="1" if with_passkey else "0")
        result = subprocess.run([sys.executable, "-c", _CREATE], cwd=source,
                                env=environment, text=True, capture_output=True, timeout=90)
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
        return json.loads(next(line.partition("=")[2] for line in result.stdout.splitlines()
                               if line.startswith("MIGRATION_CLASSROOMS=")))


_CREATE = r"""
import json, os
from sqlalchemy import text
from flask_migrate import upgrade
from app import app, db
from app.feats.base import FEATContext
from app.models import PasskeyCredential
from tests.helpers.canonical_classroom import provision_classroom
with app.app_context():
    assert 'test' in db.engine.url.database
    with db.engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    upgrade(revision=os.environ['MIGRATION_FIXTURE_REVISION'])
    classrooms = [provision_classroom(key) for key in json.loads(os.environ['MIGRATION_FIXTURE_KEYS'])]
    if os.environ['MIGRATION_FIXTURE_PASSKEY'] == '1':
        with FEATContext('FEAT-IDEN-001', idempotency_key='test:uuid-migration:passkey'):
            db.session.add(PasskeyCredential(user_id=classrooms[0].teacher_user.id,
                credential_id='cred-migration', authenticator_name='Key'))
            db.session.flush()
    result = [{'class_id': c.class_id, 'seat_id': c.students[0].seat.id,
               'teacher_seat_id': c.teacher_seat_id} for c in classrooms]
    db.session.commit()
    print('MIGRATION_CLASSROOMS=' + json.dumps(result))
"""

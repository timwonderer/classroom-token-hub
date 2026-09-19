"""Data cleanup is scoped, idempotent, and cannot rehydrate deleted material."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa


def test_claim_cleanup_upgrade_and_downgrade(monkeypatch):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/c1a1b2d3e4f5_clear_claimed_seat_artifacts.py'
    spec = importlib.util.spec_from_file_location('claim_cleanup', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('''CREATE TABLE seats (
            id INTEGER PRIMARY KEY, role TEXT, user_id INTEGER, claimed_at TEXT,
            claim_first_name_hash TEXT, claim_last_name_hash TEXT,
            roster_fingerprint TEXT, dedupe_code TEXT)'''))
        for seat_id, role, user, claimed in [(1, 'student', 10, '2026-09-15'), (2, 'student', None, None), (3, 'teacher', 20, '2026-09-15')]:
            conn.execute(sa.text("INSERT INTO seats VALUES (:id, :role, :user, :claimed, 'first', 'last', 'fingerprint', 'code')"), dict(id=seat_id, role=role, user=user, claimed=claimed))
        monkeypatch.setattr(migration.op, 'get_bind', lambda: conn)
        migration.upgrade()
        migration.upgrade()
        migration.downgrade()
        rows = conn.execute(sa.text('SELECT claim_first_name_hash, claim_last_name_hash, roster_fingerprint, dedupe_code FROM seats ORDER BY id')).all()
        assert tuple(rows[0]) == (None, None, None, None)
        assert tuple(rows[1]) == tuple(rows[2]) == ('first', 'last', 'fingerprint', 'code')

"""Durable ownership ledger shared by the staging dispatcher and independent reaper."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

from digitalocean import CLEANUP_MARGIN, LifecycleError, PROFILE, TTL, exact_id, require


class Lifecycle:
    def __init__(self, sqlite_path, provider, prove=None, *, now=time.time, sleep=time.sleep):
        self.path = Path(sqlite_path)
        self.provider = provider
        self.prove = prove
        self.now = now
        self.sleep = sleep
        require(self.path.parent.is_dir() and self.path.parent.stat().st_uid == os.geteuid()
                and self.path.parent.stat().st_mode & 0o077 == 0, 'insecure_inventory_directory')
        self.binding = hashlib.sha256(json.dumps(provider.policy, sort_keys=True,
                                                 separators=(',', ':')).encode()).hexdigest()
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, sha TEXT NOT NULL, installation_id TEXT NOT NULL UNIQUE,
                    issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, binding TEXT NOT NULL,
                    ownership TEXT NOT NULL,
                    state TEXT NOT NULL, droplet_id INTEGER, candidates TEXT NOT NULL DEFAULT '[]',
                    create_rejected INTEGER NOT NULL DEFAULT 0, delete_intent INTEGER NOT NULL DEFAULT 0,
                    reason TEXT, ancillary TEXT NOT NULL DEFAULT '[]'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_run ON runs ((1)) WHERE state != 'closed';
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def provider_lock(self):
        # Keep cloud mutation and inventory updates serialized across processes and crashes.
        # Host bootstrap and waiting for boot occur outside this lock.
        with open(self.path.with_suffix('.operations.lock'), 'a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def current(self, run_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        require(row is not None, 'unknown_run')
        return dict(row)

    def reserve(self, run_id, sha, profile):
        require(isinstance(run_id, str) and re.fullmatch('[1-9][0-9]{0,19}', run_id)
                and re.fullmatch('[a-f0-9]{40}', sha) and profile == PROFILE, 'invalid_approval')
        start = int(self.now())
        ownership = {key: self.provider.policy[key] for key in ('team_uuid','project_uuid','vpc_uuid','image_id','firewall_id')}
        ownership.update(profile=profile, hourly_limit_usd='0.05', compute_limit_usd='0.10')
        try:
            with self.db() as db:
                db.execute('INSERT INTO runs (run_id,sha,installation_id,issued_at,expires_at,binding,ownership,state) '
                           "VALUES (?,?,?,?,?,?,?,'reserved')", (run_id, sha, str(uuid4()), start, start+TTL,
                                                                 self.binding, json.dumps(ownership,sort_keys=True)))
        except sqlite3.IntegrityError:
            raise LifecycleError('active_or_previously_used_run') from None
        return self.current(run_id)

    def update(self, row, state, number=None):
        with self.db() as db:
            db.execute('UPDATE runs SET state=?, droplet_id=COALESCE(?,droplet_id) WHERE run_id=?',
                       (state, number, row['run_id']))
        return self.current(row['run_id'])

    def candidates(self, row):
        objects = self.provider.droplets()
        ids = [exact_id(obj['id']) for obj in objects]
        with self.db() as db:
            db.execute('UPDATE runs SET candidates=? WHERE run_id=?', (json.dumps(ids), row['run_id']))
        require(len(ids) <= 1, 'multiple_candidates')
        return ids

    def identify(self, row):
        require(row['binding'] == self.binding, 'provider_policy_changed')
        self.provider.identity()
        ids = self.candidates(row)
        number = row['droplet_id']
        if number is None:
            require(len(ids) == 1, 'create_outcome_unknown')
            obj = self.provider.get(ids[0])
            require(obj is not None, 'create_outcome_unknown')
            self.provider.verify(row, obj)
            require(self.prove is not None and self.provider.ready(obj) and self.prove(row, obj) is True,
                    'missing_independent_ownership_proof')
            number = exact_id(obj['id'])
            self.update(row, row['state'], number)
        require(not ids or ids == [number], 'provider_inventory_conflict')
        obj = self.provider.get(number)
        if obj is None:
            require(row['delete_intent'] == 1 and not ids and not self.provider.resources(), 'absence_unconfirmed')
            self.provider.verify_empty_extras()
        else:
            require(ids == [number], 'provider_inventory_conflict')
            self.provider.verify(row, obj)
        return obj

    def allocate(self, run_id, *, user_data, ssh_keys):
        with self.provider_lock():
            row = self.current(run_id)
            require(row['binding'] == self.binding, 'provider_policy_changed')
            require(self.now() < row['expires_at'] - CLEANUP_MARGIN, 'working_deadline')
            if row['state'] == 'reserved':
                self.provider.validate_create_inputs(user_data, ssh_keys)
                self.provider.preflight()
                require(self.now() < row['expires_at'] - CLEANUP_MARGIN, 'working_deadline')
                row = self.update(row, 'issuing')  # commit BEFORE handing the create request to the transport
                try:
                    number = self.provider.create(row, user_data, ssh_keys)
                except LifecycleError as error:
                    if str(error) == 'provider_http_422':
                        # DO explicitly rejected this request. Preserve the rejection for the reaper.
                        with self.db() as db:
                            db.execute("UPDATE runs SET create_rejected=1,state='unresolved', reason=? WHERE run_id=?",
                                       ('provider_http_422',run_id))
                    raise
                self.update(row, 'owned', exact_id(number))
            else:
                require(row['state'] in ('issuing', 'owned'), 'allocation_closed')
        # DO project membership, network interfaces and firewall assignment can converge after 202.
        for _ in range(36):
            with self.provider_lock():
                row = self.current(run_id)
                require(self.now() < row['expires_at'] - CLEANUP_MARGIN and row['state'] in ('issuing','owned'),
                        'working_deadline_or_teardown')
                try:
                    obj = self.identify(row)
                    if obj is not None and self.provider.ready(obj):
                        self.update(row, 'owned', obj['id'])
                        return obj
                except LifecycleError as error:
                    if str(error) not in ('project_membership_conflict','provider_inventory_conflict',
                                          'create_outcome_unknown','unconfirmed_firewall','absence_unconfirmed','missing_independent_ownership_proof'):
                        raise
            self.sleep(5)
        raise LifecycleError('allocation_unverified')

    def cleanup(self, run_id):
        with self.provider_lock():
            row = self.current(run_id)
            if row['state'] == 'closed':
                return row
            if row['state'] == 'reserved':
                return self.update(row, 'closed')  # no POST was issued
            row = self.update(row, 'cleaning')
            try:
                if row['create_rejected'] == 1 and row['droplet_id'] is None:
                    require(row['binding'] == self.binding, 'provider_policy_changed')
                    self.provider.identity()
                    require(not self.candidates(row) and not self.provider.resources(), 'rejected_create_conflict')
                    self.provider.verify_empty_extras()
                    return self.update(row, 'closed')
                obj = self.identify(row)
                if obj is not None:
                    self.provider.check_extras(obj)
                    # Recheck account/project ownership, the exact ID and its immutable attributes before DELETE.
                    obj = self.identify(self.current(run_id))
                    if obj is not None:
                        with self.db() as db:
                            db.execute('UPDATE runs SET delete_intent=1 WHERE run_id=? AND droplet_id=?',
                                       (run_id, exact_id(obj['id'])))
                        self.provider.delete(exact_id(obj['id']))
                require(self.identify(self.current(run_id)) is None, 'deletion_pending')
                return self.update(row, 'closed')
            except Exception as error:
                # Never copy arbitrary SSH, API, or transport error text into evidence.
                reason = str(error) if isinstance(error, LifecycleError) else ''
                known = {'provider_policy_changed','wrong_cloud_owner','multiple_candidates','create_outcome_unknown',
                         'missing_independent_ownership_proof','droplet_identity_conflict','droplet_creation_time',
                         'project_membership_conflict','provider_inventory_conflict','absence_unconfirmed',
                         'additional_team_resources','associated_resources_unresolved','deletion_pending','rejected_create_conflict',
                         'provider_communication','incomplete_project_inventory','provider_inventory_limit'}
                if reason not in known and not re.fullmatch('provider_http_[0-9]{3}', reason):
                    reason = 'verification_failed'
                ancillary = error.ancillary if isinstance(error, LifecycleError) else []
                with self.db() as db:
                    db.execute("UPDATE runs SET state='unresolved', reason=?, ancillary=? WHERE run_id=?",
                               (reason,json.dumps(ancillary),run_id))
                raise

    def sweep(self):
        with self.db() as db:
            rows = db.execute("SELECT run_id FROM runs WHERE state IN ('cleaning','unresolved') "
                              "OR (state != 'closed' AND expires_at <= ?)", (int(self.now()) + CLEANUP_MARGIN,)).fetchall()
        report = []
        for record in rows:
            try:
                self.cleanup(record['run_id'])
            except Exception:
                # Durable unresolved inventory retains its exclusive reservation and will be retried.
                pass
            row = self.current(record['run_id'])
            report.append({k: row[k] for k in ('run_id','state','droplet_id')})
        return report

---
title: Install the release database
category: self-hosting
description: Install and verify the reviewed current schema in an empty PostgreSQL database.
roles: [operator]
keywords: [self-hosting, database, installation, verification, migrations]
---

# Install the release database

Use this procedure once, on a **new, offline database**. A running or previously
initialized installation upgrades through Alembic. A backup restores through
the backup procedure. Neither is a fresh installation. The external database
owner runs this procedure; it grants no application capability.

The reviewed artifact is under `migrations/fresh/a0faf8b2a35d/`. Its source is
Git commit `1e446b0ba0507df5a5075ec5c15e76b6502d6a01`. Use a trusted checkout
containing the reviewed installer, manifest and schema together. The installer
selects the bundle for the checkout's sole Alembic head. Checksums detect
corruption; authenticating the release itself remains the operator's job.

**Tested database profile:** PostgreSQL server and `pg_dump` 14.24, local Unix
socket, UTF-8, C collation and C character classification. Use matching server
and client tools on PATH and the release Python environment with psycopg2 and
Alembic installed. An alternate OS, PostgreSQL major, collation or client format
needs separate qualification. This database check is not a completed host or
independently verified handbook installation.

## On the new host

1. Confirm the local cluster, socket, port and dedicated nonsuperuser database
   owner with the infrastructure operator. Check the host is the intended new
   installation. Keep application processes, scheduled jobs and other clients
   disconnected. Only the trusted operator may connect or issue DDL until the
   final verification: the installer lock coordinates installers, not other
   administrators. Enforce this through the cluster's access configuration;
   global role defaults, host authentication, backups and network policy are
   separate operator responsibilities. Never use a production/test fallback URL.
2. In a shell with the release virtual environment active, set the following
   example variables to the **actual new** target. Use a dedicated OS/database
   role with local authentication, or a private mode-0600 password file. Clear
   inherited `PG*` settings except an explicitly chosen `PGPASSFILE`.
   Generate a new enrollment identifier for this installation.

   ```sh
   socket=/var/run/postgresql
   port=5432
   owner=cth_install
   database=cth_new
   enrollment=$(python -c 'import uuid; print(uuid.uuid4())')
   ```

3. As the cluster's provisioning role, create the named database from template0
   with that owner. Do not drop, rename, reuse or enroll an existing database
   if creation fails. As the new database owner, mark it for this installation.
   The enrollment comment is an intent marker, not a password or a source of
   authentication. In psql, `:"db"` quotes an identifier and `:'marker'`
   quotes a string.

   ```sh
   createdb -h "$socket" -p "$port" -U postgres -T template0 -O "$owner" \
     --encoding=UTF8 --lc-collate=C --lc-ctype=C "$database" || exit 1
   psql -X -v ON_ERROR_STOP=1 -h "$socket" -p "$port" -U "$owner" \
     -d "$database" -v db="$database" -v marker="cth-fresh:$enrollment" <<'SQL'
   COMMENT ON DATABASE :"db" IS :'marker';
   SQL
   ```

4. From the release checkout execute the same command used by staging:

   ```sh
   python scripts/fresh_database.py --host "$socket" --port "$port" \
     --user "$owner" --database "$database" --installation-id "$enrollment"
   ```

   The installer verifies owner, enrollment, server and database profile. It
   compares the schema with an empty template, rejects large objects and
   database-specific role settings, and refuses a second installation. It loads
   the frozen DDL and approved reference rows without replaying migrations.
   It then locks the installed tables, exports a snapshot, checks the full
   schema digest, reads all sequence states and checks the permitted initial
   data. Only that verification transaction records the exact Alembic revision.
   Success prints `Verified new database at revision a0faf8b2a35d`.

5. Point the installation's application configuration at this database. Before
   opening traffic confirm `flask db current` equals `flask db heads` under
   that configuration; record the SHA, revision and success or failure. Check
   first authorized use and the nonempty audit chain separately. An empty
   audit table on a new database is expected and is not proof of business
   audit integration. Do not archive credential files, enrollment identifiers,
   row dumps or raw application logs as evidence.

**Interrupted installation:** The first transaction can commit the schema with
no Alembic version row so that a separate pg_dump session can read it. The
second transaction either verifies and records the head, or records no head.
An unsuccessful rerun on this nonempty target is intentional. Keep it offline.
Check the explicit target and reported revision. If the new installation has
never served anyone, create a different new, explicitly identified empty
database and investigate the failure before repeating. Do not manually stamp,
automatically drop, or retry against a populated database. Existing user state
requires its ordinary backup and recovery procedure.

## Producing a reviewed artifact

From the repository with release dependencies installed, place the reviewed
PostgreSQL 14 binaries first on PATH. The output path must not exist:

```sh
python scripts/generate_fresh_database.py \
  --source-sha 1e446b0ba0507df5a5075ec5c15e76b6502d6a01 \
  --output /tmp/cth-reviewed-a0faf8b2a35d
diff -ru migrations/fresh/a0faf8b2a35d /tmp/cth-reviewed-a0faf8b2a35d
```

The generator archives that exact commit, requires a single head, starts a new
socket-only cluster in a private directory and migrates an empty database.
It uses scratch credentials and no application configuration from the checkout.
It exports the complete schema (including constraints, index predicates,
referential actions, functions and triggers); owner names and pg_dump transport
markers/version banners are not part of the cross-host comparison. ACL
statements in the portable schema remain included. For the varchar-list checks
and partial index, it restores the original IN syntax so PostgreSQL re-creates
the migration's actual catalog expression. The digest for verification is the
original migrated schema, **not** an expression-normalized comparison.

The manifest inventories every public sequence and the 15 approved support
categories. The generator refuses other populated application tables. The seed
migration gives all categories its transaction timestamp: the installer uses
its own transaction timestamp and checks all 15 share it. Absolute creation
time is the only excluded seed field. The Alembic row is verified separately.
The generator runs the direct installer on a second database with an ordinary
database owner and compares both results before writing the output. The
temporary server stops on completion. Review artifact and manifest changes
against the exact migrations; a new seed or object class requires explicit
review. Never regenerate from production, a developer database or ORM metadata.

## B1 qualification evidence

- For the separate test of real FEAT emission, use a disposable acceptance
  database initialized above with a name ending in `_test`, on a socket-only
  test server. Use an exported checkout without a `.env` file and the test
  dependencies installed:
  `python -m tests.helpers.verify_fresh_audit --host "$socket" --port "$port" --user "$owner" --database "$database" --installation-id "$enrollment"`.
  This is a test-only, rollback-based check; never run this harness against a
  database that serves users. The B1 check passed on the direct baseline and
  preserved all 47 table counts and all 27 sequence states across rollback.
- Two clean derivations using PostgreSQL 14.24 produced identical artifacts.
  Schema SHA-256: `36c0f9a82fdc3475cf7bc559d1876250626b756d34a03a66d82ad686c2f343ad`.
  Installation SQL SHA-256: `7d843eff08f9f888b89d9c5f2f4c3ee9c4e700eccf78d4a78627f9d1afe255fd`.
  Independently created direct and migrated test databases matched in full
  portable schema, all initial data under the rule above, sequence values and
  `is_called` flags, and revision. Wrong enrollment and repeat installation
  were refused. Database-specific settings and another live connection also
  caused refusal before installation. A deliberately incorrect verification
  digest in a temporary test manifest left zero Alembic rows; attempting to
  reinstall that partial database was refused.
- Both test databases rejected conflicting support-category names (SQLSTATE
  23505) and NULL names (23502). The enabled update and delete triggers on
  `audit_events` bound to the expected functions. Both functions rejected the
  corresponding operation (P0001) on a transaction-local integer-row probe;
  no business or audit record was fabricated. This probes database enforcement,
  not an authenticated application workflow.
- Repeating derivation at actual predecessor commit
  `446d751a5815a9123892fb356b0e44f2fb09094a` produced head `a91c3d7e5f20`.
  A fresh direct database at that revision and another installed via the
  historical chain both accepted the real `a0faf8b2a35d` ledger-vocabulary
  upgrade and matched today's complete reference. Separately, disposable
  copies of today's direct and migrated databases accepted an explicit
  downgrade to that predecessor and re-upgrade; both intermediate and final
  inventories matched. No new migration was invented. A successor **after**
  today's head does not yet exist: repeat the two-path upgrade comparison when
  a real successor is reviewed. These disposable downgrade checks are not a
  production rollback recommendation.

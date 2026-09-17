# v2 Live-Test Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-001      | 2.0     | 2026-09-17     | 1.2 (issued as SOP-DEP-022) | Normative |

## I. Purpose

Provide the operator workflow for the first controlled test deployment of the
complete v2 application onto the deployment host, and for the live test that
follows it.

**This is not launch certification.** The goal is to prove that the application
installs, boots, migrates, and can be exercised on the host under maintenance
control. A successful boot, or a passing subset of routes, is not certification.

## II. Scope

Test deployments of the repository `main` branch onto the deployment host, from
release gate through go/no-go decision. Production transition after a successful
live test is governed by SOP-DEP-002.

Version 2.0 is a rewrite. Version 1.2 described the pre-v2 identity model
(`ClassMembership`, `TeacherBlock`), a fixed 664-test baseline, a `join_code`
form of the student switch-class route, a `/health/deep` endpoint, and record
storage under `docs/LOGS/` — each of which is now false or prohibited. It was
replaced rather than amended, using
`docs/TRACKING/PRODUCTION_FIRST_TEST_DEPLOYMENT_CHECKLIST_2026-09.md` as the
source of current host truth.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md` (seat state; §VIII participation and visibility)
- `SOP-DB-009_Migration_Compliance_Review.md`
- `SOP-DB-001_Migration_Specifications.md`
- `SOP-TEST-001_Validation_Execution_And_Reporting.md`

## V. Environment Truth

- Deployment branch: repository `main`. The names `codex/v2.0` and `CTH_v2.0`
  are retired and resolve to nothing.
- Host access: the approved Tailscale/SSH path to the deployment host.
- Service: `classroom-economy` systemd unit, fronted by Nginx, with PostgreSQL
  on the host.
- The v1 application, its service units, and its database are already removed;
  PostgreSQL and the Nginx holding page remain.
- Local dev and test databases are never deployment targets. The test database
  is addressed only by `TEST_DATABASE_URL` and its name contains `test`.

## VI. Release and Authority Gate

1. Confirm the release commit is on `main`, and record the full 40-character SHA.
2. Confirm the working tree at that SHA carries no unapproved local changes.
3. Confirm exactly one migration head, and that migration safety checks pass:

```bash
bash scripts/check-migrations.sh
python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt
```

   `check-migrations.sh` must report a single head. The linter must report
   **zero errors**; warnings accepted by `migrations/lint_baseline.txt` are
   pre-gate debt under SOP-DB-009 §VI and do not block. The baseline only
   shrinks — a new migration never goes into it.

4. Run the PostgreSQL-backed test suite and attach its artifact:

```bash
pytest -q
```

   Record the summary from `pytest_result/` (the CSV, summary and failures log
   for the run). Do **not** compare against a fixed historical pass count; the
   suite grows. The gate is: no failures attributable to the release, and any
   skip or failure explicitly dispositioned in the record.

5. Record SHA, branch, migration head, operator, verifier, and test window.

## VII. Runtime Preparation

1. Put the domain in maintenance/holding mode and confirm the public response.
2. Replace the existing checkout with the approved checkout at the release SHA.
3. Create or refresh the virtual environment from the pinned requirements.
4. Install the systemd unit with an explicit protected environment source.
5. Confirm bind address, worker count, timeout, logging, and restart policy.
6. `systemctl daemon-reload`, and confirm the unit does not start before the
   environment completeness check in §VIII passes.

> **Worker count for a first test deployment: one.**
> The APScheduler background scheduler starts inside `create_app`, so every
> worker process starts its own. With N workers, each hourly job — ledger
> settlement, savings interest, automatic payroll, rent reconciliation,
> insurance expiry — runs N times per hour concurrently. No leader election or
> advisory lock guards this today. Run a single worker for the live test, and
> treat single-runner enforcement as a prerequisite for any multi-worker
> deployment.

## VIII. Environment and Secrets

Provision through the approved secret-management path or a root-owned service
environment file with mode `600`. Never copy a local `.env` wholesale, and
never print or commit values.

- `SECRET_KEY` — new, high-entropy, deployment-specific.
- `ENCRYPTION_KEY` — PII-encryption key with controlled custody. It also
  encrypts TOTP secrets, so rotation touches both.
- `PEPPER_KEY` — lookup-HMAC key for username and claim-name digests,
  independent of all other keys. Rotation is an identity-reset ceremony, not a
  transparent re-key.
- `AUDIT_HMAC_KEY` — audit-lineage key, independent of all other keys.
- `DATABASE_URL` — the new v2 database only.
- `FLASK_ENV=production`, and `FLASK_APP` where CLI operations require it.
- `PASSWORDLESS_API_KEY` / `PASSWORDLESS_API_PUBLIC` — deployment pair.
- `TURNSTILE_SECRET_KEY` / `TURNSTILE_SITE_KEY` — pair registered for the
  deployment domains.
- `REDIS_URL`, or the explicitly approved rate-limit storage configuration.
- `CSRF_SECRET_KEY` where the security configuration requires it.
- `SUPPORT_EMAIL`, `MARKETING_SITE_URL`, `EXTERNAL_DOCS_BASE_URL`, and the
  status/operations URLs.
- Maintenance/status variables for the test window.

Then confirm: no test, development, or legacy database value is present; the
service identity can read the environment and no other identity can; and the
service is restarted only after the completeness check passes.

## IX. Fresh Database and Migration

1. Create one empty PostgreSQL database with the approved owner.
2. Confirm the connection target is not a local, test, or legacy database.
3. Confirm PostgreSQL version and required extensions match the rehearsal.
4. Confirm no application process is writing to the database.
5. Run the upgrade from the release artifact with the deployment `DATABASE_URL`:

```bash
flask db upgrade
flask db current
```

6. Confirm `flask db current` reports the expected single head.
7. Confirm the schema contains no v1-only objects. The v1 identity tables
   (`student`, `admin`, `teacher_block`, `student_teacher`, `class_membership`,
   `student_block`, `balance_cache`) must not exist.
8. Record migration output and the resulting revision.

## X. Application Start and Health Checks

1. Start the service under maintenance mode.
2. Confirm `systemctl is-active classroom-economy`.
3. Confirm the logs carry no missing-key, database, Redis, import, or migration
   errors.
4. Confirm `/health` returns `ok` with HTTP 200 (it executes `SELECT 1`).
5. Confirm `/health/status` returns its bounded signal set. Expect exactly one
   executed check — `database` as PASS/KNOWN. The `login`, `attendance`,
   `payroll`, `roster` and `classroom_economy` capabilities and the
   `background_jobs`, `external_integrations`, `monitoring_freshness` and
   `invariant_verification` platform signals report UNKNOWN/UNAVAILABLE with
   `CHECK_NOT_REGISTERED`. **That is the contract, not a failure:** an
   unmonitored surface must not read as a healthy one (INV-ARC-017).
6. `/health/deep` is retired and returns 404 by design. A 404 there is correct;
   a 200 means something reintroduced it.
7. Point Nginx at the service only after local health passes, then confirm
   HTTPS certificate, host routing, and security headers.

## XI. Full-App First Test

Exercise these in a real browser while maintenance remains controlled. Each
line records owner, timestamp, pass/fail/blocked, and notes or defect link.

- `/admin/login` renders and submits.
- `/student/login` renders and submits.
- `/docs` renders.
- Passwordless enrollment and authentication with deployment credentials.
- Turnstile renders on every configured route and real verification succeeds.
- Teacher creates or accesses a class boundary.
- Student seat claim, then a student session.
- Teacher current-class switching via `POST /admin/current-class`.
- Student add-class via `/student/add-class`, and switch-class via
  `POST /student/switch-class/<class_id>`. The route takes the canonical
  `class_id`; a `join_code` in that position is the retired alias form.
- Selected-class export via `/admin/export-students`. The export scopes to the
  session's active class — a query parameter does not choose the class — and
  lists claimed seats only.
- Hall-pass verification via `/verify/hallpass/<teacher_public_token>`.
- Class-scoped admin actions cannot cross the selected class boundary.
- Attendance, productivity, payroll, obligations, ledger and store paths load
  and execute through their canonical routes.
- Audit/lineage records are produced for protected mutations.
- Export and support/operations surfaces load without 500 responses.
- No PII appears in URLs, logs, errors, or browser-visible diagnostics.
- Accessibility smoke checks cover the public, login, teacher and student
  surfaces reached in this test (INV-ARC-020).

## XII. Seed and Fixture Expectations

Use the canonical identity model: `User` (authentication principal), `Seat`
(class-local actor, the activity anchor), `IdentityProfile` (display only), and
`ClassEconomy` (table `classes`, the isolation boundary). `class_id` is the
scope key; `join_code` is an ingress alias and user-facing display only.
Teacher authority is `User.user_role` plus `ClassEconomy.teacher_user_id`.

- Provision at least **two teacher-owned classes**, so current-class switching,
  selected-class export, and student switch-class are meaningful.
- Provision at least one **unclaimed** roster seat alongside claimed seats. Per
  DOM-IDEN-002 §VIII it must appear in Student Management only, and in no
  count, total, list, log or economic run elsewhere. The live test is the first
  place this is observable with real data.
- Do not hand-assemble identity rows for fixtures; provision a classroom.

## XIII. Roles and the Solo-Operator Exception

Named roles for each rehearsal or smoke pass:

- **Primary operator** — runs the upgrade and captures command output.
- **Independent verifier** — executes or witnesses the smoke routes; must not
  be the branch author.
- **Engineering escalation owner** — approves hold, fix-forward, or rollback.

Primary operator and escalation owner may be the same person. In a
single-operator environment the operator MAY assume all three roles provided
the test suite passes with no unexplained failures, every §XI line is executed
and recorded, results are written into the record, and known risks or
deviations are stated before the go/no-go decision.

AI assistance MAY be used to look for defects or invariant violations. Its
output is advisory only and is **not** independent verification authority.

## XIV. Decision and Rollback

1. The verifier reviews service, database, browser and security evidence.
2. If migration or boot fails, keep maintenance active and stop. Do not retry
   blindly.
3. If the application fails after migration, choose fix-forward or restore on
   the evidence.
4. Do **not** use `alembic downgrade` / `flask db downgrade` as automatic
   recovery. Downgrade is a rehearsed, explicitly targeted operation; the bare
   form aborts with "Ambiguous walk" when the head is a merge point.
5. Confirm a recoverable snapshot of the target database exists before the test
   window opens.
6. Reopen traffic only after the decision is recorded.

## XV. Record Storage

Capture: migration head before and after, the `pytest_result/` artifact
reference, health output, §XI results, failures, and the go/no-go decision.

Store the finalized record as a repository artifact under `docs/ops/audits/`,
or as a retained PR/ticket comment. **Do not create `docs/LOGS/`** — that root
was removed on 2026-09-05 and must not be reintroduced; chronology belongs in
`CHANGELOG.md` and rationale in `docs/PRINCIPLES/`.

The record must name the exact deployed SHA (`git rev-parse HEAD`) and be
immutable once finalized.

## XVI. Completion Condition

The first test deployment is complete only when the exact SHA runs from a fresh
database, the required integrations work, every §XI path has recorded evidence,
and the operator/verifier decision is stored.

## XVII. Amendment

Revisions require incrementing the version, updating the effective date, and
populating the Supersedes field. A claim about codebase behavior in this
document must be verifiable against the release artifact at the time of
revision; where they disagree, the code wins and this document is corrected.

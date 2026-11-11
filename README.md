![Classroom Token Hub banner](github-pages/assets/CTH_horizontal_header_logo.png)

# Classroom Token Hub (CTH)

A classroom behavior management and reward platform with built-in simulated financial products and economic engines (and an absurd amount of documentation, pytests, and opinions.)

Students earn tokens for the time they work, and spend them on rent, insurance and a class store. Teachers run the class economy without handing over student email addresses, phone numbers or school SSO. Built with Flask, SQLAlchemy and PostgreSQL. Each class period is its own isolated economy.

**Latest recorded application deployment (2026-11-08 UTC):** [v2.4.4](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.4.4) (`f530954`, deployed 2026-11-08 UTC, [release record](docs/ops/audits/DEPLOY_2026-11-08_f530954.md)).

The deployment record describes checks performed at release time, not a live health check.

**Latest published release:** ![Version](https://img.shields.io/github/v/release/timwonderer/classroom-token-hub)

**Branch:** `main`

**License:** [Polyform Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)

| | |
| --- | --- |
| Website | [classroomtokenhub.com](https://classroomtokenhub.com) |
| Application | [app.classroomtokenhub.com](https://app.classroomtokenhub.com) |
| Service status | [status.classroomtokenhub.com](https://status.classroomtokenhub.com) |
| Developer docs | [classroomtokenhub.com/docs](https://classroomtokenhub.com/docs/) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

---

## Contents

- [Features](#features)
- [Privacy](#privacy)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Releases and deployment](#releases-and-deployment)
- [Documentation](#documentation)
- [Version history](#version-history)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Features

### For teachers

- **Sign up without contact details**: three steps. Name the class, pick a username and scan a TOTP code, then confirm the code. No email or phone number is asked for
- **Roster management**: paste a roster or add students one at a time, then export it. Adding students creates class-local seats and encrypted display profiles without creating sign-in accounts. Students claim those seats through the setup flow
- **Payroll**: set hourly pay rates, pay frequency, daily time caps, and overtime thresholds and multipliers. Payroll runs on a schedule by local calendar day. Each run pays the work sessions that ended since the last run, in full; a session still open is paid by the next run. Manual payments, reversals and history are also available
- **Classroom store**: sell immediate-use, delayed-use and collective-goal items. Each item declares its economic role. Bundles, bulk discounts, holding limits, start and delist dates, and redemption approval are supported
- **Rent**: recurring bill cycles, payment tracking and teacher waivers, with optional store perks linked to rent
- **Insurance**: tiered policies, a waiting period, and claims that students file and teachers review and pay out. Students see their own claims, and cancelling a policy stops it from renewing at the next cycle boundary
- **Banking**: checking and savings accounts, PIN-confirmed transfers, and savings interest using daily balances and the configured payout cadence. NSF fees are prohibited by the current contract; retirement of leftover fee machinery is tracked in [#1647](https://github.com/timwonderer/classroom-token-hub/issues/1647)
- **Economic engine**: pricing guidance derived from the Classroom Wage Index (CWI) and the class's economic policy mode, with teacher-reviewed rebalancing and domain-specific effective dates
- **Hall passes**: requests, approval, check-out and check-in, and capability-protected verification. Passes end with their class-local day; approved passes never used read Revoked after that day
- **Interpretation**: a read-only report on each completed cycle, built from immutable history. It describes what happened; it doesn't raise alerts or recommend actions
- **Issues**: resolve or escalate student reports about a transaction, an attendance session, or anything else
- **Announcements**: class-scoped, with an expiry date, shown on the student dashboard
- **Feature settings**: turn store, rent, insurance and other features on or off per class
- **Copy Configuration**: export selected settings from one class and review/import them into another. Files expire after five days and carry configuration, not rosters or transaction history. The instance must configure `CONFIGURATION_EXPORT_KEY`

### For students

- **Portal**: balances, transactions, attendance (start and stop work), store, rent, payroll and insurance
- **Account transfers**: move money between checking and savings, confirmed with a PIN
- **Seat claim**: claim the seat your teacher set up by matching your name against the roster, then create a username, PIN and passphrase. Before the account is created, you type your new username back from where you saved it, because CTH keeps no readable copy. Join more classes with a join code
- **Account recovery**: a teacher issues a short-lived reset code, and the student redeems it to set a new username, PIN and passphrase, with the same username check as a first claim
- **Hall pass requests**: ask for a pass and follow its status on the dashboard
- **Report an issue**: about a specific transaction, an attendance session, or a general problem

### For system admins

- **Portal**: counts of teachers, students and open issues, plus escalated issues and user reports
- **Monitoring**: an authenticated Grafana proxy; the old application/error log viewer pages have been removed
- **Accounts**: sysadmins are created from the CLI (`flask create-sysadmin`) and manage their own passkeys

### Teacher account recovery

No email is involved. A teacher who loses access starts recovery by entering the usernames of students in their classes:

- one class: 6 usernames
- two classes: 3 per class
- three classes: 2 per class
- four or more classes: 1 per class

A class with fewer students than that counts if every claimed student is entered. The system then picks two students at random in each class to confirm the request from their own accounts. Either selected student can provide that class's confirmation code. Once every class is confirmed, the teacher submits the full set to reset their credentials. Recovery needs at least 3 claimed students in every owned class, so that the random pick can't be predicted. See [DOM-IDEN-003 §IX](docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md) for the proof, recipient selection and code rules.

### Platform

- **Multi-tenant**: every read and write of seat or class data is scoped by `class_id`. One user can hold seats in several classes, and each class is its own economy
- **Ledger**: every money movement is written as `PENDING` and becomes posted history only when the scheduled settlement job admits it. The database rejects any change to a posted row
- **Scheduled jobs**: APScheduler runs settlement, payroll, savings interest, rent reconciliation, insurance expiry, collective-goal expiry, hall-pass day closure, account lifecycle cleanup, and maintenance checks. They run only in the gunicorn server process, and only in the one process holding a PostgreSQL advisory lock (`app/scheduler_ownership.py`). `flask run`, `flask` commands, migrations and scripts never run them; to exercise jobs locally, start `gunicorn wsgi:app`
- **Class time**: deadlines and "today" are calculated in each class's own timezone by one temporal resolver. The policy guardrails in CI reject `timedelta` arithmetic in services, FEATs and routes
- **Progressive web app**: installable on a phone, with an offline fallback
- **In-app help**: `/docs` serves the user guides in `docs/user-guides/`, with search and a choice of teacher or student view
- **Accessibility**: WCAG 2.1 AA is the target. CI includes axe-core checks and template coverage guards. Automated checks do not establish full conformance or replace keyboard, screen-reader and user-flow validation
- **Design system**: one set of design tokens with three role themes, governed by [SPEC-DES-001](docs/SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md) and checked against every template
- **Security**: PII encrypted at rest, teacher/sysadmin TOTP sign-in, passkeys (WebAuthn via passwordless.dev) for teachers and sysadmins, CSRF protection on every form, scrypt password hashing, Cloudflare Turnstile, and rate limiting with Flask-Limiter. See [SECURITY.md](SECURITY.md) to report a vulnerability
- **Health signals**: `/health` for liveness, and `/health/status` for bounded status signals that expose no tenant data or raw exceptions
- **Access gating**: Cloudflare Access on the application hostname controls who can reach the app during maintenance. The application itself has no maintenance-mode flag or bypass (DOM-OPS-001)

---

## Privacy

> [!IMPORTANT]
>
> CTH collects as little PII as it can: no email, no phone number, no SSO, no physical location. Student names are encrypted at rest. Completed accounts retain usernames only as keyed digests. During student setup, the username is held temporarily in dedicated memory-only Redis for the retention check. These protections reduce exposure; they do not make the data anonymous or guarantee that records cannot be linked to people.
>
> CTH doesn't support native SSO. A district that needs SSO can fork the project and add its own auth layer; see [PRN-SNP-001](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md) for why.

---

## Architecture

```text
Route ──▶ FEAT (app/feats/) ──▶ Domain services (app/services/) ──▶ commit
```

1. **Identity**: `User` is the global sign-in account. `Seat` is that user's place in one class, and every activity record keys off `seat_id`. `IdentityProfile` holds display names. `ClassEconomy` is the tenant boundary, identified by `class_id`, with `join_code` as its public alias. [INV-ARC-019](docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md) and [DOM-IDEN-001](docs/DOMAIN/DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md) govern this model
2. **Domains**: ten bounded domains, each with an authority spec under [docs/DOMAIN/](docs/DOMAIN/). They are Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations, Store & Entitlements, Operations, Interpretation, Policies and Support, and they share one Core foundation
3. **FEAT layer**: the contract requires domain mutations to pass through atomic FEAT orchestration in `app/feats/`; routes must not commit domain changes, and GET handlers must not write. See [FEAT-CORE-000](docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md) and [INV-ARC-007](docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md). Open implementation gaps are tracked in [DEVELOPMENT.md](DEVELOPMENT.md)

| Component | Where | What it does |
| --- | --- | --- |
| Flask application | `app/`, `templates/`, `static/`, `wsgi.py` | Teacher, student and sysadmin surfaces; served by gunicorn behind nginx |
| Status service | `status_service/`, `status/` | Public status page and an IAP-protected operator console; deployed by `deploy-status.yml` |
| Developer docs site | `docs-generator-proof/` | Hugo + Hextra build of the documentation tree |
| Public site | `github-pages/` | Marketing pages and the public timeline, published by `github-pages.yml` |

The application doesn't serve the marketing site, and the marketing site doesn't serve the application.

---

## Quick start

### Prerequisites

- Python 3.10 for application/runtime parity (`runtime.txt`); separate CI jobs also use 3.11 and 3.13
- PostgreSQL 15 or 16 (the versions CI runs against)
- Redis 6.0 or later (`redis-server`) for student account setup. Tests that need it start their own private instance; deployment requires a dedicated, non-persistent service ([infra/student-setup/README.md](infra/student-setup/README.md))
- A virtual environment

### Setup

Create a local PostgreSQL role and an empty development database first. Replace the example
`DATABASE_URL` credentials below with that role and database. Use this `.env` creation step only
on a fresh clone; it overwrites an existing file and generates new secrets.

```bash
git clone https://github.com/timwonderer/classroom-token-hub.git
cd classroom-token-hub
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# The heredoc delimiter is deliberately unquoted so the $(...) calls run.
# With 'EOF' quoted, each key gets the literal command text as its value.
cat > .env << EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://user:password@localhost:5432/classroom_economy
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
PEPPER_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
AUDIT_HMAC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FLASK_ENV=development
EOF

flask db upgrade
flask create-sysadmin   # follow the prompts and scan the QR code with an authenticator
flask run               # http://localhost:5000
```

The six variables above are required at startup. This starts the development server; it does not
provision student setup Redis or enable every integration. Before exercising student claim or
recovery, configure the dedicated memory-only Redis described in
[infra/student-setup/README.md](infra/student-setup/README.md) and set `STUDENT_SETUP_REDIS_URL`.
For production, both Turnstile keys are also mandatory.

| Variable | Purpose |
| -------- | ------- |
| `CONFIGURATION_EXPORT_KEY` | Dedicated random signing key for class configuration files and confirmations; unset disables transfers. Rotation immediately invalidates all outstanding files and confirmations; no fallback keys |
| `TEST_DATABASE_URL` | PostgreSQL database that the test suite rebuilds |
| `CSRF_SECRET_KEY` | A separate CSRF signing key (defaults to `SECRET_KEY`) |
| `SECRET_KEY_FALLBACKS` | Previous secret keys, so a rotation doesn't sign everyone out |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile; both are required when `FLASK_ENV=production`. Local development can omit them |
| `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`, `PASSWORDLESS_API_URL` | Passkey sign-in |
| `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `DEV_ENABLE_RATELIMIT` | Rate-limit storage; rate limits are off in development unless `DEV_ENABLE_RATELIMIT=1` |
| `STUDENT_SETUP_REDIS_URL` | Dedicated, non-persistent Redis for student account setup ([infra/student-setup/README.md](infra/student-setup/README.md)). Required: student claim and recovery setup refuse to run without it. Never point it at the rate-limit store |
| `EXTERNAL_DOCS_BASE_URL`, `MARKETING_SITE_URL`, `STATUS_PAGE_URL`, `GRAFANA_URL`, `SUPPORT_EMAIL` | External links |
| `LOG_LEVEL`, `LOG_FILE` | Logging |

Don't rotate `ENCRYPTION_KEY` or `PEPPER_KEY` casually. `ENCRYPTION_KEY` protects PII and TOTP secrets and needs a re-encryption to change. `PEPPER_KEY` keys the username digests, so rotation requires a deliberate lookup-digest migration and is not a password-hashing change. To run your own instance, start with [docs/self-hosting/](docs/self-hosting/README.md).

### Running tests

Tests run against a real PostgreSQL database named by `TEST_DATABASE_URL`; there's no SQLite path. `conftest.py` builds the schema through the real migration chain once per session and gives every test a fresh copy of it, so triggers and constraints are live in every test. The test database must be local and named as a test database, and the role needs `CREATEDB` for the fast path; see [CONTRIBUTING.md](CONTRIBUTING.md). Always set `TEST_DATABASE_URL` explicitly to a disposable database; the suite destroys and rebuilds test schemas.

```bash
pytest tests/dom/obligations/ -v          # one domain
pytest tests/test_status_contracts.py -v  # one file
pytest -k recovery                      # by pattern
```

Check existing results in `pytest_result/` first, then run only the tests relevant to your change. The full suite runs nightly in [full-suite.yml](.github/workflows/full-suite.yml); request an owner-run full suite when needed.

Tests provision a whole classroom through `tests/helpers/classroom_initializer.py` rather than creating rows by hand (SPEC-TEST-001).

Templates are held to the design-token contract. While editing one, check just that file:

```bash
python scripts/lint_design_tokens.py templates/your_page.html
```

### Database migrations

```bash
flask db heads                  # must show exactly one head
flask db current                # record the revision before changing it
flask db migrate -m "Add X to Y"
flask db upgrade
flask db history                # find the revision to go back to
flask db downgrade <revision>   # disposable DB only, if the migration permits it
flask db upgrade                # prove re-application after a supported downgrade
python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt
```

> [!WARNING]
>
> A bare `flask db downgrade` stops with `Ambiguous walk` when the current revision is a merge point, and rolls nothing back. Always name the target revision, then confirm it with `flask db current`.

Some revisions are forward-only. Consult the [forward-only revision register](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-004_Live_V2_Migration_And_Versioning_Contract.md) before a rollback; production recovery follows the release runbook, not this local rehearsal.

Every migration needs the idempotency helpers from `migrations/migration_template.py.mako` and has to pass the linter. `migrations/lint_baseline.txt` records older debt, can only shrink, and is never the place for a new migration. [SOP-DB-001](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications.md) is the governing specification.

---

## Releases and deployment

Application releases use **Release v2 to Production** ([`release-v2.yml`](.github/workflows/release-v2.yml)), dispatched with an exact 40-character SHA from the approved lineage. Follow [SOP-DEP-002](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md), including the maintenance window, stopped-application backup, restore verification, balance baseline and signed evidence before dispatch.

The [host-side release gate](infra/release-gate/README.md) requires the Cloudflare Access gate to be closed and fresh signed backup/restore evidence for the requested revision. After admission, the workflow installs dependencies, applies migrations, restarts the application and probes `/health` directly on Gunicorn. A passing health probe is not functional browser validation; the runbook defines the post-release checks and reopening decision.

The public/developer sites and status service have separate deployment workflows. An application release does not deploy the status service.

For local health checks and scheduled-job development:

```bash
curl http://localhost:5000/health          # 200 "ok" if the database answers SELECT 1
curl http://localhost:5000/health/status   # bounded status signals; no tenant data
gunicorn wsgi:app --bind 127.0.0.1:8000    # enables scheduler ownership locally
```

Release history belongs in [CHANGELOG.md](CHANGELOG.md), [GitHub releases](https://github.com/timwonderer/classroom-token-hub/releases) and the dated [deployment records](docs/ops/audits/). Six early untagged deployments still lack records; that documentation gap is tracked in [#1650](https://github.com/timwonderer/classroom-token-hub/issues/1650).

### Known limits of the release evidence

Evidence that was run is not the same as coverage that was inferred (INV-ARC-017). This page does not keep a snapshot of what production has and hasn't exercised, because a snapshot goes stale with the next release. The **current release record** (linked at the top of this page) carries it: what that release verified, its browser validation under [SOP-DEP-001B](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-001B_Release_Functional_Browser_Validation.md), and its known gaps and follow-ups.

---

## Documentation

When two documents disagree, the one higher in this order wins, and the lower one gets corrected:

```text
INV-CORE → INV-ARC → DOM-* → FEAT-*
```

**Normative (these govern):**

| Document | Purpose |
| ---------- | --------- |
| [docs/INVARIANT/](docs/INVARIANT/) | Core runtime invariants and architectural rules |
| [docs/DOMAIN/](docs/DOMAIN/) | Per-domain authority specs |
| [docs/FEATURE-EXECUTION/](docs/FEATURE-EXECUTION/) | FEAT mutation contracts |
| [docs/SPEC/](docs/SPEC/) | Technical contracts, binding on runtime implementation when incorporated by INV/DOM/FEAT authority |
| [REF-TERM-001](docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md) | Developer vocabulary |
| [docs/STANDARD_OPERATING_PROCEDURES/](docs/STANDARD_OPERATING_PROCEDURES/) | Operational procedures |

**Descriptive (these summarize and can drift):**

| Document | Purpose |
| ---------- | --------- |
| [docs/TRACKING/](docs/TRACKING/) | Working plans and decision packages; the post-launch tracker is archived |
| [docs/ops/](docs/ops/) | Production host notes and dated release and audit records |
| [docs/PRINCIPLES/](docs/PRINCIPLES/) | Why a design was chosen |
| [docs/REFERENCE/](docs/REFERENCE/) | Interface references, including [REF-API-001](docs/REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE.md) for HTTP endpoints, and the user-facing vocabulary [REF-TERM-002](docs/REFERENCE/REF-TERM-002_USER_VOCABULARY.md) (recommended, subject to accessibility) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Roadmap and current priorities |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [AGENTS.md](AGENTS.md), `.Codex/` and `.claude/` | Working guidance for AI coding agents |

Agent guidance and memory help agents navigate the codebase; they are not normative authority and must not justify a design decision. Cite the INV, DOM, FEAT, SPEC or SOP document instead.

The user guides in `docs/user-guides/` are served inside the app at `/docs`. The developer docs site at [classroomtokenhub.com/docs](https://classroomtokenhub.com/docs/), built with Hugo from `docs-generator-proof/`, publishes the normative tree plus principles, references, maps and the self-hosting guide. It leaves out the user guides, dated release and audit records (`docs/ops/`), working-state tracking files (except the two durable roadmap/template files allowlisted by the builder), and [docs/archive/](docs/archive/), which holds superseded material kept for history.

---

## Version history

| Line | Status | Where it lives |
| --- | --- | --- |
| **v2** | Current. v2.0.0 released 2026-09-26; later releases are on the [releases page](https://github.com/timwonderer/classroom-token-hub/releases) and in [docs/ops/audits/](docs/ops/audits/) | `main` |
| **v1** | Retired. v1.10.0 (2026-06-14) was the final v1 release | Branch `main_legacy_v1.10.0` and the `v1.*` tags |

v2 is a ground-up rebuild with no v1 account or data carryover. For upgrades within v2, review the intervening CHANGELOG entries, migration requirements and release runbook; old patch releases are not the current deployment target.

---

## Contributing

Read the invariants first, then the domain spec for the area you're changing, then the FEAT contracts that execute it. [CONTRIBUTING.md](CONTRIBUTING.md) has the details, and pull requests use [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)

**Allowed:** classrooms, clubs, nonprofits, research and personal learning.
**Not allowed:** commercial products, SaaS, paid services and other for-profit use.

See [LICENSE](LICENSE) for the full terms and the [third-party notices](docs/user-guides/legal/third-party-notices.md).

---

## Support

- **Is the service down?** Check [status.classroomtokenhub.com](https://status.classroomtokenhub.com)
- **Found a bug?** Open an issue. For a security problem, follow [SECURITY.md](SECURITY.md) instead
- **Questions about the architecture?** Start with the relevant [domain spec](docs/DOMAIN/), then the [invariants](docs/INVARIANT/) it answers to
- **Contact:** [dev@classroomtokenhub.com](mailto:dev@classroomtokenhub.com)

This project is developed, deployed, maintained, operated and tested by one full-time high school teacher, who lives by the motto *"fine, I'll build one myself."*

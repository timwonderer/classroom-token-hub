![Classroom Token Hub banner](github-pages/assets/CTH_horizontal_header_logo.png)

# Classroom Token Hub (CTH)

A classroom behavior management and reward platform with built-in simulated financial products and economic engines (and an absurd amount of documentation, pytests, and opinions.) 

Students earn tokens for the time they work, and spend them on rent, insurance and a class store. Teachers run the class economy without handing over student email addresses, phone numbers or school SSO. Built with Flask, SQLAlchemy and PostgreSQL. Each class period is its own isolated economy.

**Current release:** [v2.0.1](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.0.1), a security release in production since 2026-09-28 (v2 launched 2026-09-26) · **Branch:** `main` · **License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)

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

- **Sign up without PII**: three steps. Name the class, pick a username and scan a TOTP code, then confirm the code. No email or phone number is asked for
- **Roster management**: upload a roster or add students one at a time, then export it. Each unclaimed seat has a claim code. An unclaimed seat keeps its balance but takes no part in the economy until a student claims it
- **Payroll**: set per-minute pay rates, pay frequency, daily time caps, and overtime thresholds and multipliers. Payroll runs on a schedule by local calendar day. Each run pays the work sessions that ended since the last run, in full; a session still open is paid by the next run. Manual payments, reversals and history are also available
- **Classroom store**: sell immediate-use, delayed-use and collective-goal items. Each item declares its economic role. Bundles, bulk discounts, holding limits, start and delist dates, and redemption approval are supported
- **Rent**: recurring bill cycles with grace periods, one-time or recurring late penalties, and waivers. The teacher can allow partial payment and choose store perks that come with rent
- **Insurance**: tiered policies, a waiting period, and claims that students file and teachers review and pay out. Students see their own claims, and cancelling a policy stops it from renewing at the next cycle boundary
- **Banking**: savings interest paid monthly on posted balances. Overdraft fees apply only to failed purchases and failed obligations, never to transfers
- **Economic engine**: pricing guidance derived from the Classroom Wage Index (CWI) and the class's economic policy mode, with a rebalance the teacher reviews before it takes effect
- **Hall passes**: requests, approval, check-out and check-in, and a verification page with a rotating token
- **Interpretation**: a read-only report on each completed cycle, built from immutable history. It describes what happened; it doesn't raise alerts or recommend actions
- **Issues**: resolve or escalate student reports about a transaction, an attendance session, or anything else
- **Announcements**: class-scoped, with an expiry date, shown on the student dashboard
- **Feature settings**: turn store, rent, insurance and other features on or off per class

### For students

- **Portal**: balances, transactions, attendance (start and stop work), store, rent, payroll and insurance
- **Account transfers**: move money between checking and savings, confirmed with a PIN
- **Seat claim**: claim the seat your teacher set up by matching your name against the roster, then create a username, PIN and passphrase. Before the account is created, you type your new username back from where you saved it, because CTH keeps no readable copy. Join more classes with a join code
- **Account recovery**: a teacher issues a short-lived reset code, and the student redeems it to set a new username, PIN and passphrase, with the same username check as a first claim
- **Hall pass requests**: ask for a pass and follow its status on the dashboard
- **Report an issue**: about a specific transaction, an attendance session, or a general problem

### For system admins

- **Portal**: counts of teachers, students and open issues, plus escalated issues and user reports
- **Logs and monitoring**: combined application and error logs and a Grafana proxy
- **Accounts**: sysadmins are created from the CLI (`flask create-sysadmin`) and manage their own passkeys

### Teacher account recovery

No email is involved. A teacher who loses access starts recovery by entering the usernames of students in their classes:

- one class: 6 usernames
- two classes: 3 per class
- three classes: 2 per class
- four or more classes: 1 per class

A class with fewer students than that counts if every claimed student is entered. The system then picks students at random in each class to confirm the request from their own accounts, and each confirming student gets a code to hand back. With all the codes, the teacher resets their credentials. Recovery needs at least 3 claimed students in each class, so that the random pick can't be predicted. See DOM-IDEN-003 §IX and FEAT-IDEN-103.

### Platform

- **Multi-tenant**: every read and write of seat or class data is scoped by `class_id`. One user can hold seats in several classes, and each class is its own economy
- **Ledger**: every money movement is written as `PENDING` and becomes posted history only when the scheduled settlement job admits it. The database rejects any change to a posted row
- **Scheduled jobs**: APScheduler runs settlement, payroll, savings interest, rent reconciliation, insurance expiry, collective-goal expiry, rebalance activation, and nightly maintenance and audit checks. They run only in the gunicorn server process, and only in the one process holding a PostgreSQL advisory lock (`app/scheduler_ownership.py`). `flask run`, `flask` commands, migrations and scripts never run them; to exercise jobs locally, start `gunicorn wsgi:app`
- **Class time**: deadlines and "today" are calculated in each class's own timezone by one temporal resolver. The policy guardrails in CI reject `timedelta` arithmetic in services, FEATs and routes
- **Progressive web app**: installable on a phone, with an offline fallback
- **In-app help**: `/docs` serves the user guides in `docs/user-guides/`, with search and a choice of teacher or student view
- **Accessibility**: built to WCAG 2.1 AA. An automated axe-core check covers every page template the app renders, and pull requests that change templates run it on those files. This is automated coverage only; no independent accessibility audit has been done
- **Design system**: one set of design tokens with three role themes, governed by [SPEC-DES-001](docs/SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md) and checked against every template
- **Security**: PII encrypted at rest, TOTP two-factor sign-in, passkeys (WebAuthn via passwordless.dev) for teachers and sysadmins, CSRF protection on every form, scrypt password hashing, Cloudflare Turnstile, and rate limiting with Flask-Limiter. See [SECURITY.md](SECURITY.md) to report a vulnerability
- **Health signals**: `/health` for liveness, and `/health/status` for bounded status signals that expose no tenant data or raw exceptions
- **Access gating**: Cloudflare Access on the application hostname controls who can reach the app during maintenance. The application itself has no maintenance-mode flag or bypass (DOM-OPS-001)

---

## Privacy

> [!IMPORTANT]
>
> CTH collects as little PII as it can: no email, no phone number, no SSO, no physical location. Student names are encrypted at rest. Usernames are stored only as keyed digests, never as plaintext. If the database leaks, it can't be linked to real people without information held somewhere else.
>
> CTH doesn't support native SSO. A district that needs SSO can fork the project and add its own auth layer; see [PRN-SNP-001](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md) for why.

---

## Architecture

```text
Route ──▶ FEAT (app/feats/) ──▶ Domain services (app/services/) ──▶ commit
```

1. **Identity**: `User` is the global sign-in account. `Seat` is that user's place in one class, and every activity record keys off `seat_id`. `IdentityProfile` holds display names. `ClassEconomy` is the tenant boundary, identified by `class_id`, with `join_code` as its public alias. INV-ARC-019 and DOM-IDEN-001 govern this model
2. **Domains**: ten bounded domains, each with an authority spec under [docs/DOMAIN/](docs/DOMAIN/). They are Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations, Store & Entitlements, Operations, Interpretation, Policies and Support, and they share one Core foundation
3. **FEAT layer**: every state change goes through a Feature Execution Transaction in `app/feats/`. Routes never call `db.session.commit()` on domain models, and GET handlers never write to the database (INV-ARC-007)

| Component | Where | What it does |
| --- | --- | --- |
| Flask application | `app/`, `templates/`, `static/`, `wsgi.py` | Teacher, student and sysadmin surfaces; served by gunicorn behind nginx |
| Status service | `status_service/`, `status/` | Public status page and an IAP-protected operator console; deployed by `deploy-status.yml` |
| Developer docs site | `docs-site/` | Docusaurus build of the documentation tree |
| Public site | `github-pages/` | Marketing pages and the public timeline, published by `github-pages.yml` |

The application doesn't serve the marketing site, and the marketing site doesn't serve the application.

---

## Quick start

### Prerequisites

- Python 3.10 or later (`runtime.txt` pins 3.10; CI runs 3.10, 3.11 and 3.13)
- PostgreSQL 15 or 16 (the versions CI runs against)
- Redis 7 or later (`redis-server`) for student account setup. Tests that need it start their own private instance; in production it is a dedicated, non-persistent service ([infra/student-setup/README.md](infra/student-setup/README.md))
- A virtual environment

### Setup

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
ENCRYPTION_KEY=$(openssl rand -base64 32)
PEPPER_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
AUDIT_HMAC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FLASK_ENV=development
EOF

flask db upgrade
flask create-sysadmin   # follow the prompts and scan the QR code with an authenticator
flask run               # http://localhost:5000
```

The app won't start without the six keys above. Everything else is optional, except that student account setup also needs `STUDENT_SETUP_REDIS_URL`:

| Variable | Purpose |
| -------- | ------- |
| `TEST_DATABASE_URL` | PostgreSQL database that the test suite rebuilds |
| `CSRF_SECRET_KEY` | A separate CSRF signing key (defaults to `SECRET_KEY`) |
| `SECRET_KEY_FALLBACKS` | Previous secret keys, so a rotation doesn't sign everyone out |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile; verification is skipped when these are unset |
| `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`, `PASSWORDLESS_API_URL` | Passkey sign-in |
| `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `DEV_ENABLE_RATELIMIT` | Rate-limit storage; rate limits are off in development unless `DEV_ENABLE_RATELIMIT=1` |
| `STUDENT_SETUP_REDIS_URL` | Dedicated, non-persistent Redis for student account setup ([infra/student-setup/README.md](infra/student-setup/README.md)). Required: student claim and recovery setup refuse to run without it. Never point it at the rate-limit store |
| `EXTERNAL_DOCS_BASE_URL`, `MARKETING_SITE_URL`, `STATUS_PAGE_URL`, `GRAFANA_URL`, `SUPPORT_EMAIL` | External links |
| `LOG_LEVEL`, `LOG_FILE` | Logging |

Don't rotate `ENCRYPTION_KEY` or `PEPPER_KEY` casually. `ENCRYPTION_KEY` protects PII and TOTP secrets and needs a re-encryption to change. `PEPPER_KEY` keys the username digests, so changing it resets identities. To run your own instance, start with [docs/self-hosting/](docs/self-hosting/README.md).

### Running tests

Tests run against a real PostgreSQL database named by `TEST_DATABASE_URL`; there's no SQLite path. `conftest.py` drops the schema and rebuilds it through the real migration chain, so triggers and constraints are live in every test.

```bash
pytest tests/dom/obligations/ -v          # one domain
pytest tests/test_status_contracts.py -v  # one file
pytest -k recovery                        # by pattern
pytest                                    # full suite: 3,900+ tests, over an hour
pytest --cov=app tests/                   # with coverage
```

Tests provision a whole classroom through `tests/helpers/classroom_initializer.py` rather than creating rows by hand (SPEC-TEST-001).

Templates are held to the design-token contract. While editing one, check just that file:

```bash
python scripts/lint_design_tokens.py templates/your_page.html
```

### Database migrations

```bash
flask db heads                  # must show exactly one head
flask db migrate -m "Add X to Y"
flask db upgrade
flask db history                # find the revision to go back to
flask db downgrade <revision>   # always pass an explicit revision
python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt
```

> [!WARNING]
>
> A bare `flask db downgrade` stops with `Ambiguous walk` when the current revision is a merge point, and rolls nothing back. Always name the target revision, then confirm it with `flask db current`.

Every migration needs the idempotency helpers from `migrations/migration_template.py.mako` and has to pass the linter. `migrations/lint_baseline.txt` records older debt, can only shrink, and is never the place for a new migration. [SOP-DB-001](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications.md) is the governing specification.

---

## Releases and deployment

Production is released by the **Release v2 to Production** workflow ([`release-v2.yml`](.github/workflows/release-v2.yml)), which is started by hand with an exact 40-character commit SHA. The workflow:

1. refuses any SHA that isn't an ancestor of the approved lineage (`main`)
2. connects to the production host over Tailscale and checks out that SHA exactly
3. installs the pinned requirements, runs `flask db upgrade`, and restarts the service
4. probes `/health` on gunicorn (`127.0.0.1:8000`) until it answers `ok`

```bash
curl http://localhost:5000/health          # 200 "ok" if the database answers SELECT 1
curl http://localhost:5000/health/status   # bounded status signals; no tenant data
gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000
```

Tags mark the exact commit production is running: `v2.0.0` is `26d1792b5` (released 2026-09-26) and `v2.0.1` is `ad64a473f` (released 2026-09-28). The full procedure is [SOP-DEP-002](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md), and each release is recorded under [docs/ops/audits/](docs/ops/audits/):

- v2.0.0: [TRANSITION_2026-09-26_26d1792b5.md](docs/ops/audits/TRANSITION_2026-09-26_26d1792b5.md)
- v2.0.1: [DEPLOY_2026-09-28_ad64a473f.md](docs/ops/audits/DEPLOY_2026-09-28_ad64a473f.md), which also covers the unrecorded `efdf09eda` release of 2026-09-27

`main` is ahead of v2.0.1 with unreleased changes, listed under **Unreleased** in [CHANGELOG.md](CHANGELOG.md): the payroll fix for the 2026-09-28 incident (#1439), a one-time payroll correction for teachers to review (#1440), and the username retention check (#1442, #1443). The retention check needs the student-setup Redis service on the production host before it is released ([SOP-DEP-002](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md) §VI, item 6).

### Known limits of the release evidence

Evidence that was actually run isn't the same as coverage that was inferred (INV-ARC-017). As of v2.0.1, production has verified:

- the migrations to `f4b8d2a6c1e9` (`users.id` as UUID) and the integrity of every reference to `users`
- a single scheduler owner (the gunicorn process), with none started by migrations
- teacher passkey registration and sign-in end to end, run by the operator after release

These surfaces haven't been exercised yet:

- **Other signed-in flows on the production host**: covered by the automated suite and by live test rounds on the same host before launch, but not repeated since the launch wipe. They'll first run in production when teachers start using it
- **Public routes after v2.0.1**: not checked at release, because the Cloudflare Access maintenance window was still in place
- **Daylight-saving and midnight transitions**: class-timezone handling is tested, but no live daylight-saving change has happened since launch
- **Load**: concurrent settlement, payroll batch runs and scheduled jobs haven't been tested under load
- **Browser accessibility**: axe covers every rendered template, but keyboard, focus and contrast behavior across the whole app still needs a person using a real browser. The signed-in insurance page's buy and cancel dialogs haven't had an axe audit yet

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
| [docs/SPEC/](docs/SPEC/) | Technical contracts |
| [REF-TERM-001](docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md) | Developer vocabulary |
| [docs/STANDARD_OPERATING_PROCEDURES/](docs/STANDARD_OPERATING_PROCEDURES/) | Operational procedures |

**Descriptive (these summarize and can drift):**

| Document | Purpose |
| ---------- | --------- |
| [docs/TRACKING/](docs/TRACKING/) | Working state: the post-launch tracker and open decisions |
| [docs/ops/](docs/ops/) | Production host notes and dated release and audit records |
| [docs/PRINCIPLES/](docs/PRINCIPLES/) | Why a design was chosen |
| [docs/REFERENCE/](docs/REFERENCE/) | Interface references, including [REF-API-001](docs/REFERENCE/REF-API-001_HTTP_INTERFACE_REFERENCE.md) for HTTP endpoints, and the user-facing vocabulary [REF-TERM-002](docs/REFERENCE/REF-TERM-002_USER_VOCABULARY.md) (recommended, subject to accessibility) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Roadmap and current priorities |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [.claude/CLAUDE.md](.claude/CLAUDE.md) and [.claude/rules/](.claude/rules/) | Working guidance for AI coding agents |

Nothing under `.claude/` is authoritative. It helps agents find their way around the codebase, and it should never be cited to justify a design decision. Cite the INV, DOM, FEAT, SPEC or SOP document instead.

The user guides in `docs/user-guides/` are served inside the app at `/docs`. The developer docs site at [classroomtokenhub.com/docs](https://classroomtokenhub.com/docs/), built from `docs-site/`, publishes the normative tree plus principles, references, maps and the self-hosting guide. It leaves out the user guides, dated release and audit records (`docs/ops/`), working-state tracking files, and [docs/archive/](docs/archive/), which holds superseded material kept for history.

---

## Version history

| Line | Status | Where it lives |
| --- | --- | --- |
| **v2** | Current. v2.0.0 released 2026-09-26; v2.0.1 (security) released 2026-09-28 | `main` |
| **v1** | Retired. v1.10.0 (2026-06-14) was the final v1 release | Branch `main_legacy_v1.10.0` and the `v1.*` tags |

v2 is a ground-up rebuild. It's a clean break: no v1 accounts or data carry over. See the [v2.0.0](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.0.0) and [v2.0.1](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.0.1) release notes. Upgrading every 2.0.0 deployment to 2.0.1 is recommended: it ties each passkey to the account it was registered to.

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

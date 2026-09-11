# Classroom Token Hub (CTH)

A classroom management platform that uses a simulated token economy to drive student engagement and participation. Built with Flask + SQLAlchemy + PostgreSQL, designed for multi-tenant deployment across multiple schools and class periods.

**Version:** v2.0 (pre-launch; unreleased changes are tracked under `[Unreleased]` in the [changelog](CHANGELOG.md)) — **Branch:** `main`
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

> [!NOTE]
>
> `main` is the v2 deployment branch; the v1 line lives on `main_legacy_v1.10.0`. The public GitHub Pages artifact currently serves a `launching soon` holding page, and the v2 landing pages are kept on the separate `launch/v2-landing-pages` branch until launch. The application and the static marketing site are separate hosts, and the application is not exposed through a Flask `/gh/` mirror.

---

## Features

### For Teachers

- **Sign Up Without PII** — Three steps: name the class, choose a username and scan a TOTP code, confirm the code. No email or phone
- **Roster Management** — Upload or add students individually; export the roster
- **Payroll** — Per-minute pay rates, pay frequency, daily time caps, overtime thresholds and multipliers. Payroll runs automatically on schedule, with manual payments, voids and history
- **Classroom Store** — Immediate, delayed-use and collective items; bundles, bulk discounts, auto-expiry; redemption approval
- **Rent** — Recurring bill cycles with grace periods, one-time or recurring late penalties, and waivers
- **Insurance** — Create policies with tiers, review and resolve student claims
- **Banking** — Savings interest paid monthly on posted balances; overdraft fees on failed purchases and obligations
- **Economic Engine** — Derives pricing guidance from the Classroom Wage Index (CWI) and the class's economic policy mode, with a reviewable rebalance
- **Hall Passes** — Requests, approval, check-out/check-in, and a rotating verification page
- **Interpretation** — Read-only report of each completed cycle, built from immutable history. It observes; it does not alert or prescribe
- **Issues** — Resolve or escalate student-reported issues about a transaction, an attendance session, or anything else
- **Announcements** — Class-scoped, with expiry, shown on the student dashboard
- **Feature Settings** — Turn store, rent, insurance and other features on per class

### For Students

- **Portal** — Balances, transactions, attendance (start/stop work), store, rent, payroll, insurance
- **Account Transfers** — Move funds between checking and savings
- **Seat Claim** — Claim a seat the teacher provisioned by matching your name against the class roster, then create a username, PIN and passphrase. Join further classes with a join code
- **Account Recovery** — A teacher issues a short-lived reset code; the student redeems it to set new credentials
- **Hall Pass Requests** — Request a pass and follow its status on the dashboard
- **Report an Issue** — About a specific transaction, an attendance session, or a general problem

### For System Admins

- **Portal** — Teacher, student and open-issue counts, escalated issues, user reports
- **Logs and Monitoring** — Combined, error and application logs; network activity; Grafana proxy
- **Accounts** — Sysadmins are created from the CLI (`flask create-sysadmin`) and manage their own passkeys

### Teacher Account Recovery

A teacher who loses access submits a join code and one student username for each class they teach. Those students each confirm the request from their own account and receive a code to hand back; with all codes, the teacher resets their credentials. No email is involved at any step.

### Platform

- **Multi-Tenant** — Every query is scoped by `class_id`. One user can hold seats in several classes, and each class is its own isolated economy
- **Ledger** — Every effect is written `PENDING` and admitted to posted history only by the scheduled settlement job; posted rows are immutable in the database
- **Scheduled Jobs** — APScheduler runs settlement, payroll, savings interest, rent reconciliation, insurance expiry, collective-goal expiry, rebalance activation, and nightly maintenance and audit checks
- **Progressive Web App** — Installable on mobile; offline fallback included
- **In-App Documentation** — `/docs` renders the user guides in `docs/user-guides/`, with search and audience selection
- **Accessibility** — Built against WCAG 2.1 AA: keyboard navigation, ARIA state on disclosure controls, screen-reader labelling. Pull requests that change templates run an accessibility check on the changed files; full-corpus conformance has not been independently certified
- **Design System** — One token layer with three role themes, governed by [SPEC-DES-001](docs/SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md) and checked over every template
- **Security** — PII encryption at rest, TOTP 2FA, passkeys (WebAuthn via passwordless.dev) for teachers and sysadmins, CSRF protection, scrypt password hashing, Cloudflare Turnstile
- **Health Signals** — `/health` for liveness and bounded `/health/status` signals that expose no tenant data or raw exceptions
- **Rate Limiting** — Flask-Limiter with Cloudflare IP detection; off in development unless `DEV_ENABLE_RATELIMIT=1`
- **Maintenance Mode** — Environment-driven maintenance page with a sysadmin bypass

> [!IMPORTANT]
>
> **Privacy First Design:** CTH minimizes PII collection (no email, phone, SSO). We do not ask for identities or physical locations. This reduces breach impact: data is meaningless without external reference.
>
> We do not support native SSO. If your district wants to self-host with SSO integration, fork this project and implement your own auth layer. We provide technical support for architecture; you retain full operational control.
>
> See [PRN-SNP-001](docs/PRINCIPLES/SECURITY_AND_PRIVACY/PRN-SNP-001_Why_Classroom_Token_Hub_Does_Not_Implement_SSO.md) for rationale.

---

## Quick Start

### Prerequisites

- Python 3.10+ (`runtime.txt` pins 3.10; CI jobs run 3.10, 3.11 and 3.13)
- PostgreSQL 15 or 16 (the versions CI runs against)
- Virtual environment (recommended)

Tests run against a real PostgreSQL database named by `TEST_DATABASE_URL`. There is no SQLite path.

### Setup

```bash
# Clone and create venv
git clone <repo-url>
cd classroom-economy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
# Note: the heredoc delimiter is deliberately unquoted so the $(...) calls are
# evaluated. With 'EOF' quoted, the file receives the literal command text as
# each key's value and the app starts with unusable secrets.
cat > .env << EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://user:password@localhost:5432/classroom_economy
ENCRYPTION_KEY=$(openssl rand -base64 32)
PEPPER_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
AUDIT_HMAC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FLASK_ENV=development
EOF

# Initialize database
flask db upgrade
flask create-sysadmin  # Follow prompts; scan QR with authenticator

# Run
flask run  # Navigate to http://localhost:5000
```

The app refuses to start without the six keys above. Everything else is optional:

| Variable | Purpose |
| -------- | ------- |
| `TEST_DATABASE_URL` | PostgreSQL database the test suite rebuilds |
| `CSRF_SECRET_KEY` | Separate CSRF signing key (defaults to `SECRET_KEY`) |
| `SECRET_KEY_FALLBACKS` | Previous secret keys, for rotation without logging everyone out |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile; verification is skipped when unset |
| `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`, `PASSWORDLESS_API_URL` | Passkey sign-in |
| `REDIS_URL`, `RATELIMIT_STORAGE_URI`, `DEV_ENABLE_RATELIMIT` | Rate-limit storage; enable limits in development |
| `MAINTENANCE_MODE`, `MAINTENANCE_BYPASS_TOKEN`, `MAINTENANCE_SYSADMIN_BYPASS`, `MAINTENANCE_EXPECTED_END`, `MAINTENANCE_CONTACT`, `MAINTENANCE_BADGE_TYPE` | Maintenance mode |
| `EXTERNAL_DOCS_BASE_URL`, `MARKETING_SITE_URL`, `STATUS_PAGE_URL`, `GRAFANA_URL`, `SUPPORT_EMAIL` | External links |
| `LOG_LEVEL`, `LOG_FILE` | Logging |

### Running Tests

```bash
# Targeted tests (preferred during development)
pytest tests/dom/operation/test_health.py -v
pytest tests/test_status_contracts.py tests/test_status_projection.py -v

# Specific domain
pytest tests/dom/obligations/ -v

# Full suite (requires TEST_DATABASE_URL). Takes over an hour: conftest.py drops
# and rebuilds the schema by running the real migration chain, so triggers and
# constraints are live in every test.
TEST_DATABASE_URL=postgresql://... pytest

# With coverage
pytest --cov=app tests/
```

Templates are held to the design-token contract by `tests/test_design_token_contract.py`. While editing a template, run the checker on just that file:

```bash
python scripts/lint_design_tokens.py templates/your_page.html
```

### Database Migrations

```bash
flask db heads                  # Must show exactly 1 head
flask db migrate -m "Description"
flask db upgrade                # Apply
flask db history                # Find the revision to return to
flask db downgrade <revision>   # Roll back to that revision
```

> [!WARNING]
>
> Always pass an explicit revision to `flask db downgrade`. The bare form walks back one step from wherever the database is, and if that revision is a merge point it cannot choose between parents and aborts with `ERROR [flask_migrate] Error: Ambiguous walk`, rolling nothing back. Read the target off `flask db history` first and confirm with `flask db current` afterward.

All migrations must include idempotency helpers and pass the linter before commit:

```bash
python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt
```

`migrations/lint_baseline.txt` freezes pre-gate debt and only ever shrinks — a new migration does not belong in it. The normative specification is [SOP-DB-011](docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-011_Migration_Specifications.md); [.claude/rules/database-migrations.md](.claude/rules/database-migrations.md) is a non-authoritative working summary of it.

---

## v2 Launch Readiness

The v2 runtime is governed by the documented authority chain rather than by route-local behavior:

```text
INV-CORE → INV-ARC → DOM-* → FEAT-*
```

The repository includes the v2 bounded domains, canonical FEAT mutation boundaries, class-scoped tenancy, canonical Ledger persistence and monetary resolution, Interpretation reporting, constitutional CI evidence selection, and production documentation/link checks. These are implementation and evidence updates, not a declaration that every launch gate is green. In particular, authenticated rendered journeys and any evidence marked `NOT_EVALUATED`, `BLOCKED`, or otherwise unresolved in the tracking documents remain launch work.

Known unproven surfaces, stated plainly rather than left to inference: daylight-saving and midnight-boundary transitions have not been exercised live; full-corpus template accessibility, keyboard, focus and contrast behavior needs a real browser; concurrent settlement, payroll batch runs and scheduled jobs have not been tested under load; and the production host itself has only been rehearsed against a local PostgreSQL cluster. Executed evidence is not the same as inferred coverage (`INV-ARC-017`).

Before launch, use the [v2 production transition runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md), the [production readiness tracker](docs/TRACKING/PRODUCTION_READINESS_2026-09.md), and the [changelog](CHANGELOG.md) as the current source for release evidence. Do not infer application availability from the GitHub Pages holding page: verify application maintenance mode, login routes, deployment health, and the exact release SHA independently.

---

## Architecture

CTH v2 uses a three-layer architecture with strict domain boundaries:

1. **Identity Layer** — `User` (auth principal) → `Seat` (class-local actor) → `ClassEconomy` (tenant boundary via `class_id`)
2. **Domain Services** — Ten bounded domains, each with an authority spec under [docs/DOMAIN/](docs/DOMAIN/): Identity, Class Configuration, Ledger, Productivity & Payroll, Obligations, Store & Entitlements, Operations, Interpretation, Policies, and Support. They sit on a shared Core foundation
3. **FEAT Layer** — All state mutations go through Feature Execution Transactions; no direct `db.session.commit` in routes

All queries must be scoped by `class_id`, never by `teacher_id` alone.

---

## Documentation

Documentation is ordered by authority, and the order is load-bearing. When two documents disagree, the higher one wins and the lower one is what gets corrected.

**Normative — these govern:**

| Document | Purpose |
| ---------- | --------- |
| **[docs/INVARIANT/](docs/INVARIANT/)** | Core runtime invariants and architectural rules |
| **[docs/DOMAIN/](docs/DOMAIN/)** | Per-domain authority specs |
| **[docs/FEATURE-EXECUTION/](docs/FEATURE-EXECUTION/)** | FEAT mutation contracts |
| **[docs/SPEC/](docs/SPEC/)** | Technical contracts |
| **[docs/STANDARD_OPERATING_PROCEDURES/](docs/STANDARD_OPERATING_PROCEDURES/)** | Operational procedures |

**Descriptive — these summarize, and may drift:**

| Document | Purpose |
| ---------- | --------- |
| **[docs/TRACKING/](docs/TRACKING/)** | Release readiness and audit status |
| **[docs/PRINCIPLES/](docs/PRINCIPLES/)** | Why a given design was chosen |
| **[DEVELOPMENT.md](DEVELOPMENT.md)** | Roadmap and current priorities |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history |
| **[.claude/CLAUDE.md](.claude/CLAUDE.md)** and **[.claude/rules/](.claude/rules/)** | Working guidance for AI coding agents |

Nothing under `.claude/` is authoritative. It is orientation for agents, not a specification, and it must never be cited to justify a design decision — cite the INV/DOM/FEAT/SPEC/SOP document instead.

User guides live in `docs/user-guides/` and are served in the app at `/docs`. `docs-site/` is a separately published Docusaurus site, which the app can link to through `EXTERNAL_DOCS_BASE_URL`.

---

## Deployment

```bash
# Liveness — 200 "ok" if the database answers SELECT 1; 500 with a JSON error otherwise
curl http://localhost:5000/health

# Bounded status signals for public publication. Every capability reports
# UNKNOWN until a lawful read-only probe is registered for it, so the endpoint
# cannot imply health it has not observed. It exposes no tenant data, table
# counts, or raw exceptions.
curl http://localhost:5000/health/status

# Application production
gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000
```

See [SOP-DEP-023](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-023_V2_Production_Transition_Runbook.md) for the full runbook.

The static public site is published separately from `github-pages/`. Until launch, `github-pages/index.html` is the holding page; the launch branch supplies the public landing pages. The application does not serve the marketing site as a Flask route.

---

## Contributing

Read the invariants first, then domain specs, then tracking docs. Authority flows downward:

```text
INV-CORE (what must be true) → INV-ARC (architectural rules) → DOM-* (domain authority) → FEAT-* (execution specs)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

**Permitted:** Classrooms, clubs, nonprofits, research, personal learning.  
**Prohibited:** Commercial products, SaaS, paid services, for-profit use.

See [LICENSE](LICENSE) for complete terms. [Third-party notices](docs/user-guides/legal/third-party-notices.md).

---

## Support

- **Questions about architecture?** Read the relevant [domain spec](docs/DOMAIN/), then the [invariants](docs/INVARIANT/) it answers to
- **Found a bug?** Open an issue
- **Ready to contribute?** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Contact:** [dev@classroomtokenhub.com](mailto:dev@classroomtokenhub.com)

This project is developed, deployed, maintained, operated, and tested by a single full-time high school teacher who lives by the motto of *"fine, I'll build one myself."*

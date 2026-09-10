# Classroom Token Hub (CTH)

A classroom management platform that uses a simulated token economy to drive student engagement and participation. Built with Flask + SQLAlchemy + PostgreSQL, designed for multi-tenant deployment across multiple schools and class periods.

**Version:** 2.0 (Pre-Launch Live Server Test) — **Branch:** `main`
**License:** [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)

> [!NOTE]
>
> This branch is the v2 deployment branch. The public GitHub Pages artifact currently uses a `launching soon` holding page; the v2 landing pages are kept on the separate `launch/v2-landing-pages` branch until launch. The application and the static marketing site are separate hosts, and the application is not exposed through a Flask `/gh/` mirror.

---

## Features

### For Teachers

- **Two-Step Sign Up** — Username + authenticator (no PII required)
- **Admin Dashboard** — Class overview, pending actions, analytics
- **Roster Management** — Provision seats; students self-claim with credentials
- **Automated Payroll** — Configure hourly rates, pay schedule, overtime thresholds
- **Classroom Store** — Create items, bundles, expiration policies; track redemptions
- **Rent System** — Recurring payments with grace periods, waivers, late fees
- **Hall Passes** — Track when students leave/return; automatic status updates
- **Analytics** — Participation rate, money velocity, budget survivability trends
- **Support Tickets** — Student-submitted issues with admin resolution tracking

### For Students

- **Portal** — View balances, transaction history, store, attendance
- **Account Transfers** — Move funds between checking and savings
- **Seat Claim** — Self-provision using teacher-issued claim credentials
- **Account Recovery** — Restore access via teacher-verified process
- **Hall Pass Requests** — Request approval; see status in real-time

### For System Admins

- **Admin Portal** — Teacher overview, support tickets, system events, announcements
- **User Management** — Provision sysadmins, manage 2FA recovery

### Platform

- **Multi-Tenant** — Full class-period isolation; students share identity across teachers
- **Progressive Web App** — Installable on mobile; offline fallback included
- **Accessibility** — Built against WCAG 2.1 AA: keyboard navigation, ARIA state on disclosure controls, screen-reader labelling. Automated auditing runs per pull request on changed templates; full-corpus conformance has not been independently certified
- **Security** — PII encryption at rest, TOTP 2FA, CSRF protection, centralized scrypt password hashing, Cloudflare Turnstile, post-claim PII deletion
- **Observability and status** — OpenTelemetry instrumentation (Flask, SQLAlchemy) with OTLP export, plus bounded `/health/status` signals that do not expose tenant data or raw exceptions
- **Rate Limiting** — Flask-Limiter with Cloudflare IP detection; disabled in dev

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

- Python 3.10+ (CI runs 3.10 and 3.11)
- PostgreSQL 12+ (developed and tested against 16)
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
CSRF_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
AUDIT_HMAC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FLASK_ENV=development
EOF

# Initialize database
flask db upgrade
flask create-sysadmin  # Follow prompts; scan QR with authenticator

# Run
flask run  # Navigate to http://localhost:5000
```

### Running Tests

```bash
# Targeted tests (preferred during development)
pytest tests/dom/operation/test_health.py -v
pytest tests/test_status_contracts.py tests/test_status_projection.py -v

# Full suite (requires TEST_DATABASE_URL set; run separately for release certification)
# Takes roughly 80 minutes: conftest.py drops and rebuilds the schema by running
# the real migration chain, so triggers and constraints are live in every test.
TEST_DATABASE_URL=postgresql://... pytest

# Specific domain
pytest tests/dom/obligations/ -v

# With coverage
pytest --cov=app tests/
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
> Always pass an explicit revision to `flask db downgrade`. The bare form walks back from the current head, and because that head is a merge point with two parents it cannot choose between them — it aborts with `ERROR [flask_migrate] Error: Ambiguous walk` and rolls nothing back. Read the target off `flask db history` first and confirm with `flask db current` afterward.

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
2. **Domain Services** — 10 bounded domains (Identity, Class Config, Ledger, Payroll, Obligations, Store, Operations, Interpretation, Policies, Support) that own canonical tables and read queries
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

---

## Deployment

```bash
# Liveness — 200 "ok" if the database answers SELECT 1, 500 otherwise
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

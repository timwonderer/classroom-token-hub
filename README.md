# 🎓 Classroom Token Hub

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

**Release Track:** Active development — see [CHANGELOG.md](CHANGELOG.md) for current version

---

## Overview

**Classroom Token Hub** is an educational banking simulation that helps students learn financial literacy through hands-on experience. Students earn tokens by attending class, which they can spend in a classroom store, use for hall passes, or manage through savings and checking accounts.

**License:** [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) - Free for educational and nonprofit use, not for commercial applications.

**Project Status:** Actively maintained classroom-economy platform with ongoing security hardening, documentation cleanup, and feature work. For the current release history, see [CHANGELOG.md](CHANGELOG.md). For the canonical system and feature docs, start at [docs/README.md](docs/README.md).

---

## Design Principles

Classroom Token Hub is built around a small set of architectural principles that guide both feature development and operational decisions.

**Minimal Personal Data**  
The system intentionally stores as little personally identifiable information as possible. Student identities are encrypted at rest, verification data is purged after account setup, and the platform avoids unnecessary linkage to real‑world identity systems.

**Strong Classroom Isolation**  
Each classroom operates as its own isolated economic environment. Join codes act as the boundary for data access, ensuring that teachers and students only interact with records belonging to their own class context.

**Transparent Economic Systems**  
All financial activity is logged and auditable within the scope of a classroom. Students can see how balances change over time, reinforcing transparency and helping the platform function as a teaching tool rather than a black box.

**Operational Simplicity**  
The platform favors simple, reliable technologies and predictable infrastructure. This keeps the system understandable for educators, maintainable for developers, and resilient in real classroom environments where networks, devices, and usage patterns can be unpredictable.

---

## Features

### Core Features

- **System Admin Portal** — Manage teachers, review error logs, and adjust student ownership
- **Teacher Dashboard** — Manage students, run payroll, configure rent/insurance/banking settings
- **Analytics Dashboard** — System health metrics, CWI analysis, participation tracking, and trend monitoring
- **Student Portal** — View balances, redeem store items, track attendance, and manage hall passes
- **Join-Code Rosters** — Upload rosters and let students self-claim seats securely
- **Shared Students** — Link multiple teachers to the same student via `student_teachers`
- **Attendance Tracking** — Start Work/Break Done system with automatic time logging
- **Automated Payroll** — Configurable pay rates, schedules, and rewards/fines
- **Transaction Logging** — Complete audit trail of all financial activities scoped by teacher
- **Classroom Store** — Virtual/physical items with bundles, expirations, and redemption tracking
- **Rent Itemization** — Specify what rent covers with store alternatives and privilege tracking
- **Hall Pass System** — Time-limited passes with automatic tracking
- **Insurance System** — Policies, enrollments, and claims managed in-app
- **Rent & Fees** — Optional recurring rent with waivers and late-fee configuration
- **TOTP Authentication** — Secure admin access with two-factor authentication
- **Passkey Support** — Passwordless sign-in for admins and system admins via Passwordless.dev

### Performance

- **Optimized Student Roster** — N+1 query elimination reduces roster page queries from ~1225 to ~10 for a class of 60 students
- **Read-Only Balance Properties** — Removed write-on-read side effects from balance calculations, eliminating race conditions
- **Scoped Balance Calculations** — All balance aggregations correctly scoped to the current class period
- **Batch Processing** — Daily limit enforcement and dashboard balance calculations use batched queries instead of per-student iteration

### Mobile & PWA Features

- **Progressive Web App** — Install as mobile app on iOS and Android devices
- **Offline Support** — Intelligent caching with offline fallback page
- **Mobile-Optimized UI** — Responsive design with hamburger menu navigation
- **Full Navigation Access** — Slide-out sidebar provides complete menu access on mobile
- **Touch-Friendly** — Larger buttons and improved touch targets throughout
- **Unified Templates** — Same responsive layout works for desktop, mobile, and PWA
- **Fast Performance** — Aggressive caching for quick load times
- **Home Screen Installation** — Add to home screen for app-like experience

### Accessibility Features 

- **Enhanced Accessibility** — Improvements following WCAG 2.1 AA guidelines
- **Screen Reader Support** — Optimized for NVDA, JAWS, and VoiceOver
- **Keyboard Navigation** — Full keyboard accessibility throughout
- **ARIA Labels** — Comprehensive labeling for assistive technologies
- **High Contrast** — Improved color contrast ratios for better readability
- **Responsive Design** — Works seamlessly across all device sizes

> [!IMPORTANT]
> While the app is designed to be accessible and meet WCAG 2.1 guidelines, no claims of compliance of any kind is being made or implied. It is not recommended to deploy this app without external audits or validations if compliance is required by law.

### Security Features

- **PII Encryption** — All student names encrypted at rest
- **Post-Claim PII Deletion** — DOB and name verification hashes automatically purged after account setup completes
- **TOTP for Admins** — Time-based one-time passwords required
- **Teacher Account Recovery Model** — Teachers recover access through student-assisted recovery, or create a new account; inactive legacy accounts self-delete after 6 months
- **CSRF Protection** — Protection against cross-site request forgery
- **Credential Hashing** — Salted and peppered password hashing
- **Deletion Confirmation Gates** — Timed in-app confirmation dialogs for destructive operations (class/period deletion, account removal)
- **Hall Pass & Admin Identity Boundaries** — Hardened authorization checks prevent cross-admin data access in hall pass flows
- **Class Deletion Audit** — Audited and patched all deletion paths; fixed BalanceCache orphaning (P1), scoping bugs (P2), and orphaned settings cleanup (P3)
- **Cloudflare Turnstile** — Bot protection on login forms
- **Database Error Logging** — Automatic error tracking and monitoring
- **Custom Error Pages** — User-friendly error handling (400, 401, 403, 404, 500, 503)

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL database
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd classroom-economy
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in the root directory:
   ```bash
   SECRET_KEY=<long-random-string>
   DATABASE_URL=postgresql://user:password@host:port/dbname
   FLASK_ENV=development
   ENCRYPTION_KEY=<32-byte-base64-key>  # Generate with: openssl rand -base64 32
   PEPPER_KEY=<secret-pepper-string>
   CSRF_SECRET_KEY=<random-string>

   # Cloudflare Turnstile (CAPTCHA) - Optional for development/testing
   # Leave unset to bypass Turnstile verification in testing environments
   TURNSTILE_SITE_KEY=<your-turnstile-site-key>
   TURNSTILE_SECRET_KEY=<your-turnstile-secret-key>

   # Optional maintenance mode banner (503 page)
   MAINTENANCE_MODE=false
   MAINTENANCE_MESSAGE="We're applying updates."
   MAINTENANCE_EXPECTED_END="Back online by <time>"
   MAINTENANCE_CONTACT="ops@example.com"
   ```

   **Getting Turnstile Keys (Optional):**

   Turnstile keys are optional for development and testing. If not configured, CAPTCHA verification will be automatically bypassed.

   For production deployment:
   1. Visit [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile)
   2. Create a new site widget
   3. Copy the Site Key and Secret Key

   For testing with CAPTCHA enabled, you can use Turnstile's test keys (always pass):
   - Site Key: `1x00000000000000000000AA`
   - Secret Key: `1x0000000000000000000000000000000AA`

4. **Initialize the database**
   ```bash
   flask db upgrade
   ```

5. **Create your first system admin**
   ```bash
   flask create-sysadmin
   ```
   Follow the prompts and scan the QR code with your authenticator app.

6. **Run the application**
   ```bash
   flask run
   ```
   Navigate to `http://localhost:5000`

### Git Hooks Setup

After cloning, configure git to use the versioned `hooks/` directory:

```bash
./scripts/setup-hooks.sh
```

This enables the repo-managed hooks used by the local development workflow, including migration safety checks on push. See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow details.

### Testing with Sample Data

- Use `student_upload_template.csv` as a reference for CSV roster uploads
- Run `python scripts/seed_dummy_students.py` to seed the database with sample students
- For operational script details, see [docs/LOGS/AUDITS/LOG-DEP-022_Scripts_Operations_Reference.md](docs/LOGS/AUDITS/LOG-DEP-022_Scripts_Operations_Reference.md)

---

## Documentation

📚 **[Complete Documentation →](docs/README.md)**

### For Users

- **[Student Guide](docs/user-guides/student_guide.md)** for students using the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** for teacher facilitating the platform
- **[Sysadmin Manual](docs/user-guides/sysadmin_manual.md)** for local maintainer

### For Developers

- **[Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** for complete explanation of system design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** for current database tables and columns
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** for complete API used by this platform
- **[Development Priorities](DEVELOPMENT.md)** for current priorities, roadmap, and tasks
- **[Changelog](CHANGELOG.md)** for most up-to-date version history and notable changes

### Deployment & Operations

- **[Deployment Guide](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** used for production deployment
- **[Operations Guides](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/)** with practical operational procedures and troubleshooting
- **[Contributing Guide](CONTRIBUTING.md)** for essential know-hows when contributing to the project

---

## Technology Stack

**Backend:**
- Flask with blueprint architecture and application factory
- SQLAlchemy ORM with Alembic migrations
- PostgreSQL database
- Gunicorn WSGI server

**Frontend:**
- Jinja2 templates
- Bootstrap 5 with Material Symbols icons
- Minimal JavaScript for real-time attendance and admin UX

**Security:**
- Flask-WTF (CSRF protection)
- pyotp (TOTP authentication)
- cryptography (PII encryption)

**Testing:**
- pytest and pytest-flask

**Deployment:**
- GitHub Actions CI/CD pipeline
- Production-ready for Linux servers (tested on Ubuntu/Debian)
- Compatible with major cloud providers

---

## Project Structure

```
classroom-economy/
├── app/                      # Application package
│   ├── __init__.py           # Application factory and global filters
│   ├── extensions.py         # Flask extensions
│   ├── models.py             # Database models (students, tenancy, payroll, rent, insurance)
│   ├── auth.py               # Authentication decorators and scoped queries
│   ├── routes/               # Blueprint-based routes (admin, student, system_admin, api, main, analytics, docs, recovery)
│   └── utils/                # Utilities (encryption, helpers, constants)
├── templates/                # Jinja2 templates
├── static/                   # CSS, JS, images
├── tests/                    # Test suite
├── migrations/               # Database migrations
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── deploy/                   # Deployment configuration (nginx, etc.)
├── tools/                    # Editor/tooling helpers
├── wsgi.py                   # WSGI entry point
└── requirements.txt          # Python dependencies
```

---

## Development

### Running Tests

```bash
pytest tests/                 # Run all tests
pytest tests/test_payroll.py  # Run specific test
pytest -v                     # Verbose output
```

### Database Migrations

```bash
flask db migrate -m "Description"  # Create migration
flask db upgrade                   # Apply migrations
flask db downgrade                 # Rollback
```

### Common Commands

```bash
flask run                     # Run development server
flask create-sysadmin         # Create system admin
python scripts/create_admin.py        # Create teacher account
python scripts/manage_invites.py      # Manage admin invites
python scripts/seed_dummy_students.py # Seed test data
```

Operational script behavior and arguments are documented in [docs/LOGS/AUDITS/LOG-DEP-022_Scripts_Operations_Reference.md](docs/LOGS/AUDITS/LOG-DEP-022_Scripts_Operations_Reference.md).

---

## Roadmap

Active development priorities, architectural follow-up work, and operational tasks are tracked in [DEVELOPMENT.md](DEVELOPMENT.md).

This repository is under active maintenance. Current capability and release history are reflected in [CHANGELOG.md](CHANGELOG.md) and the canonical docs under [`docs/`](docs/README.md).

v2.0 is under active development with brand new join-code centric schema design, complete API rework, and with even more privacy invariants and even less PII stored. 

> [!NOTE]
> v2.0 is on track to begin testing by June 2026. Until then, v1.x remains under active maintenance with occasional feature push.

---

## Monitoring

Deploy behind a production web server (e.g., NGINX). The `/health` endpoint returns a 200 status when the database is reachable.

```bash
curl http://your-domain/health
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Before contributing:**
1. Review the [Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)
2. Check [DEVELOPMENT.md](DEVELOPMENT.md) for current priorities
3. Ensure all tests pass
4. Follow the existing code style

---

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

### Permitted Uses:
- Use in classrooms, clubs, and nonprofit educational settings
- Modify for school use, assignments, or personal learning
- Share with students or other educators
- Use for research or academic presentations (non-commercial)

### Prohibited Uses:
- Use as part of a commercial product or SaaS platform
- Host a paid service or subscription
- Incorporate into revenue-generating offerings
- Use internally within for-profit businesses

### Licensing & Attribution

**Full License:** See [LICENSE](LICENSE) for complete terms

**Commercial Use Policy:** See [docs/user-guides/legal/commercial.md](docs/user-guides/legal/commercial.md) for detailed guidance on permitted and prohibited commercial activities

**Third-Party Attributions:** See [docs/user-guides/legal/third-party-notices.md](docs/user-guides/legal/third-party-notices.md) for open-source dependencies and services

**Project Philosophy:** See [docs/user-guides/legal/attribution.md](docs/user-guides/legal/attribution.md) for the project's ethical foundations

---

## Support

**Documentation:** [docs/README.md](docs/README.md)

**Issues:** Use GitHub Issues for bug reports and feature requests

**Security:** Report security issues privately to project maintainers

---

## Acknowledgments

This project is dedicated to all of the young pentesters who are relentless in testing the stability of the system and validating the invariants embedded in all the features.

![Last Updated](https://img.shields.io/github/last-commit/timwonderer/classroom-economy?label=last%20updated&color=blue)

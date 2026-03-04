# 🎓 Classroom Token Hub

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

**Version:** 1.8.0

---

## Overview

**Classroom Token Hub** is an educational banking simulation that helps students learn financial literacy through hands-on experience. Students earn tokens by attending class, which they can spend in a classroom store, use for hall passes, or manage through savings and checking accounts.

**License:** [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) - Free for educational and nonprofit use, not for commercial applications.

**Project Status:** Version 1.8.0 Released with active security hardening and performance work in progress. The 1.8.0 release added rent item types (privilege, per-use, hall pass), coverage period tracking, and stability fixes. Recent unreleased improvements include: post-claim PII minimisation (DOB and name hashes automatically deleted after account setup), comprehensive class deletion audit with P1/P2/P3 security fixes, timed deletion confirmation gates, hall pass and admin identity boundary hardening, and a major read-path performance optimization reducing student roster queries from ~1225 to ~10 for a class of 60 students. See [RELEASE_NOTES_v1.8.0.md](docs/LOGS/RELEASES/LOG-REL-015_Release_Notes_V1.8.0.md) for the full release and [CHANGELOG.md](CHANGELOG.md) for all changes.

---

## Features

### Core Features

- **System Admin Portal** — Manage teachers (including account recovery), review error logs, and adjust student ownership
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
- **Admin Account Recovery** — System admins can securely reset teacher 2FA; student recovery uses join code + reset code only
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

### Testing with Sample Data

- Use `student_upload_template.csv` as a reference for CSV roster uploads
- Run `python scripts/seed_dummy_students.py` to seed the database with sample students

---

## Documentation

📚 **[Complete Documentation →](docs/GITHUB_SITE/README.md)**

### For Users

- **[Student Guide](docs/user-guides/student_guide.md)** — How students use the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** — Comprehensive admin guide

### For Developers

- **[Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** — System design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** — Up-to-date database reference
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** — REST API documentation
- **[Development Priorities](DEVELOPMENT.md)** — Current priorities, roadmap, and tasks
- **[Changelog](CHANGELOG.md)** — Version history and notable changes

### Deployment & Operations

- **[Deployment Guide](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** — Production deployment instructions
- **[Operations Guides](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/)** — Operational procedures and troubleshooting
- **[Contributing Guide](CONTRIBUTING.md)** — How to contribute to the project

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
- Docker support with multi-stage builds
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
│   ├── routes/               # Blueprint-based routes (admin, student, system_admin, api, main)
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

---

## Roadmap

Active development priorities and the path to version 1.0 are tracked in [DEVELOPMENT.md](DEVELOPMENT.md).

**Version 1.0 Status:** All critical blockers (P0 and P1) have been resolved! The platform is ready for staging deployment and final validation before production release.

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

**Documentation:** [docs/README.md](docs/GITHUB_SITE/README.md)
**Issues:** Use GitHub Issues for bug reports and feature requests
**Security:** Report security issues privately to project maintainers

---

## Acknowledgments

Built for educators and students to make learning about finance engaging and practical.

**Last Updated:** 2026-02-25

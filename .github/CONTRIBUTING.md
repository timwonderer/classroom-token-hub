# Contributing to Classroom Token Hub

Thank you for your interest in contributing to the Classroom Token Hub project!

Classroom Token Hub v2 is developed on the `main` branch; every pull request targets
`main`. The retired v1 line survives only as the `main_legacy_v1.10.0` branch and the
`v1.*` tags, and it no longer accepts changes.

Before changing behavior, read the governing documents for the area you are touching:
the invariants in `docs/INVARIANT/`, then the domain spec in `docs/DOMAIN/`, then the
FEAT contracts in `docs/FEATURE-EXECUTION/`. When documents disagree, the higher one
(`INV-CORE → INV-ARC → DOM-* → FEAT-*`) wins.

## Getting Started

### Prerequisites

- Python 3.10 or later (`runtime.txt` pins `python-3.10`)
- PostgreSQL. The app and the test suite both need a real PostgreSQL database; there
  is no SQLite path.

### Setup

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine.
3.  **Install git hooks** (required for migration safety checks):
    ```bash
    bash scripts/setup-hooks.sh
    ```
    This configures `core.hooksPath=hooks` and enables the shared repo hooks
    (`post-checkout` and `pre-push`). Note that `hooks/post-checkout` rewrites the
    `DATABASE_URL` line in your `.env` to
    `postgresql://postgres:postgres@localhost:5432/classroom_economy` on every
    checkout, so create that database (or adjust the hook locally) before relying on it.
4.  **Set up the development environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
5.  **Configure your environment variables:**
    Create a `.env` file. The **Quick start** section of `README.md` shows how to
    generate the required keys (`SECRET_KEY`, `DATABASE_URL`, `ENCRYPTION_KEY`,
    `PEPPER_KEY`, `AUDIT_HMAC_KEY`, `FLASK_ENV`) and lists the optional variables.
    Add `TEST_DATABASE_URL` pointing at a separate PostgreSQL database if you intend
    to run the tests (see [Running Tests](#running-tests)).
6.  **Run the database migrations:**
    ```bash
    flask db upgrade
    ```
7.  **Create a system admin account** (follow the prompts and scan the QR code with
    an authenticator app):
    ```bash
    flask create-sysadmin
    ```
8.  **Run the application:**
    ```bash
    flask run
    ```

## Working with Database Migrations

**IMPORTANT:** Follow this workflow carefully to avoid migration conflicts (multiple
heads). The governing specification is
`docs/STANDARD_OPERATING_PROCEDURES/DATABASE/SOP-DB-001_Migration_Specifications.md`.

### When Your Change Requires a Database Migration

1. **Create your branch and make code changes:**
   ```bash
   git checkout -b feature/my-feature
   # Make your model changes in app/models.py
   ```

2. **Sync with main BEFORE creating the migration:**
   ```bash
   git fetch origin main
   git merge origin/main  # or: git rebase origin/main
   flask db heads         # must show exactly one head
   flask db current       # note this revision
   ```

   ⚠️ **This is critical!** Always sync immediately before `flask db migrate`.

3. **Create your migration:**
   ```bash
   flask db migrate -m "Add column X to table Y"
   ```

4. **Review and harden the generated migration file:**
   - Check `migrations/versions/` for the new file
   - Verify the `down_revision` matches the revision `flask db current` reported
   - Copy the idempotency helpers (`table_exists`, `column_exists`, `index_exists`,
     `foreign_key_exists`, …) from `migrations/migration_template.py.mako`
   - Wrap every create operation in an existence check, in both `upgrade()` and
     `downgrade()`, and discover constraint names by inspection instead of
     hardcoding them

5. **Lint the migration:**
   ```bash
   # Your migration alone
   python scripts/lint_migrations.py migrations/versions/<your_migration>.py

   # What CI runs: the whole corpus against the frozen baseline
   python scripts/lint_migrations.py --baseline migrations/lint_baseline.txt
   ```
   `migrations/lint_baseline.txt` records older debt and can only shrink. Never add
   your migration to it.

6. **Test the migration locally, including the downgrade:**
   ```bash
   flask db upgrade
   flask db history                # find the revision to go back to
   flask db downgrade <revision>   # always pass an explicit revision
   flask db current                # confirm where you landed
   flask db upgrade
   flask db heads                  # still exactly one head
   ```
   A bare `flask db downgrade` stops with `Ambiguous walk` when the current revision
   is a merge point, and rolls nothing back.

7. **Commit the model change and the migration together, and push:**
   ```bash
   git add app/models.py migrations/versions/<your_migration>.py
   git commit -m "Add column X to table Y"
   git push origin feature/my-feature
   ```

### Migration Best Practices

- ✅ **DO:** Sync with main immediately before `flask db migrate`
- ✅ **DO:** Merge migration PRs quickly (within 24 hours if possible)
- ✅ **DO:** Keep migrations small and focused (one change per migration)
- ✅ **DO:** Test both upgrade and downgrade paths
- ❌ **DON'T:** Create migrations without syncing first
- ❌ **DON'T:** Edit migration files after they're merged to main (the only exception
  is a Replay-Safety Correction under SOP-DB-001 §V.A, with all of its conditions met)
- ❌ **DON'T:** Delete merged migration files; write a new corrective migration instead

### If You Encounter Multiple Heads

If the pre-push hook or CI detects multiple heads:

```bash
# Option 1: Create a merge migration on your branch
flask db merge heads -m "Merge migration heads"
flask db upgrade
git add migrations/versions/
git commit -m "Merge migration heads"

# Option 2: Recreate your migration (if not yet merged)
rm migrations/versions/YOUR_MIGRATION.py
git fetch origin main
git merge origin/main
flask db migrate -m "Your change description"
```

Either way, the fix lands through a pull request against `main` like any other change.
Migrations are never created or edited on the production host.

### Pre-Push Hook

The versioned `hooks/pre-push` hook is enabled via `scripts/setup-hooks.sh` (see
[Getting Started](#getting-started) step 3), which sets `core.hooksPath=hooks`. This
hook checks for multiple migration heads before pushing and prevents most migration
conflicts from reaching the repository.

If you haven't run the setup script yet:
```bash
bash scripts/setup-hooks.sh
```

To bypass the check (not recommended):
```bash
git push --no-verify
```

### Automated Safety Checks

Migrations are protected in layers:

1. **Pre-push hook (your machine)**: `hooks/pre-push` blocks pushes with multiple
   heads. It can be bypassed with `--no-verify`, which you should not do.
2. **Check Database Migrations** (`.github/workflows/check-migrations.yml`): runs on
   pull requests that touch `migrations/versions/`, `migrations/lint_baseline.txt`,
   `app/models.py`, or the migration scripts. It checks for multiple heads, validates
   migration files, and runs the migration linter against the baseline.
3. **Schema Change Gate** (`.github/workflows/schema-gate.yml`): runs on pull requests
   that touch `migrations/versions/` or `app/models.py`, and rehearses the migration
   against a PostgreSQL service container.
4. **Pre-release check**: `bash scripts/check-migrations.sh` checks migration heads and
   file validity and exits non-zero when it is unsafe to release. Operators run it
   before a production release, per SOP-DEP-002.

## Submitting Changes

1.  **Create a new branch** for your feature or bug fix.
2.  **Make your changes** and commit them with a clear and descriptive commit message.
3.  **If your changes require a database migration**, follow the
    [migration workflow](#working-with-database-migrations) above.
4.  **Run the relevant tests** (see [Running Tests](#running-tests)).
5.  **Push your branch** to your fork on GitHub.
6.  **Open a pull request** from your branch against `main` of the original
    repository, and fill in the pull request template
    (`.github/PULL_REQUEST_TEMPLATE.md`).

### Checks That Run on Pull Requests

These GitHub Actions workflows run on pull requests. Some run on every PR; the rest
run only when the PR touches the paths they watch.

| Workflow | File | Runs on |
| --- | --- | --- |
| Constitutional CI | `.github/workflows/constitutional-ci.yml` | every PR |
| Policy Guardrails | `.github/workflows/policy-guardrails.yml` | every PR |
| Audit Guard | `.github/workflows/audit-guard.yml` | every PR (enforces docs-only changes on PRs labeled `audit`) |
| Check Database Migrations | `.github/workflows/check-migrations.yml` | migrations, `app/models.py`, migration scripts |
| Schema Change Gate | `.github/workflows/schema-gate.yml` | migrations, `app/models.py` |
| Accessibility Gate | `.github/workflows/accessibility-gate.yml` | `templates/`, `static/css/`, `app/routes/`, `app/forms.py` |
| Documentation Link Checks | `.github/workflows/docs-links.yml` | `README.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `docs/`, `lychee.toml` |
| Lint Workflows | `.github/workflows/actionlint.yml` | `.github/workflows/` |
| Deploy GitHub Pages Site | `.github/workflows/github-pages.yml` | `github-pages/`, `docs-site/`, `docs/` (build only on PRs) |
| Deploy status service to Google Cloud | `.github/workflows/deploy-status.yml` | `status/`, `status_service/`, `tests/test_status_*.py` (tests only on PRs) |

The full test suite (`.github/workflows/full-suite.yml`) runs nightly and on manual
dispatch, not on each pull request, so run the tests that cover your change locally.

## Releases and Deployment

Merging to `main` does **not** deploy anything. There is no push-to-deploy.

Production is released by the **Release v2 to Production** workflow
(`.github/workflows/release-v2.yml`). An operator starts it by hand with an exact
40-character commit SHA that must be an ancestor of the approved release lineage. The
workflow connects to the production host over Tailscale, checks out that SHA, installs
the pinned requirements, runs `flask db upgrade`, restarts the service, and probes
`/health`. Access to the production hostname during a release window is controlled by
Cloudflare Access, not by an application maintenance mode.

Releases are operator-only. The full procedure is
`docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md`,
summarized in the **Releases and deployment** section of `README.md`. Contributors
don't need to do anything beyond getting their pull request merged.

## Running Tests

Tests run against a real PostgreSQL database named by `TEST_DATABASE_URL` (read from
`.env`, then from the environment). There is no SQLite path. `tests/conftest.py` drops
the schema and rebuilds it through the real migration chain, so **point
`TEST_DATABASE_URL` at a dedicated test database, never at one whose data you want to
keep.** If `TEST_DATABASE_URL` is unset, `conftest.py` falls back to `DATABASE_URL`
(that is how CI configures it), which locally would mean your development database
gets wiped, so always set `TEST_DATABASE_URL` explicitly.

```bash
pytest tests/test_x.py -q      # one file
pytest -k recovery             # by pattern
pytest --cov=app tests/        # with coverage
pytest                         # full suite (takes over an hour)
```

Run the narrowest selection that proves your change while iterating, and include tests
with every feature and bug fix. Tests provision a whole classroom through
`tests/helpers/classroom_initializer.py` rather than creating rows by hand (see
`docs/SPEC/SPEC-TEST-001_CANONICAL_TEST_INITIALIZER.md`).

## License

Classroom Token Hub is licensed under the PolyForm Noncommercial License 1.0.0. The
full text is in `LICENSE` at the repository root.

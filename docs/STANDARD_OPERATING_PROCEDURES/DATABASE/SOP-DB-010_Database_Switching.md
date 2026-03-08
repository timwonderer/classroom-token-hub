# Database Configuration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DB-010| 1.2 | 2026-03-08 | 1.1 |Normative|

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Automatic Branch-Based Database Switching

This repository uses branch-based database switching through the shared git hooks.

### Protected v2 Branch

- `codex/v2.0`

This branch must use:

- the team-configured v2 dev database

### Test Database

Automated and manual tests for v2 must use:

- the team-configured PostgreSQL test database

This is not the same database as the protected dev/migration database.

### All Other Branches

All other branches may use:

- `postgresql://postgres:postgres@localhost/production_dev`

## VI. How It Works

When you checkout a branch, the `hooks/post-checkout` hook updates `DATABASE_URL` in `.env` for the branch class it recognizes.

## VII. Manual Switching

```bash
# Switch to production_dev (blocked on protected v2 branch)
./scripts/switch-db.sh production_dev

# Switch to classroom_economy
./scripts/switch-db.sh classroom_economy

# Check current database
./scripts/switch-db.sh
```

## VIII. Operator Truth

- `classroom_economy` is the v2 dev and migration rehearsal database.
- `classroom_economy_test` is the required PostgreSQL test database.
- `production_dev` is for non-v2 development branches.

## IX. Setup for Contributors

1. Run `./scripts/setup-hooks.sh`.
2. Checkout your branch.
3. Confirm `.env` contains the expected `DATABASE_URL`.
4. Before running tests on v2 work, export:

```bash
export DATABASE_URL=<team-test-db-url>
```

## X. Troubleshooting

If automatic switching is not working:

1. Verify the hook exists: `ls -la hooks/post-checkout`
2. Verify hooks path config: `git config --get core.hooksPath`
3. Verify the hook is executable: `chmod +x hooks/post-checkout`
4. Use `./scripts/switch-db.sh` manually for the dev database
5. Set the test database explicitly in the shell before running pytest
## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.

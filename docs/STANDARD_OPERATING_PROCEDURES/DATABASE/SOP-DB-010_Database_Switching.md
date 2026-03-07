# Database Configuration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-010       | 1.0     | 2026-03-01     | N/A        | Normative                 |

## Automatic Branch-Based Database Switching

This repository uses branch-based database switching.

Protected v2.0 branches:

- `join-code-centric-architecture-rebuild`
- `codex/fix-database-model-for-dob-sum-storage`
- `codex/v2.0`

These branches must always use:

- `postgresql://postgres:postgres@localhost/classroom_economy`

All other branches may use:

- `postgresql://postgres:postgres@localhost/production_dev`

### How It Works

When you checkout a branch, the `.git/hooks/post-checkout` hook automatically updates the `DATABASE_URL` in your `.env` file.

### Manual Database Switching

Manual switch command:

```bash
# Switch to production_dev (blocked on protected branches)
./scripts/switch-db.sh production_dev

# Switch to classroom_economy
./scripts/switch-db.sh classroom_economy

# Check current database
./scripts/switch-db.sh
```

### Database Purposes

- **`classroom_economy`**: Required for protected v2.0 architecture branches listed above
- **`production_dev`**: Default for non-protected branches and current v1.x work

### Setup for New Contributors

1. Run `./scripts/switch-db.sh production_dev` (or `classroom_economy` if on a protected branch)
2. Confirm `.env` contains the expected `DATABASE_URL` for your current branch

### Troubleshooting

If the automatic switching isn't working:

1. Verify the hook exists: `ls -la .git/hooks/post-checkout`
2. Verify it's executable: `chmod +x .git/hooks/post-checkout`
3. Manually switch using the script:
   - Protected branches: `./scripts/switch-db.sh classroom_economy`
   - Other branches: `./scripts/switch-db.sh production_dev`

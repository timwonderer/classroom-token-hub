# Database Configuration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-010       | 1.0     | 2026-03-01     | N/A        | Normative                 |

## Automatic Branch-Based Database Switching

This repository uses a git `post-checkout` hook to automatically switch between databases based on the current branch:

- **Most branches** → `production_dev` database
- **`join-code-centric-architecture-rebuild` branch** → `classroom_economy` database

### How It Works

When you checkout a branch, the `.git/hooks/post-checkout` hook automatically updates the `DATABASE_URL` in your `.env` file.

### Manual Database Switching

If you need to manually switch databases:

```bash
# Switch to production_dev
./scripts/switch-db.sh production_dev

# Switch to classroom_economy
./scripts/switch-db.sh classroom_economy

# Check current database
./scripts/switch-db.sh
```

### Database Purposes

- **`production_dev`**: Main development database, matches production schema
- **`classroom_economy`**: Used for the new `classroomeconomies` schema architecture (join-code-centric branch only)

### Setup for New Contributors

The git hook is already in place. When you first clone the repo:

1. Run `./scripts/switch-db.sh production_dev` to set your initial database
2. The hook will automatically switch databases when you change branches

### Troubleshooting

If the automatic switching isn't working:

1. Verify the hook exists: `ls -la .git/hooks/post-checkout`
2. Verify it's executable: `chmod +x .git/hooks/post-checkout`
3. Manually switch using the script: `./scripts/switch-db.sh production_dev`

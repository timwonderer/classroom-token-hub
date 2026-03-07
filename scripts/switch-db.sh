#!/bin/bash
# Manual database switcher script
# Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null || pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/lib/db_branch_config.sh"

if [ -z "$1" ]; then
    echo "Usage: ./scripts/switch-db.sh [production_dev|classroom_economy]"
    echo ""
    if [ -f ".env" ] && grep -q "^DATABASE_URL=" .env; then
        echo "Current DATABASE_URL:"
        grep "^DATABASE_URL=" .env
    else
        echo "No DATABASE_URL found in .env"
    fi
    exit 1
fi

DB_NAME=$1
ENV_FILE="$REPO_ROOT/.env"
BRANCH_NAME=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

case $DB_NAME in
    production_dev)
        if is_protected_branch "$BRANCH_NAME"; then
            echo "Error: '$BRANCH_NAME' must use classroom_economy to protect v2.0 migration chain."
            echo "production_dev is off-limits for this branch."
            exit 1
        fi
        DB_URL="$PRODUCTION_DEV_DB_URL"
        ;;
    classroom_economy)
        DB_URL="$CLASSROOM_ECONOMY_DB_URL"
        ;;
    *)
        echo "Error: Invalid database name. Use 'production_dev' or 'classroom_economy'."
        exit 1
        ;;
esac

# Create .env file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "DATABASE_URL=$DB_URL" > "$ENV_FILE"
    echo "✓ Created .env file and set $DB_NAME database"
    echo "  DATABASE_URL=$DB_URL"
    exit 0
fi

# Check if DATABASE_URL line exists
if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    # Update existing line
    escaped_db_url=$(printf '%s' "$DB_URL" | sed 's/[&/|]/\\&/g')
    sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$escaped_db_url|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    # Append new line
    echo "DATABASE_URL=$DB_URL" >> "$ENV_FILE"
fi

echo "✓ Switched to $DB_NAME database"
echo "  DATABASE_URL=$DB_URL"

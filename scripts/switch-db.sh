#!/bin/bash
# Branch-aware database selector helper.
# Usage:
#   ./scripts/switch-db.sh            # show auto-derived URLs for current branch
#   ./scripts/switch-db.sh v1|v2      # show URLs for a specific version

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null || pwd)"
ENV_FILE="$REPO_ROOT/.env"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/lib/db_branch_config.sh"
load_db_urls_from_env "$ENV_FILE"

BRANCH_NAME=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
TARGET_VERSION="${1:-$(branch_db_version "$BRANCH_NAME")}"

case "$TARGET_VERSION" in
  v1|V1)
    TARGET_VERSION="v1"
    DEV_DB_URL="$V1_DEV_DATABASE_URL"
    TEST_DB_URL="$V1_TEST_DATABASE_URL"
    ;;
  v2|V2)
    TARGET_VERSION="v2"
    DEV_DB_URL="$V2_DEV_DATABASE_URL"
    TEST_DB_URL="$V2_TEST_DATABASE_URL"
    ;;
  "")
    echo "Unable to determine branch version."
    exit 1
    ;;
  *)
    echo "Usage: ./scripts/switch-db.sh [v1|v2]"
    exit 1
    ;;
esac

echo "✓ Derived database URLs for $TARGET_VERSION"
echo "  Branch: $BRANCH_NAME"
echo "  DATABASE_URL=$DEV_DB_URL"
echo "  TEST_DATABASE_URL=$TEST_DB_URL"
echo ""
echo "No .env rewrite performed."
echo "For a one-off override:"
echo "  DATABASE_URL=$DEV_DB_URL TEST_DATABASE_URL=$TEST_DB_URL <command>"

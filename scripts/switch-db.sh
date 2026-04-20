#!/bin/bash
# Manual database switcher script
# Usage:
#   ./scripts/switch-db.sh            # auto-detect from current branch
#   ./scripts/switch-db.sh v1|v2      # force version

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
    echo ""
    echo "Current branch: $BRANCH_NAME"
    if [ -f "$ENV_FILE" ]; then
      echo "Current DATABASE_URL:"
      grep "^DATABASE_URL=" "$ENV_FILE" || true
      echo "Current TEST_DATABASE_URL:"
      grep "^TEST_DATABASE_URL=" "$ENV_FILE" || true
    else
      echo "No .env file found at $ENV_FILE"
    fi
    exit 1
    ;;
esac

ensure_env_var() {
  local key="$1"
  local value="$2"

  if [ ! -f "$ENV_FILE" ]; then
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    return
  fi

  if grep -q "^${key}=" "$ENV_FILE"; then
    local escaped_value
    escaped_value=$(printf '%s' "$value" | sed 's/[&/|]/\\&/g')
    sed -i.bak "s|^${key}=.*|${key}=${escaped_value}|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

touch "$ENV_FILE"
ensure_env_var "DATABASE_URL" "$DEV_DB_URL"
ensure_env_var "TEST_DATABASE_URL" "$TEST_DB_URL"

echo "✓ Switched database URLs for $TARGET_VERSION"
echo "  Branch: $BRANCH_NAME"
echo "  DATABASE_URL=$DEV_DB_URL"
echo "  TEST_DATABASE_URL=$TEST_DB_URL"

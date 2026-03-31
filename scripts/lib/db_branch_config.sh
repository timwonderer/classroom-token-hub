#!/bin/bash
# Shared database/branch policy used by hook and manual switch script.

PRODUCTION_DEV_DB_URL="postgresql://postgres:postgres@localhost:5432/production_dev"
CLASSROOM_ECONOMY_DB_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy"

LEGACY_PROTECTED_BRANCHES=(
  "join-code-centric-architecture-rebuild"
  "codex/fix-database-model-for-dob-sum-storage"
)

is_protected_branch() {
  local branch="$1"
  local protected

  case "$branch" in
    codex/v2.0|codex/v2-*)
      return 0
      ;;
  esac

  for protected in "${LEGACY_PROTECTED_BRANCHES[@]}"; do
    if [ "$branch" = "$protected" ]; then
      return 0
    fi
  done
  return 1
}

db_name_for_branch() {
  local branch="$1"
  if is_protected_branch "$branch"; then
    echo "classroom_economy"
  else
    echo "production_dev"
  fi
}

db_url_for_name() {
  local db_name="$1"
  case "$db_name" in
    classroom_economy)
      echo "$CLASSROOM_ECONOMY_DB_URL"
      ;;
    production_dev)
      echo "$PRODUCTION_DEV_DB_URL"
      ;;
    *)
      return 1
      ;;
  esac
}

is_allowed_local_db_url() {
  local db_url="$1"
  case "$db_url" in
    "$PRODUCTION_DEV_DB_URL"|"$CLASSROOM_ECONOMY_DB_URL")
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

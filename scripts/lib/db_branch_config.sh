#!/bin/bash
# Shared database/branch policy used by hook and manual switch script.

PRODUCTION_DEV_DB_URL="postgresql://postgres:postgres@localhost:5432/production_dev"
CLASSROOM_ECONOMY_DB_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy"

PROTECTED_BRANCHES=(
  "join-code-centric-architecture-rebuild"
  "codex/fix-database-model-for-dob-sum-storage"
  "codex/v2.0"
)

is_protected_branch() {
  local branch="$1"
  local protected
  for protected in "${PROTECTED_BRANCHES[@]}"; do
    if [ "$branch" = "$protected" ]; then
      return 0
    fi
  done
  return 1
}

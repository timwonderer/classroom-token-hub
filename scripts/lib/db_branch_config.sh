#!/bin/bash
# Shared database/branch policy used by hooks and manual switch scripts.

DEFAULT_V1_DEV_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/production_dev"
DEFAULT_V2_DEV_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy"
DEFAULT_V1_TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy_test"
DEFAULT_V2_TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/classroom_economy_v2_test"

_db_env_value() {
  local env_file="$1"
  local key="$2"

  if [ -f "$env_file" ]; then
    awk -F= -v target="$key" '$1 == target { sub(/^[^=]*=/, "", $0); print $0; exit }' "$env_file"
  fi
}

load_db_urls_from_env() {
  local env_file="$1"

  V1_DEV_DATABASE_URL="${V1_DEV_DATABASE_URL:-$(_db_env_value "$env_file" "V1_DEV_DATABASE_URL")}"
  V2_DEV_DATABASE_URL="${V2_DEV_DATABASE_URL:-$(_db_env_value "$env_file" "V2_DEV_DATABASE_URL")}"
  V1_TEST_DATABASE_URL="${V1_TEST_DATABASE_URL:-$(_db_env_value "$env_file" "V1_TEST_DATABASE_URL")}"
  V2_TEST_DATABASE_URL="${V2_TEST_DATABASE_URL:-$(_db_env_value "$env_file" "V2_TEST_DATABASE_URL")}"

  V1_DEV_DATABASE_URL="${V1_DEV_DATABASE_URL:-$DEFAULT_V1_DEV_DATABASE_URL}"
  V2_DEV_DATABASE_URL="${V2_DEV_DATABASE_URL:-$DEFAULT_V2_DEV_DATABASE_URL}"
  V1_TEST_DATABASE_URL="${V1_TEST_DATABASE_URL:-$DEFAULT_V1_TEST_DATABASE_URL}"
  V2_TEST_DATABASE_URL="${V2_TEST_DATABASE_URL:-$DEFAULT_V2_TEST_DATABASE_URL}"
}

is_v2_branch() {
  local branch="$1"
  case "$branch" in
    V2_*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

branch_db_version() {
  local branch="$1"
  if is_v2_branch "$branch"; then
    printf 'v2'
  else
    printf 'v1'
  fi
}

db_urls_for_branch() {
  local branch="$1"

  if is_v2_branch "$branch"; then
    printf '%s\n%s\n' "$V2_DEV_DATABASE_URL" "$V2_TEST_DATABASE_URL"
  else
    printf '%s\n%s\n' "$V1_DEV_DATABASE_URL" "$V1_TEST_DATABASE_URL"
  fi
}

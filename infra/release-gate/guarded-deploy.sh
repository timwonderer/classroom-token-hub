#!/usr/bin/env bash
# Forced command for the release workflow's deploy key, installed BY HAND on the droplet at
# /root/release-gate/guarded-deploy.sh (see README.md in this directory for the install steps — this
# repository copy is the reviewable source, not the live file). Deliberately outside
# ~/classroom-economy: that directory is reset to the release SHA on every deploy
# (`git reset --hard`, `git clean -fd docs/`), and anything inside it is something a pull request can
# edit. This file is root-owned, 0700, and nothing under version control can create, edit or delete it.
#
# Why a forced command: sshd runs THIS script for every session that authenticates with this key,
# ignoring whatever command the client asked for (available below as $SSH_ORIGINAL_COMMAND). A change
# to .github/workflows/release-v2.yml can change what command release-v2.yml *tries* to send; it cannot
# change what sshd actually executes on the other end of this key. The two checks below — the Access
# gate is closed, a real recent signed backup/restore exists — are the actual safety conditions
# SOP-DEP-002 §VII.A steps 4-7 require before any of the workflow's SSH calls (transport check, deploy,
# health probe) are allowed to run. Re-checking them unconditionally on every call, rather than trying
# to tell "this one's the dangerous command" from the text of $SSH_ORIGINAL_COMMAND, means there is
# nothing here that parses or trusts the shape of that string except the one place it's load-bearing:
# pulling out a revision to cross-check against the evidence, when one is present.
#
# Incident this exists to prevent: v2.4.0 (2026-10-29) was dispatched through the real, unmodified
# release-v2.yml before the maintenance window opened — an agent misread "the Cloudflare gate closes at
# 8:30" as a deadline rather than "maintenance hasn't started yet" and skipped SOP-DEP-002 steps 4-8.
# No GitHub-side control (branch protection, required review, environment reviewers, a repo secret)
# closes that gap in this repository today: the only GitHub identity here is the owner's own account,
# shared by every session acting on their behalf, and its connector scope cannot be narrowed further
# (confirmed 2026-10-29). This script is the one check that lives entirely outside that identity.
set -euo pipefail

RELEASE_GATE_DIR=/root/release-gate
EVIDENCE_JSON="$RELEASE_GATE_DIR/evidence/latest.json"
EVIDENCE_SIG="$RELEASE_GATE_DIR/evidence/latest.json.sig"
ALLOWED_SIGNERS="$RELEASE_GATE_DIR/allowed_signers"
MAX_EVIDENCE_AGE_SECONDS=7200   # one sitting: backup, counts, restore, evidence (SOP-DEP-002 §VII.A 5-7a)
GATE_URL=https://app.classroomtokenhub.com/static/manifest.json   # same probe as status_service/collector.py
ACCESS_LOGIN_DOMAIN=cloudflareaccess.com

fail() { echo "guarded-deploy: $1" >&2; exit 1; }

[ -n "${SSH_ORIGINAL_COMMAND:-}" ] || fail "no command requested; this key does not grant an interactive shell"

# --- 1. The Cloudflare Access gate must be closed right now -----------------------------------------
# Same classification SPEC-OPS-006 / status_service/collector.py use: an uncredentialed request for a
# static public asset that is redirected to cloudflareaccess.com (exactly, or a subdomain of it) means
# the gate is closed. A 200, a different redirect, or a bare 401/403 does not establish a closed gate,
# and this refuses rather than guess either way.
GATE_HEADERS=$(curl -s -o /dev/null -D - --max-time 10 "$GATE_URL") \
  || fail "could not reach $GATE_URL to check whether the Access gate is closed"
GATE_STATUS=$(printf '%s' "$GATE_HEADERS" | head -n1 | awk '{print $2}')
# tolower($0), not awk's IGNORECASE: that flag is a gawk extension that mawk (Debian/Ubuntu's default
# /usr/bin/awk) silently ignores, which would make this match nothing and fail the deploy with no
# evidence as to why.
GATE_LOCATION=$(printf '%s' "$GATE_HEADERS" | tr -d '\r' | awk 'tolower($0) ~ /^location:/{print $2; exit}')
GATE_HOST=$(python3 -c "
import sys
from urllib.parse import urlsplit
print((urlsplit(sys.argv[1]).hostname or '').lower())
" "${GATE_LOCATION:-}")
case "$GATE_STATUS" in
  3??) ;;
  *) fail "Access gate is not closed: probe returned $GATE_STATUS, expected a 3xx redirect to $ACCESS_LOGIN_DOMAIN" ;;
esac
case "$GATE_HOST" in
  "$ACCESS_LOGIN_DOMAIN"|*".$ACCESS_LOGIN_DOMAIN") ;;
  *) fail "Access gate is not closed: redirect host '$GATE_HOST' is not $ACCESS_LOGIN_DOMAIN" ;;
esac

# --- 2. A real, fresh, signed backup/restore evidence file must exist -------------------------------
[ -f "$EVIDENCE_JSON" ] && [ -f "$EVIDENCE_SIG" ] \
  || fail "no release evidence at $RELEASE_GATE_DIR/evidence/; run infra/db-backup/prerelease.sh evidence <sha> from the Mac mini first"

ssh-keygen -Y verify -f "$ALLOWED_SIGNERS" -I cth-release-evidence -n cth-release -s "$EVIDENCE_SIG" \
  < "$EVIDENCE_JSON" >/dev/null \
  || fail "release evidence signature does not verify against $ALLOWED_SIGNERS"

EVIDENCE_REVISION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['revision'])" "$EVIDENCE_JSON")
EVIDENCE_TAKEN_AT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['taken_at'])" "$EVIDENCE_JSON")
EVIDENCE_EPOCH=$(date -u -d "$EVIDENCE_TAKEN_AT" +%s) || fail "release evidence has an unparseable taken_at"
NOW_EPOCH=$(date -u +%s)
EVIDENCE_AGE=$(( NOW_EPOCH - EVIDENCE_EPOCH ))
{ [ "$EVIDENCE_AGE" -ge 0 ] && [ "$EVIDENCE_AGE" -le "$MAX_EVIDENCE_AGE_SECONDS" ]; } \
  || fail "release evidence is ${EVIDENCE_AGE}s old (limit ${MAX_EVIDENCE_AGE_SECONDS}s); run prerelease.sh backup/counts/restore/evidence again"

# If the requested command names an exact revision — the deploy step always does — the evidence must
# be for that exact revision, not an old backup replayed against a different SHA. Calls that name no
# revision (the transport check, the health probe) only need a fresh, validly signed evidence to exist.
if [[ "$SSH_ORIGINAL_COMMAND" =~ RELEASE_REVISION=\'([0-9a-fA-F]{40})\' ]]; then
  REQUESTED_REVISION=$(printf '%s' "${BASH_REMATCH[1]}" | tr 'A-F' 'a-f')   # evidence.revision is lowercased on write
  [ "$EVIDENCE_REVISION" = "$REQUESTED_REVISION" ] \
    || fail "release evidence is for revision $EVIDENCE_REVISION, not the requested $REQUESTED_REVISION"
fi

exec bash -c "$SSH_ORIGINAL_COMMAND"

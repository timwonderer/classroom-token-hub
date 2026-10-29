#!/usr/bin/env bash
# Forced command for `RELEASE_DEPLOY_KEY`, a key dedicated to release-v2.yml, installed BY HAND on the
# droplet at /root/release-gate/guarded-deploy.sh (see README.md in this directory for the install
# steps — this repository copy is the reviewable source, not the live file). Deliberately outside
# ~/classroom-economy: that directory is reset to the release SHA on every deploy
# (`git reset --hard`, `git clean -fd docs/`), and anything inside it is something a pull request can
# edit. This file is root-owned, 0700, and nothing under version control can create, edit or delete it.
#
# This is a SEPARATE key from the shared DO_DEPLOY_KEY that login-notice.yml and
# tailscale-ssh-smoke-test.yml also authenticate with. Those two workflows send commands this script
# does not recognize (see the three-way classifier below), so forcing this script onto DO_DEPLOY_KEY's
# authorized_keys line would refuse every one of their requests the moment it was installed. Only
# RELEASE_DEPLOY_KEY's line gets this forced command. DO_DEPLOY_KEY's line is NOT left unrestricted,
# though: it gets its own forced command, guarded-ci.sh (same directory), because being a repository
# secret it could otherwise be pointed at a deploy by editing any workflow — restricting only this key
# would not have closed that gap. See guarded-ci.sh's own header for why that matters here.
#
# Why a forced command: sshd runs THIS script for every session that authenticates with this key,
# ignoring whatever command the client asked for (available below as $SSH_ORIGINAL_COMMAND). A change
# to .github/workflows/release-v2.yml can change what command release-v2.yml *tries* to send; it cannot
# change what sshd actually executes on the other end of this key.
#
# What this does NOT do, after an earlier version of this file did: it does not `exec` or otherwise run
# $SSH_ORIGINAL_COMMAND, and it does not read or forward the client's stdin into a shell. A review
# caught that passing the original command through — even after the gate and evidence checks passed —
# meant a modified release-v2.yml could send `bash -s` with arbitrary stdin and get an unrestricted
# root shell for as long as the evidence stayed fresh, which is exactly the legitimate release window.
# Root ownership and living outside the git checkout do not help against that: the deploy key itself
# runs as root, so passing its command through at all is the hole. Instead, $SSH_ORIGINAL_COMMAND is
# only ever used to CLASSIFY the request into one of three fixed, hardcoded operations below and, for
# the deploy operation, to pull out a revision that is validated as exactly 40 hex characters before
# it touches anything. No other text from the client — not the command, not stdin — is ever executed.
# A command that doesn't match one of the three known shapes refuses, rather than guessing.
#
# Consequence: if release-v2.yml's transport-check or health-check text ever changes, the matching
# clause below has to change with it, by hand, on the droplet — a mismatch fails closed (refuses
# everything) rather than open.
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
APP_DIR=/root/classroom-economy

fail() { echo "guarded-deploy: $1" >&2; exit 1; }

[ -n "${SSH_ORIGINAL_COMMAND:-}" ] || fail "no command requested; this key does not grant an interactive shell"

# --- 1. The Cloudflare Access gate must be closed right now -----------------------------------------
# Same classification SPEC-OPS-006 / status_service/collector.py use: an uncredentialed request for a
# static public asset that is redirected to cloudflareaccess.com (exactly, or a subdomain of it) means
# the gate is closed. A 200, a different redirect, or a bare 401/403 does not establish a closed gate,
# and this refuses rather than guess either way.
#
# Headers are stripped of carriage returns as soon as they're captured. An HTTP/2 redirect has no
# reason phrase ("HTTP/2 302", not "HTTP/2 302 Found"), which makes the status code the LAST field on
# the line — if a trailing \r were still attached, it would land on the code itself ("302\r"), never
# match the "3??" pattern below, and misclassify a genuinely closed gate as open, blocking every
# legitimate release. Stripping \r from the whole response up front, not just from the Location line,
# closes that regardless of which field ends up last.
GATE_HEADERS=$(curl -s -o /dev/null -D - --max-time 10 "$GATE_URL" | tr -d '\r') \
  || fail "could not reach $GATE_URL to check whether the Access gate is closed"
GATE_STATUS=$(printf '%s' "$GATE_HEADERS" | head -n1 | awk '{print $2}')
# tolower($0), not awk's IGNORECASE: that flag is a gawk extension that mawk (Debian/Ubuntu's default
# /usr/bin/awk) silently ignores, which would make this match nothing and fail the deploy with no
# evidence as to why.
GATE_LOCATION=$(printf '%s' "$GATE_HEADERS" | awk 'tolower($0) ~ /^location:/{print $2; exit}')
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

# --- 3. Classify the request into exactly one hardcoded operation, then run OUR code, not theirs ----
# $SSH_ORIGINAL_COMMAND is only ever matched against these shapes. Nothing it or stdin contains is
# executed as a command past this point — see the file header for why.

do_transport_check() {
  test -d "$APP_DIR"
  echo "SSH transport ready on $(hostname)"
}

do_health_check() {
  local deadline=$((SECONDS + 30))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$(curl --fail --silent --max-time 2 http://127.0.0.1:8000/health || true)" = "ok" ]; then
      echo "Production health passed"
      return 0
    fi
    sleep 2
  done
  echo "Health check failed: /health on 127.0.0.1:8000 did not return ok within 30s"
  return 1
}

do_deploy() {
  local revision="$1"   # already validated below: exactly 40 hex characters, nothing else
  set -euo pipefail
  cd "$APP_DIR"
  git fetch --no-tags origin "$revision"
  git reset --hard "$revision"
  git clean -fd docs/
  source venv/bin/activate
  pip install --requirement requirements.txt
  flask db upgrade
  systemctl restart classroom-economy
  systemctl is-active --quiet classroom-economy
  echo "Released exact revision $revision"
}

if [ "$SSH_ORIGINAL_COMMAND" = 'set -e; test -d ~/classroom-economy; echo "SSH transport ready on $(hostname)"' ]; then
  do_transport_check

elif [ "$SSH_ORIGINAL_COMMAND" = 'deadline=$((SECONDS + 30)); while [ "$SECONDS" -lt "$deadline" ]; do if [ "$(curl --fail --silent --max-time 2 http://127.0.0.1:8000/health || true)" = "ok" ]; then echo "Production health passed"; exit 0; fi; sleep 2; done; echo "Health check failed: /health on 127.0.0.1:8000 did not return ok within 30s"; exit 1' ]; then
  do_health_check

elif [[ "$SSH_ORIGINAL_COMMAND" =~ ^RELEASE_REVISION=\'([0-9a-fA-F]{40})\'\ bash\ -s$ ]]; then
  REQUESTED_REVISION=$(printf '%s' "${BASH_REMATCH[1]}" | tr 'A-F' 'a-f')   # evidence.revision is lowercased on write
  [ "$EVIDENCE_REVISION" = "$REQUESTED_REVISION" ] \
    || fail "release evidence is for revision $EVIDENCE_REVISION, not the requested $REQUESTED_REVISION"
  do_deploy "$REQUESTED_REVISION" </dev/null   # the heredoc stdin release-v2.yml sends is never read; see file header

else
  fail "command does not match a known release operation"
fi

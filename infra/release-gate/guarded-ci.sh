#!/usr/bin/env bash
# Forced command for DO_DEPLOY_KEY, installed BY HAND on the droplet at
# /root/release-gate/guarded-ci.sh (see README.md in this directory for the install steps — this
# repository copy is the reviewable source, not the live file). Root-owned, 0700, outside
# ~/classroom-economy, same as guarded-deploy.sh.
#
# Why this exists: DO_DEPLOY_KEY authenticates login-notice.yml and tailscale-ssh-smoke-test.yml, and
# until this script existed, DO_DEPLOY_KEY's authorized_keys line carried no forced command at all —
# any session able to use this key (which is any session able to edit a workflow in this repository,
# since it is a repository secret) could send ANY command over it and get an unrestricted root shell.
# release-v2.yml was moved off DO_DEPLOY_KEY onto its own, gated RELEASE_DEPLOY_KEY (see
# guarded-deploy.sh), but that alone does not close the gap: the same identity that could skip
# SOP-DEP-002 in the first place could just as easily edit release-v2.yml back onto DO_DEPLOY_KEY, or
# add a new workflow step that uses it, and deploy with no gate at all — DO_DEPLOY_KEY itself was the
# hole, not which workflow happened to reference it. Every key GitHub Actions can use against the
# droplet has to be forced-command-restricted for the gate to mean anything; this is DO_DEPLOY_KEY's.
#
# Same rule as guarded-deploy.sh: $SSH_ORIGINAL_COMMAND and stdin are NEVER executed as given. This
# script classifies the request into one of two fixed, hardcoded operations — the exact two things
# login-notice.yml and tailscale-ssh-smoke-test.yml need — and, for the one that takes an argument,
# re-validates that argument itself rather than trusting whatever a workflow claims it already checked.
# A command that doesn't match either shape refuses, rather than guessing. This necessarily includes
# every one of guarded-deploy.sh's three shapes: a deploy attempt sent over this key is refused here,
# gate and evidence aside, because this script has no deploy operation at all.
set -euo pipefail

APP_DIR=/root/classroom-economy
MAX_NOTICE_B64_LEN=8000   # generous relative to login-notice.yml's 1000-character message cap

fail() { echo "guarded-ci: $1" >&2; exit 1; }

[ -n "${SSH_ORIGINAL_COMMAND:-}" ] || fail "no command requested; this key does not grant an interactive shell"

# --- Classify the request into exactly one hardcoded operation, then run OUR code, not theirs -------
# $SSH_ORIGINAL_COMMAND is only ever matched against these shapes. Nothing it or stdin contains is
# executed as a command past this point — see the file header for why.

do_smoke_test() {
  echo "Connected as $(whoami) on $(hostname)"
  test -d "$APP_DIR"
}

do_login_notice() {
  local payload_b64="$1"   # already shape-validated below: base64 alphabet, bounded length
  local dir="$APP_DIR/instance"
  local path="$dir/login_notice.json"

  if [ -z "$payload_b64" ]; then
    rm -f "$path"
    echo "Login notice cleared."
    return 0
  fi

  local decoded
  decoded=$(printf '%s' "$payload_b64" | base64 -d 2>/dev/null) \
    || fail "notice payload is not valid base64"
  # Belt-and-braces: confirm it is at least a JSON object before it ever reaches disk, independent of
  # whatever login-notice.yml's own build step claims to have validated upstream.
  printf '%s' "$decoded" | python3 -c 'import json,sys; obj=json.load(sys.stdin); assert isinstance(obj, dict)' 2>/dev/null \
    || fail "notice payload does not decode to a JSON object"

  mkdir -p "$dir"
  local tmp
  tmp="$(mktemp "$dir/.login_notice.XXXXXX")"
  printf '%s' "$decoded" > "$tmp"
  chmod 644 "$tmp"
  mv -f "$tmp" "$path"
  echo "Login notice posted."
}

if [ "$SSH_ORIGINAL_COMMAND" = 'set -e; echo "Connected as $(whoami) on $(hostname)"; test -d ~/classroom-economy' ]; then
  do_smoke_test

elif [[ "$SSH_ORIGINAL_COMMAND" =~ ^NOTICE_PAYLOAD=\'([A-Za-z0-9+/]*={0,2})\'\ bash\ -s$ ]]; then
  PAYLOAD="${BASH_REMATCH[1]}"
  [ "${#PAYLOAD}" -le "$MAX_NOTICE_B64_LEN" ] || fail "notice payload exceeds ${MAX_NOTICE_B64_LEN} base64 characters"
  do_login_notice "$PAYLOAD" </dev/null   # the heredoc stdin login-notice.yml sends is never read

else
  fail "command does not match a known CI operation"
fi

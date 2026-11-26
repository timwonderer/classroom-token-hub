#!/usr/bin/env bash
# Forced command for DOCS_DEPLOY_KEY, the key dedicated to docs-deploy.yml (SOP-DEP-003). Installed BY
# HAND at /root/release-gate/guarded-docs.sh, root-owned 0700, with docs_publish.py beside it. This
# repository copy is the reviewable source, not the live file; see README.md for installation.
#
# sshd runs this script for every session that authenticates with DOCS_DEPLOY_KEY, whatever the client
# asked for. $SSH_ORIGINAL_COMMAND is only CLASSIFIED into one of the fixed operations below; nothing
# from the client is executed, and the revision and run id are validated by shape before use. This key
# can therefore publish user guides from main and nothing else: no shell, no application deploy, no
# database access. The Access gate and backup evidence are not required (SOP-DEP-003): publishing
# changes no code, data or process.
#
# A formal release (guarded-deploy.sh) and a docs publish take the same lock, so they never interleave.
set -euo pipefail

RELEASE_GATE_DIR=/root/release-gate
LOCK="$RELEASE_GATE_DIR/deploy.lock"

fail() { echo "guarded-docs: $1" >&2; exit 1; }

[ -n "${SSH_ORIGINAL_COMMAND:-}" ] || fail "no command requested; this key does not grant an interactive shell"

read -r -a request <<< "$SSH_ORIGINAL_COMMAND"
case "${request[0]:-}" in
  transport-check)
    [ "${#request[@]}" -eq 1 ] || fail "transport-check takes no arguments"
    echo "docs transport ready on $(hostname)"
    exit 0
    ;;
  status)
    [ "${#request[@]}" -eq 1 ] || fail "status takes no arguments"
    exec python3 "$RELEASE_GATE_DIR/docs_publish.py" status
    ;;
  deploy)
    [ "${#request[@]}" -eq 3 ] || fail "usage: deploy <40-hex sha> <run id>"
    [[ "${request[1]}" =~ ^[0-9a-f]{40}$ ]] || fail "revision must be exactly 40 lowercase hex characters"
    [[ "${request[2]}" =~ ^[0-9]{1,20}$ ]] || fail "run id must be digits"
    exec 9>"$LOCK"
    flock -w 600 9 || fail "another release or docs publish holds $LOCK"
    python3 "$RELEASE_GATE_DIR/docs_publish.py" deploy "${request[1]}" "${request[2]}"
    ;;
  *)
    fail "unrecognized request; allowed: transport-check | status | deploy <sha> <run id>"
    ;;
esac

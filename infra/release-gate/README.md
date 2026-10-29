# Droplet-side release gate

Blocks `release-v2.yml`'s SSH calls to production unless the Cloudflare Access gate is actually
closed and a real, fresh, signed backup/restore evidence file exists — enforced by `sshd` itself, not
by anything in this repository. Background and rationale: `guarded-deploy.sh`'s header comment, and
`SOP-DEP-002` §VII.A. A second script, `guarded-ci.sh`, restricts the other production SSH key
(`DO_DEPLOY_KEY`) to the two unrelated operations it's actually used for — see its own header comment
and step 5 below for why that's part of the same gate, not a separate concern.

This exists because nothing on the GitHub side can be a real gate here: the repository has one
collaborator, and every session acting on the owner's behalf authenticates as that same account, with
a connector scope that cannot be narrowed further (confirmed 2026-10-29). A check that lives in
`release-v2.yml`, a repo secret, or a GitHub environment's required reviewers is editable or
satisfiable by the same identity it's meant to stop. A check enforced by `sshd` on the droplet, from a
file that `git reset --hard` never touches and that no PR can reach, is not.

**This gate needs its own SSH key, not the shared `DO_DEPLOY_KEY`.** `DO_DEPLOY_KEY` also
authenticates `login-notice.yml` and `tailscale-ssh-smoke-test.yml`, and `guarded-deploy.sh` only ever
recognizes `release-v2.yml`'s three exact command shapes — anything else is refused. Forcing
`guarded-deploy.sh` onto the existing `DO_DEPLOY_KEY` line would therefore also silently break those
two other workflows the moment it's installed. `release-v2.yml` was switched (alongside this install)
to a new, dedicated secret, `RELEASE_DEPLOY_KEY`.

**Restricting the new key is not enough on its own — `DO_DEPLOY_KEY` itself has to be restricted too.**
`DO_DEPLOY_KEY` is a repository secret: any workflow in this repository can use it, which means any
session able to edit a workflow (the same identity the whole gate exists to constrain, per the
background above) can point `release-v2.yml` back at `DO_DEPLOY_KEY`, or add a new workflow step that
uses it, and deploy with no gate at all — restricting only `RELEASE_DEPLOY_KEY` would leave that door
wide open. Before `DO_DEPLOY_KEY` had any forced command, this was already true of it in general: it
had unrestricted root access, not just access to the two things the workflows that use it actually
need. Step 6 below closes this by giving `DO_DEPLOY_KEY` its own forced command,
`guarded-ci.sh`, restricted to exactly the smoke test and the login-notice write/clear — a deploy
attempt sent over this key is refused there regardless of which workflow sent it.

## One-time install, on the droplet, as root

1. **Signing key, generated on the Mac mini, never on the droplet:**

   ```bash
   ssh-keygen -t ed25519 -f ~/cth-backup/evidence_signing_key -C cth-release-evidence -N ''
   ```

   The private key stays at `~/cth-backup/evidence_signing_key` and is never copied anywhere, including
   off-host backup storage. Only `prerelease.sh evidence` (run by hand from the Mac mini) uses it.

2. **Allowed signers file.** The public key only exists on the Mac mini (from step 1); the
   `allowed_signers` file it builds is consumed on the droplet. These are two different machines —
   run each part where it's labeled, not both on the droplet.

   **On the Mac mini**, copy the `.pub` file up:

   ```bash
   scp ~/cth-backup/evidence_signing_key.pub root@cth:/tmp/evidence_signing_key.pub
   ```

   **On the droplet, as root**, build `allowed_signers` from the file you just copied up, then remove it:

   ```bash
   install -d -m 0700 /root/release-gate /root/release-gate/evidence
   printf 'cth-release-evidence namespaces="cth-release" %s\n' "$(cut -d' ' -f1-2 < /tmp/evidence_signing_key.pub)" \
     > /root/release-gate/allowed_signers
   chmod 600 /root/release-gate/allowed_signers
   rm -f /tmp/evidence_signing_key.pub
   ```

   Only the public key ever crosses the network; the private key in step 1 never leaves the Mac mini.

3. **Both gate scripts**, copied by hand — not deployed, not symlinked. Do **not** `git pull` or
   `git reset` the droplet's `~/classroom-economy` checkout to get these files: that checkout is
   production app code, pinned to the last deployed revision by the release SOP, and advancing it
   outside a real release is exactly the kind of unreviewed change this gate exists to prevent. These
   files were added after the droplet's current deployed revision, so they may not even be present
   there yet.

   **On the Mac mini**, from this repo (make sure it's on `main`, post-merge of the PRs that added
   these files), copy both scripts up:

   ```bash
   scp infra/release-gate/guarded-deploy.sh infra/release-gate/guarded-ci.sh root@cth:/tmp/
   ```

   **On the droplet, as root**, install both from the copies and remove the copies:

   ```bash
   install -d -m 0700 /root/release-gate
   install -m 0700 -o root -g root /tmp/guarded-deploy.sh /root/release-gate/guarded-deploy.sh
   install -m 0700 -o root -g root /tmp/guarded-ci.sh /root/release-gate/guarded-ci.sh
   rm -f /tmp/guarded-deploy.sh /tmp/guarded-ci.sh
   ```

   The `install -d` is harmless to repeat if step 2 already created the directory. Re-run this step
   whenever either script changes in the repository; nothing does it automatically, by design.

4. **A dedicated SSH key for `release-v2.yml`, generated on the Mac mini, never on the droplet** — this
   is a different key from the evidence signing key in step 1, and different again from the shared
   `DO_DEPLOY_KEY`:

   ```bash
   ssh-keygen -t ed25519 -f ~/cth-backup/release_deploy_key -C cth-release-deploy -N ''
   ```

   **In GitHub**, add the private key as a new repository secret named `RELEASE_DEPLOY_KEY` (Settings →
   Secrets and variables → Actions → New repository secret; paste the full contents of
   `~/cth-backup/release_deploy_key`). `release-v2.yml` already points at this secret name.

   **On the droplet, as root**, append the public half as a brand-new line in
   `/root/.ssh/authorized_keys` — do not touch the existing `DO_DEPLOY_KEY` line or any other line, and
   put the forced-command prefix on it from the start, since nothing else will ever use this key. The
   line is the prefix below, a single space, then the *entire, unmodified contents* of
   `~/cth-backup/release_deploy_key.pub` (which already starts with `ssh-ed25519` — don't type that
   token again or it will be duplicated). Easiest done by copying the `.pub` file to the droplet and
   building the line there in one command:

   Mac mini:
   ```bash
   scp ~/cth-backup/release_deploy_key.pub root@cth:/tmp/release_deploy_key.pub
   ```

   Droplet, as root (back up the file first):
   ```bash
   cp /root/.ssh/authorized_keys /root/.ssh/authorized_keys.bak
   printf 'command="/root/release-gate/guarded-deploy.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty %s\n' \
     "$(cat /tmp/release_deploy_key.pub)" >> /root/.ssh/authorized_keys
   rm -f /tmp/release_deploy_key.pub
   ```

   The resulting line looks like:

   ```text
   command="/root/release-gate/guarded-deploy.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA... cth-release-deploy
   ```

5. **Restrict the existing `DO_DEPLOY_KEY` line too, on the droplet, as root.** This is not optional —
   see "Restricting the new key is not enough on its own" above. Find `DO_DEPLOY_KEY`'s line in
   `/root/.ssh/authorized_keys` (the one key `login-notice.yml` and `tailscale-ssh-smoke-test.yml` use;
   back the file up first, e.g. `cp /root/.ssh/authorized_keys /root/.ssh/authorized_keys.bak`) and
   prefix that line with:

   ```text
   command="/root/release-gate/guarded-ci.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty
   ```

   Keep everything after that prefix — key type, base64 blob, comment — exactly as it was. Don't touch
   the new `RELEASE_DEPLOY_KEY` line from step 4, or any other line.

6. **Verify before relying on either key.** From a shell that is NOT either key (your own login),
   confirm both lines look right and the rest of the file is unchanged, then:

   - Over the new `RELEASE_DEPLOY_KEY` (a manual `workflow_dispatch` of `release-v2.yml`, or `ssh -i
     ~/cth-backup/release_deploy_key root@cth '...'` with one of its three known commands): with no
     evidence uploaded yet and/or the gate open, any command should fail with `guarded-deploy: ...` on
     stderr. After a real `prerelease.sh backup && counts && restore && evidence <sha>` run with the
     gate closed, the same commands should succeed.
   - Over `DO_DEPLOY_KEY`: `login-notice.yml` and `tailscale-ssh-smoke-test.yml` should still work
     exactly as before (confirm with a real `workflow_dispatch` of each, or the equivalent `ssh`
     commands). A deploy-shaped command sent over this key — e.g. `ssh -i <DO_DEPLOY_KEY private key
     file> root@cth "RELEASE_REVISION='<40 hex chars>' bash -s"` — should fail with `guarded-ci: command
     does not match a known CI operation`, proving the loophole this closes is actually closed.

   Confirm all of this before the next scheduled release, not during one.

## What's deliberately not in this repository

`/root/release-gate/guarded-deploy.sh` and `/root/release-gate/guarded-ci.sh` (the installed copies),
`/root/release-gate/allowed_signers`, `~/cth-backup/evidence_signing_key` on the Mac mini, and
`~/cth-backup/release_deploy_key` (private half) on the Mac mini never appear in git — nor does the
`RELEASE_DEPLOY_KEY` secret value, which only GitHub and the Mac mini ever hold. The files in this repo
are the reviewable source for step 3 above, kept in sync by hand. If either drifts from what's actually
installed, the installed copy — not this file — is what's really protecting production; re-run step 3
after any change to either script.

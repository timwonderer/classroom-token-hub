# Droplet-side release gate

Blocks `release-v2.yml`'s SSH calls to production unless the Cloudflare Access gate is actually
closed and a real, fresh, signed backup/restore evidence file exists — enforced by `sshd` itself, not
by anything in this repository. Background and rationale: `guarded-deploy.sh`'s header comment, and
`SOP-DEP-002` §VII.A.

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
to a new, dedicated secret, `RELEASE_DEPLOY_KEY`; `DO_DEPLOY_KEY` and its line in `authorized_keys`
are untouched by anything below and keep working exactly as before.

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

3. **The gate script itself**, copied by hand — not deployed, not symlinked. Do **not** `git pull` or
   `git reset` the droplet's `~/classroom-economy` checkout to get this file: that checkout is
   production app code, pinned to the last deployed revision by the release SOP, and advancing it
   outside a real release is exactly the kind of unreviewed change this gate exists to prevent. This
   file was added after the droplet's current deployed revision, so it may not even be present there
   yet.

   **On the Mac mini**, from this repo (make sure it's on `main`, post-merge of the PR that added this
   file), copy the script up:

   ```bash
   scp infra/release-gate/guarded-deploy.sh root@cth:/tmp/guarded-deploy.sh
   ```

   **On the droplet, as root**, install it from the copy and remove the copy:

   ```bash
   install -d -m 0700 /root/release-gate
   install -m 0700 -o root -g root /tmp/guarded-deploy.sh /root/release-gate/guarded-deploy.sh
   rm -f /tmp/guarded-deploy.sh
   ```

   The `install -d` is harmless to repeat if step 2 already created the directory. Re-run this step
   whenever `guarded-deploy.sh` changes in the repository; nothing does it automatically, by design.

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
   put the forced-command prefix on it from the start, since nothing else will ever use this key:

   ```text
   command="/root/release-gate/guarded-deploy.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA... cth-release-deploy
   ```

   (Paste the actual public key from `~/cth-backup/release_deploy_key.pub` after `ssh-ed25519`, keeping
   the `cth-release-deploy` comment or whatever comment `ssh-keygen` generated, so a future read of this
   file can tell at a glance which key this line is.)

5. **Verify before relying on it.** From a shell that is NOT this key (your own login), confirm the new
   line was added correctly and the rest of the file is unchanged, then from somewhere that can use the
   new `RELEASE_DEPLOY_KEY` (a manual `workflow_dispatch` of `release-v2.yml`, or `ssh -i
   ~/cth-backup/release_deploy_key root@cth '...'` with one of its three known commands):

   - With no evidence uploaded yet and/or the gate open: any command over this key should fail with
     `guarded-deploy: ...` on stderr and a non-zero exit — including the harmless transport check.
   - After a real `prerelease.sh backup && prerelease.sh counts && prerelease.sh restore &&
     prerelease.sh evidence <sha>` run with the gate closed: the same commands should succeed.
   - `login-notice.yml` and `tailscale-ssh-smoke-test.yml`, which still use `DO_DEPLOY_KEY`, should be
     unaffected — this is worth confirming once, since they're the whole reason this key is separate.

   Confirm all of this before the next scheduled release, not during one.

## What's deliberately not in this repository

`/root/release-gate/guarded-deploy.sh` (the installed copy), `/root/release-gate/allowed_signers`,
`~/cth-backup/evidence_signing_key` on the Mac mini, and `~/cth-backup/release_deploy_key` (private
half) on the Mac mini never appear in git — nor does the `RELEASE_DEPLOY_KEY` secret value, which only
GitHub and the Mac mini ever hold. This file in the repo is the reviewable source for step 3 above,
kept in sync by hand. If it drifts from what's actually installed, the installed copy — not this file
— is what's really protecting production; re-run step 3 after any change here.

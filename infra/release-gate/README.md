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

3. **The gate script itself, on the droplet, as root** — copied by hand from the app checkout already
   on the droplet, not deployed, not symlinked:

   ```bash
   cd ~/classroom-economy/infra/release-gate
   install -m 0700 -o root -g root guarded-deploy.sh /root/release-gate/guarded-deploy.sh
   ```

   Re-run this `install` line whenever this file changes in the repository; nothing does it
   automatically, by design.

4. **The forced command, on the droplet, as root**, on the `DO_DEPLOY_KEY` line in
   `/root/.ssh/authorized_keys`. Find that line (it's the only key `release-v2.yml` uses) and prefix it:

   ```text
   command="/root/release-gate/guarded-deploy.sh",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA... do-deploy-key-comment
   ```

   Keep the rest of the line — the key type, the base64 blob, the comment — exactly as it was.

5. **Verify before relying on it.** From a shell that is NOT this key (your own login), confirm the
   key is still otherwise intact, then from somewhere that can use the deploy key:

   - With no evidence uploaded yet and/or the gate open: any command over this key should fail with
     `guarded-deploy: ...` on stderr and a non-zero exit — including the harmless transport check.
   - After a real `prerelease.sh backup && prerelease.sh counts && prerelease.sh restore &&
     prerelease.sh evidence <sha>` run with the gate closed: the same commands should succeed.

   Confirm both before the next scheduled release, not during one.

## What's deliberately not in this repository

`/root/release-gate/guarded-deploy.sh` (the installed copy), `/root/release-gate/allowed_signers`, and
`~/cth-backup/evidence_signing_key` on the Mac mini never appear in git. This file in the repo is the
reviewable source for step 3 above, kept in sync by hand. If it drifts from what's actually installed,
the installed copy — not this file — is what's really protecting production; re-run step 3 after any
change here.

---
title: "Part 3: Get CTH onto the server"
category: self-hosting
description: Download one exact Classroom Token Hub release onto the server and check it is the one you chose.
roles: [operator]
keywords: [self-hosting, tutorial, release, git, verify]
---

# Part 3: Get CTH onto the server

## 3.1 Choose a release

**What you're doing.** Picking the exact version of CTH you will install.

**Why.** The installer installs one exact commit and records it. You need to
know which one, so you can tell later what's running and what to upgrade from.

**Steps.**

1. Open the [Releases page](https://github.com/timwonderer/classroom-token-hub/releases)
   and pick a stable release that includes all the fixes below. Do this
   before Part 2 if you have not yet rented a server. See
   [which release this guide matches](before-you-begin.md#which-release-this-guide-matches).
2. Note its **tag**, such as `v2.5.0`.
3. Click the commit link on the release (a short code like `1d74ea8`). The
   commit page shows the **full 40-character SHA**.

Add to your note: **release tag** and **release SHA**.

**What you should see.** A tag beginning with `v`, and a SHA of exactly 40
characters using only `0`–`9` and `a`–`f`.

**If something looks wrong.** Don't use a branch such as `main` or a
pre-release for this tutorial. Branch names move; an exact commit SHA can
identify a rehearsal build, but it does not make it a supported release. If no
compatible release is published, wait rather than installing v2.4.5 with
instructions for newer code.

## 3.2 Download it to the server

**What you're doing.** Copying the chosen release onto the server, into
`/root/cth-installer`.

**Why.** The installer runs from this copy, and later stages copy the
application from it.

**Steps.** On **the server**, as root, replace `vX.Y.Z` with your tag:

```bash
apt-get update
apt-get install --no-install-recommends -y git ca-certificates
git clone --no-checkout https://github.com/timwonderer/classroom-token-hub.git /root/cth-installer
cd /root/cth-installer
git checkout --detach vX.Y.Z
```

**What you should see.** The clone reports objects being received. The
checkout ends with a message that you are in **"detached HEAD"** state. That's
normal: you're on one exact version, not on a branch.

**If something looks wrong.**

- **`destination path '/root/cth-installer' already exists`:** you've run this
  before. Look at what's there (`git -C /root/cth-installer log -1`) before
  doing anything else. Don't delete it to make the error go away.
- **`pathspec 'vX.Y.Z' did not match`:** you didn't replace `vX.Y.Z`, or the tag
  has a typo.

## 3.3 Check it's the version you chose

**What you're doing.** Confirming the server has exactly the commit from the
release page, with nothing changed.

**Why.** The installer runs as root, so whatever code it runs has full
control of the server. It also refuses to run from a copy that differs from
the SHA you'll record in Part 4.

**Steps.**

```bash
cd /root/cth-installer
git rev-parse HEAD
git status --porcelain --untracked-files=all
```

**What you should see.**

- `git rev-parse HEAD` prints a SHA **identical** to the release SHA in your
  note.
- `git status …` prints **nothing at all**.

**If something looks wrong.** If the SHA differs, stop, and check the tag and
the release page again. If `git status` prints anything, a file in the copy
was changed or added. Never edit files in `/root/cth-installer`; the
installer refuses a changed copy (`installer checkout must be clean`).

## Checkpoint

The release is on the server and verified. This is a safe place to stop.

**Next:** [Part 4: Describe your installation](part-4-describe-your-installation.md)

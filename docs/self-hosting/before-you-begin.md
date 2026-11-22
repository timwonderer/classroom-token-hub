---
title: Before you begin
category: self-hosting
description: Skills, accounts, budget and the services a self-hosted Classroom Token Hub needs.
roles: [operator]
keywords: [self-hosting, prerequisites, requirements, Cloudflare, Turnstile, passkeys]
---

# Before you begin

Read this page before you spend any money. It tells you what you need and
which choices are yours to make.

## Skills

You should be comfortable:

- opening a terminal (Terminal on a Mac, Windows Terminal or PowerShell on Windows)
- copying a command, changing the parts the guide tells you to change, and pressing Enter
- reading what the command printed and comparing it with what the guide says you should see
- keeping passwords and keys in a password manager

You don't need to know Linux, Python or databases. The [terms page](terms.md)
explains every technical word, and [Good to learn](good-to-learn.md) lists
background reading if you want it.

## Which release this guide matches

This guide describes the installer as it is after the fixes from the
November 2026 staging trial. Those fixes are on `main` but are **not yet in a
published release**: the newest release, v2.4.5, predates them. Wait for the
first release published after 22 November 2026, then use the newest release
on the [Releases page](https://github.com/timwonderer/classroom-token-hub/releases).
[Part 3](part-3-get-cth.md) shows how to select it.

## What is required and what is recommended

Some services below are choices, but the current installer still requires
them. This list keeps the two apart, so you know which choices are really open
today.

### Required by the current release

| What | Why | Notes |
| --- | --- | --- |
| A server running **Ubuntu 22.04 LTS, x86-64** | The installer checks for exactly this and refuses anything else. | Any provider works. This guide uses DigitalOcean only as a labelled example. Use a new, empty server for CTH alone. |
| A **domain name** you control | Your CTH needs its own web address. | A subdomain of a domain you already own is fine, for example `classroom.example.org`. |
| **Cloudflare Turnstile** keys | CTH uses Turnstile to stop bots on sign-up and sign-in pages. It refuses to start in production without it. | Turnstile is free and works for any domain. |
| **Cloudflare** in front of the server (proxy and Access) | The installer's only network setup is "Cloudflare proxy": it accepts web traffic only from Cloudflare, and checks that Cloudflare Access protects the teacher login. | The project recommends Cloudflare anyway (see below). Support for other setups is tracked in [#1792](https://github.com/timwonderer/classroom-token-hub/issues/1792). |
| **Passwordless.dev** keys | The installer won't accept a configuration without them. | In the app itself, passkeys are optional. Making the installer match is tracked in [#1791](https://github.com/timwonderer/classroom-token-hub/issues/1791). |
| An **authenticator app** (for example 2FAS, Aegis, Google Authenticator or 1Password) | Every teacher account uses a six-digit code (TOTP) at sign-in. | Install it on your phone before Part 6. |

### Strongly recommended, with alternatives

**Cloudflare proxy and Access.** The project recommends these even once
other options exist:

- Your server's address stays hidden behind Cloudflare, and the firewall
  accepts web traffic only from Cloudflare.
- **Cloudflare Access** puts an extra sign-in (an email code) in front of the
  teacher pages. Strangers can't even reach your teacher login. While you
  set up, it can hide the whole site.
- Cloudflare's free plan covers this.

*Alternative, not available yet:* serve traffic directly with your own
certificate and no Access gate. You'd skip a third-party service, but lose
the hidden origin and the extra gate in front of teacher sign-in. The current
installer can't do this; see [#1792](https://github.com/timwonderer/classroom-token-hub/issues/1792).

**Passkeys through Passwordless.dev.** Passkeys let teachers and students sign
in with a fingerprint, face or device PIN instead of typing a password.

- They're harder to phish than passwords, and students find them easier.
- Passwordless.dev handles the cryptography and has a free tier.

*Alternatives, not available yet:*

- **No passkeys at all.** Simpler, one fewer account; everyone signs in with
  passwords and codes. The app supports this, but the installer doesn't yet:
  [#1791](https://github.com/timwonderer/classroom-token-hub/issues/1791).
- **A different passkey provider,** or passkeys built into CTH itself. Not
  supported yet: [#1793](https://github.com/timwonderer/classroom-token-hub/issues/1793).

## Your computer

- **An SSH key.** You'll use it to log in to the server. If you don't have
  one, [GitHub's guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
  shows how to make one. Give it a passphrase.
- **For backups (Part 7):** about 1 GB of free disk space, and later the
  `age` encryption tool and PostgreSQL 14 client tools. Part 7 explains how to
  install them.

## Budget and billing

See the [cost table on the welcome page](README.md#time-and-cost). Two things
catch people out:

- **Billing runs until the server is destroyed.** A powered-off server is
  still billed. If you stop partway through this guide for more than a few
  days, decide whether to keep paying or to destroy the server and start Part 2
  again later.
- **Backups and snapshots** at your provider usually cost extra. The backups in
  Part 7 go to your own computer instead.

## Privacy and your students

Your server will hold student names and classroom records. You are
responsible for them: keep keys private, keep backups encrypted, and follow
your school's rules on student data. Never paste a key, a password, a student
name or a full log into a public issue or chat.

**Next:** [Terms you'll see](terms.md)

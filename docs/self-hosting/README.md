---
title: Run your own Classroom Token Hub
category: self-hosting
description: A step-by-step tutorial for teachers who want a private Classroom Token Hub on their own server.
roles: [operator]
keywords: [self-hosting, tutorial, getting started, install, server]
---

# Run your own Classroom Token Hub

This guide walks you through running your own private copy of Classroom Token
Hub (CTH) on a server you rent. It is written for someone who can follow
directions in a terminal and is willing to learn, but has never run a server
before. You don't need to be a programmer.

## What "self-hosting" means

Normally a teacher signs up on the project's hosted site. Self-hosting means
you rent your own server instead and install CTH on it. You become the
**operator**: you own the server, the web address, the passwords and keys, and
the backups. Your installation has its own classroom data, but you still rely
on your hosting and authentication providers. You are responsible for access,
maintenance and recovery; the project does not administer your server for you.

**Start with a practice installation using made-up students.** The installer
is for a new server. Upgrades and recovery onto a replacement server still
need experienced help. Check [release compatibility and current limits](before-you-begin.md#which-release-this-guide-matches)
before renting anything.

## What you'll have at the end

- A private CTH at your own web address, for example `https://classroom.example.org`.
- Your own teacher account, protected by an authenticator app.
- A class with at least one student who has claimed their account.
- A routine for backups, a tested restore, and a plan for upgrades and shutting down.

## Time and cost

| | Rough figure |
| --- | --- |
| Your time | Allow several sessions for setup, DNS changes, first-use checks and a backup restore. These are planning estimates, not measured first-time completion times. Pause at the checkpoints. |
| Server | The recorded rehearsal used 2 vCPUs, 4 GB memory and 120 GB disk, quoted at **$0.048/hour**. The original 80 GB reference plan was a different configuration. Compare the current price and billing terms before creating a server; see the [rehearsal record](rehearsal-findings.md). |
| Domain name | Usually $10–$20 a year. |
| Other services | Check the current plan limits for Cloudflare and Passwordless.dev against your expected users and usage. Budget separately for backup storage and any paid monitoring. |

> [!WARNING]
> On DigitalOcean, a server costs money **until you destroy it**; turning it
> off does not stop the bill. Other providers have their own billing rules. See
> [DigitalOcean billing](https://docs.digitalocean.com/products/droplets/details/pricing/). [Part 8](part-8-shut-down.md) shows how to shut
> everything down.

## How the installation works

CTH ships with an installer, `infra/self-hosting/install.py`. It sets up the
server in ten **stages**, and you run them one at a time, in order:

`host` → `postgres` → `redis` → `release` → `config` → `database` → `services` → `scheduler` → `ingress` → `readiness`

After every stage the installer checks its own work and either prints
`"result": "ok"` or stops with a message naming what is wrong. Each finished
stage is a **safe stop point**: you can close the terminal, go home, and carry
on tomorrow. If a stage fails, you stop and look before doing anything else.
The guide tells you how.

Run and check one stage at a time so you can identify where a failure
occurred. The installer does not provide an unattended teacher setup flow.

## The tutorial

**Before you start**

1. [Before you begin](before-you-begin.md): skills, accounts, budget, and what is required versus recommended
2. [Terms you'll see](terms.md): short definitions of common technical terms
3. [Good to learn](good-to-learn.md): optional background reading

**The eight parts**

1. [Part 1: Accounts and a domain](part-1-accounts-and-domain.md)
2. [Part 2: Create and secure the server](part-2-create-the-server.md)
3. [Part 3: Get CTH onto the server](part-3-get-cth.md)
4. [Part 4: Describe your installation](part-4-describe-your-installation.md)
5. [Part 5: Install one stage at a time](part-5-install-stages.md)
6. [Part 6: First use](part-6-first-use.md)
7. [Part 7: Keep it running](part-7-keep-it-running.md)
8. [Part 8: Shut it down](part-8-shut-down.md)

**When something goes wrong:** [Troubleshooting](troubleshooting.md)

Every step in Parts 1–8 follows the same pattern: **What you're doing**,
**Why**, **Steps**, **What you should see**, and **If something looks wrong**.

## Reference

The tutorial links to these pages when you need more detail. You don't need to
read them first.

**Operator reference**

- [Handbook overview](handbook-overview.md): what the application needs and which integrations are optional
- [Configuration dictionary](configuration.md): every field in the installation manifest and runtime file
- [Installer reference](reference-installation.md): the installer's contract, stage by stage
- [Fresh database](fresh-database.md): how the database stage installs and verifies the schema
- [Operations](operations.md): first-use checks, monitoring, backups, upgrades and decommissioning in full

**Maintainers only, not the teacher path**

These pages describe how the project's maintainers rehearse releases. You
don't need them to run your own CTH.

- [Phase C staging plan](phase-c.md)
- [Rehearsal findings](rehearsal-findings.md)
- [Attended staging workflow](staging-controller.md)
- [Staging guest bootstrap](staging-bootstrap.md)

## License

CTH is distributed under the PolyForm Noncommercial License 1.0.0. Read
`LICENSE` in the release you install before you use or share it, and keep the
required notices. [License terms](https://github.com/timwonderer/classroom-token-hub/blob/main/LICENSE)

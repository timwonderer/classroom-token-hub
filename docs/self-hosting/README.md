---
title: Run your own Classroom Token Hub
category: self-hosting
description: A step-by-step tutorial for teachers who want a private Classroom Token Hub on their own server.
roles: [operator]
keywords: [self-hosting, tutorial, getting started, install, server]
---

# Run your own Classroom Token Hub

You can learn to run CTH without having taught computer science or managed a
server before. This guide assumes you're comfortable learning a new tool,
following a sequence and checking your results. It explains the unfamiliar
parts as you reach them. You can work with an AI agent, too.

By the end, you should be able to answer three questions: **What did I just
change? How do I know it worked? What should I do if it didn't?** Copying a
command is one part of the work; understanding those answers is what lets you
keep the site running.

## What "self-hosting" means

Normally a teacher signs up on the project's hosted site. Self-hosting means
you rent your own server instead and install CTH on it. You become the
**operator**: the person responsible for the server, web address, passwords,
keys and backups. Your installation has its own classroom data, but you still rely
on your hosting and authentication providers. You are responsible for access,
maintenance and recovery; the project does not administer your server for you.

**Start with a practice installation using made-up students.** It gives you a
place to learn installation, backups and recovery before classroom records
depend on it. Check [release compatibility and current limits](before-you-begin.md#which-release-this-guide-matches)
before renting anything. A clearer guide can't supply a missing compatible release.

> [!TIP]
> **Using an AI agent?** Start with [Working with an AI agent](working-with-an-agent.md).
> It includes a setup prompt and prompts for troubleshooting, upgrades and
> recovery. An agent can explain and carry out steps within the access you give
> it. Keep the passwords and student records out of the conversation.

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

You don't need to learn all ten names now. Here's what the stages accomplish:

| Stages | What changes | What you check |
| --- | --- | --- |
| `host`, `postgres`, `redis` | Prepare the server and its data storage. | The required software and private storage services are ready. |
| `release`, `config`, `database` | Install your chosen CTH version, read its settings and create its database tables. | The version, settings and database structure agree. |
| `services`, `scheduler` | Start CTH and its timed work, including payroll. | The app answers locally and exactly one scheduler owns the timed jobs. |
| `ingress`, `readiness` | Enable the HTTPS connection and check the running installation. | The server checks pass; you still need the browser checks in Part 6. |

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

Work through one numbered section at a time. Each explains the purpose,
gives the action, shows what success looks like and offers a next step if the
result differs. **Checkpoints are decisions:** continue, pause with your place
recorded, or investigate. You don't need to finish in one sitting.

A **Tip** helps you work. A **Warning** names a consequence you need before
acting. A **Caution** marks a step that can erase data. The words carry the
meaning even if your reader doesn't show colored callouts.

## Reference

The tutorial links to these pages when you need more detail. You don't need to
read them first.

**Operator reference**

- [Handbook overview](handbook-overview.md): what the application needs and which integrations are optional
- [Configuration dictionary](configuration.md): every field in the installation manifest and runtime file
- [Installer reference](reference-installation.md): the installer's contract, stage by stage
- [Fresh database](fresh-database.md): how the database stage installs and verifies the schema
- [Operations](operations.md): detailed operational checks and the boundaries behind them
- [Working with an AI agent](working-with-an-agent.md): copyable prompts and how to evaluate its work
- [Upgrade your CTH](upgrades.md): prepare, rehearse, switch versions and recover from a failed upgrade
- [Recover onto a replacement server](recovery.md): restore matching data and keys, verify them and change the web address

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

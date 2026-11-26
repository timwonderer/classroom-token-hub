---
title: Before you begin
category: self-hosting
description: Skills, accounts, budget and the services a self-hosted Classroom Token Hub needs.
roles: [operator]
keywords: [self-hosting, prerequisites, requirements, Cloudflare, Turnstile, passkeys]
---

# Before you begin

Think of this page as deciding whether the project fits your time and budget.
The learning is part of the project. You can learn the server tools while
using them; you don't have to take a separate course before starting.

**Before spending:** confirm a compatible CTH release exists, choose where to
keep your passwords, and plan a practice installation. Real student data comes
after you've tested both sign-in and recovery.

Read this page before you spend any money. It tells you what you need and
which choices are yours to make.

## Skills

You should be comfortable:

- opening a terminal (Terminal on a Mac, Windows Terminal or PowerShell on Windows)
- copying a command, changing the parts the guide tells you to change, and pressing Enter
- reading what the command printed and comparing it with what the guide says you should see
- keeping passwords and keys in a password manager

You don't need to know Linux, Python or databases. The [terms page](terms.md)
explains common technical terms, and [Good to learn](good-to-learn.md) lists
background reading if you want it.

## Which release this guide matches

**Supported fresh-install release:** [v2.5.0](https://github.com/timwonderer/classroom-token-hub/releases/tag/v2.5.0)

Two release names matter, and they can differ:

| Name | What it is | Where to find it |
| --- | --- | --- |
| **Supported fresh-install release** | The tagged release this handbook and its fresh-install database bundle were validated against. Every new installation starts from it. | The line above, the project README, and `migrations/fresh/supported_release.json` in the repository, which is the authoritative declaration; CI checks that all three agree. |
| **Latest stable release** | The newest published stable version of CTH. | The [Releases page](https://github.com/timwonderer/classroom-token-hub/releases) and the project README |

**Install the supported fresh-install release, then upgrade.** Parts 3 to 6
install the supported fresh-install release exactly and check it with practice
data. Once Part 7's backup and restore drill passes, and **before real students
join**, follow the [upgrade walkthrough](upgrades.md) to the latest stable
release. If the two are the same, there is nothing to upgrade. With only
practice data in it, the installation is at its safest point for a first
upgrade.

Install no other release from scratch. A release that isn't the supported
fresh-install release has no validated fresh-install bundle in this guide, and
the database stage refuses a checkout whose release has no bundle. Do not use a
branch such as `main`, a pre-release, or an untagged commit. Testing an exact
unreleased commit is a separate maintainer rehearsal.

**If the supported release becomes unsafe.** The supported fresh-install release
must stay a safe place to start, even briefly. If a security defect makes it
unsafe to run even until the upgrade, the project either advances the supported
release or suspends these installation instructions and says so here and in the
README. Do not start an installation while a suspension notice is shown.

**Plan for ongoing care.** You'll renew the HTTPS certificate, check security
updates and keep usable backups. Part 7 explains those jobs. [Upgrades](upgrades.md)
and [replacement-server recovery](recovery.md) have their own guided procedures,
with prompts for an AI agent. They explain the work rather than assuming you
already know the tools.

Database backup and restore have been exercised in production;
[Part 7](part-7-keep-it-running.md#74-test-that-a-backup-restores) explains which
evidence applies to its manual drill. The expanded upgrade and replacement
procedures still need a complete rehearsal on this installation layout. Use
them with fictional data first; reading a procedure isn't a completed test.
Certificate renewal in this tutorial is manual.

**Database support.** This installer pins PostgreSQL 14.24 from Ubuntu
22.04. As checked on November 22, 2026, Ubuntu publishes
`14.24-0ubuntu0.22.04.1` in Jammy's `main` security channel. Ubuntu 22.04
standard security maintenance runs through May 2027. That is separate from
PostgreSQL 14's upstream end of life on November 12, 2026. Keep Ubuntu security
updates enabled; an exact-version installer check is not a reason to downgrade.
A major-version migration remains tracked in [#1773](https://github.com/timwonderer/classroom-token-hub/issues/1773).
Do not substitute a different major in this tutorial or assume Ubuntu coverage
applies to Homebrew, Docker or third-party packages.
[Ubuntu package](https://packages.ubuntu.com/jammy/amd64/postgresql-14) ·
[Ubuntu maintenance schedule](https://ubuntu.com/about/release-cycle) ·
[PostgreSQL version policy](https://www.postgresql.org/support/versioning/)

## What is required and what is recommended

Here's what each service does. You will create the accounts in Part 1; this
page helps you decide whether you want to use this arrangement.

| Name you'll encounter | Its job in your installation |
| --- | --- |
| Ubuntu | The server's operating system, serving the role Windows or macOS serves on your computer. |
| Flask and Python | The framework and language CTH is built with. The installer sets them up; you aren't asked to write an application. |
| PostgreSQL, often shortened to Postgres | Stores the lasting records: classes, accounts, transactions and history. |
| Redis | Holds short-lived setup information and request counters. It serves a different purpose from the database. |
| nginx (pronounced “engine-x”) | Receives web connections on the server and passes them to CTH. |
| Cloudflare proxy | Receives visitors' connections before they reach your server. |
| Turnstile | Checks for automated abuse on sign-up and sign-in pages. This is a separate Cloudflare service. |
| Passwordless.dev | Supplies the passkey integration. Its keys are currently required by the installer. |

Some integrations are optional in the application but required by this
installer. The tables below name those limits; they aren't choices you can
change by leaving out a step.

### Required by the current release

| What | Why | Notes |
| --- | --- | --- |
| A server running **Ubuntu 22.04 LTS, x86-64** | The installer checks for exactly this and refuses anything else. | Any provider works. This guide uses DigitalOcean only as a labelled example. Use a new, empty server for CTH alone. |
| A **domain name** you control | Your CTH needs its own web address. | A subdomain of a domain you already own is fine, for example `classroom.example.org`. |
| **Cloudflare Turnstile** keys | CTH uses Turnstile to stop bots on sign-up and sign-in pages. It refuses to start in production without it. | Turnstile is free and works for any domain. |
| **Cloudflare proxy** in front of the server | The installer's only network setup is "Cloudflare proxy": the server accepts web traffic only from Cloudflare. | The project recommends the proxy anyway (see below). Support for other setups is tracked in [#1792](https://github.com/timwonderer/classroom-token-hub/issues/1792). |
| **Passwordless.dev** keys | The installer won't accept a configuration without them. | In the app itself, passkeys are optional. Making the installer match is tracked in [#1791](https://github.com/timwonderer/classroom-token-hub/issues/1791). |
| An **authenticator app** (for example 2FAS, Aegis, Google Authenticator or 1Password) | Every teacher account uses a six-digit code (TOTP) at sign-in. | Install it on your phone before Part 6. |

### Strongly recommended, with alternatives

**Cloudflare proxy.** The project recommends it even once other options exist:

- Public DNS answers point to Cloudflare, and the firewall accepts web
  traffic only from Cloudflare. This does not guarantee that nobody can
  discover the origin address; the firewall is still necessary.
- Cloudflare's free plan covers it.

*Alternative, not available yet:* serve traffic directly with your own
certificate. You'd skip a third-party service, but lose the hidden origin.
The current installer can't do this; see [#1792](https://github.com/timwonderer/classroom-token-hub/issues/1792).

**Passkeys through Passwordless.dev.** Passkeys let teachers and students sign
in with a fingerprint, face or device PIN instead of typing a password.

- They're harder to phish than passwords, and students find them easier.
- Passwordless.dev handles the cryptography and has a free tier.

*Alternatives, not available yet:*

- **No passkeys at all.** Simpler, one fewer account; everyone signs in with
  their existing username and TOTP (teachers), or PIN/passphrase flows
  (students). The app supports this, but the installer doesn't yet:
  [#1791](https://github.com/timwonderer/classroom-token-hub/issues/1791).
- **A different passkey provider,** or passkeys built into CTH itself. Not
  supported yet: [#1793](https://github.com/timwonderer/classroom-token-hub/issues/1793).

### Optional

**Maintenance mode with Cloudflare Access.** Access can close your site to
everyone but you while you work on it, behind an email-code sign-in. It's not
part of the installation. [Part 7](part-7-keep-it-running.md#710-optional-maintenance-mode-with-cloudflare-access)
shows how to set it up if you want it.

**Status page and monitoring providers.** You do not need a Google Cloud
account, Cloud Run, Firestore, Loki, Grafana or a public status page to install
and use CTH. You can start with the local health checks in Part 6 and choose an
external uptime monitor separately. A monitor that reaches the login page does
not prove that student claims or payroll work.

The repository's separate status service uses Google Cloud and Firestore;
those are dependencies of that implementation, not prerequisites for hosting
the classroom app. Replacing its storage is development work, not a provider
setting. Do not deploy the bundled status service unchanged: it contains
hosted-service targets and defaults. See [status boundaries](handbook-overview.md#installation-and-integration-boundaries).

**Other choices.** DigitalOcean, its region and CPU vendor are examples. A
separate marketing site, a GitHub fork, GitHub Actions, a pull request and a
second paid staging server are not required. HTTPS, protected keys, backups
and correct classroom access remain necessary regardless of provider.

## Your computer

- **An SSH key.** You'll use it to log in to the server. If you don't have
  one, [GitHub's guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
  shows how to make one. Give it a passphrase.
- **If SSH keys are new to you:** the public key goes into your server
  provider's dashboard; the private key stays on your computer. This key pair
  logs you into the server. It is separate from CTH sign-in and backup keys.
- **For backups (Part 7):** space for encrypted archives and a restored copy
  of the database. Start with several GB for a small practice installation;
  actual needs grow with your data. You will install `age` and PostgreSQL 14
  server and client tools for an isolated restore drill.
- **On Windows:** Part 7 uses a Linux shell in WSL. Set it up before you need
  a backup, and verify SSH from that shell; it has its own SSH configuration.

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

---
title: Terms you'll see
category: self-hosting
description: Plain-language definitions of the server and Classroom Token Hub terms used in the self-hosting tutorial.
roles: [operator]
keywords: [self-hosting, glossary, terms]
---

# Terms you'll see

You don't need to memorize these. The walkthrough explains terms where you
use them; this page is a place to look one up again. If a term still leaves
you unsure what to do, ask an agent to connect it to your current step using
[this explanation prompt](working-with-an-agent.md#when-you-dont-understand-a-step).

## General terms

| Term | What it means here |
| --- | --- |
| **Server** | A computer in a data centre that you rent and control over the internet. Providers also call it a VPS, droplet, instance or VM. |
| **Provider** | The company you rent the server from, such as DigitalOcean, Hetzner, Linode or Vultr. |
| **Terminal** | A window where you type commands instead of clicking. |
| **SSH** | "Secure shell": the way your terminal connects to the server. `ssh root@203.0.113.10` opens a terminal on the server. |
| **SSH key** | A pair of files on your computer that proves who you are to the server, instead of a password. You give the server the *public* half. |
| **Host key** and **fingerprint** | The server's own identity. The first time you connect, SSH shows its fingerprint. You compare it with what the server shows in your provider's web console, so you know you reached your server and not an impostor. |
| **Web console** | A terminal in your provider's website. Some use SSH and obey its firewall rules; a separate recovery console may work when SSH does not. |
| **root** | The all-powerful administrator account on the server. The installer must run as root. |
| **IP address** | The server's numeric internet address, such as `203.0.113.10`. |
| **Hostname**, **domain**, **subdomain** | For `classroom.example.org`, `example.org` is the domain and `classroom` identifies a subdomain. The complete site name is its hostname. Enter `https://` only where the guide asks for a full URL or origin. |
| **Origin** | Depending on context, your actual server behind Cloudflare, or a browser origin such as `https://classroom.example.org` (scheme plus host, and a port if explicitly specified). The guide says which meaning applies. |
| **Registrar** / **nameserver** | The registrar is where you buy a domain. Its nameserver settings choose who manages the domain's DNS records. |
| **Port** | A numbered connection point. This guide uses 22 for SSH and 443 for HTTPS. Opening a port allows that kind of connection, subject to the firewall's source rules. |
| **TXT record** | A DNS entry holding text. Certbot asks you to publish a particular value to prove control of the hostname. |
| **DNS** and **A record** | DNS is the internet's address book. An *A record* says "this name, such as `classroom.example.org`, lives at this IP address". |
| **Proxy** | A service that receives visitors' traffic and passes it on. With Cloudflare as a proxy, visitors talk to Cloudflare, and Cloudflare talks to your server. |
| **TLS certificate** | The file that makes `https://` work and proves your site's name to browsers. It comes with a private **key** that must stay secret. |
| **Let's Encrypt** | A free certificate authority. Its `certbot` tool issues certificates. |
| **Firewall** | Rules that say which traffic may reach the server, such as "SSH only from my address, HTTPS only from Cloudflare". |
| **Package** / **apt** | Ubuntu installs software as packages. `apt-get install` installs them. |
| **systemd** and **service** | systemd starts programs when the server boots and restarts them if they crash. Each program it runs is a *service* (or *unit*), such as `cth-web.service`. |
| **journal** / **journalctl** | systemd's log. `journalctl -u cth-web.service` shows one service's messages. |
| **venv** | A Python "virtual environment": a private folder holding the exact Python libraries one release of CTH needs. |
| **Schema** / **table** | The database's structure and its organized groups of records. CTH's schema contains tables for classes, accounts and transactions, among others. |
| **Migration** / **Alembic revision** | A versioned change to the database structure. Alembic tracks which changes have been applied; its revision identifier is separate from the application's release SHA. |
| **Dump** / **restore** | A dump is a saved database copy; a restore loads that copy into a database. Restore drills in this guide use a separate target. |
| **Socket** / **loopback** | A local connection path. A Unix socket is addressed by a filesystem path; loopback uses `127.0.0.1`. Both let programs communicate inside one computer without a public connection. |
| **Permission** / **mode** | Rules for which system accounts can read, write or run a file. `600 root root` means only root can read and write that file. |
| **Shell variable** | A value saved in the current terminal, such as `manifest=/etc/cth/installation.json`. `$manifest` uses that value. Set it again after reconnecting. |
| **PostgreSQL** | The database that holds all of CTH's real data: accounts, classes, transactions. |
| **Redis** | A small, fast in-memory store. CTH runs two private copies: one counts requests to stop abuse, the other holds short-lived data while a student claims an account. |
| **Git**, **commit**, **SHA**, **tag** | Git tracks versions of the code. Each version is a *commit*, named by a 40-character *SHA*. A *tag* such as `v2.4.5` is a readable name pointing at one commit. |
| **TOTP** | The six-digit codes from an authenticator app that change every 30 seconds. |
| **Passkey** | A sign-in that uses your device's fingerprint, face or PIN instead of a password. |

## Classroom Token Hub terms

| Term | What it means here |
| --- | --- |
| **Operator** | You: the person who runs the server. Running the server doesn't put you inside anyone's class; you use CTH by signing up as a teacher like anyone else. |
| **Class** | One classroom economy, such as "Period 3 Economics". Everything inside it is kept separate from every other class. |
| **Seat** | A student's place in one class. A teacher adds seats to the roster, and a student *claims* one. One student can hold seats in several classes. |
| **Join code** | A short code for a class. Students type it when they claim their seat. It's not a password and grants nothing on its own. |
| **Teacher account** | Created at `/admin/signup`. Signs in with a username and a TOTP code, or with a passkey once one is added. |
| **Student account** | Created when a student claims a seat at `/student/claim-account` and sets a PIN and passphrase. |
| **Installation manifest** | A small file, `/etc/cth/installation.json`, that describes *this* installation: its ID, the server's identity, the release, the web address and where the other files live. |
| **Runtime file** | `/etc/cth/runtime.env`: the private settings and secret keys the app reads when it starts. |
| **Stage** | One of the installer's ten steps: `host`, `postgres`, `redis`, `release`, `config`, `database`, `services`, `scheduler`, `ingress`, `readiness`. |
| **apply** / **check** | `apply` performs a stage and then checks it. `check` only checks, and changes nothing. |
| **Stage journal** | The installer's record of which stages are finished, in `/var/lib/cth-installer/`. It stops you running stages out of order. Never edit or delete it. |
| **Access gate** | Optional. Cloudflare Access used as **maintenance mode**: while it is up, the site is closed to everyone except you, the operator, who passes it with a one-time code sent to your email. |
| **Audit chain** | A tamper-evident record linking protected changes. Verifying the complete chain helps show records weren't silently changed; an ordinary service log isn't the same check. |
| **Cutover** / **rollback** | Cutover switches users to a different server or application version. Rollback returns to a previous version when it remains compatible with the database. |
| **Release** | A published, numbered version of CTH, such as v2.4.5, pointing at one exact commit. |

**Next:** [Good to learn](good-to-learn.md), or go straight to [Part 1](part-1-accounts-and-domain.md).

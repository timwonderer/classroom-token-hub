---
title: "Part 5: Install one stage at a time"
category: self-hosting
description: Run the Classroom Token Hub installer's ten stages in order, check each one, and handle a failed stage safely.
roles: [operator]
keywords: [self-hosting, tutorial, install, stages, installer]
---

# Part 5: Install one stage at a time

The installer has ten stages. You run them **one at a time, in order**. Each
one takes from a few seconds to a few minutes. The whole part takes about an
hour, most of it waiting.

## 5.0 How every stage works

**Before each session.** Log in as root, then run:

```bash
cd /root/cth-installer
manifest=/etc/cth/installation.json
```

Every stage command uses `$manifest`, so run these two lines again whenever
you open a new SSH session.

**Running a stage.** `apply` performs the stage and then checks its own work.
`check` only checks, and changes nothing. You can run
`python3 infra/self-hosting/install.py check STAGE --config "$manifest"` for any
finished stage, at any time.

**A stage succeeded** when it prints one line ending in `"result": "ok"`:

```text
{"installation_id": "…", "release_sha": "…", "stage": "host", "action": "apply", "result": "ok"}
```

Only then move on. Each finished stage is a **safe stop point**.

**A stage failed** when it prints the stage name, a colon and a message, such
as `redis: service account cannot reach Redis socket`. Then:

1. **Stop.** Don't start the next stage, and don't change the manifest, the
   runtime file or anything under `/var/lib/cth-installer`.
2. Read the message and look it up in that stage's **If something looks
   wrong**, then in [Troubleshooting](troubleshooting.md).
3. Fix the cause, then run **the same `apply` again**.

> [!IMPORTANT]
> Running a failed stage's `apply` a second time **does not redo its work**.
> It only checks whether the stage's results are now all in place. If they
> are, the stage is recorded as done; if not, it fails again and names what's
> missing. So a second `apply` is safe, but it won't repair anything by
> itself. Repeating it in the hope that it works only wastes time.

If you can't work out how to fix a stage, you can always start again on a
clean server: see [Starting over](#starting-over).

## 5.1 host: system packages and accounts

**What you're doing.** Installing the system software CTH needs and creating
its service accounts.

**Why.** It installs PostgreSQL 14, Python 3.10, two Redis services and nginx,
all from Ubuntu's own package archive, plus three locked-down accounts
(`cthapp`, `cthowner`, `cthrate`) that run CTH without root powers. It also
creates `/opt/cth`, where releases will live. It first checks this really is
the empty Ubuntu 22.04 server named in your manifest.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply host --config "$manifest"
```

**What you should see.** A few minutes of silence, then `"stage": "host"` …
`"result": "ok"`.

**If something looks wrong.**

| Message | What it means |
| --- | --- |
| `machine identity mismatch` | The manifest's `machine_id` isn't this server's. Did you rebuild the server? See [Starting over](#starting-over). |
| `expected Ubuntu 22.04` or `expected Ubuntu x86-64` | Wrong image. Create a new Ubuntu 22.04 x86-64 server. |
| `installation path already exists`, `service identity already exists`, `unexpected existing service unit`, `existing listening socket on a reference host port` | This server isn't empty: something was installed before. Use a fresh server. |
| `trusted APT candidate must be PostgreSQL 14.24` | Ubuntu has moved on to a newer PostgreSQL 14 package than this release expects. Your server is fine; the release needs updating. Report it, and see [Troubleshooting](troubleshooting.md#postgresql-package-version). |
| `first operation must apply host on a fresh target` | You ran `check` (or another stage) before applying `host`. |

## 5.2 postgres: the database

**What you're doing.** Creating CTH's two database roles and an empty
database, `cth_reference`.

**Why.** `cthowner` owns the database structure; `cthapp`, which the running
app uses, can read and write data but can't change the structure. The empty
database is labelled with your installation ID, so a later stage can't install
into a database that belongs to something else.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply postgres --config "$manifest"
```

**What you should see.** `"stage": "postgres"` … `"result": "ok"` within seconds.

**If something looks wrong.** `foreign database present` or `foreign login
present` means PostgreSQL already holds someone else's data. Stop: this isn't
a fresh server.

## 5.3 redis: two private Redis services

**What you're doing.** Starting two small Redis services that only CTH can reach.

**Why.** One (`cth-rate-limit`) counts requests so the app can slow down
attackers. The other (`cth-student-setup`) briefly holds data while a student
claims an account. It is memory-only: it never writes to disk, so that
short-lived data disappears on restart.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply redis --config "$manifest"
```

**What you should see.** `"stage": "redis"` … `"result": "ok"`. The stage
waits up to 25 seconds for each Redis service to answer.

**If something looks wrong.**

- `service account cannot reach Redis socket`: check both services with
  `systemctl status cth-rate-limit.service cth-student-setup.service --no-pager`.
  Both should say `active (running)`.
- On releases from before 22 November 2026 this stage failed once on its first
  run even when nothing was wrong. See [Troubleshooting](troubleshooting.md#redis-stage-fails-on-its-first-run).

## 5.4 release: the application

**What you're doing.** Copying your chosen release to
`/opt/cth/releases/<SHA>` and installing its Python libraries into
`/opt/cth/venvs/<SHA>`.

**Why.** Each release gets its own folders named by its SHA. A later upgrade
can then sit beside the old one rather than overwrite it.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply release --config "$manifest"
```

**What you should see.** Several minutes while libraries download and build,
then `"stage": "release"` … `"result": "ok"`.

**If something looks wrong.** `release: external command failed` usually means
a download failed. Check the server can reach the internet
(`curl -sI https://pypi.org | head -1` should print an `HTTP` line) and has
free disk space (`df -h /`).

## 5.5 config: check the runtime file

**What you're doing.** Having the installer validate your runtime file.

**Why.** The next stages start the app with these settings. This stage only
reads the file: it checks every required setting is present, every key has the
right format, and no two keys are the same. It never prints a value.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply config --config "$manifest"
```

**What you should see.** `"stage": "config"` … `"result": "ok"` immediately.

**If something looks wrong.** The messages are the ones in
[Part 4, step 4.5](part-4-describe-your-installation.md#45-check-your-files-before-installing).
`unsafe file ownership or mode` means the runtime file isn't `600 root root`;
fix it with `chmod 600 /etc/cth/runtime.env`.

## 5.6 database: install the schema

**What you're doing.** Creating all of CTH's tables in the empty database.

**Why.** Each release ships a verified copy of its database structure. This
stage installs it, checks it matches, and then gives `cthapp` exactly the
permissions the app needs and no more.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply database --config "$manifest"
```

**What you should see.** `"stage": "database"` … `"result": "ok"` within a minute.

**If something looks wrong.**

- `release lacks a matching database baseline`: this release can't create a
  new database. Choose a different release and start over on a clean server.
- Any other failure leaves the database partly built. Don't try to fix it by
  hand. On a new server with no real data, [start over](#starting-over). The
  [fresh database reference](fresh-database.md) explains what the stage checks.

## 5.7 services: start the web app

**What you're doing.** Starting CTH itself as the `cth-web` service.

**Why.** The app runs as `cthapp` and listens only on the server itself
(`127.0.0.1:8000`). Nothing outside can reach it until the `ingress` stage.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply services --config "$manifest"
```

**What you should see.** `"stage": "services"` … `"result": "ok"`. You can also
run `curl -s http://127.0.0.1:8000/health`, which prints `ok`.

**If something looks wrong.** Look at the app's own messages:

```bash
systemctl status cth-web.service --no-pager
journalctl -u cth-web.service -n 50 --no-pager
```

The log may name a setting or a missing service. Don't paste full logs
anywhere public; they can contain names and keys.

## 5.8 scheduler: check the timed jobs

**What you're doing.** Checking that exactly one copy of CTH's scheduler is
running.

**Why.** The scheduler runs timed jobs such as payroll and rent. Two copies
could pay students twice; none would pay them never. This stage installs
nothing. It checks the database to confirm one process holds the scheduler.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply scheduler --config "$manifest"
```

**What you should see.** `"stage": "scheduler"` … `"result": "ok"`.

**If something looks wrong.** `expected one scheduler advisory-lock owner` or
`scheduler startup evidence missing`: the app may still be starting. Wait a
minute and run the same `apply` again. If it keeps failing, look at
`journalctl -u cth-web.service -n 50 --no-pager`.

## 5.9 ingress: open HTTPS to Cloudflare

**What you're doing.** Starting a dedicated nginx (`cth-ingress`) that accepts
HTTPS on port 443, only from Cloudflare, and passes it to the app.

**Why.** This is the step that makes your site reachable. Before starting it,
the stage checks your certificate and confirms that Cloudflare Access is
protecting the teacher login.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply ingress --config "$manifest"
```

**What you should see.** `"stage": "ingress"` … `"result": "ok"`.

**If something looks wrong.**

| Message | What it means |
| --- | --- |
| `unauthenticated public login did not reach the selected admission gate` | An anonymous visit to `/admin/login` isn't redirected to your admission hostname. Check the Access application from [Part 2, step 2.6](part-2-create-the-server.md#26-put-cloudflare-access-in-front-of-the-site) and the admission hostname in the manifest. |
| `runtime check failed (openssl)` | The certificate has expired. Renew it ([Part 7](part-7-keep-it-running.md#76-renew-the-certificate)). |
| `unsafe file ownership or mode: /etc/cth/tls/…` | Fix with `chmod 644 /etc/cth/tls/origin.crt` and `chmod 600 /etc/cth/tls/origin.key`. |
| `runtime check failed (curl)` after the service starts | The certificate doesn't match your hostname, or isn't publicly trusted. See the note in [Part 4, step 4.4](part-4-describe-your-installation.md#44-get-the-https-certificate). |

## 5.10 readiness: check everything together

**What you're doing.** Running every check again, together.

**Why.** It confirms the services, health, scheduler, HTTPS and the Access
gate all work at the same moment, not just one after another.

**Steps.**

```bash
python3 infra/self-hosting/install.py apply readiness --config "$manifest"
```

**What you should see.** `"stage": "readiness"` … `"result": "ok"`. Then, in a
browser, open `https://` + your CTH hostname + `/admin/login`. After the Access
email code, you see the CTH teacher sign-in page.

**If something looks wrong.** The message names the failing check; look it up
under the stage it belongs to above.

## Starting over

On a new installation with no real data, the most reliable fix for a muddled
stage is a clean server:

1. Use your provider's **Rebuild** (or **Reinstall**) option with a fresh
   Ubuntu 22.04 x86-64 image. This wipes the disk and usually keeps the IP
   address. Or destroy the server and create a new one ([Part 2](part-2-create-the-server.md)).
2. The server now has a **new fingerprint**. SSH will warn
   `REMOTE HOST IDENTIFICATION HAS CHANGED`. Read the new fingerprint in the
   web console ([2.2](part-2-create-the-server.md#22-read-the-servers-fingerprint-in-the-web-console)),
   then remove the old one on your computer with
   `ssh-keygen -R 203.0.113.10` (your IP) and connect again, comparing as before.
3. Repeat [Part 3](part-3-get-cth.md) and [Part 4](part-4-describe-your-installation.md).
   Reuse your provider keys; new generated keys are fine because there's no data yet.
   You can reuse the certificate if you copied it off the server first;
   otherwise get a new one.

> [!CAUTION]
> Never "start over" this way once real classes use your server. A rebuild
> erases all their data. Restore from a backup instead
> ([Part 7](part-7-keep-it-running.md)).

## Checkpoint

All ten stages are finished, and your CTH is live behind the Access gate.

**Next:** [Part 6: First use](part-6-first-use.md)
